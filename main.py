import os, httpx, uvicorn, re, json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import litellm
from litellm import completion
from duckduckgo_search import DDGS

litellm.telemetry = False
app = FastAPI(title="OpenFred")
WORKSPACE = os.path.abspath("./workspace")

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

def save_to_history(agent_name: str, role: str, text: str):
    path = get_safe_path(agent_name, "history.json")
    history = []
    if os.path.exists(path):
        with open(path, "r") as f: history = json.load(f)
    history.append({"role": role, "text": text})
    with open(path, "w") as f: json.dump(history, f)

def web_search(query: str):
    """Executes a live DuckDuckGo search and returns top snippets."""
    print(f"🌐 DEBUG: Executing DuckDuckGo for: {query}")
    try:
        with DDGS() as ddgs:
            # Flatten the results into a readable block
            raw_results = list(ddgs.text(query, max_results=5))
            if not raw_results: return "No results found on the web."
            
            context_bits = []
            for r in raw_results:
                context_bits.append(f"TITLE: {r.get('title')}\nINFO: {r.get('body')}\n")
            return "\n---\n".join(context_bits)
    except Exception as e:
        print(f"❌ SEARCH ERROR: {str(e)}")
        return f"Web search service is currently unavailable: {str(e)}"

@app.get("/")
async def get_ui():
    with open("index.html", "r") as f: return HTMLResponse(content=f.read())

@app.get("/agents")
async def list_agents():
    try:
        entries = os.listdir(WORKSPACE)
        agent_list = [d for d in entries if os.path.isdir(os.path.join(WORKSPACE, d)) and not d.startswith('.')]
        return ["Main"] + sorted([a for a in agent_list if a != "Main"])
    except Exception: return ["Main"]

@app.get("/history")
async def get_history(name: str):
    path = get_safe_path(name, "history.json")
    if os.path.exists(path):
        with open(path, "r") as f: return json.load(f)
    return []

@app.post("/chat")
async def chat(name: str, message: str, model: str, api_key: Optional[str] = None):
    is_ollama = "ollama" in model
    save_to_history(name, "user", message)
    
    soul_p, mem_p = get_safe_path(name, "soul.md"), get_safe_path(name, "memory.md")
    soul = open(soul_p, "r").read() if os.path.exists(soul_p) else "Chief of Staff."
    mem = open(mem_p, "r").read() if os.path.exists(mem_p) else ""

    # Clear instructions for the "Agentic Loop"
    system_prompt = (
        f"IDENTITY: {soul}\nMEMORY: {mem}\n"
        f"TODAY'S DATE: Monday, February 16, 2026\n\n"
        "INSTRUCTIONS:\n"
        "1. If you need current info (like phone numbers, news, or 2026 facts), reply ONLY with: SEARCH: [query]\n"
        "2. Once you have search results, provide a final helpful answer.\n"
        "3. Keep answers concise."
    )

    try:
        # PASS 1: Generate response or SEARCH command
        response = completion(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
            api_key=api_key if (api_key and not is_ollama) else "any",
            base_url="http://127.0.0.1:11434" if is_ollama else None
        )
        
        reply = response.choices[0].message.content.strip()

        # PASS 2: Check if the LLM requested a search
        if reply.startswith("SEARCH:"):
            # Robust query extraction
            search_query = reply.replace("SEARCH:", "").strip().split("\n")[0]
            
            # Perform actual web search
            context = web_search(search_query)
            
            # Final Pass: Synthesize the answer
            final_call = completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": reply},
                    {"role": "system", "content": f"WEB SEARCH RESULTS:\n{context}\n\nUsing this info, provide the final answer to the user."}
                ],
                api_key=api_key if (api_key and not is_ollama) else "any",
                base_url="http://127.0.0.1:11434" if is_ollama else None
            )
            reply = final_call.choices[0].message.content

        # Handle Memory Updates
        if "COMMIT:" in reply:
            commit_match = re.search(r"COMMIT:\s*(.*)", reply)
            if commit_match:
                with open(mem_p, "a") as f: f.write(f"\n- {commit_match.group(1).strip()}")
                reply = reply.replace(f"COMMIT: {commit_match.group(1).strip()}", "*(Memory Updated)*")

        save_to_history(name, "assistant", reply)
        return {"reply": reply}
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {str(e)}")
        return {"reply": f"❌ Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)