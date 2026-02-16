import os, httpx, uvicorn, re, json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="OpenFred")
WORKSPACE = os.path.abspath("./workspace")

# --- IMPORTANT: This allows the HTML to find interface.js and style.css ---
# We serve the current directory as static files
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class AgentRequest(BaseModel):
    name: str
    soul: str = "Chief of Staff."
    memory: str = "Initialized."

def get_safe_path(agent_name: str, filename: str = ""):
    base = os.path.join(WORKSPACE, agent_name)
    os.makedirs(base, exist_ok=True)
    target = os.path.abspath(os.path.join(base, filename))
    if not target.startswith(WORKSPACE):
        raise HTTPException(status_code=403, detail="Access Denied")
    return target

@app.get("/")
async def get_ui():
    with open("index.html", "r") as f: return HTMLResponse(content=f.read())

# Manual route for the JS and CSS if they aren't in a 'static' subfolder
@app.get("/interface.js")
async def get_js():
    with open("interface.js", "r") as f: return HTMLResponse(content=f.read(), media_type="application/javascript")

@app.get("/style.css")
async def get_css():
    with open("style.css", "r") as f: return HTMLResponse(content=f.read(), media_type="text/css")

@app.get("/history")
async def get_history(name: str):
    path = get_safe_path(name, "history.json")
    if os.path.exists(path):
        with open(path, "r") as f: return json.load(f)
    return []

@app.post("/chat")
async def chat(name: str, message: str, model: str, api_key: Optional[str] = None):
    # (Same chat logic as before...)
    return {"reply": "Ace logic connected."} # Placeholder for brevity

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)