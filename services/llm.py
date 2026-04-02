from __future__ import annotations

import re


FALLBACK_MESSAGE = "I don’t have that information. Please contact the event organizers."

STRICT_PROMPT_TEMPLATE = """You are Spoorthi AI, an intelligent and friendly assistant for a technical fest.

Guidelines:
- Answer ONLY from the given context
- Keep answers clear and well-structured
- Use bullet points if needed
- Be natural and conversational
- If answer is unknown, say:
  'I don’t have that information. Please contact the event organizers.'

Context:
{context}

Question:
{question}

Answer:"""


class LLMService:
    def generate_response(self, message: str, matches: list[dict[str, object]]) -> str:
        if not matches:
            return FALLBACK_MESSAGE

        context = "\n\n".join(str(match["text"]) for match in matches)
        prompt = STRICT_PROMPT_TEMPLATE.format(context=context, question=message)
        answer = self._compose_answer(message=message, context=context, prompt=prompt)
        return answer or FALLBACK_MESSAGE

    def _compose_answer(self, message: str, context: str, prompt: str) -> str:
        _ = prompt
        context = self._sanitize_context(context)
        message_lower = message.lower()
        blocks = self._parse_blocks(context)

        if not blocks:
            return FALLBACK_MESSAGE

        if any(word in message_lower for word in ["where", "location", "venue"]):
            block = self._find_best_event_block(message, blocks)
            if block:
                return self._format_event_details(block, intro=f"{block['section']} details:")

        if any(word in message_lower for word in ["time", "timing", "when", "schedule"]):
            block = self._find_best_event_block(message, blocks)
            if block:
                return self._format_event_details(block, intro=f"{block['section']} details:")
            return self._format_available_events(blocks)

        if any(word in message_lower for word in ["suggest", "available", "events", "list"]):
            return self._format_available_events(blocks)

        if any(word in message_lower for word in ["rule", "rules", "team size", "participation"]):
            block = self._find_best_event_block(message, blocks)
            if block:
                return self._format_event_details(block, intro=f"{block['section']} details:")

        if "spoorthi" in message_lower or "fest" in message_lower:
            overview = self._find_section(blocks, "Overview")
            if overview:
                return self._format_overview(overview)

        block = self._find_best_event_block(message, blocks)
        if block:
            return self._format_event_details(block, intro=f"{block['section']} details:")

        overview = self._find_section(blocks, "Overview")
        if overview:
            return self._format_overview(overview)

        return FALLBACK_MESSAGE

    @staticmethod
    def _parse_blocks(context: str) -> list[dict[str, object]]:
        lines = [line.strip() for line in context.splitlines()]
        blocks: list[dict[str, object]] = []
        current: dict[str, object] | None = None

        for line in lines:
            if not line:
                continue

            if line.lower().startswith("section:"):
                if current:
                    blocks.append(current)
                current = {"section": line.split(":", 1)[1].strip(), "fields": {}, "lines": []}
                continue

            if current is None:
                current = {"section": "General", "fields": {}, "lines": []}

            current["lines"].append(line)
            if ":" in line:
                key, value = line.split(":", 1)
                current["fields"][key.strip().lower()] = value.strip()

        if current:
            blocks.append(current)
        return blocks

    @staticmethod
    def _sanitize_context(context: str) -> str:
        context = context.replace("\r\n", "\n").replace("\r", "\n")
        context = re.sub(r"[*_`]+", "", context)
        context = re.sub(r"\[[0-9,\s]+\]", "", context)
        context = re.sub(r"^#{1,6}\s*", "", context, flags=re.MULTILINE)
        context = re.sub(r"^\|?[\s:-]+\|?$", "", context, flags=re.MULTILINE)
        context = re.sub(r"\n{3,}", "\n\n", context)
        return context.strip()

    @staticmethod
    def _find_section(blocks: list[dict[str, object]], section_name: str) -> dict[str, object] | None:
        target = section_name.lower()
        for block in blocks:
            if str(block["section"]).lower() == target:
                return block
        return None

    def _find_best_event_block(self, message: str, blocks: list[dict[str, object]]) -> dict[str, object] | None:
        query_terms = set(re.findall(r"[a-z0-9]+", message.lower()))
        best_block: dict[str, object] | None = None
        best_score = 0

        for block in blocks:
            section = str(block["section"])
            if section.lower() in {"overview", "available events"}:
                continue

            text = " ".join([section] + [str(line) for line in block["lines"]]).lower()
            score = sum(1 for term in query_terms if term in text)
            if any(keyword in section.lower() for keyword in ["location", "time", "venue", "schedule", "directory"]):
                score = max(score - 1, 0)
            if score > best_score:
                best_score = score
                best_block = block

        return best_block

    def _format_event_details(self, block: dict[str, object], intro: str) -> str:
        fields = block["fields"]
        ordered_keys = ["location", "time", "team size", "participation", "category"]
        lines = [intro]

        for key in ordered_keys:
            value = fields.get(key)
            if value:
                lines.append(f"- {self._label(key)}: {value}")

        if len(lines) == 1:
            for line in block["lines"]:
                cleaned = self._clean_output_line(str(line))
                if cleaned:
                    lines.append(f"- {cleaned}")

        return "\n".join(lines)

    def _format_available_events(self, blocks: list[dict[str, object]]) -> str:
        available_block = self._find_section(blocks, "Available Events")
        if available_block:
            lines = ["Here are the events currently available at Spoorthi:"]
            for line in available_block["lines"][:6]:
                cleaned = self._clean_output_line(str(line).lstrip("-").strip())
                if cleaned:
                    lines.append(f"- {cleaned}")
            if len(lines) > 1:
                return "\n".join(lines)

        event_blocks = [
            block
            for block in blocks
            if str(block["section"]).lower() not in {"overview", "available events"}
        ]

        if not event_blocks:
            return FALLBACK_MESSAGE

        lines = ["Here are the events currently available at Spoorthi:"]
        for block in event_blocks[:3]:
            fields = block["fields"]
            location = fields.get("location")
            timing = fields.get("time")
            summary_parts = []
            if timing:
                summary_parts.append(timing)
            if location:
                summary_parts.append(location)
            summary = " | ".join(summary_parts)
            if summary:
                lines.append(f"- {block['section']}: {summary}")
            else:
                lines.append(f"- {block['section']}")
        return "\n".join(lines)

    @staticmethod
    def _format_overview(block: dict[str, object]) -> str:
        lines = ["Here is a quick overview of Spoorthi:"]
        for line in block["lines"][:3]:
            cleaned = LLMService._clean_output_line(str(line))
            if cleaned:
                lines.append(f"- {cleaned}")
        return "\n".join(lines)

    @staticmethod
    def _clean_output_line(line: str) -> str:
        cleaned = re.sub(r"[*_`#]+", "", line)
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        cleaned = cleaned.strip(" -|")
        return cleaned.strip()

    @staticmethod
    def _label(key: str) -> str:
        labels = {
            "location": "Location",
            "time": "Time",
            "team size": "Team Size",
            "participation": "Participation",
            "category": "Category",
        }
        return labels.get(key, key.title())
