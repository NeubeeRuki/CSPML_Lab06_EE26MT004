# CSPML_TA_AI_v5 — Project Plan

## Project
CSPML in Practice — Lab 06

## Objective
Extend the working CSPML Lab 05 teaching-agent baseline into a stable, demonstrable V5 end-to-end application while preserving the core RAG + Qwen LLM workflow.

## Major Features

### 1. Chat
- Continuous messenger-style conversations
- Multiple question/answer exchanges per conversation
- New Chat
- Chat history
- Chat rename and delete
- Persistent messages
- Copy response
- Response feedback

### 2. Library
- NCERT knowledge-base organization
- User Library
- Files and folders
- File upload
- File/folder rename
- File/folder deletion
- Chat context selection
- Direct chat-to-library workflow

### 3. RAG + LLM
- Existing NCERT retrieval workflow retained
- TF-IDF-based retrieval and indexed NCERT content
- Qwen3-4B-Instruct-2507 as the backend LLM
- Hugging Face API configuration through environment variables

### 4. User Settings
- Course
- Degree
- Language
- Tone
- Answer depth
- Response format
- Nickname
- Custom instructions

### 5. Analytics
- Conversation count
- Question/response counts
- Library statistics
- Storage/activity information where available

### 6. System Check
- Environment/package checks
- Configuration checks
- Backend checks
- Storage checks
- NCERT knowledge-base checks
- Application readiness diagnostics

### 7. Documentation
- How It Works section
- System architecture
- System block diagram
- Local setup instructions
- Render deployment information

## Implementation Principles
1. Preserve working Lab 05 functionality.
2. Prefer incremental and reversible changes.
3. Test backend/API behavior before UI integration.
4. Verify browser functionality after frontend changes.
5. Run regression tests after meaningful changes.
6. Never expose API keys or secrets in source control.

## Deployment
- Source code hosted on GitHub.
- Application deployed as a FastAPI web service on Render.
- Hugging Face token supplied through deployment environment variables.

## Final Verification
- Requirements check passes.
- Automated tests pass.
- Local application launches.
- Chat workflow works.
- RAG/LLM workflow works.
- Library/context workflow is testable.
- Settings, analytics, documentation and system diagnostics are accessible.
- Public Render deployment is tested.

## Security
The actual `.env` file and Hugging Face API token must not be included in the submission ZIP or GitHub repository. Use `.env.example` for configuration placeholders.
