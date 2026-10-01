from pathlib import Path
import sys, importlib.util, os

ROOT = Path(__file__).resolve().parent
print("=" * 58)
print("CSPML_TA_AI_v5 — REQUIREMENTS CHECK")
print("=" * 58)
print(f"Python : {sys.executable}")
print(f"Version: {sys.version.split()[0]}\n")

packages = {
    "fastapi":"fastapi","uvicorn":"uvicorn","python-dotenv":"dotenv",
    "python-multipart":"multipart","httpx":"httpx","pytest":"pytest"
}
failed = False
for name, mod in packages.items():
    try:
        m=__import__(mod)
        print(f"[OK]      {name:<20} {getattr(m,'__version__','installed')}")
    except Exception:
        print(f"[MISSING] {name}")
        failed=True

print("\n--- V5 files ---")
files = [
    "backend/app.py","frontend/index.html","requirements.txt",
    ".env.example","render.yaml","README.md"
]
for f in files:
    ok=(ROOT/f).is_file()
    print(f"[{'OK' if ok else 'MISSING':<7}] {f}")
    failed |= not ok

print("\n--- Data / storage ---")
dirs = [
    "data","data/Users","data/NCERT","data/Library",
    "storage","storage/library"
]
for d in dirs:
    ok=(ROOT/d).is_dir()
    print(f"[{'OK' if ok else 'MISSING':<7}] {d}")
    failed |= not ok

print("\n--- NCERT collections ---")
ncert = ROOT/"data"/"ncert"
for d in ["Physics_XI_Part_1","Physics_XI_Part_2",
          "Physics_XII_Part_1","Physics_XII_Part_2"]:
    ok = (ncert/d).is_dir()
    print(f"[{'OK' if ok else 'MISSING':<7}] data/ncert/{d}")
    failed |= not ok

print("\n--- Environment ---")
env=ROOT/".env"
print(f"[{'OK' if env.is_file() else 'WARN':<7}] .env {'exists' if env.is_file() else 'not found'}")
if env.is_file():
    from dotenv import load_dotenv
    load_dotenv(env)
    token=bool(os.getenv("HF_TOKEN"))
    print(f"[{'OK' if token else 'WARN':<7}] HF_TOKEN {'configured' if token else 'not configured'}")

print("\n--- Backend import ---")
try:
    from backend.app import app
    print("[OK]      backend.app import")
except Exception as e:
    print("[FAIL]    backend.app import")
    print("          ", repr(e))
    failed=True

print("\nRESULT:", "FAIL — fix the items above." if failed else "PASS — V5 environment is ready.")
sys.exit(1 if failed else 0)
