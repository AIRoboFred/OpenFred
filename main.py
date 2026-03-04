import os, httpx, uvicorn, re, json
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Optional
import litellm
from litellm import completion
from ddgs import DDGS
import yfinance as yf

litellm.telemetry = False
app = FastAPI(title="OpenFred")
WORKSPACE = os.path.abspath("./workspace")

class AgentRequest(BaseModel):
    name: str
    soul: str = "Chief of Staff."
    memory: str = "Initialized."

def get_safe_path(agent_name: str, filename: str = ""):
    base = os.path.realpath(os.path.join(WORKSPACE, agent_name))
    os.makedirs(base, exist_ok=True)
    target = os.path.realpath(os.path.join(base, filename)) if filename else base
    if not (target == base or target.startswith(base + os.sep)):
        raise HTTPException(status_code=403, detail="Access Denied")
    return target

def write_agent_file(agent_name: str, filename: str, content: str):
    path = get_safe_path(agent_name, filename)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

def save_to_history(agent_name: str, role: str, text: str):
    path = get_safe_path(agent_name, "history.json")
    history = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f: # Added UTF-8
            history = json.load(f)
    history.append({"role": role, "text": text})
    with open(path, "w", encoding="utf-8") as f: # Added UTF-8
        json.dump(history, f)

def get_stock_price(ticker: str):
    """Fetches real-time stock price for a given ticker."""
    print(f"📈 DEBUG: Fetching Stock for: {ticker}")
    try:
        ticker = ticker.strip().upper().replace("$", "")
        stock = yf.Ticker(ticker)
        price = stock.fast_info['last_price']
        currency = stock.fast_info['currency']
        return f"The current price of {ticker} is {price:.2f} {currency}."
    except Exception as e:
        return f"Could not find stock data for {ticker}: {e}"

def web_search(query: str):
    """Executes a live DuckDuckGo search and returns top snippets."""
    print(f"🌐 DEBUG: Executing Web Search for: {query}")
    try:
        with DDGS() as ddgs:
            raw_results = list(ddgs.text(query, max_results=5))
            if not raw_results: return "No results found on the web."
            
            context_bits = []
            for r in raw_results:
                context_bits.append(f"TITLE: {r.get('title')}\nINFO: {r.get('body')}\nURL: {r.get('href')}")
            return "\n---\n".join(context_bits)
    except Exception as e:
        print(f"❌ SEARCH ERROR: {str(e)}")
        return f"Web search service is currently unavailable: {str(e)}"

@app.get("/")
async def get_ui():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>index.html not found</h1>")

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
        with open(path, "r", encoding="utf-8") as f: # Added UTF-8
            return json.load(f)
    return []

@app.post("/chat")
async def chat(name: str, message: str, model: str, api_key: Optional[str] = None):
    is_ollama = "ollama" in model
    save_to_history(name, "user", message)
    
    soul_p, mem_p = get_safe_path(name, "soul.md"), get_safe_path(name, "memory.md")
    
    # Safe file reading
    soul = "Chief of Staff."
    if os.path.exists(soul_p):
        with open(soul_p, "r", encoding="utf-8") as f: soul = f.read()
    
    mem = ""
    if os.path.exists(mem_p):
        with open(mem_p, "r", encoding="utf-8") as f: mem = f.read()

    system_prompt = (
        f"IDENTITY: {soul}\nMEMORY: {mem}\n"
        f"TODAY'S DATE: Wednesday, February 25, 2026\n\n"
        "INSTRUCTIONS:\n"
        "1. If you need current info, news, or 2026 facts, reply ONLY with: SEARCH: [query]\n"
        "2. To look up a stock price, reply ONLY with: STOCK: [TICKER]\n"
        "3. To look up homes/real estate, reply ONLY with: SEARCH: site:zillow.com [location] homes for sale\n"
        "4. Once you have results, provide a final helpful answer.\n"
        "5. To save important info to memory, end response with: COMMIT: [info]\n"
        "6. To write a file to your folder, include a block in your response:\n"
        "   WRITE: relative/path/filename.txt\n"
        "   [file content here]\n"
        "   END_WRITE\n"
        "   You may write to subdirectories (e.g. reports/summary.txt). The file will be saved to your workspace folder."
    )

    try:
        # PASS 1: Generate command or answer
        response = completion(
            model=model,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": message}],
            api_key=api_key if (api_key and not is_ollama) else "any",
            base_url="http://127.0.0.1:11434" if is_ollama else None
        )
        
        reply = response.choices[0].message.content.strip()
        tool_context = ""

        # PASS 2: Tool Execution Logic
        if reply.startswith("STOCK:"):
            ticker = reply.replace("STOCK:", "").strip().split()[0]
            tool_context = get_stock_price(ticker)
        
        elif reply.startswith("SEARCH:"):
            query = reply.replace("SEARCH:", "").strip().split("\n")[0]
            tool_context = web_search(query)

        # PASS 3: Synthesis if tool was used
        if tool_context:
            final_call = completion(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": reply},
                    {"role": "system", "content": f"TOOL OUTPUT:\n{tool_context}\n\nFinal response:"}
                ],
                api_key=api_key if (api_key and not is_ollama) else "any",
                base_url="http://127.0.0.1:11434" if is_ollama else None
            )
            reply = final_call.choices[0].message.content

        # Handle Memory Updates
        if "COMMIT:" in reply:
            commit_match = re.search(r"COMMIT:\s*(.*)", reply)
            if commit_match:
                with open(mem_p, "a", encoding="utf-8") as f:
                    f.write(f"\n- {commit_match.group(1).strip()}")
                reply = re.sub(r"COMMIT:.*", "*(Memory Updated)*", reply)

        # Handle File Writes
        for write_match in re.finditer(r"WRITE:\s*(\S+)\n(.*?)END_WRITE", reply, re.DOTALL):
            filename = write_match.group(1).strip()
            content = write_match.group(2)
            try:
                write_agent_file(name, filename, content)
                print(f"📝 Agent '{name}' wrote file: {filename}")
                replacement = f"*(File Saved: {filename})*"
            except HTTPException:
                print(f"❌ Agent '{name}' was denied write access to: {filename}")
                replacement = f"*(Write Denied: {filename} is outside your workspace)*"
            reply = reply.replace(write_match.group(0), replacement)

        save_to_history(name, "assistant", reply)
        return {"reply": reply}
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {str(e)}")
        return {"reply": f"❌ Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)