# app.py
import gradio as gr
from rag_query import get_answer

def answer_question(user_input, history):
    # 1) 防呆：history 可能是 None（第一次呼叫）
    history = history or []

    # 2) 防呆：空輸入就不查
    if not str(user_input).strip():
        # 回傳原 history，不改動；來源欄位給提示
        return history, "（請輸入要查詢的問題）"

    # 3) RAG 問答（會用到歷史做查詢重寫）
    answer, sources = get_answer(user_input, history=history, return_sources=True)

    # 4) 更新對話
    history.append((user_input, answer))

    # 5) 顯示來源（去重後）
    sources_display = "\n".join(sorted({f"📂 來源：{src}" for src in sources})) if sources else "(未提供來源)"
    return history, sources_display

with gr.Blocks(title="ESG資訊") as demo:
    gr.Markdown("""
    # 📚 ES機難雜症
    ### ESG RAG 對話機器人（支援上下文記憶與查詢重寫）
    """)

    with gr.Row():
        with gr.Column(scale=1):
            chatbot = gr.Chatbot(label="問答對話區")
            sources_box = gr.Textbox(label="來源檔案資訊", interactive=False)

            with gr.Row():
                user_input = gr.Textbox(
                    placeholder="請輸入 ESG 數據或資訊查詢，如：台積電 2024 範疇一排放量",
                    label="輸入問題",
                    lines=2
                )
                send_btn = gr.Button("🔍 送出問題")

            # 點擊送出
            send_btn.click(
                fn=answer_question,
                inputs=[user_input, chatbot],
                outputs=[chatbot, sources_box]
            ).then(  # 清空輸入框（UX 友善）
                fn=lambda: "",
                inputs=[],
                outputs=[user_input]
            )

            # Enter 送出
            user_input.submit(
                fn=answer_question,
                inputs=[user_input, chatbot],
                outputs=[chatbot, sources_box]
            ).then(
                fn=lambda: "",
                inputs=[],
                outputs=[user_input]
            )

demo.launch()
