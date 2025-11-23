# api_server.py
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Tuple
from rag_query import get_answer
from llm import chat_response

app = FastAPI(title="ESG RAG API")

# CORS：開發階段先全開，上線請改成你的前端網域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    question: str
    session_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}

# 路由自檢：確認 summarize 是否掛上
@app.get("/__routes")
def list_routes():
    return {"routes": [r.path for r in app.routes]}

@app.post("/query")
def query(data: dict = Body(...)):
    question   = (data.get("question") or "").strip()
    mode       = (data.get("mode") or "all").strip()             # 'all' / 'esg' / 'news'
    history = data.get("history", [])

    # 新版 get_answer 以 session_id 管記憶，請勿再傳 history
    answer, sources = get_answer(
        question, 
        history=history, 
        return_sources=True, 
        mode=mode
    )

    # 回傳目前的 session 狀態（方便前端或你除錯）
    return {
        "answer": answer,
        "sources": sources,
    }

# 產生短標題（14 字內、偏中文）
@app.post("/title")
def make_title(data: dict = Body(...)):
    first_user = (data.get("first_user") or "").strip()
    if not first_user:
        return {"title": "新對話"}
    prompt = f"請為以下聊天主題生成一個精簡中文小標題，14 個中文字以內，不要加引號：\n{first_user}\n只輸出標題本身。"
    title = chat_response(prompt).strip().replace("\n", "")[:14] or "新對話"
    return {"title": title}

# 總結多段對話（history 是 [[user, assistant], ...]）
@app.post("/summarize")
def summarize_chats(data: dict = Body(...)):
    items: List[dict] = data.get("items", [])
    mode = data.get("mode", "all")

    parts = []
    for it in items:
        title = it.get("title", "未命名對話")
        hist: List[Tuple[str, str]] = it.get("history", [])
        body = "\n".join([f"使用者：{u}\n助理：{a}" for u, a in hist])
        parts.append(f"【{title}】\n{body}")

    joined = "\n\n---\n\n".join(parts) if parts else "(無內容)"
    prompt = f"""
你是一位精準的助理。請針對下列多段對話（模式：{mode}）做整合摘要，要求：
- 先給 2–3 行的總結（重點/決策/結論）
- 接著條列：關鍵事實/數據（保留數值與單位）、未解決問題、下一步行動清單
- 語氣精簡專業，輸出為 Markdown，不要加入多餘前言

對話內容：
{joined}
"""
    summary = chat_response(prompt).strip()
    return {"summary": summary}

# ✅ 把啟動放在最底（所有路由之後）
if __name__ == "__main__":
    import uvicorn
    # 建議用這個指令在外部啟動也行： uvicorn api_server:app --reload
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True,  http="h11")
