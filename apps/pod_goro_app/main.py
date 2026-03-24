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
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Kmetija Pod Goro V2 AI</title>
        <meta charset="UTF-8">
        <style>
            body { font-family: system-ui; max-width: 600px; margin: 50px auto; padding: 20px; background: #f4f9f3; }
            #chat { border: 1px solid #c8dfc5; height: 400px; overflow-y: auto; padding: 10px; margin-bottom: 10px; background: #fff; border-radius: 10px; }
            .user { color: #2d5229; margin: 5px 0; }
            .bot { color: #1a4d2e; margin: 5px 0; white-space: pre-wrap; }
            #input { width: 80%; padding: 10px; border: 1px solid #c8dfc5; border-radius: 8px; }
            button { padding: 10px 20px; background: #3a6b35; color: #fff; border: none; border-radius: 8px; cursor: pointer; }
            nav { margin-bottom: 20px; }
            nav a { margin-right: 15px; color: #3a6b35; }
            h1 { color: #3a6b35; }
        </style>
    </head>
    <body>
        <h1>Kmetija Pod Goro — AI asistent</h1>
        <div id="chat"></div>
        <input type="text" id="input" placeholder="Vprašajte..." onkeypress="if(event.key==='Enter')send()">
        <button onclick="send()">Pošlji</button>

        <script>
            let sessionId = null;
            const chat = document.getElementById('chat');
            const input = document.getElementById('input');

            async function send() {
                const msg = input.value.trim();
                if (!msg) return;

                chat.innerHTML += `<div class="user"><b>Vi:</b> ${msg}</div>`;
                input.value = '';

                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({message: msg, session_id: sessionId})
                });
                const data = await res.json();
                sessionId = data.session_id;
                chat.innerHTML += `<div class="bot"><b>Pod Goro AI:</b> ${data.reply}</div>`;
                chat.scrollTop = chat.scrollHeight;
            }
        </script>
    </body>
    </html>
    """


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
