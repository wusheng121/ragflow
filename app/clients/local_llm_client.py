import json
import logging
import re
from collections import Counter

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class LocalLLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def chat(self, system_prompt: str, user_prompt: str, temperature: float = 0.2) -> str:
        if not self.settings.local_llm_enabled:
            return self._mock_response(user_prompt)

        headers = {"Content-Type": "application/json"}
        if self.settings.local_llm_api_key:
            headers["Authorization"] = f"Bearer {self.settings.local_llm_api_key}"

        payload = {
            "model": self.settings.local_llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(base_url=self.settings.local_llm_base_url, timeout=60.0) as client:
                response = await client.post(self.settings.local_llm_chat_path, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("Local LLM call failed, fallback to mock: %s", exc)
            return self._mock_response(user_prompt)

    @staticmethod
    def parse_json_block(text: str) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if not match:
                return {}
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                return {}

    @staticmethod
    def _mock_response(prompt: str) -> str:
        if ("JSON" in prompt and "terms" in prompt) or "术语" in prompt:
            material = prompt
            marker = "课程资料:"
            if marker in prompt:
                material = prompt.rsplit(marker, 1)[1]

            tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[一-鿿]{2,10}", material)
            stopwords = {
                "课程", "资料", "可以", "我们", "这个", "一个", "因为", "所以", "通过", "以及", "进行", "要求", "输出",
                "json", "terms", "count", "material",
            }
            candidates = [t for t in tokens if t.lower() not in stopwords]
            top_terms = []
            for term, _ in Counter(candidates).most_common(8):
                if term not in top_terms:
                    top_terms.append(term)
            if not top_terms:
                top_terms = ["核心概念", "关键定义", "典型例子"]
            return json.dumps({"terms": top_terms[:6]}, ensure_ascii=False)
        if "评分" in prompt or "score" in prompt.lower():
            return (
                '{"score": 62, "feedback": "解释较笼统，缺少与课件一致的关键条件。", '
                '"correction": "边际效应递减是指在其他条件不变时，连续增加某一投入要素，其带来的边际产出最终会下降。", '
                '"missing_points": ["其他条件不变", "边际产出变化", "结合实际例子"]}'
            )
        return "请解释该概念，并说明在真实场景中的一个例子。"

