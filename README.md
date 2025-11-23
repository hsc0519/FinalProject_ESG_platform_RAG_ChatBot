# ESG RAG ChatBot Project

This project builds a simple end-to-end ESG information system including:

- **Scraper** — collects ESG report data from TWSE GenPlus using Playwright (2021–2022 HTML tables) and official APIs (2023–2024), performing normalization, numeric extraction, and long/wide-format CSV/JSON generation.  
  Sentiment- and topic-tagged data were incorporated during early experimentation to enrich retrieval but are not included in the repository.

- **RAG_ChatBot** — a complete retrieval-augmented generation backend using (1) scraped ESG datasets, (2) classified news CSV files, and (3) metadata-enhanced vector search.  
  It integrates query rewriting, multi-query retrieval, metadata-aware filtering, and ChromaDB semantic search, and exposes the following FastAPI inference endpoints:  
  - `POST /query` — RAG answering (ESG / News / All modes)  
  - `POST /title` — auto-generate short conversation titles  
  - `POST /summarize` — multi-conversation summarization  
  - `GET /health` — health check endpoint

- **API** — provides company list, numeric ESG field lookup, and structured ESG search (filters for code, name, year, category, keyword).  
  This API is primarily designed for the front-end ESG data dashboard and loads the preprocessed numeric dataset `all number data.json` generated from the scraper, enabling fast and clean access to structured ESG data.

- **RAG merge** — combines the ChatBot endpoints (`/query`, `/title`, `/summarize`, `/health`) and the structured ESG Data API endpoints (`/companies`, `/fields`, `/search`) into a single FastAPI service.  
  This merged version uses the same RAG backend but loads a compact preprocessed JSON dataset (`all number data.json`) instead of the full CSV files.

This repository contains only the source code.  
(API keys and vector database files are excluded.)


