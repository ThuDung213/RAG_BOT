from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain.tools import tool
from dotenv import load_dotenv
import os
import json
import time
import random
import re
import threading
from tools.danang_history_knowledge_base import create_danang_history_tool
from tools.google_search_vi import google_search_vi
from core.agent.data_utils import parse_agent_response

load_dotenv()

# --- Cấu hình DB đã lưu ---
persist_directory = 'chroma_db_for_agent_bge' 
embedding_model_name = "BAAI/bge-small-en-v1.5"
MODEL_NAME = "gemini-2.5-flash-lite"

# Reload Embedding model
embedding_model = HuggingFaceEmbeddings(model_name=embedding_model_name)

# Load Vector Store (ChromaDB)
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

5.Nếu câu hỏi KHÔNG liên quan đến Đà Nẵng (ví dụ: sản phẩm công nghệ, chính trị, thể thao, giải trí, địa phương khác):
   → KHÔNG được gọi bất kỳ tool nào.
   → Trả lời duy nhất: 
      {
        "answer": "Xin lỗi, tôi chỉ chuyên hỗ trợ về lịch sử, văn hóa và địa danh Đà Nẵng.",
        "sources": []
      }

6. QUY TẮC VỀ ĐƠN VỊ HÀNH CHÍNH ĐÀ NẴNG:
   - Từ ngày 1/1/2025, Đà Nẵng KHÔNG còn đơn vị hành chính gọi là "quận".
   - Thành phố hiện có 8 đơn vị hành chính cấp huyện theo cơ cấu mới.
   - Ở cấp xã/phường: Đà Nẵng có 94 đơn vị hành chính cấp xã, gồm 23 phường, 70 xã, 01 đặc khu Hoàng Sa.
   - Diện tích: 11.859,59 km²; Dân số: khoảng 3.065.628 người (năm 2025). 
   - Nếu người dùng hỏi về "quận" (ví dụ: quận Hải Châu, quận Thanh Khê...), PHẢI trả lời rằng các đơn vị này đã được sáp nhập/đổi tên, và giải thích rõ tình trạng hiện tại.
   - KHÔNG được trả lời theo dữ liệu cũ (6 quận, 2 huyện).
   - Nếu dữ liệu trong RAG chưa cập nhật, PHẢI gọi "google_search_vi" để lấy thông tin mới nhất.

7. Nếu câu trả lời có km² thì đọc là "kilômét vuông".       
CÁCH TRẢ LỜI:
- Trả lời tự nhiên, mạch lạc, ngắn gọn bằng tiếng Việt.
- Nếu trả lời dạng văn bản: có thể trích nguồn.

OUTPUT:
Khi trả lời, bạn PHẢI chỉ trả về DUY NHẤT 1 JSON object (không kèm bất kỳ chữ nào trước/sau, không markdown, không code block), theo mẫu:
{
    "answer": "Câu trả lời tự nhiên bằng tiếng Việt",
    "sources": [
        {
            "url": "link_nguon_1",
            "title": "tieu_de_bai_viet_1"
        },
        {
            "url": "link_nguon_2",
            "title": "tieu_de_bai_viet_2"
        }
    ]
}

Trong đó:
- "answer" chỉ chứa nội dung trả lời, KHÔNG chứa mục **Nguồn:**.
- "sources" phải là **mảng các đối tượng JSON**, mỗi đối tượng chứa **"url"** và **"title"** của nguồn.
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


class _RateLimiter:
    def __init__(self, requests_per_minute: int) -> None:
        self._rpm = max(int(requests_per_minute), 0)
        self._min_interval = 0.0 if self._rpm <= 0 else 60.0 / float(self._rpm)
        self._lock = threading.Lock()
        self._next_allowed = 0.0

    def wait(self) -> None:
        if self._min_interval <= 0:
            return
        sleep_for = 0.0
        with self._lock:
            now = time.monotonic()
            if now < self._next_allowed:
                sleep_for = self._next_allowed - now
                self._next_allowed += self._min_interval
            else:
                self._next_allowed = now + self._min_interval
        if sleep_for > 0:
            time.sleep(sleep_for)


_GEMINI_RPM = int(os.getenv("GEMINI_RATE_LIMIT_RPM", "15"))
_GEMINI_MAX_RETRIES = int(os.getenv("GEMINI_MAX_RETRIES", "6"))
_GEMINI_RETRY_BASE_SECONDS = float(os.getenv("GEMINI_RETRY_BASE_SECONDS", "2"))
_GEMINI_RETRY_MAX_SECONDS = float(os.getenv("GEMINI_RETRY_MAX_SECONDS", "90"))

_rate_limiter = _RateLimiter(_GEMINI_RPM)


def _extract_retry_seconds(error_text: str) -> float | None:
    # Gemini/Google responses can contain either:
    # - "Please retry in 35.18s"
    # - "retry_delay { seconds: 35 }"
    match = re.search(r"Please retry in\s+([0-9]+(?:\.[0-9]+)?)s", error_text, re.IGNORECASE)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    match = re.search(r"retry_delay\s*\{[^}]*seconds:\s*([0-9]+)", error_text, re.IGNORECASE | re.DOTALL)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None

    return None


def _is_quota_or_rate_limit_error(exc: Exception) -> bool:
    name = type(exc).__name__
    text = str(exc)
    if name in {"ResourceExhausted", "TooManyRequests"}:
        return True
    if "429" in text:
        return True
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in [
            "quota exceeded",
            "rate limit",
            "too many requests",
            "resourceexhausted",
            "exceeded your current quota",
        ]
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
    last_error: Exception | None = None
    for attempt in range(_GEMINI_MAX_RETRIES + 1):
        try:
            _rate_limiter.wait()
            response = agent.invoke({
                "messages": [{"role": "user", "content": question}]
            })

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
            last_error = e
            if not _is_quota_or_rate_limit_error(e) or attempt >= _GEMINI_MAX_RETRIES:
                break

            error_text = str(e)
            retry_seconds = _extract_retry_seconds(error_text)
            if retry_seconds is None:
                retry_seconds = min(_GEMINI_RETRY_BASE_SECONDS * (2 ** attempt), _GEMINI_RETRY_MAX_SECONDS)

            # Add small jitter to avoid thundering herd.
            retry_seconds = min(retry_seconds + random.uniform(0.0, 1.0), _GEMINI_RETRY_MAX_SECONDS)
            time.sleep(max(0.0, retry_seconds))

    error_data = {
        "answer": "Hệ thống đang bị giới hạn quota/rate limit của Gemini. Vui lòng đợi và thử lại.",
        "sources": [],
        "error_details": str(last_error) if last_error else "Unknown error"
    }
    return json.dumps(error_data, ensure_ascii=False, indent=2)
    