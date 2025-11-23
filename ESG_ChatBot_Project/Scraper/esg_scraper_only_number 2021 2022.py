# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

# ===== 只抓 2021 / 2022 的版本 =====
COMPANIES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2881": "富邦金",
    "2412": "中華電", "2382": "廣達", "2308": "台達電", "2882": "國泰金",
    "2891": "中信金", "3711": "日月光投控",
}
YEARS = [2022, 2021]

OUTDIR = Path("./esg_scraper_only_number 2021 2022")
OUTDIR.mkdir(parents=True, exist_ok=True)
WIDE_JSON_PATH = OUTDIR / "esg_scraper_only_number 2021 2022"

# ===== 分類映射 =====
ENV_TOPICS = {"溫室氣體排放","氣候相關議題管理","能源管理","水資源管理","廢棄物管理","產品生命週期"}
SOC_TOPICS = {"人力發展","職業安全衛生","產品品質與安全"}
GOV_TOPICS = {"董事會","功能性委員會","持股及控制力","投資人溝通","風險管理政策","反競爭行為法律訴訟"}

def topic_to_category(topic: str) -> str:
    if topic in ENV_TOPICS: return "環境"
    if topic in SOC_TOPICS: return "社會"
    if topic in GOV_TOPICS: return "治理"
    return "—"

def to_numeric_value(text: Optional[str]):
    """轉數字；非數字回 None"""
    if text is None: return None
    s = text.strip()
    if s in {"", "-", "—", "N/A"}: return None
    s2 = s.replace(",", "")
    if s2.endswith("%"):
        try: return float(s2[:-1])/100
        except: return None
    try: return float(s2)
    except: return None

def fetch_one(code: str, name: str, year: int) -> pd.DataFrame:
    """使用 Playwright 抓取頁面"""
    from playwright.sync_api import sync_playwright
    url = f"https://esggenplus.twse.com.tw/inquiry/info/individual?companyCode={code}&year={year}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)

        js = r"""
        () => {
          const sel = 'table[aria-label="查詢結果"] tbody tr[id], table[aria-label="查詢結果"] tbody tr[data-tr-key]';
          const trs = document.querySelectorAll(sel);
          const out = [];
          trs.forEach(tr => {
            const rawKey = tr.getAttribute("id") || tr.getAttribute("data-tr-key") || "";
            const indicator = (rawKey.split("_").pop() || "").trim();
            const tds = Array.from(tr.querySelectorAll("td"));
            let field = "", value = "";
            const w150 = tr.querySelector("td.w150-p");
            if (w150) {
              field = (w150.innerText || "").trim();
              const idx = tds.indexOf(w150);
              if (idx >= 0) {
                for (let i = idx + 1; i < tds.length; i++) {
                  const txt = (tds[i].innerText || "").trim();
                  if (txt) { value = txt; break; }
                }
              }
            } else {
              if (tds.length >= 1) field = (tds[0].innerText || "").trim();
              const desc = tr.querySelector("td.desc-col");
              if (desc) value = (desc.innerText || "").trim();
              else if (tds.length >= 2) value = (tds[1].innerText || "").trim();
            }
            if (indicator && field) out.push({indicator, field, value});
          });
          return out;
        }
        """
        rows = page.evaluate(js)
        browser.close()

    # 只保留「數字」
    records: List[Dict[str, Any]] = []
    for r in rows:
        val = to_numeric_value(r["value"])
        if val is None:
            continue
        cat = topic_to_category(r["indicator"])
        records.append({
            "公司代碼": code,
            "公司名稱": name,
            "年度": year,
            "類別": cat,
            "欄位名稱": r["field"],
            "數值": val,
        })
    return pd.DataFrame(records)

# ===== 主程式 =====
def main():
    all_dfs = []
    for code, name in COMPANIES.items():
        for y in YEARS:
            try:
                df = fetch_one(code, name, y)
                if not df.empty:
                    all_dfs.append(df)
                    print(f"✔ {name}({code}) {y} → {len(df)} 筆")
                else:
                    print(f"⚠ {name}({code}) {y} 無數字資料")
            except Exception as e:
                print(f"✗ {name}({code}) {y} 失敗: {e}")

    if not all_dfs:
        print("✗ 沒有任何資料")
        return

    df = pd.concat(all_dfs, ignore_index=True)
    # 寬表整合
    df["path"] = df[["類別","欄位名稱"]].astype(str).agg("/".join, axis=1)

    wide_records = []
    for (code, name, year), g in df.groupby(["公司代碼","公司名稱","年度"]):
        row = {"公司代碼": code, "公司名稱": name, "年度": int(year)}
        for _, r in g.iterrows():
            row[r["path"]] = r["數值"]
        wide_records.append(row)

    # 只輸出 JSON
    WIDE_JSON_PATH.write_text(json.dumps(wide_records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 完成寬表 JSON：{WIDE_JSON_PATH.resolve()}")

if __name__ == "__main__":
    main()
