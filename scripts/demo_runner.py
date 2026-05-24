from pathlib import Path
import sys
from datetime import datetime

from fastapi.testclient import TestClient

# Ensure project root is on sys.path so `from app.main import app` works when running this script
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


if __name__ == "__main__":
    with TestClient(app) as client:
        stamp = datetime.now().strftime("%H%M%S")
        demo_name = f"demo_user_{stamp}"
        auth = client.post(
            "/api/v1/users/register",
            json={"name": demo_name, "password": "Demo12345", "email": f"{demo_name}@example.com", "level": "intermediate"},
        ).json()
        client.headers.update({"Authorization": f"Bearer {auth['access_token']}"})

        material = client.post(
            "/api/v1/materials",
            json={
                "title": "管理学第1章",
                "source_name": "demo",
                "content": "边际效应递减意味着新增投入在一定阶段后收益减少。机会成本是放弃选项中的最高价值。",
            },
        ).json()

        cards = client.post(
            "/api/v1/assistant/knowledge-cards/generate",
            json={"material_id": material["id"], "count": 2, "user_level": "intermediate"},
        ).json()

        q = client.post(
            "/api/v1/assistant/practice/question",
            json={"material_id": material["id"], "concept": cards[0]["concept"], "user_level": "intermediate"},
        ).json()

        result = client.post(
            "/api/v1/assistant/practice/answer",
            json={
                "material_id": material["id"],
                "concept": q["concept"],
                "question": q["question"],
                "answer": "我理解是投入越多收益一定越多。",
                "user_level": "intermediate",
            },
        ).json()

        print("Material:", material)
        print("Flashcards:", cards)
        print("Practice question:", q)
        print("Evaluation:", result)
        print("Mistakes:", client.get("/api/v1/mistakes").json())

