from __future__ import annotations

from dataclasses import dataclass
import re
import logging

from app.clients.local_llm_client import LocalLLMClient
from app.clients.ragflow_client import RagflowClient
from app.services.prompt_templates import (
    ASSISTANT_SYSTEM_PROMPT,
    EVALUATION_PROMPT,
    QUESTION_PROMPT,
    TERM_EXTRACTION_PROMPT,
    FLASHCARD_PROMPT,
)

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    score: int
    feedback: str
    correction: str
    missing_points: list[str]


class AssistantService:
    def __init__(self) -> None:
        self.rag_client = RagflowClient()
        self.llm_client = LocalLLMClient()

    async def build_flashcards(self, material_text: str, count: int, user_level: str) -> list[dict[str, str]]:
        # LLM-first strategy: ask the model to output JSON cards, validate; if fails, fallback to rule-based
        language = self._detect_material_language(material_text)
        prompt = FLASHCARD_PROMPT.format(
            material=material_text[:6000],
            count=count,
            language_rule=self._flashcard_language_rule(language),
        )
        cards: list[dict[str, str]] = []
        raw_responses: list[str] = []

        for attempt in range(2):
            temperature = 0.2 if attempt == 0 else 0.0
            try:
                raw = await self.llm_client.chat(ASSISTANT_SYSTEM_PROMPT, prompt, temperature=temperature)
            except Exception as exc:
                logger.warning("LLM call failed on attempt %s: %s", attempt, exc)
                raw = ""
            raw_responses.append(raw)
            parsed = self.llm_client.parse_json_block(raw)
            if self._validate_cards_structure(parsed):
                try:
                    for item in parsed.get("cards", [])[:count]:
                        concept = str(item.get("concept", "")).strip()
                        explanation = str(item.get("explanation", "")).strip()
                        example = (
                            str(item.get("example", "")).strip() if item.get("example") is not None else ""
                        )
                        if not concept or not explanation:
                            continue
                        cards.append({"concept": concept, "explanation": explanation, "example": example})
                    if cards:
                        return await self._format_flashcards_for_output(cards[:count], language)
                except Exception:
                    logger.exception("Error processing parsed cards")

        # if reached here, LLM output not valid — log raw responses and fallback
        logger.warning("LLM did not produce valid flashcards; raw responses: %s", raw_responses)

        # Fallback: use structured terms and simple extraction
        terms = await self._extract_card_terms(material_text, count=count)
        seen: set[str] = set()
        for concept in terms:
            if concept in seen:
                continue
            seen.add(concept)
            cards.append(
                {
                    "concept": concept,
                    "explanation": self._fallback_explanation(concept, material_text),
                    "example": self._fallback_example(concept, material_text),
                }
            )

        default_fill = ["核心概念", "关键机制", "典型场景", "应用方法", "常见误区"]
        idx = 0
        while len(cards) < count:
            concept = default_fill[idx % len(default_fill)]
            idx += 1
            if concept in seen:
                continue
            seen.add(concept)
            cards.append(
                {
                    "concept": concept,
                    "explanation": self._fallback_explanation(concept, material_text),
                    "example": self._fallback_example(concept, material_text),
                }
            )

        return await self._format_flashcards_for_output(cards[:count], language)

    async def _extract_card_terms(self, material_text: str, count: int) -> list[str]:
        terms = self._clean_terms(self._extract_structured_terms(material_text))
        if len(terms) < count:
            prompt = TERM_EXTRACTION_PROMPT.format(material=material_text[:6000], count=max(count * 2, count))
            response = await self.llm_client.chat(ASSISTANT_SYSTEM_PROMPT, prompt)
            parsed = self.llm_client.parse_json_block(response)

            raw_terms = parsed.get("terms") if isinstance(parsed.get("terms"), list) else []
            for term in self._clean_terms([str(item) for item in raw_terms if str(item).strip()]):
                if term not in terms:
                    terms.append(term)
                if len(terms) >= count:
                    break
        if len(terms) < count:
            for term in self._clean_terms(self.rag_client.extract_keywords(material_text, count=count * 2)):
                if term not in terms:
                    terms.append(term)
                if len(terms) >= count:
                    break
        return terms

    @staticmethod
    def _extract_structured_terms(material_text: str) -> list[str]:
        terms: list[str] = []
        for fragment in re.split(r"[。！？\n]", material_text):
            line = fragment.strip()
            if not line:
                continue
            prefix = line.split("：", 1)[0].split(":", 1)[0].strip()
            if not prefix:
                continue
            if len(prefix) < 2 or len(prefix) > 20:
                continue
            if any(ch.isspace() for ch in prefix):
                continue
            if prefix not in terms:
                terms.append(prefix)
        return terms

    @staticmethod
    def _clean_terms(raw_terms: list[str]) -> list[str]:
        if not raw_terms:
            return []

        generic_noise = {
            "课程",
            "资料",
            "可以",
            "我们",
            "这个",
            "一个",
            "通过",
            "要求",
            "输出",
            "内容",
            "知识",
            "概念",
            "关键定义",
            "核心概念",
            "典型例子",
            "关键机制",
            "典型场景",
            "应用方法",
            "常见误区",
        }

        cleaned: list[str] = []
        seen: set[str] = set()
        for item in raw_terms:
            term = str(item).strip().strip('"\'`，。；：、,.')
            if not term or term in seen:
                continue
            if len(term) < 2 or len(term) > 20:
                continue
            if "�" in term:
                continue

            if term in generic_noise or term.lower() in generic_noise:
                continue

            if re.fullmatch(r"[\W_]+", term):
                continue

            seen.add(term)
            cleaned.append(term)
        return cleaned

    async def generate_guided_question(self, concept: str, user_level: str, material_text: str, dataset_id: str = "") -> tuple[str, list[str]]:
        concept = self._normalize_concept(concept, material_text)
        references = await self.rag_client.retrieve(concept, material_text, top_k=3, dataset_id=dataset_id)
        if not references:
            references = self._split_sentences(material_text, limit=3)

        prompt = QUESTION_PROMPT.format(
            language=self._question_language_label(material_text),
            level=user_level,
            concept=concept,
            evidence="\n".join(f"- {ref}" for ref in references),
        )
        raw_question = await self.llm_client.chat(ASSISTANT_SYSTEM_PROMPT, prompt)
        question = await self._normalize_question_output(raw_question, concept, references, material_text, user_level)
        if self._is_llm_question_acceptable(question, concept):
            final_question = question
        else:
            final_question = self._make_concise_question(question, concept, references, user_level)
        compact_refs = self._compact_references(references, concept, final_question)
        return final_question, compact_refs

    async def format_supporting_points_for_output(self, points: list[str], material_text: str) -> list[str]:
        _ = material_text
        cache: dict[str, str] = {}
        formatted: list[str] = []
        for item in points:
            text = str(item).strip()
            if not text:
                continue
            normalized = await self._to_chinese_text(text, cache)
            if normalized and normalized not in formatted:
                formatted.append(normalized)
        return formatted

    @staticmethod
    def _validate_cards_structure(parsed: dict) -> bool:
        if not isinstance(parsed, dict):
            return False
        cards = parsed.get("cards")
        if not isinstance(cards, list) or not cards:
            return False
        for item in cards:
            if not isinstance(item, dict):
                return False
            concept = item.get("concept")
            explanation = item.get("explanation")
            if not concept or not explanation:
                return False
        return True

    async def evaluate_answer(
        self,
        concept: str,
        question: str,
        answer: str,
        references: list[str],
    ) -> EvalResult:
        basis_points = self._derive_basis_points(concept, references, question=question)
        prompt = EVALUATION_PROMPT.format(
            concept=concept,
            question=question,
            answer=answer,
            evidence="\n".join(f"- {ref}" for ref in references),
            basis_points="\n".join(f"- {point}" for point in basis_points),
        )
        raw = await self.llm_client.chat(ASSISTANT_SYSTEM_PROMPT, prompt)
        parsed = self.llm_client.parse_json_block(raw)

        score = int(parsed.get("score", self._consistency_score(answer, basis_points)))
        feedback = str(parsed.get("feedback", "答案和资料有部分偏差，请补充关键条件。"))
        correction = str(parsed.get("correction", "请根据知识源重新组织定义、条件和例子。"))
        missing_points = parsed.get("missing_points") if isinstance(parsed.get("missing_points"), list) else []
        if isinstance(parsed.get("basis_points"), list) and parsed.get("basis_points"):
            basis_points = [str(item) for item in parsed.get("basis_points") if str(item).strip()]

        return EvalResult(score=score, feedback=feedback, correction=correction, missing_points=missing_points)

    @staticmethod
    def _consistency_score(answer: str, references: list[str]) -> int:
        if not references:
            return 60

        evidence_text = " ".join(references)
        answer_tokens = set(answer.lower().split())
        evidence_tokens = set(evidence_text.lower().split())
        if not answer_tokens:
            return 0

        overlap = len(answer_tokens & evidence_tokens)
        ratio = overlap / max(len(answer_tokens), 1)
        raw_score = ratio * 100 + 30
        bounded = int(min(100, max(0, raw_score)))
        return int(bounded)

    @staticmethod
    def _normalize_concept(concept: str, material_text: str) -> str:
        candidate = concept.strip()
        if candidate and not AssistantService._is_bad_concept(candidate):
            return candidate

        keywords = RagflowClient.extract_keywords(material_text, count=8)
        for kw in keywords:
            text = str(kw).strip()
            if text and not AssistantService._is_bad_concept(text):
                return text

        for term in AssistantService._extract_structured_terms(material_text):
            text = str(term).strip()
            if text and not AssistantService._is_bad_concept(text):
                return text

        return "课程核心概念"

    @staticmethod
    def _is_bad_concept(text: str) -> bool:
        token = str(text or "").strip().lower().strip("'\"`.,:;!?()[]{}")
        if not token:
            return True

        bad_words = {
            "why", "what", "how", "when", "where", "which", "who", "whom", "whose",
            "question", "questions", "answer", "answers", "material", "materials",
            "concept", "concepts", "example", "examples", "please", "define", "definition",
            "课程", "资料", "问题", "答案", "概念", "核心概念",
        }
        if token in bad_words:
            return True

        if len(token) <= 1:
            return True

        if re.fullmatch(r"[\W_]+", token):
            return True

        return False

    @staticmethod
    def _split_sentences(text: str, limit: int = 3) -> list[str]:
        chunks = [chunk.strip() for chunk in re.split(r"[\n。！？]", text) if chunk.strip()]
        return chunks[:limit]

    def _fallback_explanation(self, concept: str, material_text: str) -> str:
        sentences = self._split_sentences(material_text, limit=8)
        matched = next((sentence for sentence in sentences if concept and concept in sentence), "")
        if matched:
            detail = re.split(r"[:：]", matched, 1)
            if len(detail) == 2 and detail[1].strip():
                return f"{concept}：{detail[1].strip()[:70]}"
            return f"{concept}：{matched[:70]}"
        if sentences:
            return f"{concept}：{sentences[0][:70]}"
        return f"{concept} 是资料中的关键概念。"

    def _fallback_example(self, concept: str, material_text: str) -> str:
        sentences = self._split_sentences(material_text, limit=8)
        for sentence in sentences:
            if concept and concept in sentence:
                continue
            if sentence:
                return sentence[:80]
        return ""

    def _derive_basis_points(self, concept: str, references: list[str], question: str = "") -> list[str]:
        q = question.strip()
        if not q:
            q = self._make_concise_question("", concept, references, "beginner")

        evidence_hint = self._concept_reference_focus(references, concept)

        if "是什么" in q or "定义" in q:
            points = [
                f"准确说出 {concept} 的核心定义",
                "使用课件中的关键术语，不要改写成相反结论",
                f"可结合证据短句：{evidence_hint}",
            ]
        elif "方法" in q or "性质" in q or "特点" in q:
            points = [
                f"列出 {concept} 的方法/性质（建议至少2点）",
                "每一点都要能在课件证据中找到对应表述",
                f"可优先覆盖：{evidence_hint}",
            ]
        else:
            points = [
                f"围绕 {concept} 直接回答问题，不偏题",
                "答案应与课件证据一致，不添加无依据结论",
                f"可参考证据短句：{evidence_hint}",
            ]

        cleaned: list[str] = []
        for item in points:
            text = str(item).strip()
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned[:6]

    def _make_concise_question(self, question: str, concept: str, references: list[str], user_level: str) -> str:
        q = self._sanitize_question_text(question)
        if self._is_concise_question(q):
            return q if q.endswith(("？", "?")) else q + "？"

        q_type = self._question_type_from_context(q, references, user_level)
        # Choose from a small set of concise templates to avoid always returning the exact same sentence
        templates = []
        if q_type == "methods":
            templates = [
                f"{concept}有哪些方法或性质？",
                f"关于{concept}，常见的方法或性质有哪些？",
                f"列举{concept}的主要性质或方法。",
            ]
        elif q_type == "condition":
            templates = [
                f"{concept}在什么条件下成立？",
                f"哪些条件会导致{concept}成立？",
                f"影响{concept}成立的关键因素有哪些？",
            ]
        else:
            templates = [
                f"{concept}是什么？",
                f"如何定义{concept}？",
                f"{concept}的核心含义是什么？",
            ]

        # deterministic selection per concept to add variation across concepts while keeping tests stable
        try:
            idx = abs(hash(concept)) % len(templates)
        except Exception:
            idx = 0
        return templates[idx]

    @staticmethod
    def _is_llm_question_acceptable(question: str, concept: str) -> bool:
        q = str(question or "").strip()
        if not q:
            return False
        if len(q) < 8 or len(q) > 56:
            return False
        if not q.endswith(("？", "?")):
            return False
        if q.startswith(("请解释该概念", "请说明一下", "请回答以下问题")):
            return False
        # Reject overly generic placeholder phrases that don't reference the concept
        lower_q = q.lower()
        bad_placeholders = ("该点", "该概念", "该问题", "该点涉及", "该要点")
        if any(ph in lower_q for ph in bad_placeholders):
            return False

        if concept and concept not in q and len(re.findall(r"[\u4e00-\u9fffA-Za-z]", q)) < 10:
            return False
        return True

    @staticmethod
    def _is_concise_question(question: str) -> bool:
        if not question:
            return False
        if len(question) > 28:
            return False
        if not question.endswith(("？", "?")):
            return False
        if any(mark in question for mark in ["，", "；", "：", ",", ";", ":"]):
            return False
        return True

    @staticmethod
    def _question_type_from_context(question: str, references: list[str], user_level: str) -> str:
        combined = f"{question} {' '.join(references)}".lower()
        if any(word in combined for word in ["方法", "性质", "特点", "步骤", "类型", "principle", "method", "property"]):
            return "methods"
        if any(word in combined for word in ["条件", "前提", "边界", "机制", "condition", "mechanism"]):
            return "condition"
        _ = user_level
        return "definition"

    def _compact_references(self, references: list[str], concept: str, question: str) -> list[str]:
        if not references:
            return []

        q_type = self._question_type_from_context(question, references, "beginner")
        selected: list[str] = []
        concept_refs = [str(ref).strip() for ref in references if concept and concept in str(ref)]
        source_refs = concept_refs if concept_refs else [str(ref).strip() for ref in references]

        for text in source_refs:
            if not text:
                continue
            if q_type == "methods" and not any(k in text for k in ["方法", "性质", "特点", "类型", "步骤"]):
                continue
            compact = re.sub(r"\s+", "", text)
            compact = re.sub(r"[。！？!?]+$", "", compact)
            compact = compact[:36]
            if compact and compact not in selected:
                selected.append(compact)
            if len(selected) >= 2:
                break

        if not selected:
            fallback = [re.sub(r"\s+", "", str(ref).strip())[:36] for ref in references if str(ref).strip()]
            selected = [item for item in fallback if item][:2]

        return selected

    @staticmethod
    def _question_language_label(material_text: str) -> str:
        _ = material_text
        return "中文"

    @staticmethod
    def _flashcard_language_rule(language: str) -> str:
        _ = language
        return "默认中文输出；术语可保留英文原名。"

    @staticmethod
    def _detect_material_language(text: str) -> str:
        cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", text))
        latin_chars = len(re.findall(r"[A-Za-z]", text))
        if cjk_chars == 0 and latin_chars == 0:
            return "zh"
        if cjk_chars >= latin_chars:
            return "zh"
        return "en"

    async def _normalize_question_output(
        self,
        raw_question: str,
        concept: str,
        references: list[str],
        material_text: str,
        user_level: str,
    ) -> str:
        language = self._detect_material_language(material_text)
        question = self._sanitize_question_text(raw_question)

        if self._should_fallback_question(question, language):
            question = self._fallback_question(concept, references, user_level, language)

        if language == "zh":
            if not question.endswith(("？", "?")):
                question = question.rstrip("。.!！") + "？"
            return question

        question_zh = await self._translate_to_chinese(question)
        if not question_zh:
            question_zh = self._fallback_question(concept, references, user_level, "zh")
        if not question_zh.endswith(("？", "?")):
            question_zh = question_zh.rstrip("。.!！") + "？"
        return question_zh

    async def _format_flashcards_for_output(self, cards: list[dict[str, str]], language: str) -> list[dict[str, str]]:
        _ = language
        cache: dict[str, str] = {}
        formatted: list[dict[str, str]] = []
        for item in cards:
            concept = await self._to_chinese_text(str(item.get("concept", "")).strip(), cache)
            explanation = await self._to_chinese_text(str(item.get("explanation", "")).strip(), cache)
            example_raw = str(item.get("example", "")).strip()
            example = await self._to_chinese_text(example_raw, cache) if example_raw else ""
            if not concept or not explanation:
                continue
            formatted.append({"concept": concept, "explanation": explanation, "example": example})
        return formatted if formatted else cards

    async def _to_chinese_text(self, text: str, cache: dict[str, str]) -> str:
        plain = text.strip()
        if not plain:
            return ""
        if re.search(r"[\u4e00-\u9fff]", plain):
            return plain

        # If a bilingual line is returned upstream, keep only the Chinese part.
        if "中文:" in plain:
            zh = plain.split("中文:", 1)[1].strip().strip("| ")
            if zh:
                return zh

        chinese = cache.get(plain)
        if chinese is None:
            chinese = await self._translate_to_chinese(plain)
            cache[plain] = chinese

        if not chinese:
            return plain
        return chinese

    async def _translate_to_chinese(self, text: str) -> str:
        raw = str(text or "").strip()
        if not raw:
            return ""
        if re.search(r"[\u4e00-\u9fff]", raw):
            return raw

        prompt = (
            "将下列英文改写为简洁自然的中文，保留原意，不要解释。"
            "只输出中文一句话。\n"
            f"英文: {raw}"
        )
        try:
            translated = await self.llm_client.chat(ASSISTANT_SYSTEM_PROMPT, prompt, temperature=0.0)
        except Exception:
            return ""
        text_out = self._sanitize_question_text(translated)
        if not text_out or re.search(r"[A-Za-z]{4,}", text_out):
            return ""
        return text_out


    @staticmethod
    def _sanitize_question_text(text: str) -> str:
        question = str(text or "").strip().strip('"“”')
        return question.replace("\n", " ").strip()

    @staticmethod
    def _should_fallback_question(question: str, language: str) -> bool:
        if not question:
            return True

        if len(question) < 6 or len(question) > 160:
            return True

        generic_prefixes = (
            "请解释",
            "请说明",
            "请问",
            "请回答",
            "根据资料请",
            "根据课程资料请",
            "please explain",
            "please describe",
            "what is the concept",
            "explain the concept",
        )
        lowered = question.lower()
        if any(lowered.startswith(prefix) for prefix in generic_prefixes):
            return True

        if language == "zh":
            cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", question))
            latin_chars = len(re.findall(r"[A-Za-z]", question))
            if cjk_chars == 0 or latin_chars > cjk_chars * 2:
                return True
        else:
            latin_chars = len(re.findall(r"[A-Za-z]", question))
            cjk_chars = len(re.findall(r"[\u4e00-\u9fff]", question))
            if latin_chars == 0 or cjk_chars > latin_chars:
                return True

        return False

    @staticmethod
    def _fallback_question(concept: str, references: list[str], user_level: str, language: str) -> str:
        focus = AssistantService._reference_focus(references, concept)
        level = user_level.strip().lower()

        if language == "zh":
            if level in {"beginner", "初级", "基础"}:
                return f"根据资料，{concept} 的核心定义是什么？"
            if level in {"advanced", "高级"}:
                return f"结合资料中的“{focus}”，{concept} 在什么边界条件下最容易被误解？"
            return f"结合资料中的“{focus}”，{concept} 的条件或作用机制是什么？"

        if level in {"beginner", "初级", "基础"}:
            return f"According to the material, what is the definition of {concept}?"
        if level in {"advanced", "高级"}:
            return f"Based on the material, under what boundary conditions is {concept} most likely to be misunderstood?"
        return f"Based on the material, what conditions or mechanism does {concept} involve?"

    @staticmethod
    def _reference_focus(references: list[str], concept: str) -> str:
        for reference in references:
            focus = reference.strip()
            if not focus:
                continue
            focus = re.sub(r"[。！？!?]+$", "", focus)
            if concept and concept in focus:
                continue
            return focus[:28]
        return concept or "the material"

    @staticmethod
    def _concept_reference_focus(references: list[str], concept: str) -> str:
        if concept:
            for reference in references:
                text = str(reference).strip()
                if text and concept in text:
                    return re.sub(r"[。！？!?]+$", "", text)[:28]
        return AssistantService._reference_focus(references, concept)

