import json
import logging
from collections.abc import Callable
from pathlib import Path

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class RagflowError(Exception):
    pass


class RagflowClient:
    """RAGFlow HTTP API client (dataset upload, parse, chunk retrieval, LLM)."""

    def __init__(self) -> None:
        self.settings = get_settings()
        if not self.settings.ragflow_enabled:
            raise RagflowError("RAGFlow API URL 或 API Key 未配置")
        self._cached_chat_id: str | None = None

    @property
    def base_url(self) -> str:
        return self.settings.ragflow_api_url.rstrip("/")

    def _headers(self, json_body: bool = True) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.settings.ragflow_api_key}"}
        if json_body:
            headers["Content-Type"] = "application/json"
        # ngrok free tier
        headers["ngrok-skip-browser-warning"] = "true"
        return headers

    def _check_response(self, data: dict) -> dict:
        if data.get("code") != 0:
            raise RagflowError(data.get("message") or f"RAGFlow 错误 code={data.get('code')}")
        return data.get("data", data)

    async def create_dataset(self, name: str) -> str:
        payload = {
            "name": name[:128],
            "description": f"RAGFlow review assistant - {name}",
            "chunk_method": "naive",
            "parser_config": {
                "chunk_token_num": 512,
                "delimiter": "\n!?;。；！？",
                "layout_recognize": "true",
            },
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/datasets",
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = self._check_response(resp.json())
            return data["id"]

    async def upload_document(self, dataset_id: str, file_path: Path, filename: str) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            with file_path.open("rb") as f:
                resp = await client.post(
                    f"{self.base_url}/api/v1/datasets/{dataset_id}/documents",
                    headers=self._headers(json_body=False),
                    files={"file": (filename, f)},
                )
            resp.raise_for_status()
            data = self._check_response(resp.json())
            if isinstance(data, list) and data:
                return data[0]["id"]
            raise RagflowError("上传文档失败：无返回 document id")

    async def parse_documents(self, dataset_id: str, document_ids: list[str]) -> None:
        if not document_ids:
            return
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/chunks",
                headers=self._headers(),
                json={"document_ids": document_ids},
            )
            resp.raise_for_status()
            self._check_response(resp.json())

    async def get_document_run_status(self, dataset_id: str, document_id: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/datasets/{dataset_id}/documents",
                headers=self._headers(json_body=False),
                params={"id": document_id, "page": 1, "page_size": 1},
            )
            resp.raise_for_status()
            data = self._check_response(resp.json())
            docs = data.get("docs") or []
            if not docs:
                return "UNKNOWN"
            run = str(docs[0].get("run", "")).upper()
            if run in {"3", "DONE"}:
                return "DONE"
            if run in {"4", "FAIL"}:
                return "FAIL"
            if run in {"1", "RUNNING"}:
                return "RUNNING"
            if run in {"0", "UNSTART"}:
                return "UNSTART"
            return run

    async def wait_documents_ready(
        self,
        dataset_id: str,
        document_ids: list[str],
        on_progress: Callable[[int, str], None] | None = None,
        progress_base: int = 20,
        progress_span: int = 35,
    ) -> None:
        import asyncio

        timeout = self.settings.ragflow_parse_timeout
        interval = self.settings.ragflow_parse_poll_interval
        elapsed = 0
        pending = set(document_ids)

        while pending and elapsed < timeout:
            done: set[str] = set()
            failed: list[str] = []
            for doc_id in pending:
                status = await self.get_document_run_status(dataset_id, doc_id)
                if status == "DONE":
                    done.add(doc_id)
                elif status == "FAIL":
                    failed.append(doc_id)
            pending -= done
            if failed:
                raise RagflowError(f"文档解析失败: {', '.join(failed)}")
            if not pending:
                return
            if on_progress:
                ratio = min(1.0, elapsed / max(timeout, 1))
                pct = progress_base + int(progress_span * ratio)
                on_progress(pct, f"等待文档解析（剩余 {len(pending)} 个）…")
            await asyncio.sleep(interval)
            elapsed += interval

        if pending:
            raise RagflowError(f"文档解析超时（{timeout}s），未完成: {', '.join(pending)}")

    async def fetch_document_chunks_text(self, dataset_id: str, document_id: str) -> str:
        parts: list[str] = []
        page = 1
        page_size = 50
        async with httpx.AsyncClient(timeout=60.0) as client:
            while True:
                resp = await client.get(
                    f"{self.base_url}/api/v1/datasets/{dataset_id}/documents/{document_id}/chunks",
                    headers=self._headers(json_body=False),
                    params={"page": page, "page_size": page_size},
                )
                resp.raise_for_status()
                data = self._check_response(resp.json())
                chunks = data.get("chunks") or []
                if not chunks:
                    break
                for chunk in chunks:
                    content = chunk.get("content") or chunk.get("content_with_weight") or ""
                    if content.strip():
                        parts.append(content.strip())
                if len(chunks) < page_size:
                    break
                page += 1
        return "\n\n".join(parts)

    async def collect_corpus(
        self, dataset_id: str, document_ids: list[str], source_names: dict[str, str]
    ) -> str:
        sections: list[str] = []
        for doc_id in document_ids:
            text = await self.fetch_document_chunks_text(dataset_id, doc_id)
            if text:
                label = source_names.get(doc_id, doc_id)
                sections.append(f"=== 资料：{label} ===\n{text}")
        return "\n\n".join(sections)

    async def list_chats(self, page_size: int = 20) -> list[dict]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v1/chats",
                headers=self._headers(json_body=False),
                params={"page": 1, "page_size": page_size},
            )
            resp.raise_for_status()
            data = self._check_response(resp.json())
            return data.get("chats") or []

    async def resolve_chat_id(self) -> str:
        if self.settings.ragflow_chat_id:
            return self.settings.ragflow_chat_id
        if self._cached_chat_id:
            return self._cached_chat_id

        chats = await self.list_chats()
        if not chats:
            raise RagflowError(
                "未找到 RAGFlow 对话助手。请在 RAGFlow 控制台创建一个 Chat Assistant，"
                "或在 backend/.env 中设置 RAGFLOW_CHAT_ID"
            )

        self._cached_chat_id = chats[0]["id"]
        logger.info(
            "Auto-selected RAGFlow chat assistant: %s (%s)",
            chats[0].get("name") or "unnamed",
            self._cached_chat_id,
        )
        return self._cached_chat_id

    async def chat_extract_concepts(self, subject_name: str, corpus: str, count: int = 10) -> list[dict]:
        prompt = self._build_extraction_prompt(subject_name, corpus, count)
        content = await self._call_llm(prompt)
        return self._parse_concept_json(content)

    async def chat_messages(self, messages: list[dict]) -> str:
        return await self._call_llm_messages(messages)

    async def _call_llm(self, prompt: str) -> str:
        return await self._call_llm_messages([{"role": "user", "content": prompt}])

    async def _call_llm_messages(self, messages: list[dict]) -> str:
        chat_id = await self.resolve_chat_id()
        body: dict = {
            "stream": False,
            "messages": messages,
            "model": "model",
        }

        urls = [
            f"{self.base_url}/api/v1/openai/{chat_id}/chat/completions",
            f"{self.base_url}/api/v1/chats_openai/{chat_id}/chat/completions",
        ]

        last_error: Exception | None = None
        for url in urls:
            try:
                async with httpx.AsyncClient(timeout=180.0) as client:
                    resp = await client.post(url, headers=self._headers(), json=body)
                    if resp.status_code == 404:
                        continue
                    resp.raise_for_status()
                    return self._parse_llm_response(resp.text)
            except httpx.HTTPStatusError as exc:
                last_error = exc
                if exc.response.status_code == 404:
                    continue
                raise RagflowError(f"RAGFlow 模型调用失败 ({exc.response.status_code}): {exc.response.text[:200]}") from exc
            except Exception as exc:
                last_error = exc
                raise RagflowError(f"RAGFlow 模型调用失败: {exc}") from exc

        raise RagflowError(
            "RAGFlow 对话接口不可用。请确认 RAGFLOW_CHAT_ID 正确，"
            "或在 RAGFlow 中创建 Chat Assistant。"
            + (f" 详情: {last_error}" if last_error else "")
        )

    def _parse_llm_response(self, raw: str) -> str:
        # OpenAI-compatible JSON
        try:
            result = json.loads(raw)
            if "choices" in result:
                return result["choices"][0]["message"]["content"]
            if result.get("code") == 0:
                data = result.get("data")
                if isinstance(data, dict) and data.get("answer"):
                    return data["answer"]
        except json.JSONDecodeError:
            pass

        # RAGFlow SSE: data:{...}
        answer = self._parse_sse_answer(raw)
        if answer:
            return answer

        raise RagflowError("无法解析 LLM 响应")

    @staticmethod
    def _parse_sse_answer(raw: str) -> str:
        last = ""
        for line in raw.splitlines():
            line = line.strip()
            if not line.startswith("data:"):
                continue
            payload = line[5:].strip()
            if payload in {"true", "[DONE]"}:
                continue
            try:
                obj = json.loads(payload)
            except json.JSONDecodeError:
                continue
            data = obj.get("data")
            if isinstance(data, dict) and data.get("answer"):
                last = data["answer"]
        return last

    @staticmethod
    def _build_extraction_prompt(subject_name: str, corpus: str, count: int = 10) -> str:
        count = max(1, min(50, count))
        return f"""你是一位专业的学习资料分析助手。请仔细阅读以下「{subject_name}」课程资料原文，抽取其中的**专业术语**并生成知识卡片。

**只抽取专业术语（必须来自资料原文）：**
- 学科专用词汇、核心概念名称（如：熵、梯度下降、进程调度）
- 定理/定律/效应的名称（只抽名称，不抽公式）
- 领域内的专有名词（模型名、算法名、协议名等）

**不要抽取：**
- 日常通用词（如：方法、问题、系统、研究、分析）
- 数学/物理/化学公式或纯符号算式
- 章节标题、页码、作者姓名等非术语内容

**每个术语输出一个 JSON 对象：**
- concept: 术语名称（简短，如「熵」）
- type: term | theorem | definition | other（不要用 formula）
- summary: 简介，**一句话**，**不超过20个汉字**，基于资料解释该术语核心含义，不要只重复术语名
- detail: 具体介绍，**不超过100字**，基于资料展开说明（定义/背景/应用/意义等），句子之间用中文句号分隔

**格式示例（仅供理解字段要求，不要照抄内容）：**
术语：熵
简介：系统混乱程度或不确定性的度量。
具体介绍：它源于热力学，刻画孤立系统中热量与温度之比，并揭示了熵增原理——自发过程总使无序度增加，直至平衡态。在信息论里，熵用于量化信息源的平均信息量，不确定性越高则熵越大。日常生活中，破镜难重圆、冰自然融化等现象都是熵增的体现。因此，熵被视为理解宇宙演化方向的关键标尺。

**输出要求：**
- 仅返回 JSON 数组，不要 markdown，不要其他文字
- 抽取 {count} 个最重要的专业术语，按重要性排序
- summary 严格不超过20字，detail 严格不超过5句，内容必须能在资料中找到依据

**资料原文：**
{corpus[:12000]}
"""

    @staticmethod
    def _parse_concept_json(content: str) -> list[dict]:
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1]
            if text.endswith("```"):
                text = text.rsplit("```", 1)[0]
        start = text.find("[")
        end = text.rfind("]") + 1
        if start < 0 or end <= start:
            raise RagflowError("LLM 未返回有效的 JSON 数组")
        items = json.loads(text[start:end])
        if not isinstance(items, list):
            raise RagflowError("LLM 返回格式错误")
        return items
