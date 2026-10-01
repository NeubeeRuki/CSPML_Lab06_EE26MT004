from fastapi.testclient import TestClient
from backend.app import app
c=TestClient(app)
def test_health():
 r=c.get('/health'); assert r.status_code==200 and r.json()['model']
def test_home(): assert c.get('/').status_code==200
def test_chats(): assert c.get('/api/chats').status_code==200
def test_library(): assert c.get('/api/library').status_code==200
def test_settings(): assert c.get('/api/settings').status_code==200
def test_system_check():
 r=c.get('/api/system-check'); assert r.status_code==200 and r.json()['total']>=1
def test_rename_chat():
 i=c.post('/api/chats').json()['id']; r=c.put(f'/api/chats/{i}',json={'title':'Physics Chat'}); assert r.status_code==200
