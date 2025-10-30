from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from core.rag_agent import get_agent_response

app = FastAPI(title="Danang History Agent API")

origins = [
    "http://localhost:5173", 
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # Cho phép các nguồn gốc này
    allow_credentials=True,
    allow_methods=["*"],              # RẤT QUAN TRỌNG: Cho phép tất cả phương thức, bao gồm OPTIONS
    allow_headers=["*"],              # Cho phép tất cả các Header (bao gồm Content-Type)
)
class Question(BaseModel):
    question: str
    
@app.post("/ask")
async def ask_question(payload: Question):
    try:
        answer = get_agent_response(payload.question)
        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}