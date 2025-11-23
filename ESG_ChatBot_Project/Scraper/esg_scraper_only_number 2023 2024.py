# -*- coding: utf-8 -*-
"""
ESG GenPlus 批次擷取 → 扁平化 → 單一 JSON（全公司×年度）
目標輸出「結構像你貼的扁平化 JSON」：每家公司×年度一個物件，
物件裡除了基本欄位（公司代碼/公司名稱/年度）外，其餘 key 為：
  類別/指標名稱/區段/欄位名稱
但**只保留 value 解析得出「數字或百分比」的欄位**（非數字的文字一律剔除）。

輸出檔：./esg_api_flat/all_companies_flat.json
"""

import json
from pathlib import Path
from typing import Any, Dict, List

import requests

API_URL = "https://esggenplus.twse.com.tw/api/api/mopsEsg/singleCompanyData"

# 公司清單
COMPANIES: Dict[str, str] = {
    "2330": "台積電",
    "2317": "鴻海",
    "2454": "聯發科",
    "2881": "富邦金",
    "2412": "中華電",
    "2382": "廣達",
    "2308": "台達電",
    "2882": "國泰金",
    "2891": "中信金",
    "3711": "日月光投控",
}

# 年度清單
YEARS: List[int] = [2023,2024]

# 參數：百分比轉成比例(0~1)或保留原數字(例如 7.5 表示 7.5%)
PERCENT_AS_RATIO = True

# 輸出路徑
OUTDIR = Path("./esg_scraper_only_number 2023 2024")
OUTDIR.mkdir(parents=True, exist_ok=True)
OUTFILE = OUTDIR / "esg_scraper_only_number 2023 2024.json"

HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://esggenplus.twse.com.tw",
    "Referer": "https://esggenplus.twse.com.tw/",
    "User-Agent": "Mozilla/5.0",
}


def call_api(code: str, year: int) -> Dict[str, Any]:
    payload = {
        "companyCode": code,
        "yearList": [year],
        "companyName": None,
        "year": year,
    }
    r = requests.post(API_URL, headers=HEADERS, json=payload, timeout=30)
    r.raise_for_status()
    return r.json()


def parse_numeric(val: Any) -> float | None:
    """
    嘗試把 value 轉為數字：
    - '12,345' -> 12345.0
    - '7.5%'   -> 0.075 (或 7.5，視 PERCENT_AS_RATIO)
    - 其他不可解析者 -> None
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)

    if isinstance(val, str):
        s = val.strip()
        if s == "" or s == "-":
            return None

        # 百分比
        if s.endswith("%"):
            try:
                num = float(s[:-1].replace(",", "").strip())
                return num / 100.0 if PERCENT_AS_RATIO else num
            except ValueError:
                return None

        # 一般數字（含千分位）
        try:
            return float(s.replace(",", ""))
        except ValueError:
            return None

    return None


def flatten_company_year(code: str, name: str, year: int, payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    產生單一物件（寬表扁平化）：
    {
      "公司代碼": "...",
      "公司名稱": "...",
      "年度": 2023,
      "環境/溫室氣體排放/.../數據": 26283.0,
      "環境/能源管理/.../再生能源使用率": 0.76,
      ...
    }
    只保留可解析為數字或百分比的 value；其餘（文字）不輸出。
    """
    out: Dict[str, Any] = {
        "公司代碼": code,
        "公司名稱": name,
        "年度": year,
    }

    data_list = payload.get("data", [])
    if not isinstance(data_list, list) or not data_list:
        return out

    root = data_list[0]
    models = root.get("treeModels", [])

    for block in models:
        category = block.get("categoryString") or block.get("category")
        if category not in ("環境", "社會", "治理"):
            continue

        for it in block.get("items", []):
            declare_item = it.get("declareItemName") or it.get("declareItemShowName") or it.get("item")
            for sec in it.get("sections", []):
                section_name = sec.get("name") or sec.get("showName")

                for ctrl in sec.get("controls", []):
                    title = (ctrl.get("title") or ctrl.get("showTitle") or "").strip()
                    parsed = parse_numeric(ctrl.get("value"))
                    if parsed is None:
                        # 不是數字/百分比 → 丟掉，不寫入
                        continue

                    key = f"{category}/{section_name}"
                    out[key] = parsed

    return out


def main():
    all_docs: List[Dict[str, Any]] = []

    for code, name in COMPANIES.items():
        for y in YEARS:
            try:
                payload = call_api(code, y)
                doc = flatten_company_year(code, name, y, payload)
                all_docs.append(doc)
                print(f"✔ {name}({code}) 年度 {y}：扁平欄位 {len(doc) - 3} 個（僅數值）")
            except Exception as e:
                print(f"✗ {name}({code}) 年度 {y} 失敗：{e}")

    with open(OUTFILE, "w", encoding="utf-8") as f:
        json.dump(all_docs, f, ensure_ascii=False, indent=2)

    print(f"📄 已輸出：{OUTFILE.resolve()}")


if __name__ == "__main__":
    main()
