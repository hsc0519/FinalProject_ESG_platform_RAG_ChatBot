# rag_query.py —— 查詢（OpenAI 版，含 Memory / Rewriter / MultiQuery / 漏斗過濾 / 友善引導 / 新聞URL）
import os
import re
import random
import hashlib
from typing import List, Tuple, Iterable, Optional

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from config import PERSIST_DIR, COLLECTION_NAME, EMBED_MODEL
from llm import chat_response

# -------------------------
# 讀取 API Key
# -------------------------
api_key = None
if os.path.exists("api_key.txt"):
    with open("api_key.txt", "r", encoding="utf-8") as f:
        api_key = f.read().strip()
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")
assert api_key, "找不到 OpenAI API Key，請建立 api_key.txt 或設 OPENAI_API_KEY 環境變數。"

# -------------------------
# Embeddings / DB
# -------------------------
embedding = OpenAIEmbeddings(model=EMBED_MODEL, api_key=api_key)
db = Chroma(
    persist_directory=str(PERSIST_DIR),
    embedding_function=embedding,
    collection_name=COLLECTION_NAME
)

# =========================
# 可調參數（召回穩定度↑）
# =========================
TOP_K = 5             # 每個子查詢一次取回的文件數
N_HISTORY = 15         # 回顧對話輪數，餵給重寫器
N_VARIANTS = 5        # Query Rewriter 產生同義/互補問法的數量
MIN_UNIQUE_DOCS = 1   # 低召回回退門檻
DEBUG = True          # 顯示除錯訊息

# =========================
# 公司清單（僅這 10 家）
# =========================
COMPANY_CODE_NAME = {
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
COMPANY_WHITELIST = set(COMPANY_CODE_NAME.values())

# 保留後綴規則（避免把一般名詞誤當公司）
COMPANY_SUFFIXES = ("公司", "科技", "電子", "電", "光", "鋼", "化", "金", "銀", "銀行", "控股", "集團")

# =========================
# 基本工具
# =========================
def _extract_years(text: str) -> list[int]:
    """從使用者輸入抓單一年或範圍（例 2021-2023 → [2021,2022,2023]）。"""
    years = set()
    for m in re.finditer(r"(20\d{2})(?:\s*[-~–至到]\s*(20\d{2}))?", text or ""):
        y1 = int(m.group(1))
        y2 = int(m.group(2)) if m.group(2) else None
        if 2000 <= y1 <= 2099:
            if y2 and y1 <= y2 <= 2099 and y2 >= y1:
                years.update(range(y1, y2 + 1))
            else:
                years.add(y1)
    return sorted(years)

def _sha1(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8", errors="ignore")).hexdigest()

def _doc_key(d) -> tuple:
    """去重所用的唯一鍵：優先 chunk_id，否則 source+內容哈希。"""
    meta = getattr(d, "metadata", {}) or {}
    cid = meta.get("chunk_id")
    if cid:
        return (meta.get("source", "unknown"), cid)
    return (meta.get("source", "unknown"), _sha1(d.page_content))

def _norm_where(flt: Optional[dict]) -> Optional[dict]:
    """
    將「多鍵同層」轉為 Chroma 期望的 where 形狀：
    - None / {} -> None（不帶過濾）
    - 已含 $and/$or/$not -> 視為已是運算子格式
    - 其他多鍵 -> {"$and":[{k1:v1},{k2:v2},...]}
    """
    if not flt:
        return None
    if any(op in flt for op in ("$and", "$or", "$not")):
        return flt
    items = [{k: v} for k, v in flt.items()]
    return items[0] if len(items) == 1 else {"$and": items}

# --- 檢索模式過濾 ---
def build_filter(mode: str) -> Optional[dict]:
    """mode: 'esg' -> 只查 ESG；'news' -> 只查新聞；'all' -> 不過濾"""
    m = (mode or "all").lower()
    if m == "esg":
        return {"doc_type": "esg"}
    if m == "news":
        return {"doc_type": "news"}
    return None

# --- 引導用的 mode 規範：任何非 esg/news（含 None/'all'）一律視為 esg ---
def _canon_mode(x: Optional[str]) -> str:
    m = (x or "esg").lower()
    return m if m in {"esg", "news"} else "esg"

# -------- Memory：把最近 n 輪對話接起來，給重寫器用 --------
def build_history_context(history: Optional[List[Tuple[str, str]]], n: int = N_HISTORY) -> str:
    if not history:
        return ""
    pairs = history[-n:]
    return "\n".join([f"使用者：{u}\n助理：{a}" for u, a in pairs])

# -------- 從輸入抽公司線索（公司代號 / 中文公司名）--------
def _extract_company_hints(text: str) -> list[str]:
    """抓 4 碼代號與疑似中文公司名（限定在你的 10 家），避免把指標詞誤判為公司。"""
    if not text:
        return []
    hints = set()

    # 4 碼公司代號（僅你清單內）
    for m in re.finditer(r"\b(\d{4})\b", text):
        code = m.group(1)
        if code in COMPANY_CODE_NAME:
            hints.add(code)

    # 候選中文詞（僅白名單內）
    for m in re.finditer(r"[\u4e00-\u9fff]{2,12}", text):
        w = m.group(0)
        if (w in COMPANY_WHITELIST) or w.endswith(COMPANY_SUFFIXES):
            if w in COMPANY_WHITELIST:  # 僅收你的 10 家
                hints.add(w)

    return list(hints)

def build_filter_from_query(mode: str, user_query: str) -> dict:
    """
    依使用者輸入建立 metadata 漏斗：
    - 若含 4 碼代號（限你清單） → company_code 精確過濾
    - 若含中文公司名（限你清單） → company_name 精確過濾
    - news 模式：解析 正面/負面/中立/pos/neg/neu → sentiment 精確過濾
    """
    f: dict = {}
    hints = _extract_company_hints(user_query or "")

    # 代號優先
    codes = [h for h in hints if re.fullmatch(r"\d{4}", h)]
    if codes:
        f["company_code"] = codes[0] if len(codes) == 1 else {"$in": codes}
    else:
        cnames = [h for h in hints if h in COMPANY_WHITELIST]
        if cnames:
            f["company_name"] = cnames[0] if len(cnames) == 1 else {"$in": cnames}

    if (mode or "").lower() == "news":
        s = (user_query or "").lower()
        if any(k in s for k in ["正面", "positive", "pos"]):
            f["sentiment"] = "正面"
        elif any(k in s for k in ["負面", "negative", "neg"]):
            f["sentiment"] = "負面"
        elif any(k in s for k in ["中立", "neutral", "neu"]):
            f["sentiment"] = "中立"

    return f

# -------- 相關性候選（引導用；不使用熱門度，不產生遞迴） --------
def _related_meta_values(user_input: str, mode_hint: str = "esg",
                         n_variants: int = 2, k_per_query: int = 20, max_each: int = 10) -> dict:
    """
    以「使用者當下輸入」為中心，做小量相似度檢索並萃取 metadata 候選。
    不做熱門度統計；依檢索排名先後收集，去重即可。
    ※ 重要：呼叫 rewrite_query(..., allow_guidance=False) 以避免遞迴觸發引導。
    """
    m = _canon_mode(mode_hint)
    where = {"doc_type": m}

    # 1) 用當下輸入為核心，產生輕量查詢（引導階段 history=None）
    base_q = (user_input or "").strip()
    if not base_q:
        base_q = "ESG" if m == "esg" else "新聞"

    # 輕量 rewrite（禁用引導）與少量變體
    try:
        q_re = rewrite_query(base_q, history=None, mode_hint=m, allow_guidance=False)
    except Exception:
        q_re = base_q

    queries = [q_re]
    try:
        variants = generate_alternative_queries(q_re, n_variants)
        queries = [q_re] + [v for v in variants if v != q_re]
    except Exception:
        pass

    # 2) 依檢索排名順序蒐集 metadata 候選（維持先出現先保留）
    def _ordered_add(lst, seen_set, val):
        if val is None:
            return
        if isinstance(val, str):
            val = val.strip()
            if not val:
                return
        if val not in seen_set:
            lst.append(val)
            seen_set.add(val)

    keys_esg  = ["company_name", "company_code", "indicator", "sub_field", "category", "year"]
    keys_news = ["company_name", "company_code", "category", "sentiment", "keyword"]
    keys = keys_news if m == "news" else keys_esg

    out = {k: [] for k in keys}
    seen = {k: set() for k in keys}

    for q in queries:
        docs = _search(q, k=k_per_query, flt=where)
        for d in docs:
            md = getattr(d, "metadata", {}) or {}
            for k in keys:
                v = md.get(k)
                # 僅收你清單內的公司
                if k == "company_name" and v and v not in COMPANY_WHITELIST:
                    continue
                if k == "company_code" and v and v not in COMPANY_CODE_NAME:
                    continue
                if k == "year" and not isinstance(v, int):
                    continue
                _ordered_add(out[k], seen[k], v)
        if all(len(out[k]) >= max_each for k in keys):
            break

    return {k: out[k][:max_each] for k in keys}

# -------- 友善引導（只用 mode_hint：影響語氣/模板與取樣） --------
def _generate_guidance_reply(user_input: str, mode_hint: str = None) -> str:
    """
    產生引導訊息（繁中、簡短、有例句）。
    ※ 僅用 mode_hint 來決定引導的「語氣/模板」與取樣過濾；不影響主檢索邏輯。
    """
    m = _canon_mode(mode_hint)
    mode_line = "目前預設在【ESG 指標】模式。" if m == "esg" else "目前預設在【新聞】模式。"

    # 依當前輸入的相關性候選（不做熱門排序；不會遞迴）
    pop = _related_meta_values(user_input, mode_hint=m, n_variants=2, k_per_query=20, max_each=8)

    examples = []
    if m == "esg":
        companies = _pick_some(pop.get("company_name") or pop.get("company_code") or [], 2)
        subs      = _pick_some(pop.get("sub_field") or pop.get("indicator") or [], 2)
        years     = _pick_some(pop.get("year") or [], 3)
        if companies and subs and years:
            examples.append(f"{companies[0]} {years[0]} {subs[0]}")
            examples.append(f"{companies[0]} {min(years)}-{max(years)} {subs[-1]}")
            if len(companies) > 1:
                examples.append(f"{companies[1]} {years[-1]} {subs[0]}")
    else:
        companies = _pick_some(pop.get("company_name") or pop.get("company_code") or [], 2)
        cats  = _pick_some(pop.get("category") or [], 1)
        sents = _pick_some(pop.get("sentiment") or [], 1)
        kw    = _pick_some(pop.get("keyword") or [], 1)
        if companies:
            examples.append(f"{companies[0]} {cats[0] if cats else 'ESG'} 新聞")
            if sents:
                examples.append(f"{companies[0]} {sents[0]} 新聞")
            if len(companies) > 1 and kw:
                examples.append(f"{companies[1]} {kw[0]} 新聞")

    prompt = f"""
使用者剛輸入：「{(user_input or '').strip()}」
引導使用者繼續查 ESG/新聞資料。
說明需要哪些關鍵資訊（公司/代號、年份、指標或新聞）。
了解使用者問題，給予回覆，
不要提供任何數字或事實內容，不要假裝已找到資料。
語氣自然，不要制式公文口吻。

{mode_line}

（以下是根據你輸入所檢索到的相關候選詞，請自行挑選合理組合，不要逐條照抄）
- 公司/代號：{', '.join(_pick_some(pop.get('company_name') or pop.get('company_code') or [], 6)) or '（暫無）'}
- 指標/欄位（ESG）：{', '.join(_pick_some((pop.get('sub_field') or []) + (pop.get('indicator') or []), 6)) or '（暫無）'}
- 年份（ESG）：{', '.join(map(str, _pick_some(pop.get('year') or [], 6))) or '（暫無）'}
- 新聞分類/情緒（News）：{', '.join(_pick_some((pop.get('category') or []) + (pop.get('sentiment') or []), 6)) or '（暫無）'}

{chr(10).join('• ' + ex for ex in examples)}
"""
    return chat_response(prompt, model="gpt-4o-mini")

def _pick_some(lst, n):
    lst = [x for x in lst if x]
    if not lst:
        return []
    if len(lst) <= n:
        return lst
    return random.sample(lst, n)

# -------- Query Rewriter：強化召回 + 模糊引導 --------
def rewrite_query(
    user_input: str,
    history: Optional[List[Tuple[str, str]]],
    mode_hint: str = None,
    allow_guidance: bool = True,   # ★ 新增：可關閉引導（避免遞迴）
) -> str:
    ctx = build_history_context(history)
    base = (user_input or "").strip().lower()

    # 模糊/探索型觸發引導（僅 allow_guidance=True 時才生效）
    vague_phrases = [
        "可以查", "能查", "查什麼", "有哪些", "有什麼", "能問", "幫我查", "幫我看", "您好",
        "怎麼查", "哪些資料", "我想知道", "介紹一下", "怎麼用", "怎麼開始", "嗨", "你好", "哈囉"
    ]
    if allow_guidance and (any(p in base for p in vague_phrases) or base in {"", "？", "help", "help me", "hi", "嗨"}):
        if DEBUG:
            print("[REWRITE-GUIDE] Triggered guidance mode")
        guidance = _generate_guidance_reply(user_input, mode_hint=_canon_mode(mode_hint))
        return "__GUIDANCE__" + guidance

    # 正常改寫流程（公司清單改成僅你這 10 家）
    prompt = f"""
你是查詢重寫器，目標是提升 ESG 檢索的召回率。
請把使用者問題改寫成【單行關鍵詞查詢】。
規則：
- 若提到公司請修改成最相近的，"台積電", "鴻海", "聯發科", "富邦金", "中華電", "廣達", "台達電", "國泰金", "中信金", "日月光投控"。
- 若有年份範圍（如 2021-2024），請展開為每一年（2021 2022 2023 2024）。
- 對 ESG 指標使用常見同義詞。
- 只輸出一行關鍵詞串，詞與詞之間用空格分隔，不要加標點或解釋。

【對話脈絡】
{ctx}

【使用者當前問題】
{user_input}

只輸出一行查詢關鍵詞。
"""
    rewritten = chat_response(prompt).strip()
    rewritten = " ".join(rewritten.split())  # 壓縮多餘空白
    if DEBUG:
        print(f"[REWRITE] {rewritten}")
    return rewritten or user_input.strip()

# -------- MultiQuery：多角度檢索問法 --------
def generate_alternative_queries(query: str, n_variants: int = N_VARIANTS) -> List[str]:
    if n_variants <= 0:
        return [query]
    prompt = (
        f"請針對以下查詢產生 {n_variants} 個互補或同義的檢索問法（每行一個、勿編號）：\n{query}\n\n"
        "變化方向：同義詞、欄位別名、補充公司/年份關鍵詞、細化指標名。"
    )
    raw = chat_response(prompt)
    lines = [ln.strip() for ln in raw.splitlines()]
    cleaned = []
    for ln in lines:
        ln = ln.lstrip(" ・-•\t0123456789.").strip().strip('"\'')
        ln = " ".join(ln.split())
        if len(ln) < 2:
            continue
        cleaned.append(ln)

    seen, uniq = set(), []
    for q in [query] + cleaned:
        key = q.casefold()
        if key not in seen:
            uniq.append(q)
            seen.add(key)

    uniq = [uniq[0]] + uniq[1:n_variants+1]
    if DEBUG:
        print(f"[MULTI-QUERY] {uniq}")
    return uniq

# -------- 去重：以 chunk_id 或內容哈希為唯一鍵 --------
def unique_docs(docs: Iterable) -> List:
    seen, out = set(), []
    for d in docs:
        key = _doc_key(d)
        if key not in seen:
            out.append(d)
            seen.add(key)
    return out

# -------- 安全檢索（包一層，轉正確 where） --------
def _search(q: str, k: int, flt: Optional[dict]):
    try:
        if not q or not q.strip() or k <= 0:
            return []
        wf = _norm_where(flt)
        if not wf:
            return db.similarity_search(q, k=k)
        return db.similarity_search(q, k=k, filter=wf)
    except Exception as e:
        if DEBUG:
            print("[SEARCH-ERROR]", e)
        return []

# -------- 主查詢 --------
def get_answer(
    query: str,
    history: Optional[List[Tuple[str, str]]] = None,
    return_sources: bool = True,
    k: int = TOP_K,
    mode: str = "all",   # 'esg' / 'news' / 'all'
    suggest_on_empty: bool = True,       # 找不到時給友善建議
):
    # 0) 基礎：mode 過濾 & 標籤
    flt_mode = build_filter(mode) or {}
    label = {"esg": "ESG 數據", "news": "新聞資訊"}.get((mode or "all").lower(), "全部資料")

    # 1) Rewrite（提高召回）—— 引導語氣使用 mode_hint（規範後）
    q_re = rewrite_query(query, history, mode_hint=_canon_mode(mode), allow_guidance=True)

    # 若 rewrite 回「引導模式」，直接回覆 guidance，跳過檢索
    if q_re.startswith("__GUIDANCE__"):
        guidance = q_re[len("__GUIDANCE__"):]
        return (guidance, []) if return_sources else guidance

    # 2) MultiQuery 變體
    queries = generate_alternative_queries(q_re, N_VARIANTS)

    # 2.1 metadata 漏斗：依輸入抽公司/情緒條件
    flt_from_query = build_filter_from_query(mode, query)

    # 2.2 若為 ESG → 從使用者原文抽年份，做「硬過濾」
    years = _extract_years(query) if (mode or "").lower() == "esg" else []
    flt_combined = {**flt_mode, **flt_from_query}
    if years:
        flt_combined["year"] = {"$in": years}

    # 2.3 檢索（帶過濾器）
    merged = []
    for q in queries:
        merged.extend(_search(q, k=k, flt=flt_combined))
    docs = unique_docs(merged)

    # 2.4 ESG 且有指定年份 → 檢查覆蓋，缺的逐年補查
    if years:
        hit_years = {d.metadata.get("year") for d in docs if d.metadata.get("year") is not None}
        missing = [y for y in years if y not in hit_years]
        if DEBUG:
            print(f"[YEAR CHECK] asked={years} hit={sorted(hit_years)} miss={missing}")
        for y in missing:
            flt_y = dict(flt_combined)
            flt_y["year"] = y
            docs.extend(_search(q_re, k=max(3, k // 2), flt=flt_y))
        docs = unique_docs(docs)

    # 2.5 低召回保護
    if len(docs) < MIN_UNIQUE_DOCS and q_re != query:
        if DEBUG:
            print("[BACKOFF] 召回過低，改用原始查詢再補一次")
        docs.extend(_search(query, k=k, flt=flt_combined))
        docs = unique_docs(docs)

    # 3) 無命中 → 友善引導
    if not docs:
        if suggest_on_empty:
            prompt = f"""
            使用者剛輸入：
            「{query}」

            但在向量資料庫中沒有找到任何相關內容。
            請你用【繁體中文】自然地引導他繼續對話。
            請：
            1. 先親切說明「沒找到」的可能原因（簡短、自然）。
            2. 問他想查 ESG 指標或新聞？哪家公司（名稱或代號）？哪一年或年份範圍？
            3. 給 2–3 句可直接複製的查詢建議。
            語氣溫和自然，不要太制式。
            """
            guidance = chat_response(prompt)
            return (guidance, []) if return_sources else guidance
        else:
            msg = "目前資料庫中無相關資訊。"
            return (msg, []) if return_sources else msg

    # 4) 組合上下文
    context = "\n---\n".join([d.page_content for d in docs]) or "(無內容)"

    # 4.1 Debug：來源/年份/片段 id
    if DEBUG:
        debug_srcs = [
            (
                d.metadata.get("source"),
                d.metadata.get("company_code"),
                d.metadata.get("company_name"),
                d.metadata.get("year"),
                d.metadata.get("chunk_id", _sha1(d.page_content)[:8])
            )
            for d in docs
        ]
        print("[HITS]", len(docs), debug_srcs)

    # 4.2 新聞模式：準備「來源清單」（含 URL）
    news_refs = ""
    if (mode or "").lower() == "news":
        rows = []
        for d in docs:
            m = d.metadata or {}
            title = m.get("title") or ""
            url = m.get("url") or ""
            company = m.get("company_name") or ""
            senti = m.get("sentiment") or ""
            if title or url:
                rows.append(f"- {title}｜{company}｜{senti}｜{url}")
        if rows:
            news_refs = "【新聞來源清單】\n" + "\n".join(rows) + "\n\n"

    # 5) 產生回答（兩種模式：ESG / NEWS）
    if (mode or "").lower() == "news":
        prompt = (
        "你是一位 ESG 文章助理。請只根據下列檢索內容作答。\n" 
        "回覆規則：\n"
        "務必做好排版、重點加粗、換行等等\n" 
        "列點 2 則重點新聞：其他指標請列在文末「次相關可查詢」。\n" 
        "每一條用『標題（若有公司名與情緒可附上）』並附上 URL，不要顯示全部網址，用markdown\n" 
        "依照內容給予1-2簡短的介紹\n" "新聞後，提供簡介總結2-4句話重點（只用已檢索到的 content）。\n" 
        
        f"{news_refs}" 
        f"【檢索到的內容】\n{context}\n\n" 
        f"【使用者問題】\n{query}\n"
    )
      
    else:
        prompt = (
        "你是一位 ESG 數據整理助理，請僅根據下列【檢索到的內容】輸出，禁止臆測或引用外部資料。\n"
        f"資料來源：{label}\n\n"
        "【輸出目標】\n"
        "以「公司主題 → 指標 → 年份值」的格式輸出，但**清單僅限 1–2 個「最相關關鍵字」**；其他指標請列在文末「次相關可查詢」。\n"
        "判斷相關性優先順序：\n"
        "1) 使用者問題中明確提到的指標名稱（必選）\n"
        "2) 與使用者關鍵詞最接近、且在內容中出現頻率較高者\n"
        "3) 最近年度有數據者\n\n"
        "【輸出格式（嚴禁使用表格或程式碼區塊）】\n"
        " <公司名稱> 數據 \n"
        " **<指標名稱> (<原單位>)**\n"
        "<年份>: <數值>（原單位：<原單位>）\n"
        "<年份>: <數值>（原單位：<原單位>）\n"
        "（每個指標獨立成區塊，年份由舊到新；主清單最多 2 個指標）\n"
        "\n"
        " **指標說明**：\n"
        "• 針對主清單中的每個指標，各以 1–2 句白話說明其意義/衡量方向。\n"
        "\n"
        " **總結與分析**：\n"
        "• 以 1–3 句總結主清單指標的趨勢（上升/下降/波動）、最高/最低年份與數值、近一年相對前一年的變化(% )；資料不足即明說。\n"
        "\n"
        " **次相關可查詢**：\n"
        "• 列出最多 5 個與問題次相關但未列入主清單的「指標名稱」（只列名稱，不要附年份與數值）。\n"
        "\n"
        "【排版規則】\n"
        "1) 若單位為「仟元」，請自動換算為「元」並加上千分位（例：3,633,000）。\n"
        "2) 其他單位（噸CO2e、kWh、人、百分比等）保留原單位；欄位文字若已帶單位則沿用。\n"
        "3) 年份用阿拉伯數字，依時間由舊到新；缺值可略過或寫「該項數值未提供」。\n"
        "4) 僅當使用者問題沒指名指標時，才依規則自動挑選最相關 1–2 個；若使用者點名多個指標，請以使用者指定為主（可超過 2 個）。\n"
        "5) 重點標題、指標一定用粗體呈現，與資料間間隔一行\n"
        "\n"
        f"【檢索到的內容】\n{context}\n\n"
        f"【使用者問題】\n{query}\n"
        )

    answer = chat_response(prompt)

    # 6) 回傳結果與來源
    if not return_sources:
        return answer
    sources = list({d.metadata.get("source", "未知來源") for d in docs})
    return answer, sources
