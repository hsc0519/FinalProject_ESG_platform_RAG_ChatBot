# -*- coding: utf-8 -*-
from fastapi import FastAPI, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List, Tuple
import os
import json
from pathlib import Path
# === ② RAG API（第二段） ===
from rag_query import get_answer
from llm import chat_response


# === 建立單一應用 ===
app = FastAPI(title="Merged ESG APIs")

# === CORS 設定（沿用第一段的環境變數控制） ===
_frontend_env = os.getenv("FRONTEND_ORIGINS", "")
origins = [o.strip() for o in _frontend_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],  # 部署時建議改成具體網域清單
    allow_credentials=False if not origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# === ① ESG Lookup（第一段） ===
DATA_PATH = Path(__file__).parent / "all number data.json"
with open(DATA_PATH, encoding="utf-8") as f:
    data = json.load(f)

@app.get("/")
def root():
    return {"message": "ESG Lookup API 上線成功"}

@app.get("/companies")
@app.get("/companies/")  # 允許 /companies/
def list_companies():
    """列出所有公司代碼與名稱（乾淨化）"""
    result: Dict[str, str] = {}
    for r in data:
        code = str(r["公司代碼"]).strip()
        name = r["公司名稱"].strip()
        result[code] = name
    return result


@app.get("/fields")
def list_fields(code: Optional[str] = None, year: Optional[int] = None):
    """
    列出欄位名稱（只保留數值型欄位）
    - 不給參數 → 全部數值型欄位
    - 有給 code+year → 該公司/年度的數值型欄位
    """
    if code and year:
        row = next(
            (r for r in data if str(r["公司代碼"]).strip() == str(code).strip() and int(r["年度"]) == int(year)),
            None
        )
        if not row:
            return {"error": "查無資料"}

        fields: List[str] = []
        for k, v in row.items():
            if k in ("公司代碼", "公司名稱", "年度"):
                continue
            if isinstance(v, (int, float)):  # ✅ 只保留數值型
                fields.append(k)

        return {"company_code": str(code).strip(), "year": int(year), "fields": fields}

    else:
        all_fields = set()
        for r in data:
            for k, v in r.items():
                if k in ("公司代碼", "公司名稱", "年度"):
                    continue
                if isinstance(v, (int, float)):  # ✅ 固定過濾，只留數值
                    all_fields.add(k)
        return {"欄位清單": sorted(all_fields)}

KEEP_KEYS = {"公司代碼", "公司名稱", "年度"}

def normalize_category_filter(cat: Optional[str]) -> Optional[str]:
    """只允許中文『環境』『社會』『治理』三類；沒輸入或其他字 → 不過濾"""
    if not cat:
        return None
    s = cat.strip()
    if s in ("環境", "社會", "治理"):
        return s
    return None

def _filter_data(
    code: Optional[str] = None,
    name: Optional[str] = None,
    year: Optional[int] = None,
    category: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """依 code/name/year 篩資料列；若指定 category，於欄位層級只保留該類別(且為數值)欄位"""
    target = data

    if code:
        c = str(code).strip()
        target = [r for r in target if str(r["公司代碼"]).strip() == c]

    if name:
        n = name.strip()
        target = [r for r in target if r["公司名稱"].strip() == n]

    if year:
        y = int(year)
        target = [r for r in target if int(r["年度"]) == y]

    want_cat = normalize_category_filter(category)
    if not want_cat:
        return target

    prefix = want_cat + "/"
    pruned: List[Dict[str, Any]] = []
    for r in target:
        nr = {k: r[k] for k in KEEP_KEYS}
        for k, v in r.items():
            if k in KEEP_KEYS:
                continue
            if isinstance(v, (int, float)) and k.startswith(prefix):
                nr[k] = v
        pruned.append(nr)
    return pruned

@app.get("/search")
def search(
    keyword: Optional[str] = None,
    category: Optional[str] = None,   # 僅允許 環境/社會/治理；未輸入 → 全部
    code: Optional[str] = None,
    name: Optional[str] = None,
    year: Optional[int] = None,
):
    # 依條件與類別篩選
    target_rows = _filter_data(code=code, name=name, year=year, category=category)
    parts = [p.strip() for p in (keyword or "").split("/") if p.strip()]

    items: List[Dict[str, Any]] = []
    for row in target_rows:
        for k, v in row.items():
            if k in KEEP_KEYS:
                continue
            if not isinstance(v, (int, float)):
                continue
            if parts and not all(p in k for p in parts):
                continue

            cat = k.split("/", 1)[0] if "/" in k else "未分類"
            items.append({
                "company_code": str(row["公司代碼"]).strip(),
                "company_name": row["公司名稱"].strip(),
                "year": int(row["年度"]),
                "category": cat,           # 依 key 第一段
                "field": k.split("/", 1)[-1] if "/" in k else k,
                "value": v,
            })

    return {"items": items, "total": len(items)}



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
    # 建議用這個指令在外部啟動也行： uvicorn merged_api:app --reload --port 8000
    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=True, http="h11")

