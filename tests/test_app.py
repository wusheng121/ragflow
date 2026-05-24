import asyncio
from fastapi.testclient import TestClient
import time
import re
from unittest.mock import AsyncMock

from app.main import app
from app.api.v1.assistant import assistant_service
from app.services.assistant_service import AssistantService

MATERIAL_TEXT = """
边际效应递减：在其他条件不变时，连续增加一种投入要素，新增产出会先增加后下降。
机会成本：为了得到一种东西而放弃的最大价值。
需求弹性：价格变化引起需求量变化的敏感程度。
""".strip()


def test_assistant_flow() -> None:
    with TestClient(app) as client:
        username = f"test_user_{int(time.time())}"
        register_res = client.post(
            "/api/v1/users/register",
            json={"name": username, "password": "12345678a", "email": "test@example.com", "level": "beginner"},
        )
        assert register_res.status_code == 200
        auth = register_res.json()
        client.headers.update({"Authorization": f"Bearer {auth['access_token']}"})

        create_res = client.post(
            "/api/v1/materials",
            json={"title": "经济学复习", "content": MATERIAL_TEXT, "source_name": "manual"},
        )
        assert create_res.status_code == 200
        material_id = create_res.json()["id"]

        flash_res = client.post(
            "/api/v1/assistant/knowledge-cards/generate",
            json={"material_id": material_id, "count": 3, "user_level": "beginner"},
        )
        assert flash_res.status_code == 200
        assert len(flash_res.json()) == 3

        question_res = client.post(
            "/api/v1/assistant/practice/question",
            json={"material_id": material_id, "concept": "边际效应递减", "user_level": "beginner"},
        )
        assert question_res.status_code == 200
        payload = question_res.json()

        answer_res = client.post(
            "/api/v1/assistant/practice/answer",
            json={
                "material_id": material_id,
                "concept": payload["concept"],
                "question": payload["question"],
                "answer": "是投入越多，产出就一直越高。",
                "user_level": "beginner",
            },
        )
        assert answer_res.status_code == 200
        assert "score" in answer_res.json()

        mistakes_res = client.get("/api/v1/mistakes")
        assert mistakes_res.status_code == 200
        assert isinstance(mistakes_res.json(), list)


def test_flashcard_terms_extract_from_definition_lines() -> None:
    text = (
        "\u8fb9\u9645\u6548\u5e94\u9012\u51cf\uff1a\u5728\u5176\u4ed6\u6761\u4ef6\u4e0d\u53d8\u65f6\uff0c\u8fde\u7eed\u589e\u52a0\u4e00\u79cd\u6295\u5165\u8981\u7d20\uff0c\u65b0\u589e\u4ea7\u51fa\u4f1a\u5148\u589e\u52a0\u540e\u4e0b\u964d\u3002"
        "\u673a\u4f1a\u6210\u672c\uff1a\u4e3a\u4e86\u5f97\u5230\u4e00\u79cd\u4e1c\u897f\u800c\u653e\u5f03\u7684\u6700\u5927\u4ef7\u503c\u3002"
        "\u9700\u6c42\u5f39\u6027\uff1a\u4ef7\u683c\u53d8\u5316\u5f15\u8d77\u9700\u6c42\u91cf\u53d8\u5316\u7684\u654f\u611f\u7a0b\u5ea6\u3002"
    )

    async def run() -> list[str]:
        service = AssistantService()
        return await service._extract_card_terms(text, count=3)

    terms = asyncio.run(run())
    assert terms[:3] == ["边际效应递减", "机会成本", "需求弹性"]


def test_build_flashcards_prefers_real_terms() -> None:
    text = (
        "\u8fb9\u9645\u6548\u5e94\u9012\u51cf\uff1a\u5728\u5176\u4ed6\u6761\u4ef6\u4e0d\u53d8\u65f6\uff0c\u8fde\u7eed\u589e\u52a0\u4e00\u79cd\u6295\u5165\u8981\u7d20\uff0c\u65b0\u589e\u4ea7\u51fa\u4f1a\u5148\u589e\u52a0\u540e\u4e0b\u964d\u3002"
        "\u673a\u4f1a\u6210\u672c\uff1a\u4e3a\u4e86\u5f97\u5230\u4e00\u79cd\u4e1c\u897f\u800c\u653e\u5f03\u7684\u6700\u5927\u4ef7\u503c\u3002"
        "\u9700\u6c42\u5f39\u6027\uff1a\u4ef7\u683c\u53d8\u5316\u5f15\u8d77\u9700\u6c42\u91cf\u53d8\u5316\u7684\u654f\u611f\u7a0b\u5ea6\u3002"
    )

    async def run() -> list[dict[str, str]]:
        service = AssistantService()
        return await service.build_flashcards(text, 3, "beginner")

    cards = asyncio.run(run())
    assert [card["concept"] for card in cards] == ["边际效应递减", "机会成本", "需求弹性"]
    assert all(card["concept"] not in {"核心概念", "关键机制", "典型场景"} for card in cards)


def test_guided_question_defaults_to_chinese_and_is_specific() -> None:
    async def run() -> tuple[str, list[str]]:
        service = AssistantService()
        service.llm_client.chat = AsyncMock(return_value="请解释该概念。")
        return await service.generate_guided_question("边际效应递减", "beginner", MATERIAL_TEXT)

    question, references = asyncio.run(run())
    assert any("边际效应递减" in ref for ref in references)
    assert "请解释该概念" not in question
    assert question.endswith(("？", "?"))
    assert re.search(r"[\u4e00-\u9fff]", question)
    assert any(keyword in question for keyword in ["是什么", "方法", "性质", "条件"])


def test_guided_question_prefers_llm_original_when_valid() -> None:
    async def run() -> str:
        service = AssistantService()
        service.llm_client.chat = AsyncMock(return_value="边际效应递减在生产决策里最关键的判断点是什么？")
        question, _ = await service.generate_guided_question("边际效应递减", "intermediate", MATERIAL_TEXT)
        return question

    question = asyncio.run(run())
    assert question == "边际效应递减在生产决策里最关键的判断点是什么？"


def test_normalize_concept_ignores_question_words() -> None:
    text = (
        "Why does output eventually decline when labor keeps increasing? "
        "Matrix transformation maps vectors between coordinate systems."
    )
    concept = AssistantService._normalize_concept("", text)
    assert concept.lower() != "why"


def test_guided_question_for_english_material_defaults_to_chinese() -> None:
    english_material = (
        "Matrix transformation changes a vector's coordinates. "
        "A point is mapped through a linear transformation."
    )

    async def run() -> str:
        service = AssistantService()
        service.llm_client.chat = AsyncMock(return_value="How does matrix transformation preserve linearity")
        question, _ = await service.generate_guided_question("Matrix transformation", "intermediate", english_material)
        return question

    question = asyncio.run(run())
    assert question.endswith(("？", "?"))
    assert re.search(r"[\u4e00-\u9fff]", question)


def test_flashcards_english_material_defaults_to_chinese() -> None:
    english_material = (
        "Matrix transformation changes a vector's coordinates. "
        "A point is mapped through a linear transformation."
    )

    async def fake_chat(_: str, user_prompt: str, temperature: float = 0.2) -> str:
        if "请根据课程资料生成最多" in user_prompt:
            return '{"cards": [{"concept": "Matrix transformation", "explanation": "Maps vectors into a new coordinate system.", "example": "Rotate point (1,0) to (0,1)."}]}'
        if "英文:" in user_prompt:
            return "矩阵变换"
        return ""

    async def run() -> list[dict[str, str]]:
        service = AssistantService()
        service.llm_client.chat = AsyncMock(side_effect=fake_chat)
        return await service.build_flashcards(english_material, 1, "intermediate")

    cards = asyncio.run(run())
    assert len(cards) == 1
    assert re.search(r"[\u4e00-\u9fff]", cards[0]["concept"])
    assert re.search(r"[\u4e00-\u9fff]", cards[0]["explanation"])


def test_practice_question_english_material_defaults_to_chinese_points() -> None:
    async def fake_chat(_: str, user_prompt: str, temperature: float = 0.2) -> str:
        if "根据课程资料生成1个引导性问题" in user_prompt:
            return "How does matrix transformation preserve linearity"
        if "英文:" in user_prompt:
            return "矩阵变换如何保持线性"
        if "请评估学生答案" in user_prompt:
            return '{"score": 80, "feedback": "Good", "correction": "OK", "missing_points": []}'
        return ""

    old_chat = assistant_service.llm_client.chat
    assistant_service.llm_client.chat = AsyncMock(side_effect=fake_chat)

    try:
        with TestClient(app) as client:
            username = f"en_user_{int(time.time())}"
            register_res = client.post(
                "/api/v1/users/register",
                json={"name": username, "password": "12345678a", "email": "en@example.com", "level": "intermediate"},
            )
            assert register_res.status_code == 200
            auth = register_res.json()
            client.headers.update({"Authorization": f"Bearer {auth['access_token']}"})

            create_res = client.post(
                "/api/v1/materials",
                json={
                    "title": "Linear Algebra",
                    "content": "Matrix transformation maps vectors between coordinate systems. It preserves addition and scalar multiplication.",
                    "source_name": "manual",
                },
            )
            assert create_res.status_code == 200
            material_id = create_res.json()["id"]

            question_res = client.post(
                "/api/v1/assistant/practice/question",
                json={"material_id": material_id, "concept": "Matrix transformation", "user_level": "intermediate"},
            )
            assert question_res.status_code == 200
            payload = question_res.json()

            assert re.search(r"[\u4e00-\u9fff]", payload["question"])
            assert payload["references"] and all(re.search(r"[\u4e00-\u9fff]", item) for item in payload["references"])
            assert payload["basis_points"] and all(re.search(r"[\u4e00-\u9fff]", item) for item in payload["basis_points"])
            assert any("定义" in item or "方法" in item or "性质" in item or "证据" in item for item in payload["basis_points"])
    finally:
        assistant_service.llm_client.chat = old_chat


