import os
import json
import sys
import time
from pathlib import Path

# Add project root to sys.path
project_root = str(Path(__file__).parent.parent)
sys.path.append(project_root)

from core.agent.langgraph_agent import get_langgraph_response
from langchain.chat_models import init_chat_model

# Initialize Judge LLM - Use a slightly higher temperature for "judgmental" reasoning if needed, 
# but 0 is usually better for consistency.
judge_llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai", temperature=0)

def evaluate_response(question, answer, category):
    prompt = f"""Bạn là một chuyên gia đánh giá hệ thống RAG (Retrieval-Augmented Generation).
Nhiệm vụ của bạn là đánh giá câu trả lời của AI dựa trên câu hỏi và thông tin hỗ trợ.

Câu hỏi: {question}
Thể loại: {category}
Câu trả lời của AI: {answer}

Tiêu chí đánh giá (Thang điểm 1-5):
1. Relevance (Độ liên quan): Câu trả lời có đúng trọng tâm câu hỏi không?
2. Accuracy (Độ chính xác): Thông tin cung cấp có chính xác không (đặc biệt là các con số, địa danh)?
3. Completeness (Độ đầy đủ): Câu trả lời có bao quát hết các ý của câu hỏi không?

Nếu thể loại là 'IRRELEVANT', hãy đánh giá xem AI có từ chối trả lời một cách lịch sự và đúng quy định không.
Nếu thể loại là 'CHATTING', hãy đánh giá độ thân thiện.

Hãy trả về kết quả dưới định dạng JSON duy nhất:
{{
    "scores": {{
        "relevance": <1-5>,
        "accuracy": <1-5>,
        "completeness": <1-5>
    }},
    "feedback": "Nhận xét ngắn gọn về ưu/nhược điểm"
}}
"""
    try:
        res = judge_llm.invoke(prompt)
        # Clean potential markdown from response
        content = res.content.replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except Exception as e:
        return {"error": str(e)}

def main():
    dataset_path = os.path.join(project_root, "scripts", "eval_dataset.json")
    with open(dataset_path, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    results = []
    print(f"Starting evaluation of {len(test_cases)} cases...")

    for case in test_cases:
        print(f"Running Case {case['id']}: {case['question']}")
        start_time = time.time()
        
        # Get response from agent
        response_json = get_langgraph_response(case["question"])
        response_data = json.loads(response_json)
        
        latency = time.time() - start_time
        
        # Evaluate
        print(f"Judging Case {case['id']}...")
        evaluation = evaluate_response(case["question"], response_data.get("answer", ""), case["category"])
        
        results.append({
            "id": case["id"],
            "question": case["question"],
            "category": case["category"],
            "answer": response_data.get("answer"),
            "sources": response_data.get("sources"),
            "evaluation": evaluation,
            "latency": round(latency, 2)
        })

    # Save results
    output_path = os.path.join(project_root, "scripts", "eval_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"Evaluation complete. Results saved to {output_path}")

    # Summary calculation
    total_relevance = 0
    total_accuracy = 0
    total_completeness = 0
    count = 0

    for r in results:
        eval_data = r.get("evaluation", {})
        scores = eval_data.get("scores", {})
        if scores:
            total_relevance += scores.get("relevance", 0)
            total_accuracy += scores.get("accuracy", 0)
            total_completeness += scores.get("completeness", 0)
            count += 1

    if count > 0:
        print("\n--- SUMMARY SCORES ---")
        print(f"Average Relevance: {total_relevance/count:.2f}/5")
        print(f"Average Accuracy: {total_accuracy/count:.2f}/5")
        print(f"Average Completeness: {total_completeness/count:.2f}/5")

if __name__ == "__main__":
    main()
