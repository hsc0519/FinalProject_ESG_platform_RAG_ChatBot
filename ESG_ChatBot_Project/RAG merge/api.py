# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any, List
import os
import json
from pathlib import Path

# === 建立應用 ===
app = FastAPI()

# === CORS 設定 ===
# 建議在部署時用環境變數設定允許的前端網域（逗號分隔）
# 例：FRONTEND_ORIGINS="https://your-frontend.site,https://another.site,http://localhost:3000"
_frontend_env = os.getenv("FRONTEND_ORIGINS", "")
origins = [o.strip() for o in _frontend_env.split(",") if o.strip()]

# 若你「不帶 cookie」或「不需要憑證型請求」，可開放全部來源（最省事）
# 如果你「需要 cookie/Authorization 並使用跨站傳遞憑證」，請改用上面 origins 清單，且把 allow_credentials=True
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins else ["*"],  # 部署時建議改成具體網域清單
    allow_credentials=False if not origins else True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

# === 載入查表 JSON（用檔案所在目錄為基準） ===
DATA_PATH = Path(__file__).parent / "all number data cindy.json"
with open(DATA_PATH, encoding="utf-8") as f:
    data = json.load(f)

@app.get("/")
def root():
    return {"message": "ESG Lookup API 上線成功"}

@app.get("/companies")
@app.get("/companies/")  # 允許 /companies/
def list_companies():
    """列出所有公司代碼與名稱（乾淨化）"""
    result = {}
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

        fields = []
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

    items = []
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

# ✅ 把啟動放在最底（所有路由之後）
if __name__ == "__main__":
    import uvicorn
    # 建議用這個指令在外部啟動也行： uvicorn api_server:app --reload
    uvicorn.run("api:app", host="127.0.0.1", port=5000, reload=True,  http="h11")