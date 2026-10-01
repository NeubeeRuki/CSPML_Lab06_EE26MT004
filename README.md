# CSPML_TA_AI_v5 — Lab 06

V5 is an incremental extension of the working V3 Teaching Agent. It retains the V3 TF-IDF RAG pipeline and Qwen3-4B-Instruct-2507 Hugging Face inference while adding persistent messenger-style chats, Library management, chat context selection, settings, analytics, and live System Check diagnostics.

## Main V5 features
- Continuous persistent messenger chat
- New chat, history, rename, delete, copy, feedback
- NCERT and Library context selection
- Library folders/files, upload, rename, delete
- Direct upload from chat into Library and context
- TF-IDF RAG using the existing NCERT indexes
- Qwen3-4B-Instruct-2507 via Hugging Face
- Settings/personalization
- Application analytics
- System Check tab
- Architecture and system workflow diagrams
- Render-compatible single FastAPI application

## Local run
Use the existing CSPML_LAB_ENV Python environment:
`C:\Users\Milind\Documents\CSPML_LAB_ENV\Scripts\python.exe -m pip install -r requirements.txt`
`C:\Users\Milind\Documents\CSPML_LAB_ENV\Scripts\python.exe -m pytest -q`
`C:\Users\Milind\Documents\CSPML_LAB_ENV\Scripts\python.exe -m uvicorn backend.app:app --host 127.0.0.1 --port 8000`

Open `http://127.0.0.1:8000/`.

## Environment
Copy `.env.example` to `.env` and configure `HF_TOKEN`. Optional `HF_MODEL` defaults to `Qwen/Qwen3-4B-Instruct-2507`.

## Deployment
The app is designed for Render-style deployment with Uvicorn. Keep `.env` and API keys out of GitHub.
