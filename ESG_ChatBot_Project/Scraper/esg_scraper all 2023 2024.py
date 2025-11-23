import requests
import pandas as pd
import json
from pathlib import Path
from typing import Any, Dict, List
import numpy as np


API_URL = "https://esggenplus.twse.com.tw/api/api/mopsEsg/singleCompanyData"
USE_CHINESE_HEADERS = False  # True=輸出中文欄位, False=輸出代碼


COMPANIES = {
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

YEARS = [2024, 2023]  # 你要輸出的年度

OUTDIR = Path("./esg_scraper_all_2023_2024")
RAW_DIR = OUTDIR / "raw"
CSV_DIR = OUTDIR / "csv"
RAW_DIR.mkdir(parents=True, exist_ok=True)
CSV_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "Content-Type": "application/json;charset=UTF-8",
    "Origin": "https://esggenplus.twse.com.tw",
    "Referer": "https://esggenplus.twse.com.tw/",
    "User-Agent": "Mozilla/5.0",
}


def make_lookup_records(df: pd.DataFrame) -> list[dict]:
    def to_native(x):
        if pd.isna(x):
            return None
        if isinstance(x, (np.integer,)):
            return int(x)
        if isinstance(x, (np.floating,)):
            return float(x)
        return x

    records = []
    for (code, name, year), g in df.groupby(["公司代碼", "公司名稱", "年度"]):
        row = {
            "公司代碼": str(code),
            "公司名稱": str(name),
            "年度": int(year) if not isinstance(year, str) else year,  # 轉成原生 int
        }
        for _, r in g.iterrows():
            key = f"{r['類別']}/{r['指標名稱']}/{r['區段']}/{r['欄位名稱']}"
            row[key] = to_native(r["數值"])  # 數值轉成原生
        records.append(row)
    return records


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


def save_raw(code: str, year: int, data: Any):
    path = RAW_DIR / f"{code}_{year}_raw.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def flatten_payload(code: str, name: str, year: int, payload: Dict[str, Any]) -> pd.DataFrame:
    rows = []
    data_list = payload.get("data", [])
    if not isinstance(data_list, list) or not data_list:
        return pd.DataFrame()

    root = data_list[0]
    models = root.get("treeModels", [])

    for block in models:
        category = block.get("categoryString") or block.get("category")

        # 🔹 只要 社會 / 治理
        if category not in ("環境", "社會", "治理"):
            continue

        for it in block.get("items", []):
            declare_item = (
                it.get("declareItemShowName")
                or it.get("declareItemName")
                or it.get("item")
            )
            for sec in it.get("sections", []):
                section_name = sec.get("showName") or sec.get("name")
                for ctrl in sec.get("controls", []):
                    def _clean_value(val):
                        if val is None:
                            return None
                        if isinstance(val, str):
                            v = val.strip()
                            # 🔹 百分比處理（轉成比例 0~1）
                            if v.endswith("%"):
                                try:
                                    return float(v.replace("%", "").replace(",", "").strip()) / 100
                                except ValueError:
                                    return val  # 轉換失敗就保留字串
                            # 🔹 一般數字（含千分位）
                            try:
                                return float(v.replace(",", ""))
                            except ValueError:
                                return val
                        return val  # 已經是數字就直接回傳

                    rows.append({
                        "companyCode": code,
                        "companyName": name,
                        "year": year,
                        "category": category,
                        "declareItemName": declare_item,
                        "section": section_name,
                        "controlTitle": ctrl.get("showTitle") or ctrl.get("title"),
                        "code": ctrl.get("code"),
                        "value": _clean_value(ctrl.get("value")),  # ✅ 改這裡
                        "ctrType": ctrl.get("ctrType"),
                    })

    df = pd.DataFrame(rows)

    # 改欄位名稱成中文
    df = df.rename(columns={
        "companyCode": "公司代碼",
        "companyName": "公司名稱",
        "year": "年度",
        "category": "類別",
        "declareItemName": "指標名稱",
        "section": "區段",
        "controlTitle": "欄位名稱",
        "code": "指標代碼",
        "value": "數值",
        "ctrType": "數據型態",
    })

    return df


def main():
    all_dfs: List[pd.DataFrame] = []

    # 先把所有 公司×年度 逐一抓下來 → 累積到 all_dfs
    for code, name in COMPANIES.items():
        for y in YEARS:
            try:
                payload = call_api(code, y)
                save_raw(code, y, payload)  # 存原始 JSON（前端也可直接用）
                df = flatten_payload(code, name, y, payload)
                if not df.empty:
                    # 單家公司×年度的長表
                    out_path = CSV_DIR / f"{code}_{y}_long.csv"
                    df.to_csv(out_path, index=False, encoding="utf-8-sig")
                    print(f"✔ {name}({code}) 年度 {y} → {out_path}")
                    all_dfs.append(df)
                else:
                    print(f"⚠ {name}({code}) 年度 {y} 沒有資料")
            except Exception as e:
                print(f"✗ {name}({code}) 年度 {y} 失敗: {e}")

    # === 迴圈全部跑完，再做合併輸出 ===
    if not all_dfs:
        print("✗ 沒有任何資料可合併，請檢查 raw/*.json")
        return

    merged = pd.concat(all_dfs, ignore_index=True)
    merged.to_csv(OUTDIR / "all_companies_long.csv", index=False, encoding="utf-8-sig")
    print(f"📄 合併輸出：{(OUTDIR / 'all_companies_long.csv').resolve()}")

    # Pivot（先用代碼）
    pivot = merged.pivot_table(
        index=["公司代碼", "公司名稱", "年度"],
        columns="指標代碼",
        values="數值",
        aggfunc="first"
    ).reset_index()

    # 保留原始欄位順序（依 merged 首次出現順序）
    col_order = (
        merged.drop_duplicates(subset=["指標代碼"])["指標代碼"].tolist()
    )

    if USE_CHINESE_HEADERS:
        # 代碼 → 中文欄位名 對照
        code_to_cn = (
            merged[["指標代碼", "欄位名稱"]]
            .drop_duplicates()
            .set_index("指標代碼")["欄位名稱"]
            .to_dict()
        )
        pivot = pivot.rename(columns=code_to_cn)
        col_order = [code_to_cn.get(c, c) for c in col_order]

    # 重新排欄位順序（只保留真的存在的欄位，避免 KeyError）
    valid_cols = [c for c in col_order if c in pivot.columns]
    pivot = pivot[["公司代碼", "公司名稱", "年度"] + valid_cols]

    out_pivot = OUTDIR / "all_companies_pivot.csv"
    pivot.to_csv(out_pivot, index=False, encoding="utf-8-sig")
    print(f"📄 Pivot 輸出（依原始順序）→ {out_pivot.resolve()}")

    # 合併 raw JSON 成整包（給前端一次抓全部）
    big_json = {}
    for raw_file in RAW_DIR.glob("*_raw.json"):
        parts = raw_file.stem.split("_")
        code_key, year_key = parts[0], parts[1]
        with open(raw_file, encoding="utf-8") as f:
            big_json.setdefault(code_key, {})[year_key] = json.load(f)
    with open(OUTDIR / "all_companies.json", "w", encoding="utf-8") as f:
        json.dump(big_json, f, ensure_ascii=False, indent=2)
    print(f"📄 JSON 輸出：{(OUTDIR / 'all_companies.json').resolve()}")

    # 產生查表版 JSON（用中文 key 直接查）
    lookup_records = make_lookup_records(merged)
    out_lookup = OUTDIR / "all_companies_lookup.json"
    out_lookup.write_text(json.dumps(lookup_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 Lookup JSON 輸出：{out_lookup.resolve()}")


if __name__ == "__main__":
    main()
