# rag_setup.py —— 重建向量庫（OpenAI + Chroma；含健壯性／去重／chunk_id／NEWS 自動分段／分批寫入）
import os
import shutil
import hashlib
from typing import List, Optional

import pandas as pd
from langchain_openai import OpenAIEmbeddings
from langchain.schema import Document
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter

from config import PERSIST_DIR, COLLECTION_NAME, EMBED_MODEL

# =========================
# 讀取 API Key（檔案優先，環境變數次之）
# =========================
api_key: Optional[str] = None
if os.path.exists("api_key.txt"):
    with open("api_key.txt", "r", encoding="utf-8") as f:
        api_key = f.read().strip()
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")
assert api_key, "找不到 OpenAI API Key，請建立 api_key.txt 或設 OPENAI_API_KEY 環境變數。"

# =========================
# Embeddings
# =========================
embedding = OpenAIEmbeddings(
    model=EMBED_MODEL,
    api_key=api_key,
)

# （ESG 不切段；NEWS 用下方專用 splitter）
NEWS_SPLITTER = RecursiveCharacterTextSplitter(
    chunk_size=800,       # 給新聞較大的 chunk，提升可讀性與命中率
    chunk_overlap=120,
    separators=["\n\n", "\n", "。", "、", " "]
)

# =========================
# 工具函式
# =========================
def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def safe_read_csv(path: str) -> pd.DataFrame:
    """以常見編碼嘗試讀 CSV，並給清楚錯誤訊息。"""
    if not os.path.exists(path):
        raise FileNotFoundError(f"找不到檔案：{path}")
    for enc in ["utf-8-sig", "utf-8", "big5", "cp950"]:
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise ValueError(f"無法以常見編碼讀取檔案: {path}（請確認編碼或檔案格式）")

def _to_int(v) -> Optional[int]:
    try:
        s = str(v).strip()
        if s == "" or s.lower() == "nan":
            return None
        return int(float(s))
    except Exception:
        return None

def _to_float(v) -> Optional[float]:
    """嘗試把 value 解讀成數字；若是純文字則回 None。"""
    try:
        s = str(v).replace(",", "").strip()
        if s == "" or s.lower() == "nan":
            return None
        # 只接受純數字（含小數），不含單位
        if not pd.Series([s]).str.match(r"^[-+]?\d+(\.\d+)?$").item():
            return None
        return float(s)
    except Exception:
        return None

def _norm_text(s: str) -> str:
    return (s or "").replace("\r\n", "\n").replace("\r", "\n").strip()

def _ensure_cols(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c not in df.columns:
            df[c] = ""
    return df

# =========================
# ESG：DataFrame -> Documents（不切段）
# 期待欄位（原始可能為中文）：公司代號/公司名稱/年度/類別/指標名稱/欄位名稱/區段/數值
# =========================
ESG_RENAME = {
    "公司代號": "company_code",
    "公司名稱": "company_name",
    "年度": "year",
    "類別": "category",
    "指標名稱": "indicator",
    "欄位名稱": "sub_field",
    "區段": "field",
    "數值": "value",
}

def df_to_docs_esg(df: pd.DataFrame, source_name: str) -> List[Document]:
    df = df.copy()
    df = df.rename(columns=ESG_RENAME)
    df = _ensure_cols(
        df,
        ["company_code", "company_name", "year", "category", "indicator", "sub_field", "field", "value"]
    ).fillna("")

    docs: List[Document] = []
    for idx, row in df.iterrows():
        company_code = str(row.get("company_code", "")).strip()
        company_name = str(row.get("company_name", "")).strip()
        year_raw     = str(row.get("year", "")).strip()
        category     = str(row.get("category", "")).strip()
        indicator    = str(row.get("indicator", "")).strip()
        field        = str(row.get("field", "")).strip()
        sub_field    = str(row.get("sub_field", "")).strip()
        value_raw    = str(row.get("value", ""))  # 可能為純文字或純數字（無單位）

        year_int   = _to_int(year_raw)     # 給 metadata 過濾用
        value_num  = _to_float(value_raw)  # 純數字時才有值；否則 None

        content = _norm_text(
            f"公司代號: {company_code}\n"
            f"公司名稱: {company_name}\n"
            f"年度: {year_raw}\n"
            f"類別: {category}\n"
            f"指標名稱: {indicator}\n"
            f"區段: {field}\n"
            f"欄位名稱: {sub_field}\n"
            f"數值: {value_raw}\n"
        )

        meta = {
            "source": source_name,
            "doc_type": "esg",
            "company_code": company_code,
            "company_name": company_name,
            "year": year_int,
            "category": category,
            "field": field,
            "indicator": indicator,
            "sub_field": sub_field,
            "value_text": value_raw,  # 保留原文字
            "value_num": value_num,   # 可選的數字版
            "chunk_id": _sha1(f"{source_name}|{idx}|{company_code}|{company_name}|{year_raw}|{indicator}|{sub_field}|{value_raw}")
        }

        docs.append(Document(page_content=content, metadata=meta))

    return docs

# =========================
# NEWS：DataFrame -> Documents（長內文自動分段）
# ※ 這裡假設 News 欄位名已是英文：title/content/url/image_url/category/company_name/company_code/sentiment/keyword
# =========================
def df_to_docs_news(df: pd.DataFrame, source_name: str) -> List[Document]:
    df = df.copy().fillna("")

    must = ["title", "content", "url", "image_url", "category",
            "company_name", "company_code", "sentiment", "keyword"]
    df = _ensure_cols(df, must)

    docs: List[Document] = []
    for idx, row in df.iterrows():
        title        = _norm_text(row.get("title", ""))
        body         = _norm_text(row.get("content", ""))
        url          = str(row.get("url", "")).strip()
        image_url    = str(row.get("image_url", "")).strip()
        category     = str(row.get("category", "")).strip()
        company_name = str(row.get("company_name", "")).strip()
        company_code = str(row.get("company_code", "")).strip()
        sentiment    = str(row.get("sentiment", "")).strip()
        keyword      = str(row.get("keyword", "")).strip()

        # 每篇文章給一個 article_id，分段後共用；chunk_id 加段落序號
        article_id = _sha1(f"{source_name}|{idx}|{title}|{company_name}|{company_code}|{url}")

        # 合併「標題 + 內文」再分段，保上下文
        full_text = _norm_text(f"{title}\n\n{body}")
        chunks = NEWS_SPLITTER.split_text(full_text) or [full_text]

        for j, ch in enumerate(chunks):
            content = _norm_text(
                f"title：{title}\n"
                f"content_chunk：{ch}\n"
                f"category：{category}\n"
                f"company_name：{company_name}\n"
                f"sentiment：{sentiment}\n"
                f"company_code：{company_code}\n"
                f"keyword：{keyword}\n"
            )

            meta = {
                "source": source_name,
                "doc_type": "news",
                "article_id": article_id,
                "chunk_index": j,
                "title": title,
                "url": url,
                "image_url": image_url,
                "category": category,
                "company_name": company_name,
                "company_code": company_code,
                "sentiment": sentiment,
                "keyword": keyword,
                "chunk_id": _sha1(f"{article_id}|chunk|{j}")
            }

            docs.append(Document(page_content=content, metadata=meta))

    return docs

# =========================
# 去重（以 chunk_id 或內容哈希）
# =========================
def unique_docs(docs: List[Document]) -> List[Document]:
    seen, out = set(), []
    for d in docs:
        meta = d.metadata or {}
        key = (meta.get("source", "unknown"), meta.get("chunk_id") or _sha1(d.page_content))
        if key not in seen:
            out.append(d)
            seen.add(key)
    return out

# =========================
# 讀檔 → 轉 Document → 去重 → 清庫 → 建庫（分批 add）
# =========================
if __name__ == "__main__":
    # 載入資料
    df1 = safe_read_csv("all_companies_long_2023_2024.csv")
    df2 = safe_read_csv("all_companies_long_2021_2022.csv")
    df3 = safe_read_csv("classify.csv")

    docs_esg_1 = df_to_docs_esg(df1, source_name="all_companies_long_2023_2024.csv")
    docs_esg_2 = df_to_docs_esg(df2, source_name="all_companies_long_2021_2022.csv")
    docs_news  = df_to_docs_news(df3, source_name="classify.csv")

    # 合併 + 去重
    all_documents = unique_docs(docs_esg_1 + docs_esg_2 + docs_news)

    # 清空舊庫
    if os.path.isdir(PERSIST_DIR):
        shutil.rmtree(PERSIST_DIR)

    # 建立空的 collection（不要用 from_documents，一次塞太多會爆 token）
    vectorstore = Chroma(
        embedding_function=embedding,
        collection_name=COLLECTION_NAME,
        persist_directory=str(PERSIST_DIR)
    )

    # 分批器（簡單版）
    def batched(iterable, n):
        batch = []
        for x in iterable:
            batch.append(x)
            if len(batch) >= n:
                yield batch
                batch = []
        if batch:
            yield batch

    # 推薦每批 200（內容長度不同時也安全）
    total = 0
    for i, batch in enumerate(batched(all_documents, 200), start=1):
        vectorstore.add_documents(batch)
        # ⚠️ 新版 chroma 多為自動持久化；舊版才需要 persist。
        # 這裡做「相容性嘗試」，能叫就叫，不能叫就忽略（不會拋例外）。
        try:
            if hasattr(vectorstore, "persist") and callable(getattr(vectorstore, "persist")):
                vectorstore.persist()
            elif hasattr(vectorstore, "_client") and hasattr(vectorstore._client, "persist") and callable(getattr(vectorstore._client, "persist")):
                vectorstore._client.persist()
        except Exception:
            pass

        total += len(batch)
        print(f"[BUILD] 已加入批次 {i}，本批 {len(batch)} 筆，累計 {total} 筆")

    print(f"✅ 已重建向量庫：{PERSIST_DIR}/{COLLECTION_NAME}，共 {len(all_documents)} 筆 chunks")
    print("[DEBUG] df1 shape (ESG_1):", df1.shape)
    print("[DEBUG] df2 shape (ESG_2):", df2.shape)
    print("[DEBUG] df3 shape (NEWS):", df3.shape)
    print("[DEBUG] docs_esg_total:", len(docs_esg_1) + len(docs_esg_2))
    print("[DEBUG] docs_news:", len(docs_news))
