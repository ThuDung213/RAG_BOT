from fastapi import FastAPI
from pydantic import BaseModel
from core.rag_agent import get_agent_response

app = FastAPI(title="Danang History Agent API")

class Question(BaseModel):
    question: str
    
@app.post("/ask")
async def ask_question(payload: Question):
    try:
        answer = get_agent_response(payload.question)
        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}