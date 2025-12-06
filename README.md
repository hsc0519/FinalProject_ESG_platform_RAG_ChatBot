# ESG RAG ChatBot Project
### 🎥 System Demo

[![Watch the Demo Video](https://img.youtube.com/vi/XSENbbyN3uA/maxresdefault.jpg)](https://youtu.be/XSENbbyN3uA?t=4m34s)

> **Note:** The video narration is in Traditional Chinese. To save your time, the link above starts directly at the **Live Demo**. 
> You can also explore specific sections:
> * [**03:28** - Technical Implementation & Workflow](https://youtu.be/XSENbbyN3uA?t=3m28s) (Architecture explanation)
> * [**04:34** - Live System Demo](https://youtu.be/XSENbbyN3uA?t=4m34s) (Chatbot interaction showcase)
---

# 1. 專題背景與介紹 / Project Background

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

The diagram below illustrates the complete system architecture. My primary contributions are highlighted in **Yellow**, **Green (Bottom Right)**, and **Blue**, covering the core RAG engine, data processing pipeline, and API integration.

![Technical Implementation](./Technical%20Implementation.png)

> **Legend of Responsibility:**
> * 🟨 **Yellow Area:** Core RAG Chatbot Construction (The "Brain")
> * 🟩 **Green Area (Bottom Right):** Sustainability Report Data Pipeline (The "Knowledge Base")
> * 🟦 **Blue Area:** API Architecture & Design (The "Connectors")

---
### 2.1 ESG 報告爬蟲建置（Playwright + API） / ESG Report Crawlers

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

The following diagram illustrates the data flow within the RAG Chatbot system, covering data ingestion, vectorization, retrieval, and response generation.

![System Architecture](./Chatbot_DFD.jpg)

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
