from dotenv import load_dotenv
from langchain_community.document_loaders import DirectoryLoader
from langchain_community.document_loaders import JSONLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
import os
import shutil
from langchain_chroma import Chroma
from langchain_google_genai.embeddings import GoogleGenerativeAIEmbeddings as GoogleEmbeddings
from google import genai
DATA_PATH = "data_sources"
CHROMA_PATH = "chroma"
load_dotenv()

def json_content_extractor(data):
    return data.get("content")

# def load_documents():
#     "Load json documents from a folder."
#     loader = DirectoryLoader(
#         DATA_PATH, 
#         glob="*.json", # <-- Change the glob to target JSON files
#         loader_cls=JSONLoader, # <-- Specify the JSONLoader class
#         loader_kwargs={ # <-- Pass arguments needed by JSONLoader
#             'jq_schema': '.', # Use '.' to load the entire JSON object as a document
#             'content_key': 'content', # Keys to look for content (adjust as needed)
#             'text_content': True # Treat the output as text content
#         }
#     )
#     documents = loader.load()
#     return documents
# ĐƯỜNG DẪN ĐẾN FILE BẠN MUỐN CHẠY THỬ
SINGLE_FILE_PATH = os.path.join(DATA_PATH, "aicschool_danang_history_20250924_122809_simple.json") 
# Bạn phải thay thế "your_single_test_file.json" bằng tên file JSON cụ thể của bạn

# Hàm mới để tải 1 file
def load_single_document():
    "Load a single JSON document for testing."
    # Sử dụng JSONLoader trực tiếp
    loader = JSONLoader(
        file_path=SINGLE_FILE_PATH,
        # Nếu file của bạn là đối tượng duy nhất có khóa 'content'
        jq_schema='.',       
        content_key='content',
        # Bạn có thể bỏ qua text_content=True vì nó là mặc định trong JSONLoader mới
    )
    documents = loader.load()
    return documents
def split_text(documents: list[Document]):
    "Split documents into chunks."
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=300,
        chunk_overlap=100,
        length_function=len,
        add_start_index=True,
    )
    
    chunks = text_splitter.split_documents(documents)
    print(f"Split {len(documents)} documents into {len(chunks)} chunks.")
    return chunks

# 3. Định nghĩa Hàm Lưu trữ vào ChromaDB (Save to Chroma)
def save_to_chroma(chunks: list[Document]):
    """Xóa DB cũ và lưu các chunks mới vào ChromaDB."""
    if os.path.exists(CHROMA_PATH):
        shutil.rmtree(CHROMA_PATH)
    client = genai.Client()
    embedding_model = client.models.embed_content(
        model="gemini-embedding-001"
    )

    # Tạo và lưu DB
    db = Chroma.from_documents(
        chunks, embedding_model, persist_directory=CHROMA_PATH
    )
    print(f"Saved {len(chunks)} chunks to {CHROMA_PATH}.")

# 4. Thực thi
def create_vector_db():
    documents = load_single_document()
    doc_chunks = split_text(documents)
    save_to_chroma(doc_chunks)

if __name__ == "__main__":
    create_vector_db()