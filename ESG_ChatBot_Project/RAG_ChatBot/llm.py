# llm.py —— OpenAI 官方 API 版
from openai import OpenAI
import os

# 讀取 API Key：api_key.txt（單行）或環境變數 OPENAI_API_KEY
api_key = None
if os.path.exists("api_key.txt"):
    with open("api_key.txt", "r", encoding="utf-8") as f:
        api_key = f.read().strip()
if not api_key:
    api_key = os.getenv("OPENAI_API_KEY")
assert api_key, "請建立 api_key.txt 或設置環境變數 OPENAI_API_KEY"

client = OpenAI(api_key=api_key)

def chat_response(prompt: str, model: str = "gpt-4o-mini", system_prompt: str = None) -> str:
    """統一的聊天呼叫，供 rag_query.py / app.py 使用"""
    system_prompt = system_prompt or "你是一個有幫助的助理，請務必僅根據提供的內容作答，簡潔、準確。"

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3,
        max_tokens=1000,
    )
    return resp.choices[0].message.content.strip()
