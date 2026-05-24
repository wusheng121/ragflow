import logging
from collections import Counter
import re
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class RagflowClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def upload_document(self, content: str, source_name: str, dataset_id: str | None = None) -> str:
        if not self.settings.ragflow_enabled:
            return "local-dataset"

        ds_id = dataset_id or self.settings.ragflow_dataset_id
        if not ds_id:
            return ""

        endpoint = self.settings.ragflow_upload_path.format(dataset_id=ds_id)
        headers = self._headers()
        payload = {"name": source_name, "content": content}

        try:
            async with httpx.AsyncClient(base_url=self.settings.ragflow_base_url, timeout=30.0) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = self._response_data(response)
                return self._dataset_id_from_response(data) or ds_id
        except httpx.HTTPStatusError as exc:
            body = exc.response.text if exc.response is not None else ""
            logger.warning(
                "RAGFlow upload failed (status=%s, url=%s): %s %s",
                exc.response.status_code if exc.response is not None else "unknown",
                endpoint,
                exc,
                body,
            )
            return ""
        except Exception as exc:
            logger.warning("RAGFlow upload failed, fallback to local mode: %s", exc)
            return ""

    async def retrieve(self, query: str, source_text: str, top_k: int = 3, dataset_id: str = "") -> list[str]:
        if self.settings.ragflow_enabled:
            payload = {
                "query": query,
                "top_k": top_k,
                "dataset_id": dataset_id or self.settings.ragflow_dataset_id,
            }
            try:
                async with httpx.AsyncClient(base_url=self.settings.ragflow_base_url, timeout=30.0) as client:
                    response = await client.post(
                        self.settings.ragflow_retrieve_path,
                        json=payload,
                        headers=self._headers(),
                    )
                    response.raise_for_status()
                    data = self._response_data(response)
                    texts = self._extract_texts(data)
                    if texts:
                        return texts[:top_k]
            except httpx.HTTPStatusError as exc:
                body = exc.response.text if exc.response is not None else ""
                logger.warning(
                    "RAGFlow retrieve failed (status=%s, url=%s): %s %s",
                    exc.response.status_code if exc.response is not None else "unknown",
                    self.settings.ragflow_retrieve_path,
                    exc,
                    body,
                )
            except Exception as exc:
                logger.warning("RAGFlow retrieve failed, fallback to lexical retrieval: %s", exc)

        return self._local_retrieve(query, source_text, top_k=top_k)

    @staticmethod
    def extract_keywords(text: str, count: int = 10) -> list[str]:
        tokens = re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[一-鿿]{2,8}", text)
        stopwords = {"以及", "因为", "所以", "进行", "我们", "可以", "这个", "一个", "通过", "and", "the"}
        filtered = [tok for tok in tokens if tok.lower() not in stopwords]
        ranked = Counter(filtered).most_common(count * 2)
        result = []
        for term, _ in ranked:
            if term not in result:
                result.append(term)
            if len(result) >= count:
                break
        return result

    @staticmethod
    def _local_retrieve(query: str, source_text: str, top_k: int = 3) -> list[str]:
        chunks = [chunk.strip() for chunk in re.split(r"[\n。！？]", source_text) if chunk.strip()]
        query_tokens = set(re.findall(r"[A-Za-z0-9_一-鿿]+", query.lower()))

        scored: list[tuple[int, str]] = []
        for chunk in chunks:
            chunk_tokens = set(re.findall(r"[A-Za-z0-9_一-鿿]+", chunk.lower()))
            score = len(query_tokens & chunk_tokens)
            if score > 0:
                scored.append((score, chunk))

        if not scored:
            return chunks[:top_k]

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.ragflow_api_key:
            headers["Authorization"] = f"Bearer {self.settings.ragflow_api_key}"
        return headers

    @staticmethod
    def _response_data(response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        if isinstance(data, dict):
            return data
        return {"data": data}

    @staticmethod
    def _dataset_id_from_response(data: dict[str, Any]) -> str:
        for key in ("dataset_id", "datasetId"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        nested = data.get("data")
        if isinstance(nested, dict):
            for key in ("dataset_id", "datasetId"):
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

        return ""

    @staticmethod
    def _extract_texts(data: dict[str, Any]) -> list[str]:
        candidates: list[Any] = []
        for key in ("data", "chunks", "results", "documents", "items"):
            value = data.get(key)
            if isinstance(value, list):
                candidates.extend(value)
            elif isinstance(value, dict):
                for nested_key in ("chunks", "results", "documents", "items"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        candidates.extend(nested_value)

        texts: list[str] = []
        for item in candidates:
            text = RagflowClient._item_text(item)
            if text and text not in texts:
                texts.append(text)
        return texts

    @staticmethod
    def _item_text(item: Any) -> str:
        if isinstance(item, dict):
            for key in ("content", "text", "chunk", "chunk_text", "answer", "content_text"):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return ""
        return str(item).strip() if item else ""

