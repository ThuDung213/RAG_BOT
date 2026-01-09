from langchain_core.documents import Document
import json
import os
import re

def load_and_clean_json(file_path):
    """
    Tải file JSON, chuẩn hóa cấu trúc (list/dict), và trích xuất nội dung 'content' 
    để tạo LangChain Documents.
    """
    documents = []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Lỗi đọc file {file_path}: {e}")
        return documents

    # Chuẩn hóa dữ liệu: Đảm bảo data_list là một list các đối tượng
    if isinstance(data, dict):
        data_list = [data]
    elif isinstance(data, list):
        data_list = data
    else:
        # Dữ liệu không hợp lệ (không phải list hoặc dict)
        return documents

    # Duyệt và trích xuất nội dung
    for item in data_list:
        if isinstance(item, dict) and item.get('content'):
            source_file = os.path.basename(file_path)
            
            doc = Document(
                page_content=item['content'],
                metadata={
                    "source_file": source_file,
                    "title": item.get('title', 'N/A'),
                    "url": item.get('url', 'N/A')
                } 
            )
            documents.append(doc)
    return documents

def parse_agent_response(response_text: str) -> dict:
    """
    Parse response text from agent to extract JSON if present.
    Returns a dictionary with keys "answer" and "sources".
    """
    # Nếu response_text là một chuỗi JSON hợp lệ, thì parse trực tiếp
    try:
        data = json.loads(response_text)
        if isinstance(data, dict) and "answer" in data and "sources" in data:
            return data
    except json.JSONDecodeError:
        pass

    # Nếu không, tìm kiếm pattern code block chứa JSON
    pattern = r'```json\s*(.*?)\s*```'
    matches = re.findall(pattern, response_text, re.DOTALL)
    if matches:
        json_str = matches[0]
        try:
            data = json.loads(json_str)
            if isinstance(data, dict) and "answer" in data and "sources" in data:
                return data
        except json.JSONDecodeError:
            pass

    # Nếu model trả về dạng: <text>\n\n{ "answer": ..., "sources": ... }
    # thì cố gắng trích JSON object đầu tiên hợp lệ từ chuỗi.
    decoder = json.JSONDecoder()
    for i, ch in enumerate(response_text):
        if ch != "{":
            continue
        try:
            obj, _end = decoder.raw_decode(response_text[i:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "answer" in obj and "sources" in obj:
            return obj

    # Nếu không tìm thấy JSON, trả về toàn bộ response_text làm answer và sources rỗng
    return {
        "answer": response_text,
        "sources": []
    }