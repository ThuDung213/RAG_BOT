from langchain.tools import tool
import requests
import os
from dotenv import load_dotenv

load_dotenv()  # load từ file .env

@tool("google_search_vi")
def google_search_vi(query: str) -> str:
    """Tìm kiếm tiếng Việt bằng Google Custom Search API"""
    API_KEY = os.getenv("CUSTOM_SEARCH_API")
    CX = os.getenv("SEARCH_ENGINE_ID")
    url = (
        f"https://www.googleapis.com/customsearch/v1"
        f"?q={query}&cx={CX}&key={API_KEY}&lr=lang_vi&safe=active"
        f"&fields=items(title,link,snippet)"
    )

    try:
        data = requests.get(url).json()
        results = []
        for item in data.get("items", []):
            title = item.get("title", "")
            link = item.get("link", "")
            snippet = item.get("snippet", "")
            results.append(f"{title}\n{link}\n{snippet}")
        return "\n\n".join(results) if results else "Không tìm thấy kết quả."
    except Exception as e:
        return f"Lỗi khi gọi Google API: {e}"
