from langchain.tools import tool

def create_danang_history_tool(retriever):
    @tool("danang_history_knowledge_base")
    def danang_history_knowledge_base(query: str) -> str:
        """
        Công cụ truy xuất kiến thức nội bộ về Lịch sử / Văn hóa Đà Nẵng.
        """
        print("---DANANG HISTORY KNOWLEDGE BASE---", query)
        docs = retriever.invoke(query)
        formatted = []
        for i, d in enumerate(docs, start=1):
            src = d.metadata.get("source") or d.metadata.get("id") or f"doc_{i}"
            page = d.metadata.get("page")
            tag = f"{src}" + (f":p{page}" if page is not None else "")
            formatted.append(f"[{tag}]\n{d.page_content}")
        return "\n\n".join(formatted) if formatted else "Không tìm thấy tài liệu phù hợp."

    return danang_history_knowledge_base
