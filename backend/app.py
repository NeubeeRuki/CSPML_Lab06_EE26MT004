from pathlib import Path
import json, os, re, shutil, sqlite3, uuid
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from .rag import is_indexed, build_index, retrieve, extract_text
from .llm import ask_llm

ROOT=Path(__file__).resolve().parent.parent
load_dotenv(ROOT/".env")
DATA=ROOT/"data"; NCERT=DATA/"ncert"; USERS=DATA/"users"; LIB=ROOT/"storage"/"library"; DB=ROOT/"data"/"v5.db"
for p in (DATA,NCERT,USERS,LIB,DB.parent): p.mkdir(parents=True,exist_ok=True)
MODEL=os.getenv("HF_MODEL") or os.getenv("HF_MODEL_BASIC") or "Qwen/Qwen3-4B-Instruct-2507"
app=FastAPI(title="CSPML Teaching Agent V5",version="5.1.0")
app.add_middleware(CORSMiddleware,allow_origins=["*"],allow_methods=["*"],allow_headers=["*"])

def now(): return datetime.now(timezone.utc).isoformat(timespec="seconds")
def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def cols(c,t): return {r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()}
def addcol(c,t,name,decl):
    if name not in cols(c,t): c.execute(f"ALTER TABLE {t} ADD COLUMN {name} {decl}")
def init():
    c=db(); c.executescript("""
    CREATE TABLE IF NOT EXISTS chats(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT NOT NULL,created TEXT NOT NULL,updated TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY AUTOINCREMENT,chat_id INTEGER NOT NULL,role TEXT NOT NULL,content TEXT NOT NULL,created TEXT NOT NULL,feedback INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS folders(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,parent_id INTEGER,path TEXT,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,path TEXT NOT NULL,size INTEGER NOT NULL,folder_id INTEGER,created TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS contexts(chat_id INTEGER NOT NULL,file_id INTEGER,folder_id INTEGER,ncert_folder TEXT);
    CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),course TEXT,degree TEXT,language TEXT,tone TEXT,depth TEXT,format TEXT,instructions TEXT,nickname TEXT,topk INTEGER);
    CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_type TEXT,detail TEXT,created TEXT);
    """)
    addcol(c,'chats','created','TEXT'); addcol(c,'chats','updated','TEXT')
    addcol(c,'folders','created','TEXT'); addcol(c,'folders','path','TEXT'); addcol(c,'files','created','TEXT'); addcol(c,'contexts','ncert_folder','TEXT')
    # Backfill physical paths for any pre-existing folders.
    for row in c.execute("SELECT id,path FROM folders WHERE path IS NULL OR path=''").fetchall():
        p=LIB/'folder_'+uuid.uuid4().hex; p.mkdir(parents=True,exist_ok=True); c.execute("UPDATE folders SET path=? WHERE id=?",(str(p),row['id']))
    c.execute("INSERT OR IGNORE INTO settings VALUES(1,'','','English','default','balanced','mixed','','',5)")
    c.commit(); c.close()
init()

class Ask(BaseModel): question:str=Field(min_length=1); top_k:int|None=None
class ChatRename(BaseModel): title:str=Field(min_length=1,max_length=80)
class Context(BaseModel): file_ids:list[int]=[]; folder_ids:list[int]=[]; ncert_folders:list[str]=[]
class Settings(BaseModel):
    course:str=''; degree:str=''; language:str='English'; tone:str='default'; depth:str='balanced'; format:str='mixed'; instructions:str=''; nickname:str=''; topk:int=5
class FolderIn(BaseModel): name:str=Field(min_length=1,max_length=80); parent_id:int|None=None

@app.get('/')
def home(): return FileResponse(ROOT/'frontend'/'index.html')
@app.get('/health')
def health(): return {'status':'healthy','version':'5.1.0','model':MODEL,'rag':'TF-IDF'}

@app.get('/architecture.svg')
def architecture(): return FileResponse(ROOT/'frontend'/'architecture.svg', media_type='image/svg+xml')

@app.get('/system_block_diagram.svg')
def system_block_diagram(): return FileResponse(ROOT/'frontend'/'system_block_diagram.svg', media_type='image/svg+xml')

@app.get('/api/chats')
def chats():
    c=db(); rows=c.execute("SELECT ch.*,COUNT(m.id) message_count FROM chats ch LEFT JOIN messages m ON m.chat_id=ch.id GROUP BY ch.id ORDER BY ch.updated DESC").fetchall(); c.close(); return {'chats':[dict(r) for r in rows]}
@app.post('/api/chats')
def new_chat():
    t=now(); c=db(); r=c.execute("INSERT INTO chats(title,created,updated) VALUES(?,?,?)",('New Chat',t,t)); c.commit(); i=r.lastrowid; c.close(); return {'id':i,'title':'New Chat'}
@app.get('/api/chats/{cid}')
def get_chat(cid:int):
    c=db(); ch=c.execute('SELECT * FROM chats WHERE id=?',(cid,)).fetchone()
    if not ch: c.close(); raise HTTPException(404,'Chat not found')
    ms=c.execute('SELECT * FROM messages WHERE chat_id=? ORDER BY id',(cid,)).fetchall()
    ctx=c.execute('SELECT * FROM contexts WHERE chat_id=?',(cid,)).fetchall(); c.close()
    return {'chat':dict(ch),'messages':[dict(x) for x in ms],'context':[dict(x) for x in ctx]}
@app.put('/api/chats/{cid}')
def rename_chat(cid:int,x:ChatRename):
    title=' '.join(x.title.split()).strip(); c=db(); r=c.execute('UPDATE chats SET title=?,updated=? WHERE id=?',(title,now(),cid)); c.commit(); c.close()
    if not r.rowcount: raise HTTPException(404,'Chat not found')
    return {'ok':True,'title':title}
@app.delete('/api/chats/{cid}')
def delete_chat(cid:int):
    c=db(); c.execute('DELETE FROM messages WHERE chat_id=?',(cid,)); c.execute('DELETE FROM contexts WHERE chat_id=?',(cid,)); c.execute('DELETE FROM chats WHERE id=?',(cid,)); c.commit(); c.close(); return {'ok':True}

async def answer_for(cid,question,top_k=None):
    c=db(); ch=c.execute('SELECT * FROM chats WHERE id=?',(cid,)).fetchone()
    if not ch: c.close(); raise HTTPException(404,'Chat not found')
    hist=[dict(x) for x in c.execute("SELECT role,content FROM messages WHERE chat_id=? ORDER BY id",(cid,)).fetchall()]
    ctx=c.execute('SELECT * FROM contexts WHERE chat_id=?',(cid,)).fetchall(); c.close()
    contexts=[]; sources=[]; ncerts=[x['ncert_folder'] for x in ctx if x['ncert_folder']]
    # Default to XI Part 1 for backward-compatible V3 behavior.
    if not ncerts and not [x for x in ctx if x['file_id'] or x['folder_id']]: ncerts=['Physics_XI_Part_1']
    for name in ncerts:
        p=NCERT/name
        if p.is_dir() and is_indexed(p):
            rs=retrieve(p,question,top_k or 5); contexts.append(f'## {name}\n'+'\n\n'.join(r['text'] for r in rs)); sources += [{'source':name,'chunk':r['chunk'],'score':r.get('score')} for r in rs]
    for x in ctx:
        if x['folder_id']:
            r=c=db(); row=r.execute('SELECT path,name FROM folders WHERE id=?',(x['folder_id'],)).fetchone(); r.close()
            if row:
                p=Path(row['path'])
                if p.is_dir():
                    if not is_indexed(p):
                        try: build_index(p)
                        except ValueError: pass
                    if is_indexed(p):
                        rs=retrieve(p,question,top_k or 5); contexts.append(f"## Library folder: {row['name']}\n"+'\n\n'.join(z['text'] for z in rs)); sources += [{'source':row['name'],'chunk':z['chunk'],'score':z.get('score')} for z in rs]
        if x['file_id']:
            c=db(); row=c.execute('SELECT path,name FROM files WHERE id=?',(x['file_id'],)).fetchone(); c.close()
            if row:
                p=Path(row['path']); text=extract_text(p); contexts.append(f"## Library file: {row['name']}\n{text[:9000]}"); sources.append({'source':row['name'],'chunk':0,'score':None})
    context='\n\n'.join(contexts)
    try: ans=await ask_llm(question,context,history=hist)
    except RuntimeError as e: raise HTTPException(502,str(e))
    c=db(); t=now(); c.execute('INSERT INTO messages(chat_id,role,content,created) VALUES(?,?,?,?)',(cid,'user',question,t)); c.execute('INSERT INTO messages(chat_id,role,content,created) VALUES(?,?,?,?)',(cid,'assistant',ans,t));
    if ch['title']=='New Chat': c.execute('UPDATE chats SET title=?,updated=? WHERE id=?',(question[:55],t,cid))
    else: c.execute('UPDATE chats SET updated=? WHERE id=?',(t,cid))
    c.execute('INSERT INTO events(event_type,detail,created) VALUES(?,?,?)',('question',str(cid),t)); c.commit(); mids=c.execute('SELECT id FROM messages WHERE chat_id=? ORDER BY id DESC LIMIT 1',(cid,)).fetchone()['id']; c.close()
    return {'answer':ans,'message_id':mids,'retrieved_chunks':len(sources),'sources':sources}
@app.post('/api/chats/{cid}/ask')
async def ask(cid:int,a:Ask): return await answer_for(cid,a.question,a.top_k)

@app.post('/api/messages/{mid}/feedback')
def feedback(mid:int,value:int):
    if value not in (-1,1,0): raise HTTPException(400,'Feedback must be -1, 0, or 1')
    c=db(); c.execute('UPDATE messages SET feedback=? WHERE id=?',(value,mid)); c.commit(); c.close(); return {'ok':True}

@app.get('/api/library')
def library():
    c=db(); fs=[dict(x) for x in c.execute('SELECT * FROM folders ORDER BY parent_id,name').fetchall()]; files=[dict(x) for x in c.execute('SELECT * FROM files ORDER BY folder_id,name').fetchall()]; c.close()
    ncert=[{'name':p.name,'path':p.name,'type':'ncert','indexed':is_indexed(p),'documents':len([x for x in p.iterdir() if x.is_file() and x.suffix.lower() in {'.pdf','.txt','.md'}])} for p in sorted(NCERT.iterdir()) if p.is_dir() and not p.name.startswith('.')]
    return {'folders':fs,'files':files,'ncert':ncert}
@app.post('/api/library/folders')
def create_folder(x:FolderIn):
    name=' '.join(x.name.split()); c=db();
    if x.parent_id and not c.execute('SELECT id FROM folders WHERE id=?',(x.parent_id,)).fetchone(): c.close(); raise HTTPException(404,'Parent folder not found')
    if c.execute('SELECT id FROM folders WHERE name=? AND parent_id IS ?',(name,x.parent_id)).fetchone(): c.close(); raise HTTPException(409,'Folder already exists')
    path=LIB / uuid.uuid4().hex; path.mkdir(parents=True,exist_ok=True); folder_path=LIB/('folder_'+uuid.uuid4().hex); folder_path.mkdir(parents=True,exist_ok=True); r=c.execute('INSERT INTO folders(name,parent_id,path,created) VALUES(?,?,?,?)',(name,x.parent_id,str(folder_path),now())); c.commit(); i=r.lastrowid; c.close(); return {'id':i,'name':name}
@app.put('/api/library/folders/{fid}')
def rename_folder(fid:int,x:FolderIn):
    c=db(); r=c.execute('UPDATE folders SET name=? WHERE id=?',(' '.join(x.name.split()),fid)); c.commit(); c.close()
    if not r.rowcount: raise HTTPException(404,'Folder not found')
    return {'ok':True}
@app.delete('/api/library/folders/{fid}')
def delete_folder(fid:int):
    c=db(); children=c.execute('SELECT id FROM folders WHERE parent_id=?',(fid,)).fetchall();
    if children: c.close(); raise HTTPException(400,'Move/delete child folders first')
    row=c.execute('SELECT id FROM folders WHERE id=?',(fid,)).fetchone();
    if not row: c.close(); raise HTTPException(404,'Folder not found')
    c.execute('UPDATE files SET folder_id=NULL WHERE folder_id=?',(fid,)); c.execute('DELETE FROM folders WHERE id=?',(fid,)); c.commit(); c.close(); return {'ok':True}
@app.post('/api/library/upload')
async def upload(file:UploadFile=File(...),folder_id:int|None=Form(None)):
    name=Path(file.filename or 'upload').name
    if not name: raise HTTPException(400,'Invalid filename')
    if folder_id:
        c=db(); ok=c.execute('SELECT id FROM folders WHERE id=?',(folder_id,)).fetchone(); c.close()
        if not ok: raise HTTPException(404,'Folder not found')
    c=db(); base=LIB
    if folder_id:
        row=c.execute('SELECT path FROM folders WHERE id=?',(folder_id,)).fetchone(); base=Path(row['path']) if row and row['path'] else LIB
    else:
        base=LIB/('loose_'+uuid.uuid4().hex); base.mkdir(parents=True,exist_ok=True)
    base.mkdir(parents=True,exist_ok=True); p=base/name; b=await file.read(); p.write_bytes(b)
    r=c.execute('INSERT INTO files(name,path,size,folder_id,created) VALUES(?,?,?,?,?)',(name,str(p),len(b),folder_id,now())); c.commit(); i=r.lastrowid; c.close(); return {'id':i,'name':name,'size':len(b)}
@app.put('/api/library/files/{fid}')
def rename_file(fid:int,x:ChatRename):
    c=db(); row=c.execute('SELECT path FROM files WHERE id=?',(fid,)).fetchone();
    if not row: c.close(); raise HTTPException(404,'File not found')
    old=Path(row['path']); new=old.with_name(Path(x.title).name); old.rename(new); c.execute('UPDATE files SET name=?,path=? WHERE id=?',(new.name,str(new),fid)); c.commit(); c.close(); return {'ok':True,'name':new.name}
@app.put('/api/library/files/{fid}/move')
def move_file(fid:int,folder_id:int|None=Form(None)):
    c=db(); row=c.execute('SELECT path FROM files WHERE id=?',(fid,)).fetchone();
    if not row: c.close(); raise HTTPException(404,'File not found')
    if folder_id and not c.execute('SELECT id FROM folders WHERE id=?',(folder_id,)).fetchone(): c.close(); raise HTTPException(404,'Folder not found')
    c.execute('UPDATE files SET folder_id=? WHERE id=?',(folder_id,fid)); c.commit(); c.close(); return {'ok':True}
@app.delete('/api/library/files/{fid}')
def delete_file(fid:int):
    c=db(); row=c.execute('SELECT path FROM files WHERE id=?',(fid,)).fetchone();
    if row: Path(row['path']).unlink(missing_ok=True); c.execute('DELETE FROM contexts WHERE file_id=?',(fid,)); c.execute('DELETE FROM files WHERE id=?',(fid,)); c.commit()
    c.close(); return {'ok':True}

@app.put('/api/chats/{cid}/context')
def set_context(cid:int,x:Context):
    c=db();
    if not c.execute('SELECT id FROM chats WHERE id=?',(cid,)).fetchone(): c.close(); raise HTTPException(404,'Chat not found')
    c.execute('DELETE FROM contexts WHERE chat_id=?',(cid,))
    for fid in x.file_ids: c.execute('INSERT INTO contexts(chat_id,file_id) VALUES(?,?)',(cid,fid))
    for fid in x.folder_ids: c.execute('INSERT INTO contexts(chat_id,folder_id) VALUES(?,?)',(cid,fid))
    for name in x.ncert_folders:
        if (NCERT/name).is_dir(): c.execute('INSERT INTO contexts(chat_id,ncert_folder) VALUES(?,?)',(cid,name))
    c.commit(); c.close(); return {'ok':True}

@app.get('/api/settings')
def get_settings(): c=db(); r=c.execute('SELECT * FROM settings WHERE id=1').fetchone(); c.close(); return dict(r)
@app.put('/api/settings')
def save_settings(s:Settings):
    c=db(); c.execute('UPDATE settings SET course=?,degree=?,language=?,tone=?,depth=?,format=?,instructions=?,nickname=?,topk=? WHERE id=1',(s.course,s.degree,s.language,s.tone,s.depth,s.format,s.instructions,s.nickname,s.topk)); c.commit(); c.close(); return {'ok':True}
@app.get('/api/analytics')
def analytics():
    c=db(); r={'conversations':c.execute('SELECT COUNT(*) n FROM chats').fetchone()['n'],'questions':c.execute("SELECT COUNT(*) n FROM messages WHERE role='user'").fetchone()['n'],'responses':c.execute("SELECT COUNT(*) n FROM messages WHERE role='assistant'").fetchone()['n'],'files':c.execute('SELECT COUNT(*) n FROM files').fetchone()['n'],'folders':c.execute('SELECT COUNT(*) n FROM folders').fetchone()['n'],'storage_bytes':c.execute('SELECT COALESCE(SUM(size),0) n FROM files').fetchone()['n'],'activity': [dict(x) for x in c.execute("SELECT substr(created,1,10) day,COUNT(*) count FROM messages WHERE role='user' GROUP BY day ORDER BY day DESC LIMIT 14").fetchall()]}; c.close(); return r

@app.get('/api/system-check')
def system_check():
    checks=[]
    def add(name,ok,detail=''): checks.append({'name':name,'ok':bool(ok),'detail':detail})
    add('Python environment',True,os.getenv('VIRTUAL_ENV','interpreter managed by launcher'))
    add('HF_TOKEN',bool(os.getenv('HF_TOKEN')),'configured' if os.getenv('HF_TOKEN') else 'missing')
    for dep in ['fastapi','uvicorn','dotenv','httpx','pypdf','sklearn','huggingface_hub']:
        try: __import__(dep); add('Package: '+dep,True)
        except Exception as e: add('Package: '+dep,False,str(e))
    for p,label in [(ROOT/'backend'/'app.py','backend/app.py'),(ROOT/'backend'/'rag.py','backend/rag.py'),(ROOT/'backend'/'llm.py','backend/llm.py'),(ROOT/'frontend'/'index.html','frontend/index.html'),(ROOT/'.env','.env')]: add(label,p.exists())
    add('Database',DB.exists(),str(DB))
    add('Library storage',LIB.exists(),str(LIB))
    for name in ['Physics_XI_Part_1','Physics_XI_Part_2','Physics_XII_Part_1','Physics_XII_Part_2']:
        p=NCERT/name; add('NCERT '+name,p.is_dir(),('indexed' if p.is_dir() and is_indexed(p) else 'not indexed'))
    return {'version':'5.1.0','model':MODEL,'passed':sum(x['ok'] for x in checks),'total':len(checks),'checks':checks}
