from langchain_community.document_loaders import JSONLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from core.data_utils import load_and_clean_json

from dotenv import load_dotenv
import json
import os

load_dotenv()

# --- BƯỚC 1: Tải Dữ liệu (Load Data) ---

# Config data and DB
# file_path = './data_sources/danang_history_paragraphs_20250924_123855.json' 
data_dir = './data'
jq_schema = '.[].content' 
CHUNK_SIZE = 1000    # 1000 tokens là khoảng 4000 ký tự (văn bản tiếng Việt có thể hơi khác)
CHUNK_OVERLAP = 200
persist_directory = 'chroma_db_for_agent_bge' 
model_name = "BAAI/bge-small-en-v1.5" 

# --- B1: Tải Dữ liệu từ Nhiều File (Load Multiple Data)
all_documents = []
file_count = 0

print(f"Bắt đầu tải dữ liệu từ thư mục: {data_dir}")

for filename in os.listdir(data_dir):
    if filename.endswith(".json"):
        file_path = os.path.join(data_dir, filename)

        # documents sẽ là một list các đối tượng Document của LangChain
        current_documents = load_and_clean_json(file_path)

        # Thêm metadata tên file vào mỗi Document
        for doc in current_documents:
            doc.metadata['source_file'] = filename
        
        all_documents.extend(current_documents)
        file_count += 1
        print(f"  > Đã tải {len(current_documents)} đoạn từ file: {filename}")

if file_count == 0:
    print("❌ Lỗi: Không tìm thấy file JSON nào trong thư mục data.")
    exit()

print(f"✅ Hoàn thành tải. Tổng cộng {len(all_documents)} tài liệu gốc từ {file_count} file.")


# --- B2: Chunking
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size = CHUNK_SIZE,
    chunk_overlap = CHUNK_OVERLAP,
    length_function = len,  # Sử dụng hàm len để tính độ dài ký tự
    separators = ["\n\n", "\n", " ", ""]
)

chunks = text_splitter.split_documents(all_documents)

print(f"Tổng số đoạn (chunks) đã tạo: {len(chunks)}")


# --- B3: Embedding and Save
model_kwargs = {'device': 'cpu'}  # 'cpu' là an toàn nhất. Dùng 'cuda' nếu bạn có GPU mạnh.
encode_kwargs = {'normalize_embeddings': True}

embedding_model = HuggingFaceEmbeddings(
    model_name=model_name,
    model_kwargs=model_kwargs,
    encode_kwargs=encode_kwargs
)
print("✅ Đã khởi tạo thành công Embedding Model.{model_name}")
print(f"📁 Vector Database sẽ được lưu tại: {persist_directory}")

# Create vs Save vector store
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embedding_model,
    persist_directory=persist_directory
)

print("🎉 Hoàn thành Bước 3! Đã nhúng tất cả dữ liệu và lưu vào Chroma DB.")