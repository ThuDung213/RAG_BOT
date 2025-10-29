from langchain_core.documents import Document
import json
import os

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