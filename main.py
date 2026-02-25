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
        with open(path, "r", encoding="utf-8") as f:
            history = json.load(f)
    history.append({"role": role, "text": text})
    with open(path, "w", encoding="utf-8") as f:
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
        with open(path, "r", encoding="utf-8") as f:
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
        "5. To save important info to memory, end response with: COMMIT: [info]"
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

        save_to_history(name, "assistant", reply)
        return {"reply": reply}
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {str(e)}")
        return {"reply": f"❌ Error: {str(e)}"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)