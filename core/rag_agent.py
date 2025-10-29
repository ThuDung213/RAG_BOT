from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from dotenv import load_dotenv
import os

load_dotenv()

# --- Cấu hình DB đã lưu ---
persist_directory = 'chroma_db_for_agent_bge' 
embedding_model_name = "BAAI/bge-small-en-v1.5"
MODEL_NAME = "gemini-2.5-flash"

# Reload Embedding model
embedding_model = HuggingFaceEmbeddings(model_name=embedding_model_name)

# Load Vector Store
vectorstore = Chroma(
    persist_directory=persist_directory,
    embedding_function=embedding_model
)

#  Create Retriever vs Tools RAG
retriever = vectorstore.as_retriever(search_kwargs={"k":5})

# Wrap retriever as a proper Tool that returns text
@tool("danang_history_knowledge_base")
def danang_history_knowledge_base(query: str) -> str:
    """
    Sử dụng công cụ này ĐẶC BIỆT khi trả lời các câu hỏi về LỊCH SỬ ĐÀ NẴNG
    hoặc các thông tin có trong kho kiến thức nội bộ. Đầu vào phải là câu hỏi cụ thể.
    """
    docs = retriever.invoke(query)
    # ghép nội dung ngắn gọn để agent có thể suy luận
    formatted = []
    for i, d in enumerate(docs, start=1):
        src = d.metadata.get("source") or d.metadata.get("id") or f"doc_{i}"
        page = d.metadata.get("page")
        tag = f"{src}" + (f":p{page}" if page is not None else "")
        formatted.append(f"[{tag}]\n{d.page_content}")
    return "\n\n".join(formatted) if formatted else "Không tìm thấy tài liệu phù hợp."

TOOLS = [danang_history_knowledge_base]


# initialize LLM 
model = init_chat_model(
    "gemini-2.5-flash",
    model_provider="google_genai",
    temperature=0,
)

# Create agent
agent = create_agent(
    model=model,
    tools=[danang_history_knowledge_base],
)

# Get Agent Response
def get_agent_response(question: str) -> str:
    """Hàm chạy Agent Executor với câu hỏi của người dùng."""
    try:
        response = agent.invoke({
            "messages": [{"role": "user", "content": question}]
        })
         # In ra các message trong luồng phản hồi
        for msg in response["messages"]:
            msg.pretty_print()
            
        final_msg = response["messages"][-1].content if "messages" in response else None
        return final_msg
    except Exception as e:
        return f"Lỗi khi thực thi Agent: {e}"
    
if __name__ == "__main__":
    test_question = "Đà Nẵng được biết đến là gì trong lịch sử dân tộc?"
    response = get_agent_response(test_question)
    print("\n--- PHẢN HỒI AGENT ---")
    print(response)