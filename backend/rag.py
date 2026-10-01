import json,pickle,re
from pathlib import Path
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
CHUNK_SIZE=1200; CHUNK_OVERLAP=200
def extract_pdf_text(path): return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
def extract_text(path):
 p=Path(path)
 if p.suffix.lower()=='.pdf': return extract_pdf_text(p)
 if p.suffix.lower() in {'.txt','.md'}: return p.read_text(encoding='utf-8',errors='ignore')
 return ''
def chunk_text(text):
 text=re.sub(r'\s+',' ',text).strip(); chunks=[]; start=0
 while text and start<len(text):
  end=min(start+CHUNK_SIZE,len(text)); chunks.append(text[start:end].strip())
  if end>=len(text): break
  start=max(end-CHUNK_OVERLAP,start+1)
 return [x for x in chunks if x]
def index_paths(folder):
 folder=Path(folder); return folder/'index'/'chunks.json',folder/'index'/'tfidf.pkl'
def is_indexed(folder):
 a,b=index_paths(folder); return a.exists() and b.exists()
def build_index(folder):
 folder=Path(folder); idx=folder/'index'; idx.mkdir(exist_ok=True); all_chunks=[]
 for p in sorted(folder.iterdir()):
  if p.is_file() and p.suffix.lower() in {'.pdf','.txt','.md'}:
   for i,ch in enumerate(chunk_text(extract_text(p))): all_chunks.append({'source':p.name,'chunk':i,'text':ch})
 if not all_chunks: raise ValueError('No supported documents found in folder.')
 v=TfidfVectorizer(stop_words='english',max_features=50000); m=v.fit_transform([x['text'] for x in all_chunks]); (idx/'chunks.json').write_text(json.dumps(all_chunks,ensure_ascii=False),encoding='utf-8'); pickle.dump((v,m),open(idx/'tfidf.pkl','wb')); return {'status':'indexed','chunks':len(all_chunks),'documents':len({x['source'] for x in all_chunks})}
def retrieve(folder,query,top_k=5):
 cp,mp=index_paths(folder)
 if not cp.exists() or not mp.exists(): raise FileNotFoundError('Folder has not been indexed.')
 chunks=json.loads(cp.read_text(encoding='utf-8')); v,m=pickle.load(open(mp,'rb')); scores=cosine_similarity(v.transform([query]),m).ravel(); out=[]
 for i in scores.argsort()[::-1][:top_k]:
  if scores[i]>0: out.append({**chunks[i],'score':round(float(scores[i]),4)})
 return out
