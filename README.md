# ESG RAG ChatBot Project

---

# 1. 專題背景與介紹 / Project Background

這是我在大學階段完成的畢業專題，主題為 **ESG（環境、社會、治理）資訊整合平台**。  
主要目的是解決 ESG 資訊分散、格式不一致與查詢不便的問題，例如：

- ESG 報告格式差異大、難以比較  
- 數值欄位分散、缺乏統一標準  
- 新聞與 ESG 報告內容無法跨來源整合  
- 使用者難以以自然語言查詢 ESG 數據  

本系統整合多種 ESG 相關資訊來源，包括：

- **ESG 報表資料（2021–2024）**  
- **新聞語意分析：**  
  - 情緒分類 → 正面／中立／負面  
  - 主題分類 → 一般新聞／科普文章／綠色金融服務  
- **公司歷年 ESG 評分與趨勢視覺化**  
- **結構化 ESG 指標（ESG 數據儀表板）**  
- **RAG（Retrieval-Augmented Generation）語意檢索**  
- **ChromaDB 向量資料庫**  
- **FastAPI ChatBot API ＆ Data API ＆ News API**

最終形成一個結合 **查詢、分析、視覺化與互動式對話** 的 ESG 資訊整合平台。

This project is an undergraduate capstone focused on building an **integrated ESG information platform** to address common issues in ESG report usage:

- Inconsistent formatting across sustainability reports  
- Numeric metrics scattered and unstandardized  
- No cross-source search between news & sustainability reports  
- Users cannot query ESG information using natural language  

The system integrates multiple ESG-related sources:

- **ESG sustainability reports (2021–2024)**  
- **News semantic analysis:**  
  - Sentiment classification → positive / neutral / negative  
  - Topic classification → general news / science articles / green financial services    
- **Historical ESG score visualization**  
- **Structured ESG metrics dashboard**  
- **RAG-based semantic search**  
- **ChromaDB vector database**  
- **FastAPI-based ChatBot API & ESG Data API ＆ News API**

Together, the platform provides **interactive querying, analysis, visualization, and conversational ESG understanding**.

---

# 2. 系統最終成果與分工 / Team Contributions

本專題最終整合為四大核心功能：

- **公司資訊儀表板（Dashboard） / ESG Dashboard**  
- **RAG 聊天機器人（ChatBot） / RAG-based ChatBot**  
- **文章瀏覽（Article Explorer） / Article Explorer**  
- **首頁推薦與探索（Recommendation / Discovery） / Recommendation & Discovery Page**

---

## 我負責的部分（後端核心架構 & ESG 資料整合） / My Contributions (Backend Core Architecture & ESG Data Integration)

### 2.1 ESG 報告爬蟲建置（Playwright + API） / ESG Report Crawlers

使用 Playwright 擷取 2021–2022 年 HTML 版本 ESG 報表，並透過官方 TWSE API 擷取 2023–2024 年資料。
負責欄位正規化、數值抽取、寬表/長表轉換與跨年度欄位對齊，使資料可直接用於向量化、語意檢索與 ESG 儀表板顯示。

Developed automated pipelines for collecting ESG report data using Playwright (2021–2022 HTML tables) and TWSE official APIs (2023–2024).
Performed normalization, numeric extraction, long/wide formatting, and cross-year validation to support metadata-enriched semantic retrieval and dashboard integration.

---

### 2.2 RAG 聊天機器人後端架構 / RAG ChatBot Backend

Designed the complete RAG backend pipeline, including:  
- **Query rewriting** to reformulate user queries into retrieval-friendly versions  
- **Multi-query retrieval** to increase semantic coverage
- **Intent-guided filtering** that activates guided mode for ambiguous queries
- **Metadata filtering** based on company, year, category, and source  
- **Guided mode triggering (intent detection)**:  
  Automatically analyzes whether a user query is ambiguous and switches to guided mode when needed  
- **Structured generation prompt** to enforce output formatting, citation rules, table rendering, and anti-hallucination logic  
- **Three retrieval modes (All / Data / News)** supporting differentiated retrieval/generation flows and enabling multi-document synthesis across ESG metrics and classified news.

---

### 2.3 向量資料庫建置（ChromaDB） / Vector Database Construction (ChromaDB)

將 ESG 報告與新聞情緒／主題分類整合為 metadata-enriched embeddings，寫入 ChromaDB，形成含公司代碼、年份、類別與來源的語意向量資料庫。  
Built a metadata-enriched vector database integrating ESG report content and classified news (sentiment + topic labels), enriched with metadata such as company code, year, category, and source to support semantic retrieval.

---

### 2.4 ESG Data API 設計 / ESG Data API Development

Developed the structured ESG Data API endpoints:  
- `GET /companies` — company list  
- `GET /fields` — numeric ESG fields for a given company/year  
- `GET /search` — keyword-based ESG metric search with filters  

Used by both the dashboard and the RAG system, enabling hybrid deterministic lookup + LLM reasoning.

---

### 2.5 三種檢索模式（All / Data / News） / Three Retrieval Modes

- **All mode**: retrieve both ESG reports and news  
- **Data mode**: ESG-numeric-only retrieval  
- **News mode**: news-only semantic retrieval  

---

### 2.6 FastAPI 後端整合 / FastAPI Backend Integration

負責所有後端 API 的架構設計、路由整合、CORS 設定、測試與除錯。  
Responsible for the entire FastAPI backend architecture, routing, API integration, CORS, testing, and debugging.

**RAG ChatBot Endpoints**
- `POST /query` — RAG answering  
- `POST /title` — conversation title generation  
- `POST /summarize` — multi-dialog summarization  
- `GET /health` — health check  

**ESG Data Endpoints**
- `GET /companies`  
- `GET /fields`  
- `GET /search`

---

## 組員負責的部分（新聞資料、分類與前端） / Teammates' Contributions (News Pipeline & Frontend)

### 2.7 新聞資料與前端模組 / News & Frontend Modules

- 新聞資料爬蟲與前處理（ESG 新聞、綠色服務文章、一般新聞）  
- 新聞情緒與主題分類模型（正/中/負；一般／科普／綠色服務），產生標記 CSV  
- 相似度搜尋內文查詢（使用者貼上文章，找出語意相近新聞）  
- 前端 UI/UX 與 ESG 儀表板：
  - ESG 數據儀表板（結構化 ESG 指標）  
  - 公司新聞情緒分布圖  
  - 公司歷年 ESG 評分趨勢圖  
  - 聊天介面（含模式切換與資料呈現）  
  - 首頁推薦、熱門新聞、文字雲探索  
  
- News crawling and preprocessing (ESG news, green-service content, general news)  
- News sentiment & topic classification models (positive/neutral/negative; general/science/green-service), generating labeled CSV files  
- Semantic similarity search on the frontend (users paste an article and retrieve similar news)  
- Frontend UI/UX and ESG dashboard:
  - Structured ESG metric dashboards  
  - Company news sentiment visualization  
  - Multi-year ESG score trend charts  
  - Chat interface with mode selection and answer rendering  
  - Home recommendation page, trending news, and wordcloud exploration  

---

# 3. My Technical Overview

This project builds a complete ESG information system composed of scraping pipelines, structured ESG APIs, a vector-based RAG chatbot, and a unified FastAPI backend.

## Scraper
Collects ESG report data from TWSE GenPlus using Playwright (2021–2022 HTML tables) and official APIs (2023–2024), performing normalization, numeric extraction, and long/wide-format CSV/JSON generation.  
Sentiment- and topic-tagged data were incorporated during early experimentation but are not included in the repository.

## RAG_ChatBot
A complete retrieval-augmented generation backend using:

1. Scraped ESG datasets  
2. Classified news CSV files  
3. Metadata-enhanced vector search  

Features include query rewriting, multi-query retrieval, metadata filtering, and ChromaDB semantic search.

**FastAPI Endpoints:**
- `POST /query` — RAG answering (ESG / News / All modes)  
- `POST /title` — auto-generate short conversation titles  
- `POST /summarize` — multi-conversation summarization  
- `GET /health` — health check endpoint  

## API
Provides:

- Company list  
- Numeric ESG field lookup  
- Structured ESG search (filters: code, name, year, category, keyword)

This API uses the preprocessed dataset `all number data.json` generated from the scraper and is primarily used by the front-end dashboard.

## RAG Merge
Combines ChatBot endpoints (`/query`, `/title`, `/summarize`, `/health`) and structured ESG API endpoints (`/companies`, `/fields`, `/search`) into a single FastAPI service.  
This merged version loads a compact JSON dataset instead of full CSV files.

---

# 4. My RAG Chatbot Data Flow Architecture

![System Architecture](./Chatbot DFD.jpg)

---

# 5. Repository Structure

```bash
ESG_Platform/                               # Overall project (team project)
│
├── ESG_CHATBOT_PROJECT/                    # My responsibility (backend + RAG + API)
│   │
│   ├── API/
│   │   ├── api.py
│   │   └── test_ngrok_api.html
│   │
│   ├── RAG_merge/
│   │   ├── api_server.py
│   │   ├── api.py
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── index.html
│   │   ├── llm.py
│   │   ├── rag_query.py
│   │   └── rag_setup.py
│   │
│   ├── RAG_ChatBot/
│   │   ├── api_server.py
│   │   ├── app.py
│   │   ├── config.py
│   │   ├── index.html
│   │   ├── llm.py
│   │   ├── rag_query.py
│   │   └── rag_setup.py
│   │
│   ├── Scraper/
│   │   ├── esg_scraper_all_2021_2022.py
│   │   ├── esg_scraper_all_2023_2024.py
│   │   ├── esg_scraper_only_number_2021_2022.py
│   │   └── esg_scraper_only_number_2023_2024.py
│   │
│   └── README.md
│
├── frontend/                               # Teammate responsibility
├── Wordcloud/                              # Teammate responsibility
├── NewsData/                               # Teammate responsibility
│   ├── NewsScraper/
│   ├── NewsTopicClassify/
│   ├── NewsSentimentClassify/
│   └── api.py/
│
└── (other frontend assets)
