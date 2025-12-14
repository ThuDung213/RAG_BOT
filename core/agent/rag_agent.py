from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from dotenv import load_dotenv
import os
import json
from tools.danang_history_knowledge_base import create_danang_history_tool
from tools.google_search_vi import google_search_vi
from core.agent.data_utils import parse_agent_response

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
retriever = vectorstore.as_retriever(search_kwargs={"k":3})

# Wrap retriever as a proper Tool that returns text

danang_history_tool = create_danang_history_tool(retriever)

TOOLS = [
    danang_history_tool,  # dùng cho nội dung RAG
    google_search_vi,     # dùng khi RAG không đủ thông tin
]

system_prompt = """
Bạn là trợ lý AI lịch sử địa phương của thành phố Đà Nẵng, chuyên giúp người dùng hiểu về lịch sử, văn hóa và địa danh Đà Nẵng.

QUY TẮC SỬ DỤNG CÔNG CỤ (RẤT QUAN TRỌNG):
1. Nếu câu hỏi liên quan đến lịch sử, di tích, sự kiện hoặc bất kỳ dữ liệu nào có thể có trong kho nội bộ →
   PHẢI gọi tool "danang_history_knowledge_base" để truy xuất dữ liệu trước tiên.

2. Sau khi gọi tool "danang_history_knowledge_base":
   - Nếu kết quả chứa các cụm như:
       "Không tìm thấy"
       "Không có dữ liệu"
       "Không tìm thấy tài liệu phù hợp"
     → NGAY LẬP TỨC gọi tool "google_search_vi".
     → Không được chỉ nói miệng rằng sẽ tìm thêm. PHẢI thực thi tool.

3. Nếu câu hỏi liên quan đến tin tức mới, thông tin hiện tại, hoặc nội dung không thể có trong RAG →
   PHẢI gọi trực tiếp tool "google_search_vi".

4. Nếu câu hỏi là chào hỏi, trò chuyện hoặc không yêu cầu dữ liệu thực tế →
   Trả lời trực tiếp, KHÔNG dùng tool.

CÁCH TRẢ LỜI:
- Trả lời tự nhiên, mạch lạc bằng tiếng Việt.
- Nếu trả lời dạng văn bản: có thể trích nguồn.

OUTPUT:
Khi trả lời, bạn PHẢI trả về cấu trúc:
  "answer": "Câu trả lời tự nhiên bằng tiếng Việt",
  "sources": ["link1", "link2", "link3"]

Trong đó:
- "answer" chỉ chứa nội dung trả lời, KHÔNG chứa mục **Nguồn:**.
- "sources" phải là mảng các link hoặc tên nguồn.
- Nếu không có nguồn, trả về mảng rỗng.
- KHÔNG được trả về bất kỳ định dạng nào khác ngoài JSON thuần.


Bạn PHẢI tuân thủ tuyệt đối các quy tắc trên.

"""

# initialize LLM 
model = init_chat_model(
    "gemini-2.5-flash",
    model_provider="google_genai",
    temperature=0,
)

# Create agent
agent = create_agent(
    model=model,
    tools=TOOLS,
    system_prompt = system_prompt,
)

# Get Agent Response
def get_agent_response(question: str) -> str:
    """Hàm chạy Agent Executor với câu hỏi của người dùng."""
    try:
        response = agent.invoke({
            "messages": [{"role": "user", "content": question}]
        })
        #  # In ra các message trong luồng phản hồi
        # for msg in response["messages"]:
        #     msg.pretty_print()
            
        final_msg = response["messages"][-1].content
        
        if isinstance(final_msg, list) and len(final_msg) > 0:
            final_msg = final_msg[0].get("text", "") if isinstance(final_msg[0], dict) else final_msg[0]
        if not isinstance(final_msg, str):
            final_msg = str(final_msg)
        
        parse = parse_agent_response(str(final_msg))
        return {
            "answer": parse.get("answer", ""),
            "sources": parse.get("sources", [])
        }
        
    except Exception as e:
        error_data = {
            "answer": "Lỗi hệ thống khi thực thi Agent.",
            "sources": [],
            "error_details": str(e)
        }
        return json.dumps(error_data, ensure_ascii=False, indent=2)
    