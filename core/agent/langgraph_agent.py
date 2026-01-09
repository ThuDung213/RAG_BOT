import os, json, time, random, re
from typing import List, TypedDict, Union
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain.chat_models import init_chat_model
from langchain_core.documents import Document
from langgraph.graph import END, StateGraph
from tools.google_search_vi import google_search_vi
from core.agent.data_utils import parse_agent_response
from dotenv import load_dotenv

load_dotenv()

# --- Initialization ---
llm = init_chat_model("gemini-2.5-flash-lite", model_provider="google_genai", temperature=0)
vectorstore = Chroma(persist_directory='chroma_db_for_agent_bge', embedding_function=HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5"))
retriever = vectorstore.as_retriever(search_kwargs={"k": 5})

def llm_invoke(prompt: str) -> str:
    for attempt in range(int(os.getenv("GEMINI_MAX_RETRIES", "6")) + 1):
        try:
            return str(llm.invoke(prompt).content)
        except Exception as e:
            if any(m in str(e).lower() for m in ["429", "quota", "limit"]) and attempt < 6:
                time.sleep(min(2**attempt + random.uniform(0, 1), 60))
                continue
            raise e
    return ""

class GraphState(TypedDict, total=False):
    question: str
    generation: str
    documents: List[Union[Document, str]]
    iterations: int
    category: str  # HISTORY, NEWS, CHATTING, IRRELEVANT

# --- Nodes ---
def check_relevance(state):
    print("---CHECK RELEVANCE---")
    prompt = f"""Bạn là bộ lọc thông minh cho trợ lý ảo Đà Nẵng.
    Nhiệm vụ: Phân loại câu hỏi của người dùng để quyết định quy trình xử lý.
    
    Câu hỏi: '{state['question']}'
    
    Quy tắc phân loại:
    1. 'HISTORY': Câu hỏi liên quan đến lịch sử, di tích, sự kiện, địa danh hoặc dữ liệu văn hóa có thể có trong kho nội bộ Đà Nẵng.
    2. 'NEWS': Câu hỏi liên quan đến tin tức mới, sự kiện đang diễn ra, thông tin hiện tại hoặc nội dung không thể có trong kho dữ liệu cũ.
    3. 'CHATTING': Các câu chào hỏi, giới thiệu hoặc trò chuyện xã giao không yêu cầu dữ liệu thực tế.
    4. 'IRRELEVANT': Câu hỏi hoàn toàn không liên quan đến Đà Nẵng (vd: hỏi về Hà Nội, lập trình, toán học).
    
    CHỈ trả về duy nhất từ: 'HISTORY', 'NEWS', 'CHATTING' hoặc 'IRRELEVANT'. Không giải thích.
    """
    res = llm_invoke(prompt).upper()
    category = "IRRELEVANT"
    if "HISTORY" in res: category = "HISTORY"
    elif "NEWS" in res: category = "NEWS"
    elif "CHATTING" in res: category = "CHATTING"
    
    return {"category": category}

def handle_irrelevant(state):
    return {"generation": json.dumps({"answer": "Xin lỗi, tôi là trợ lý ảo chuyên trách về du lịch và lịch sử Đà Nẵng. Tôi chưa có dữ liệu để hỗ trợ các chủ đề khác. Bạn có muốn hỏi gì về địa danh, món ăn hay lịch sử của Đà Nẵng không?", "sources": []}, ensure_ascii=False)}

def handle_chatting(state):
    print("---CHATTING---")
    prompt = f"""Bạn là trợ lý AI lịch sử địa phương của thành phố Đà Nẵng.
    Hãy trả lời thân thiện câu hỏi/lời chào: '{state['question']}'
    
    Yêu cầu:
    - Trả lời tự nhiên, mạch lạc bằng tiếng Việt.
    - KHÔNG dùng tool.
    - PHẢI trả về JSON thuần: {{"answer": "...", "sources": []}}
    """
    return {"generation": llm_invoke(prompt)}

def retrieve(state):
    print("---RETRIEVE---")
    return {"documents": retriever.invoke(state["question"]), "iterations": 1}

def generate_answer(state):
    print("---GENERATE---")
    q, docs, iters = state["question"], state.get("documents", []), state.get("iterations", 0)
    
    # Chuẩn bị context và trích xuất thông tin nguồn
    context_entries = []
    for i, d in enumerate(docs):
        meta = d.metadata if hasattr(d, "metadata") else {}
        context_entries.append(f"--- NGUỒN {i+1} ---\nTiêu đề: {meta.get('title', 'N/A')}\nURL: {meta.get('url', 'N/A')}\nNội dung: {d.page_content}")
    ctx_text = "\n\n".join(context_entries)

    # Chỉ thị động dựa trên số lần lặp
    if iters <= 1:
        logic_instr = """Nếu bối cảnh KHÔNG ĐỦ thông tin để trả lời CHÍNH XÁC, CHI TIẾT và TRỰC TIẾP câu hỏi (ví dụ: thiếu số lượng cụ thể, ngày tháng, hoặc sự kiện chính), bạn PHẢI trả về 'NEED_SEARCH'."""
    else:
        logic_instr = """Đây là thông tin từ KẾT QUẢ TÌM KIẾM GOOGLE. PHẢI tổng hợp thông tin từ các nguồn này để trả lời. 
        - Nếu có con số cụ thể, hãy nêu ra. 
        - Nếu các nguồn không thống nhất, hãy nêu các con số khác nhau hoặc danh sách các cây cầu quan trọng nhất.
        - TUYỆT ĐỐI KHÔNG trả lời rằng 'không có thông tin' nếu trong bối cảnh có nhắc đến bất kỳ địa danh hay con số nào liên quan. Hãy cố gắng hữu ích nhất có thể."""

    prompt = f"""Bạn là chuyên gia trợ lý AI về Đà Nẵng.
    Nhiệm vụ: Trả lời câu hỏi dựa trên bối cảnh.
    
    YÊU CẦU CỐT LÕI:
    1. {logic_instr}
    2. CÁCH TRẢ LỜI: 
       - Trả lời trực diện, mạch lạc, tự nhiên.
       - Không giải thích về quá trình tìm kiếm.
    3. JSON OUTPUT:
       {{
         "answer": "Câu trả lời của bạn",
         "sources": [
            {{"url": "...", "title": "..."}}
         ]
       }}
    
    Bối cảnh:
    {ctx_text}
    
    Câu hỏi: {q}
    """
    
    gen = llm_invoke(prompt)
    # Hậu kiểm: Nếu model trả lời "không tìm thấy" ở lần lặp đầu tiên
    if iters <= 1:
        not_found_patterns = ["không tìm thấy", "không có dữ liệu", "không tìm thấy tài liệu phù hợp", "rất tiếc", "không có thông tin"]
        if any(p in gen.lower() for p in not_found_patterns):
            return {"generation": '{"answer": "NEED_SEARCH", "sources": []}'}
            
    return {"generation": gen}

def rewrite_question(state):
    print("---REWRITE---")
    prompt = f"""Bạn là một thuật toán tối ưu hóa tìm kiếm. 
    Câu hỏi: '{state['question']}'
    
    Nhiệm vụ: Chuyển câu hỏi trên thành một cụm từ tìm kiếm Google ngắn gọn, hiệu quả nhất.
    - Nếu câu hỏi hỏi về số lượng (bao nhiêu), hãy thêm từ khóa 'thống kê' hoặc 'danh sách'.
    - Nếu là sự kiện, hãy thêm năm hoặc địa điểm.
    - Chỉ trả về duy nhất chuỗi tìm kiếm, không giải thích.
    """
    return {"question": llm_invoke(prompt).strip('"')}

def web_search(state):
    search_query = state["question"]
    print(f"---WEB SEARCH FOR: {search_query}---")
    res = google_search_vi.run(search_query)
    return {"documents": [Document(page_content=res, metadata={"url": "Google Search", "title": "Kết quả tổng hợp từ Google"})], "iterations": 2}

# --- Graph ---
workflow = StateGraph(GraphState)
workflow.add_node("check_relevance", check_relevance)
workflow.add_node("handle_irrelevant", handle_irrelevant)
workflow.add_node("handle_chatting", handle_chatting)
workflow.add_node("retrieve", retrieve)
workflow.add_node("generate", generate_answer)
workflow.add_node("rewrite_question", rewrite_question)
workflow.add_node("web_search", web_search)

workflow.set_entry_point("check_relevance")

def route_after_relevance(state):
    cat = state.get("category", "IRRELEVANT")
    if cat == "HISTORY": return "history"
    if cat == "NEWS": return "news"
    if cat == "CHATTING": return "chatting"
    return "irrelevant"

workflow.add_conditional_edges(
    "check_relevance", 
    route_after_relevance, 
    {
        "history": "retrieve", 
        "news": "rewrite_question", 
        "chatting": "handle_chatting", 
        "irrelevant": "handle_irrelevant"
    }
)

workflow.add_edge("handle_irrelevant", END)
workflow.add_edge("handle_chatting", END)
workflow.add_edge("retrieve", "generate")
workflow.add_conditional_edges("generate", lambda x: "rew" if "NEED_SEARCH" in x["generation"] and x.get("iterations", 0) < 2 else END, {"rew": "rewrite_question", END: END})
workflow.add_edge("rewrite_question", "web_search")
workflow.add_edge("web_search", "generate")
app = workflow.compile()

def get_langgraph_response(question: str):
    try:
        res = app.invoke({"question": question, "documents": []})
        ans = parse_agent_response(res.get("generation", ""))
        if ans.get("answer") == "NEED_SEARCH":
            ans["answer"] = "Rất tiếc, tôi không tìm thấy thông tin chi tiết về vấn đề này."
        return json.dumps(ans, ensure_ascii=False, indent=2)
    except Exception as e:
        return json.dumps({"answer": f"Lỗi: {str(e)}", "sources": []}, ensure_ascii=False)
