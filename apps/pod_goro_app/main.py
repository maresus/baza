"""
Kmetija Pod Goro V2 AI - Chatbot s rezervacijami.
Nastanitev, kosilo, kolesa, hranjenje živali.
"""
from pathlib import Path
import sys
import os

from dotenv import load_dotenv

# Load .env before imports
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.chat.router import router as chat_router
from app.services.admin_router import router as admin_router
from app.rag.search import load_knowledge

app = FastAPI(title="Kmetija Pod Goro V2 AI", version="2.0.0")

# CORS - allow widget embedding
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.on_event("startup")
def startup():
    kb_path = Path(__file__).parent / "knowledge.jsonl"
    count = load_knowledge(kb_path)
    print(f"[startup] Loaded {count} knowledge chunks")
    print(f"[startup] Pod Goro V2 ready - nastanitev, kosilo, kolesa, hranjenje živali")


@app.get("/health")
def health():
    return {"status": "ok", "version": "v2", "project": "pod-goro"}


@app.get("/", response_class=HTMLResponse)
def home():
    html_path = Path("static/widget.html")
    if html_path.exists():
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Pod Goro AI</h1>", status_code=200)


@app.get("/widget", response_class=HTMLResponse)
def widget_page():
    html_path = Path("static/widget.html")
    if not html_path.exists():
        return HTMLResponse("<h1>Widget UI manjka (static/widget.html)</h1>", status_code=500)
    return HTMLResponse(content=html_path.read_text(encoding="utf-8"))


# Include routers
app.include_router(chat_router)
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8002))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
