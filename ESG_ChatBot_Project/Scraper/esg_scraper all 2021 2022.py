# -*- coding: utf-8 -*-
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np
import requests

from playwright.sync_api import sync_playwright

# ===== 公司 / 年份設定 =====
COMPANIES = {
    "2330": "台積電", "2317": "鴻海", "2454": "聯發科", "2881": "富邦金",
    "2412": "中華電", "2382": "廣達", "2308": "台達電", "2882": "國泰金",
    "2891": "中信金", "3711": "日月光投控",
}
YEARS_HTML = [2022, 2021]

OUTDIR = Path("./esg_scraper_all_2022_2021")
OUTDIR.mkdir(parents=True, exist_ok=True)
RAW_DIR = OUTDIR / "raw"
RAW_DIR.mkdir(exist_ok=True)

CSV_PATH = OUTDIR / "all_companies_long.csv"
JSON_PATH = OUTDIR / "all_companies_wide.json"

# ===== 類別對應 =====
ENV_TOPICS = {"溫室氣體排放","氣候相關議題管理","能源管理","水資源管理","廢棄物管理","產品生命週期"}
SOC_TOPICS = {"人力發展","職業安全衛生","產品品質與安全"}
GOV_TOPICS = {"董事會","功能性委員會","持股及控制力","投資人溝通","風險管理政策","反競爭行為法律訴訟"}
def topic_to_category(t): 
    if t in ENV_TOPICS: return "環境"
    if t in SOC_TOPICS: return "社會"
    if t in GOV_TOPICS: return "治理"
    return "—"

# ===== 數值清理 =====
def to_value(x):
    if not x:return None
    s = str(x).strip().replace(",", "")
    if s.endswith("%"):
        try:return float(s[:-1]) / 100
        except:return s
    try:return float(s)
    except:return s


# ===== HTML 版（for 2021 2022） =====
def fetch_html_table(code: str, name: str, year: int) -> pd.DataFrame:
    url = f"https://esggenplus.twse.com.tw/inquiry/info/individual?companyCode={code}&year={year}"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(url, wait_until="networkidle", timeout=60000)

        js = r"""
        () => {
          const trs = document.querySelectorAll('table[aria-label="查詢結果"] tbody tr[id], table[aria-label="查詢結果"] tbody tr[data-tr-key]');
          const out = [];
          trs.forEach(tr => {
            const rawKey = tr.getAttribute("id") || tr.getAttribute("data-tr-key") || "";
            const indicator = rawKey.split("_").pop()?.trim() || "";
            const tds = Array.from(tr.querySelectorAll("td"));
            let field = "";
            let value = "";

            const w150 = tr.querySelector("td.w150-p");
            if (w150) {
              field = w150.innerText.trim();
              const idx = tds.indexOf(w150);
              if (idx >= 0 && idx + 1 < tds.length)
                value = (tds[idx + 1].innerText || "").trim();
            } else {
              if (tds.length >= 1) field = (tds[0].innerText || "").trim();
              const desc = tr.querySelector("td.desc-col");
              if (desc) value = desc.innerText.trim();
              else if (tds.length >= 2) value = (tds[1].innerText || "").trim();
            }
            if (indicator && field) out.push({indicator, field, value});
          });
          return out;
        }
        """
        rows = page.evaluate(js)
        browser.close()

    data = []
    for r in rows:
        cat = topic_to_category(r["indicator"])
        val = to_value(r["value"])
        data.append({
            "公司代碼": code, "公司名稱": name, "年度": year,
            "類別": cat, "指標名稱": r["indicator"], "欄位名稱": r["field"], "數值": val
        })
    return pd.DataFrame(data)

# ===== 主流程 =====
def main():
    all_dfs = []
    for code, name in COMPANIES.items():
        
        # --- 再 HTML 年份 ---
        for y in YEARS_HTML:
            try:
                df = fetch_html_table(code, name, y)
                if not df.empty:
                    all_dfs.append(df)
                    print(f"✔ {name}({code}) {y} HTML 抓取 {len(df)} 筆")
            except Exception as e:
                print(f"✗ {name}({code}) {y} HTML 失敗: {e}")

    if not all_dfs:
        print("✗ 沒有任何資料"); return
    merged = pd.concat(all_dfs, ignore_index=True)
    merged.to_csv(CSV_PATH, index=False, encoding="utf-8-sig")

    merged["path"] = merged[["類別","指標名稱","欄位名稱"]].astype(str).agg("/".join, axis=1)
    wide = []
    for (c, n, y), g in merged.groupby(["公司代碼","公司名稱","年度"]):
        row = {"公司代碼": c, "公司名稱": n, "年度": int(y)}
        for _, r in g.iterrows():
            row[r["path"]] = r["數值"]
        wide.append(row)
    JSON_PATH.write_text(json.dumps(wide, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"📄 輸出 CSV：{CSV_PATH.resolve()}")
    print(f"📄 輸出 JSON：{JSON_PATH.resolve()}")

if __name__ == "__main__":
    main()
