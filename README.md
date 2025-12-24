## ⚙️ Cài đặt & Chạy dự án

### 1. Cài đặt môi trường `uv`

Nếu chưa có `uv`, cài nhanh bằng PowerShell:

```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2. Tạo môi trường ảo & cài dependencies

```
cd chatbot_rag
uv venv
uv add fastapi uvicorn langchain langchain-core langchain-community langchain-huggingface langchain-chroma langchain-text-splitters python-dotenv langchain-google-genai sentence_transformers python-jose
```

### 3. Tạo file .env

```
GOOGLE_API_KEY=your_google_api_key_here
```

### 4. Chạy API server

```
uv run uvicorn api.main:app --reload --port 8000
```

Server sẽ khởi động tại: http://127.0.0.1:8000/

## API Endpoint

POST /ask

Gửi câu hỏi và nhận câu trả lời từ Agent RAG.

Request Body Example:

```
{
  "question": "Đà Nẵng được biết đến là gì trong lịch sử dân tộc?"
}
```
