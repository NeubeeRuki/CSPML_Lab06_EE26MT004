from pathlib import Path
import os
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parent.parent; load_dotenv(ROOT/'.env')
NCERT_ROOT=ROOT/'data'/'ncert'; USER_ROOT=ROOT/'data'/'users'; STORAGE_ROOT=ROOT/'storage'; DB_PATH=ROOT/'data'/'v5.db'
for p in (NCERT_ROOT,USER_ROOT,STORAGE_ROOT,ROOT/'storage'/'library'): p.mkdir(parents=True,exist_ok=True)
HOST=os.getenv('APP_HOST','127.0.0.1'); PORT=int(os.getenv('APP_PORT','8000'))
