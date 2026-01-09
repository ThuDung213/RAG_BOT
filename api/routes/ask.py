from fastapi import APIRouter
from pydantic import BaseModel
from core.agent.rag_agent import get_agent_response
import asyncio
import time
import json
router = APIRouter()
class Question(BaseModel):
    question: str
 
# Cache đơn giản
response_cache = {}
CACHE_TIMEOUT = 300
   
@router.post("/ask")
async def ask_question(payload: Question):
    start_time = time.time()
    
    try:
        # Kiểm tra cache
        cache_key = payload.question.strip().lower()
        if cache_key in response_cache:
            cache_data = response_cache[cache_key]
            if time.time() - cache_data['timestamp'] < CACHE_TIMEOUT:
                print(f"Cache hit: {time.time() - start_time:.2f}s")
                return cache_data['response']
        
        # Chạy agent trong thread pool để không block event loop
        loop = asyncio.get_event_loop()
        answer = await loop.run_in_executor(
            None,  # Sử dụng default thread pool
            get_agent_response, 
            payload.question
        )

        # get_agent_response returns dict on success, JSON string on error
        if isinstance(answer, str):
            try:
                response_data = json.loads(answer)
            except Exception:
                response_data = {"answer": answer, "sources": []}
        else:
            response_data = answer
        
        # Lưu cache
        response_cache[cache_key] = {
            'response': response_data,
            'timestamp': time.time()
        }
        
        print(f"Request completed: {time.time() - start_time:.2f}s")
        return response_data
        
    except Exception as e:
        print(f"Error: {time.time() - start_time:.2f}s - {str(e)}")
        return {"error": "Có lỗi xảy ra khi xử lý câu hỏi"}