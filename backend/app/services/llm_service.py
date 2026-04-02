from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod

import httpx

from app.config import Settings
from app.utils.text import extract_keywords, normalize_source_text, normalize_text


logger = logging.getLogger(__name__)
FALLBACK_ANSWER = "I don’t have that information. Please contact the organizers."
STRICT_PROMPT_TEMPLATE = (
    "You are Spoorthi Chatbot, a helpful assistant for a technical fest.\n\n"
    "Guidelines:\n"
    "- Answer clearly and professionally\n"
    "- Use bullet points\n"
    "- Keep answers structured\n"
    "- Do NOT hallucinate\n"
    "- If unknown, say:\n"
    "  'I don’t have that information. Please contact the organizers.'\n\n"
    "Context:\n"
    "{context}\n\n"
    "Question:\n"
    "{question}\n\n"
    "Answer:"
)

SCHEDULE_TABLE_RE = re.compile(
    r"\|\s*(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM))\s*\|\s*(?P<event>[^|]+?)\s*\|\s*(?P<location>[^|]+?)\s*\|",
    re.IGNORECASE,
)
PLAIN_SCHEDULE_RE = re.compile(
    r"(?:^|\n)\s*(?:\d+\.\s*)?(?P<event>[A-Za-z][^:\n]{2,90}):\s*(?P<time>\d{1,2}:\d{2}\s*(?:AM|PM)(?:\s*to\s*\d{1,2}:\d{2}\s*(?:AM|PM))?)(?:\s*(?:at|in)\s*(?P<location>[^\n.]+))?",
    re.IGNORECASE,
)
PLAIN_FIELD_RE = re.compile(r"(?:^|\n)\s*(?:[-*]\s*)?(?P<label>[A-Za-z][A-Za-z /&()'-]{2,60}):\s*(?P<value>[^\n]+)")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+|\n+")


class ProviderError(RuntimeError):
    """Raised when an LLM provider cannot fulfill a request."""


class BaseProvider(ABC):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def generate_response(self, context: str, query: str) -> str:
        raise NotImplementedError

    def build_prompt(self, context: str, query: str) -> str:
        safe_context = context.strip() or FALLBACK_ANSWER
        return STRICT_PROMPT_TEMPLATE.format(context=safe_context, question=query.strip())


class OpenAIProvider(BaseProvider):
    endpoint = "https://api.openai.com/v1/chat/completions"

    async def generate_response(self, context: str, query: str) -> str:
        if not self.settings.openai_api_key:
            raise ProviderError("OPENAI_API_KEY is not configured.")

        prompt = self.build_prompt(context, query)
        payload = {
            "model": self.settings.openai_model,
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {"Authorization": f"Bearer {self.settings.openai_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(self.endpoint, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            try:
                error_payload = exc.response.json()
                error_message = error_payload.get("error", {}).get("message", exc.response.text)
            except ValueError:
                error_message = exc.response.text

            if status_code == 401:
                raise ProviderError("OpenAI rejected the API key. Check OPENAI_API_KEY in backend/.env.") from exc
            if status_code == 429:
                raise ProviderError("OpenAI rate limit or quota reached. Check your billing and usage limits.") from exc
            raise ProviderError(f"OpenAI request failed ({status_code}): {error_message}") from exc
        except httpx.RequestError as exc:
            raise ProviderError(
                "Could not reach OpenAI from the backend. Check your internet connection or firewall settings."
            ) from exc

        body = response.json()
        return self._clean_output(body["choices"][0]["message"]["content"].strip())

    def _clean_output(self, text: str) -> str:
        cleaned = normalize_source_text(text)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned or FALLBACK_ANSWER


class OllamaProvider(BaseProvider):
    async def generate_response(self, context: str, query: str) -> str:
        prompt = self.build_prompt(context, query)
        payload = {
            "model": self.settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.settings.temperature,
                "num_predict": self.settings.max_tokens,
            },
        }
        endpoint = f"{self.settings.ollama_base_url.rstrip('/')}/api/generate"
        try:
            async with httpx.AsyncClient(timeout=90) as client:
                response = await client.post(endpoint, json=payload)
                response.raise_for_status()
        except httpx.RequestError as exc:
            raise ProviderError("Could not reach Ollama. Make sure the Ollama server is running locally.") from exc
        except httpx.HTTPStatusError as exc:
            raise ProviderError(f"Ollama request failed ({exc.response.status_code}).") from exc

        body = response.json()
        answer = normalize_source_text(body.get("response", "").strip())
        if not answer:
            raise ProviderError("Ollama returned an empty response.")
        return answer


class LocalProvider(BaseProvider):
    async def generate_response(self, context: str, query: str) -> str:
        context = normalize_source_text(context)
        if not context or context == "NO_CONTEXT_FOUND":
            return FALLBACK_ANSWER

        retrieved_context = self._extract_retrieved_context(context)
        if not retrieved_context.strip():
            return FALLBACK_ANSWER

        query_text = query.lower()
        query_tokens = set(extract_keywords(query))
        if not query_tokens:
            query_tokens = set(extract_keywords(query, keep_generic_terms=True))

        schedule_items = self._extract_schedule_items(retrieved_context)
        fields = self._extract_fields(retrieved_context)
        sentences = self._extract_sentences(retrieved_context)

        if any(term in query_text for term in ("today", "schedule", "agenda", "happening", "timing")):
            answer = self._answer_schedule(query_text, query_tokens, schedule_items)
            if answer:
                return answer

        if any(term in query_text for term in ("register", "registration", "help desk", "id card")):
            answer = self._answer_registration(fields)
            if answer:
                return answer

        if any(term in query_text for term in ("where", "venue", "location", "hall", "room", "auditorium", "lab")):
            answer = self._answer_location(query_tokens, schedule_items, fields, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("rule", "rules", "allowed", "coding contest")):
            answer = self._answer_rules(fields, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("beginner", "beginners", "suggest")):
            answer = self._answer_beginner_events(schedule_items, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("history", "legacy", "overview", "about", "what is")):
            answer = self._answer_overview(sentences)
            if answer:
                return answer

        answer = self._answer_generic(query_tokens, sentences)
        return answer or FALLBACK_ANSWER

    def _extract_retrieved_context(self, context: str) -> str:
        matches = re.findall(r"Content:\s*(.*?)(?=(?:\n\[\d+\]\s+Source:)|$)", context, flags=re.DOTALL)
        if matches:
            return "\n\n".join(match.strip() for match in matches if match.strip())

        if "Retrieved context:" in context:
            return context.split("Retrieved context:", 1)[1].strip()

        return context

    def _extract_schedule_items(self, text: str) -> list[dict[str, str]]:
        items: list[dict[str, str]] = []

        for match in SCHEDULE_TABLE_RE.finditer(text):
            items.append(
                {
                    "time": normalize_text(match.group("time")),
                    "event": normalize_text(match.group("event")),
                    "location": normalize_text(match.group("location")),
                }
            )

        for match in PLAIN_SCHEDULE_RE.finditer(text):
            item = {
                "time": normalize_text(match.group("time")),
                "event": normalize_text(match.group("event")),
                "location": normalize_text(match.group("location") or "Location not specified"),
            }
            if not any(existing["event"].lower() == item["event"].lower() and existing["time"].lower() == item["time"].lower() for existing in items):
                items.append(item)

        return items

    def _extract_fields(self, text: str) -> dict[str, str]:
        fields: dict[str, str] = {}
        for match in PLAIN_FIELD_RE.finditer(text):
            label = normalize_text(match.group("label")).lower()
            value = normalize_text(match.group("value"))
            if label and value and label not in fields:
                fields[label] = value
        return fields

    def _extract_sentences(self, text: str) -> list[str]:
        cleaned = text.replace("|", " ")
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        parts = [part.strip(" -") for part in SENTENCE_RE.split(cleaned) if part.strip()]
        return [normalize_text(part) for part in parts if len(normalize_text(part)) >= 12]

    def _answer_schedule(self, query_text: str, query_tokens: set[str], items: list[dict[str, str]]) -> str | None:
        if not items:
            return None

        ranked = self._rank_schedule_items(query_tokens, items)
        if ranked and ranked[0][0] >= 0.5 and not any(term in query_text for term in ("today", "happening", "schedule", "agenda")):
            item = ranked[0][1]
            return (
                f"{item['event']} Details:\n"
                f"- Time: {item['time']}\n"
                f"- Location: {item['location']}"
            )

        if "workshop" in query_text:
            workshop_items = [item for item in items if "workshop" in item["event"].lower()]
            if workshop_items:
                lines = ["Here are the workshop timings available in the fest context:"]
                for item in workshop_items[:4]:
                    lines.append(f"- {item['time']}: {item['event']} ({item['location']})")
                return "\n".join(lines)

        lines = ["Here is the schedule available in the current fest context:"]
        for item in items[:6]:
            lines.append(f"- {item['time']}: {item['event']} ({item['location']})")
        return "\n".join(lines)

    def _answer_registration(self, fields: dict[str, str]) -> str | None:
        points = []
        for key in ("registration help desk", "spot registration", "id requirement", "group event limit", "registration help desk location"):
            if key in fields:
                points.append(f"- {key.title()}: {fields[key]}")
        if not points:
            return None
        return "Registration Details:\n" + "\n".join(points[:5])

    def _answer_location(
        self,
        query_tokens: set[str],
        schedule_items: list[dict[str, str]],
        fields: dict[str, str],
        sentences: list[str],
    ) -> str | None:
        ranked = self._rank_schedule_items(query_tokens, schedule_items)
        if ranked and ranked[0][0] >= 0.35:
            item = ranked[0][1]
            return (
                f"{item['event']} Details:\n"
                f"- Location: {item['location']}\n"
                f"- Time: {item['time']}"
            )

        if "registration" in query_tokens and "registration help desk" in fields:
            return f"Registration Help Desk:\n- Location: {fields['registration help desk']}"

        top_sentences = self._top_sentences(query_tokens, sentences, limit=2)
        if top_sentences:
            return "Here is the location information I found:\n" + "\n".join(f"- {sentence}" for sentence in top_sentences)
        return None

    def _answer_rules(self, fields: dict[str, str], sentences: list[str]) -> str | None:
        points = []
        for key in ("rules", "id requirement", "group event limit", "late entry", "judging"):
            if key in fields:
                points.append(f"- {key.title()}: {fields[key]}")
        if not points:
            rule_sentences = [sentence for sentence in sentences if any(term in sentence.lower() for term in ("participants", "judges", "late entry", "team", "id card"))]
            points = [f"- {sentence}" for sentence in rule_sentences[:4]]
        if not points:
            return None
        return "Rules and Guidelines:\n" + "\n".join(points[:5])

    def _answer_beginner_events(self, schedule_items: list[dict[str, str]], sentences: list[str]) -> str | None:
        suggestions: list[str] = []
        preferred_terms = ("workshop", "technical quiz", "poster", "project expo", "paper presentation")

        for item in schedule_items:
            if any(term in item["event"].lower() for term in preferred_terms):
                suggestions.append(f"- {item['event']} at {item['time']} ({item['location']})")

        if not suggestions:
            for sentence in sentences:
                lowered = sentence.lower()
                if any(term in lowered for term in preferred_terms):
                    suggestions.append(f"- {sentence}")
                if len(suggestions) >= 4:
                    break

        if not suggestions:
            return None

        intro = "Here are a few beginner-friendly options from the available fest context:"
        return intro + "\n" + "\n".join(suggestions[:4])

    def _answer_overview(self, sentences: list[str]) -> str | None:
        overview_terms = ("spoorthi", "jntuh", "ece", "technical", "techno-cultural", "flagship", "2004", "2009")
        selected = [sentence for sentence in sentences if sum(term in sentence.lower() for term in overview_terms) >= 2]
        if not selected:
            return None
        lines = ["Here is a quick overview of Spoorthi:"]
        for sentence in self._dedupe(selected)[:5]:
            lines.append(f"- {sentence}")
        return "\n".join(lines)

    def _answer_generic(self, query_tokens: set[str], sentences: list[str]) -> str | None:
        top_sentences = self._top_sentences(query_tokens, sentences, limit=3)
        if not top_sentences:
            return None
        if len(top_sentences) == 1:
            return top_sentences[0]
        return "Here’s what I found:\n" + "\n".join(f"- {sentence}" for sentence in top_sentences)

    def _rank_schedule_items(self, query_tokens: set[str], items: list[dict[str, str]]) -> list[tuple[float, dict[str, str]]]:
        ranked: list[tuple[float, dict[str, str]]] = []
        for item in items:
            haystack = f"{item['event']} {item['location']}".lower()
            overlap = len(query_tokens & set(extract_keywords(haystack, keep_generic_terms=True)))
            bonus = 0.2 if any(token in haystack for token in query_tokens if len(token) >= 4) else 0.0
            ranked.append((overlap + bonus, item))
        ranked.sort(key=lambda entry: entry[0], reverse=True)
        return ranked

    def _top_sentences(self, query_tokens: set[str], sentences: list[str], limit: int) -> list[str]:
        ranked: list[tuple[float, str]] = []
        for sentence in sentences:
            lowered = sentence.lower()
            overlap = len(query_tokens & set(extract_keywords(sentence, keep_generic_terms=True)))
            bonus = 0.2 if any(token in lowered for token in query_tokens if len(token) >= 4) else 0.0
            score = overlap + bonus
            if score <= 0:
                continue
            ranked.append((score, sentence))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return self._dedupe([sentence for _, sentence in ranked])[:limit]

    def _dedupe(self, sentences: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for sentence in sentences:
            normalized = sentence.lower().strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(sentence)
        return deduped


class LLMService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.local_provider = LocalProvider(settings)
        self.provider = self._create_provider(settings.llm_provider)

    def _create_provider(self, provider_name: str) -> BaseProvider:
        providers: dict[str, type[BaseProvider]] = {
            "openai": OpenAIProvider,
            "ollama": OllamaProvider,
            "local": LocalProvider,
        }
        provider_cls = providers.get(provider_name.lower())
        if provider_cls is None:
            raise ProviderError(f"Unsupported LLM_PROVIDER '{provider_name}'.")
        return provider_cls(self.settings)

    async def generate_response(self, context: str, query: str) -> str:
        if not context or context == "NO_CONTEXT_FOUND":
            return FALLBACK_ANSWER

        try:
            answer = await self.provider.generate_response(context=context, query=query)
        except ProviderError:
            if self.settings.local_fallback_enabled and not isinstance(self.provider, LocalProvider):
                logger.warning("Provider failed, falling back to local response generation.", exc_info=True)
                answer = await self.local_provider.generate_response(context=context, query=query)
            else:
                raise

        cleaned = normalize_source_text(answer)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned or FALLBACK_ANSWER

    async def stream_response(self, context: str, query: str):
        answer = await self.generate_response(context=context, query=query)
        tokens = re.findall(r"\S+\s*", answer)
        for token in tokens:
            yield token
            await asyncio.sleep(0.01)
