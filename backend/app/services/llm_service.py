from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import re

from app.config import Settings
from app.utils.text import extract_keywords, fuzzy_token_hits, normalize_query_text, normalize_source_text, normalize_text


logger = logging.getLogger(__name__)
FALLBACK_ANSWER = "I don’t have that information. Please contact the organizers."
CONTEXT_BLOCK_RE = re.compile(
    r"(?:\[(?P<index>\d+)\]\s+Source:\s*(?P<source>[^\n]+)\nSection:\s*(?P<section>[^\n]+)\nContent:\s*(?P<content>.*?))(?=(?:\n\[\d+\]\s+Source:)|$)",
    re.DOTALL,
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
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"(?:\+?\d[\d\s\-]{8,}\d)")
COORD_RE = re.compile(r"\bco\s+ord(?:\s+inator)?s?\b", re.IGNORECASE)
REPORT_SECTION_RE = re.compile(r"^(?:\d+\.\s+)?(?P<title>[A-Za-z][A-Za-z0-9 &+/'()-]{2,90})$")
EVENT_LINE_RE = re.compile(
    r"^(?P<name>[A-Za-z][A-Za-z0-9 &+/'()-]{2,80}?)(?:\s*\([^)]*\))?\s*(?:[:\-–—]|$)",
    re.IGNORECASE,
)
IGNORED_EVENT_TITLES = {
    "about jntuh",
    "about the ece department",
    "available events",
    "contacts",
    "cultural and engagement activities",
    "event overview",
    "institutional context",
    "institutional overview & event identity",
    "history & evolution",
    "organization & management",
    "leadership & coordinators",
    "master schedule",
    "promotional activities",
    "registration details",
    "rules and participation notes",
    "technical competitions",
    "technical events & event heads",
    "faculty team",
    "sponsors & partnerships",
    "legacy & social impact",
    "venue directory",
    "workshops",
    "workshops and emerging tech",
}
FIELD_LABELS = {
    "category": "Category",
    "faculty coordinator": "Faculty Coordinator",
    "faculty coordinators": "Faculty Coordinators",
    "group event limit": "Team Size",
    "group event size": "Team Size",
    "id requirement": "ID Requirement",
    "location": "Location",
    "official email": "Official Email",
    "official web platforms": "Official Web Platforms",
    "participation": "Participation",
    "phone": "Phone",
    "registration help desk": "Registration Help Desk",
    "registration help desk location": "Registration Help Desk",
    "spot registration": "Spot Registration",
    "student coordinator": "Student Coordinator",
    "student coordinators": "Student Coordinators",
    "student coordinator contact number": "Student Coordinator Contact Number",
    "support email": "Support Email",
    "support phone": "Support Phone",
    "team size": "Team Size",
    "time": "Time",
}

FIELD_ALIASES = {
    "faculty coordinators": "faculty coordinator",
    "student coordinators": "student coordinator",
}

FALLBACK_ANSWER = "I don't have that information. Please contact the organizers."


class ProviderError(RuntimeError):
    """Raised when local response generation cannot complete a request."""


@dataclass(slots=True)
class EventCard:
    title: str
    fields: dict[str, str]
    lines: list[str]


@dataclass(slots=True)
class ContextBlock:
    section: str
    source: str
    content: str


class LocalProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate_response(self, context: str, query: str) -> str:
        context = normalize_source_text(context)
        if not context or context == "NO_CONTEXT_FOUND":
            return FALLBACK_ANSWER

        blocks = self._extract_context_blocks(context)
        retrieved_context = "\n\n".join(block.content for block in blocks if block.content.strip())
        if not retrieved_context.strip():
            retrieved_context = self._extract_retrieved_context(context)
        if not retrieved_context.strip():
            return FALLBACK_ANSWER

        query_text = normalize_query_text(query)
        query_tokens = set(extract_keywords(query_text))
        if not query_tokens:
            query_tokens = set(extract_keywords(query_text, keep_generic_terms=True))

        schedule_items = self._extract_schedule_items(retrieved_context)
        event_cards = self._extract_event_cards(retrieved_context)
        self._merge_event_cards_into_schedule(schedule_items, event_cards)
        fields = self._extract_fields(retrieved_context)
        sentences = self._extract_sentences(retrieved_context)

        if any(
            term in query_text
            for term in ("contact", "coordinator", "coord", "faculty", "organizer", "email", "phone", "help desk")
        ):
            answer = self._answer_contact(query_text, fields, sentences)
            if answer:
                return answer

        if any(
            term in query_text
            for term in (
                "list all events",
                "available events",
                "what are the events",
                "which events",
                "what events are happening",
                "events are happening",
                "what events",
                "happening today",
            )
        ):
            answer = self._answer_event_list(schedule_items, event_cards, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("today", "schedule", "agenda", "happening", "timing")):
            answer = self._answer_schedule(query_text, query_tokens, schedule_items, event_cards)
            if answer:
                return answer

        if any(term in query_text for term in ("register", "registration", "help desk", "id card")):
            answer = self._answer_registration(fields)
            if answer:
                return answer

        if any(term in query_text for term in ("where", "venue", "location", "hall", "room", "auditorium", "lab")):
            answer = self._answer_location(query_tokens, schedule_items, event_cards, fields, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("rule", "rules", "allowed", "coding contest")):
            answer = self._answer_rules(query_tokens, event_cards, fields, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("beginner", "beginners", "suggest")):
            answer = self._answer_beginner_events(schedule_items, event_cards, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("workshop", "presentation", "expo", "challenge", "quiz", "contest", "hackathon")):
            answer = self._answer_event_specific(query_text, query_tokens, schedule_items, event_cards, sentences)
            if answer:
                return answer

        if any(term in query_text for term in ("history", "legacy", "overview", "about", "what is")):
            answer = self._answer_overview(sentences)
            if answer:
                return answer

        answer = self._answer_generic(query_tokens, schedule_items, event_cards, sentences)
        return answer or FALLBACK_ANSWER

    def _extract_context_blocks(self, context: str) -> list[ContextBlock]:
        blocks: list[ContextBlock] = []
        for match in CONTEXT_BLOCK_RE.finditer(context):
            section = normalize_text(match.group("section"))
            source = normalize_text(match.group("source"))
            content = normalize_source_text(match.group("content"))
            if not content:
                continue
            blocks.append(ContextBlock(section=section or "general", source=source or "document", content=content))
        return blocks

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
            label = FIELD_ALIASES.get(label, label)
            value = normalize_text(match.group("value"))
            if label and value and label not in fields:
                fields[label] = value
        return fields

    def _extract_event_cards(self, text: str) -> list[EventCard]:
        cards: list[EventCard] = []
        for block in [part.strip() for part in re.split(r"\n{2,}", text) if part.strip()]:
            lines = [line.strip() for line in block.splitlines() if line.strip()]
            if len(lines) < 2:
                continue

            title = self._clean_report_title(lines[0].lstrip("#").strip())
            lowered_title = title.lower()

            report_cards = self._extract_report_style_cards(lowered_title, title, lines[1:])
            if report_cards:
                cards.extend(report_cards)
                continue

            if (
                not title
                or ":" in title
                or lowered_title in IGNORED_EVENT_TITLES
                or any(term in lowered_title for term in ("contact", "overview", "registration", "rules", "schedule", "venue"))
            ):
                continue

            fields: dict[str, str] = {}
            for line in lines[1:]:
                if ":" not in line:
                    continue
                key, value = line.split(":", 1)
                normalized_key = normalize_text(key).lower()
                normalized_value = normalize_text(value)
                if normalized_key and normalized_value:
                    fields[normalized_key] = normalized_value

            if len(fields) >= 2:
                cards.append(EventCard(title=title, fields=fields, lines=lines))
        return cards

    def _clean_report_title(self, title: str) -> str:
        match = REPORT_SECTION_RE.match(normalize_text(title))
        if not match:
            return normalize_text(title)
        return normalize_text(match.group("title"))

    def _extract_report_style_cards(self, lowered_title: str, title: str, body_lines: list[str]) -> list[EventCard]:
        cards: list[EventCard] = []

        if lowered_title == "workshops":
            for line in body_lines:
                card = self._card_from_named_line(line, details_key="details")
                if card:
                    cards.append(card)
            return cards

        if lowered_title == "technical events & event heads":
            for line in body_lines:
                card = self._card_from_named_line(line, details_key="coordinators")
                if card:
                    cards.append(card)
            return cards

        if lowered_title == "experience zones":
            for line in body_lines:
                card = self._card_from_named_line(line, details_key="managed by")
                if card:
                    cards.append(card)
            return cards

        if lowered_title == "hackathon":
            fields: dict[str, str] = {}
            for line in body_lines:
                if ":" in line:
                    key, value = line.split(":", 1)
                    fields[normalize_text(key).lower()] = normalize_text(value)
                else:
                    fields.setdefault("details", normalize_text(line))
            if fields:
                return [EventCard(title=title, fields=fields, lines=[title, *body_lines])]

        if lowered_title == "promotional activities":
            for line in body_lines:
                normalized_line = normalize_text(line)
                if not normalized_line:
                    continue
                cards.append(EventCard(title="Flashmob", fields={"details": normalized_line}, lines=[title, normalized_line]))
            return cards

        return cards

    def _card_from_named_line(self, line: str, *, details_key: str) -> EventCard | None:
        normalized_line = normalize_text(line)
        if not normalized_line:
            return None

        if details_key == "coordinators":
            match = re.match(r"^(?P<title>.+?)\s*[-–—]\s*Coordinators?\s*:\s*(?P<value>.+)$", normalized_line, re.IGNORECASE)
            if match:
                return EventCard(
                    title=self._clean_report_title(match.group("title")),
                    fields={"coordinators": normalize_text(match.group("value"))},
                    lines=[normalized_line],
                )

        if ":" in normalized_line:
            raw_title, raw_value = normalized_line.split(":", 1)
            title = self._clean_report_title(raw_title)
            value = normalize_text(raw_value)
            if not title or not value:
                return None

            if details_key == "details" and "Coordinators:" in value:
                details_part, coordinators_part = value.split("Coordinators:", 1)
                fields = {"details": normalize_text(details_part)}
                if normalize_text(coordinators_part):
                    fields["coordinators"] = normalize_text(coordinators_part)
                return EventCard(title=title, fields=fields, lines=[normalized_line])

            return EventCard(title=title, fields={details_key: value}, lines=[normalized_line])

        return None

    def _extract_sentences(self, text: str) -> list[str]:
        cleaned = text.replace("|", " ")
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        parts = [part.strip(" -") for part in SENTENCE_RE.split(cleaned) if part.strip()]
        return [normalize_text(part) for part in parts if len(normalize_text(part)) >= 12]

    def _answer_contact(self, query_text: str, fields: dict[str, str], sentences: list[str]) -> str | None:
        wants_faculty = "faculty" in query_text and "coordinator" in query_text
        wants_student = "student" in query_text and "coordinator" in query_text
        wants_current = any(term in query_text for term in ("current", "present", "now", "latest"))
        faculty_value = self._resolve_field(fields, "faculty coordinator")
        student_value = self._resolve_field(fields, "student coordinator")
        student_contact_number = self._resolve_field(fields, "student coordinator contact number")
        official_email = self._resolve_field(fields, "official email", "support email")
        phone_value = self._resolve_field(fields, "support phone", "phone")

        if wants_faculty and faculty_value:
            lines = [
                "- Faculty Coordinator: " + faculty_value,
            ]
            if official_email:
                lines.append("- Official Email: " + official_email)
            return "Faculty Coordinator Details:\n" + "\n".join(lines)

        if wants_student and student_value:
            lines = [
                "- Student Coordinator: " + student_value,
            ]
            if student_contact_number:
                lines.append("- Student Coordinator Contact Number: " + student_contact_number)
            elif phone_value:
                lines.append("- Phone: " + phone_value)
            if official_email:
                lines.append("- Official Email: " + official_email)
            return "Student Coordinator Details:\n" + "\n".join(lines)

        contact_points: list[str] = []
        preferred_keys = (
            "faculty coordinator",
            "student coordinator",
            "student coordinator contact number",
            "support email",
            "official email",
            "support phone",
            "phone",
            "official web platforms",
            "registration help desk",
        )

        for key in preferred_keys:
            value = self._resolve_field(fields, key)
            if value:
                contact_points.append(f"- {self._field_label(key)}: {value}")

        if not wants_faculty and not wants_student and "coordinator" in query_text and (faculty_value or student_value):
            prioritized = []
            if faculty_value:
                prioritized.append(f"- Faculty Coordinator: {faculty_value}")
            if student_value:
                prioritized.append(f"- Student Coordinator: {student_value}")
            if student_contact_number:
                prioritized.append(f"- Student Coordinator Contact Number: {student_contact_number}")
            elif phone_value:
                prioritized.append(f"- Phone: {phone_value}")
            if official_email:
                prioritized.append(f"- Official Email: {official_email}")
            if prioritized:
                return "Organizer Contact Details:\n" + "\n".join(prioritized[:5])

        if not contact_points:
            for sentence in sentences:
                lowered = sentence.lower()
                if wants_current and "historical" in lowered:
                    continue
                if EMAIL_RE.search(sentence) or PHONE_RE.search(sentence) or any(
                    term in lowered for term in ("coordinator", "organizer", "contact", "help desk")
                ):
                    contact_points.append(f"- {sentence}")
                if len(contact_points) >= 5:
                    break

        if not contact_points:
            return None
        return "Organizer Contact Details:\n" + "\n".join(self._dedupe(contact_points)[:5])

    def _answer_event_list(
        self,
        items: list[dict[str, str]],
        event_cards: list[EventCard],
        sentences: list[str],
    ) -> str | None:
        grouped = self._collect_event_groups(items, event_cards, sentences)

        lines = ["Here are the main Spoorthi activities mentioned in the current context:"]

        if grouped["workshops"]:
            lines.append("- Workshops: " + ", ".join(grouped["workshops"][:4]))
        if grouped["competitions"]:
            lines.append("- Technical Events: " + ", ".join(grouped["competitions"][:7]))
        if grouped["activities"]:
            lines.append("- Other Highlights: " + ", ".join(grouped["activities"][:5]))

        if len(lines) > 1:
            return "\n".join(lines)

        seen: set[str] = set()
        fallback_lines = ["Available Events:"]

        for item in items:
            event_name = normalize_text(item["event"])
            normalized = event_name.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            summary = []
            if item.get("time") and item["time"] != "Time not specified":
                summary.append(item["time"])
            if item.get("location") and item["location"] != "Location not specified":
                summary.append(item["location"])
            suffix = f" ({' | '.join(summary)})" if summary else ""
            fallback_lines.append(f"- {event_name}{suffix}")
            if len(fallback_lines) >= 7:
                return "\n".join(fallback_lines)

        for card in event_cards:
            normalized = card.title.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            summary_bits = []
            if card.fields.get("time"):
                summary_bits.append(card.fields["time"])
            if card.fields.get("location"):
                summary_bits.append(card.fields["location"])
            suffix = f" ({' | '.join(summary_bits)})" if summary_bits else ""
            fallback_lines.append(f"- {card.title}{suffix}")
            if len(fallback_lines) >= 7:
                break

        return "\n".join(fallback_lines) if len(fallback_lines) > 1 else None

    def _answer_schedule(
        self,
        query_text: str,
        query_tokens: set[str],
        items: list[dict[str, str]],
        event_cards: list[EventCard],
    ) -> str | None:
        if not items:
            best_card = self._best_event_card(query_tokens, event_cards)
            if best_card:
                return self._format_event_card(best_card, heading=f"{best_card.title} Details:")
            return None

        ranked = self._rank_schedule_items(query_tokens, items)
        if "workshop" in query_text:
            workshop_items = [
                item
                for item in items
                if "workshop" in item["event"].lower() and item["time"] != "Time not specified"
            ]
            if workshop_items:
                lines = ["Here are the workshop timings available in the fest context:"]
                for item in workshop_items[:4]:
                    lines.append(f"- {item['time']}: {item['event']} ({item['location']})")
                return "\n".join(lines)

        if (
            ranked
            and ranked[0][0] >= 0.5
            and ranked[0][1]["time"] != "Time not specified"
            and not any(term in query_text for term in ("today", "happening", "schedule", "agenda", "timing", "workshops", "events"))
        ):
            item = ranked[0][1]
            return (
                f"{item['event']} Details:\n"
                f"- Time: {item['time']}\n"
                f"- Location: {item['location']}"
            )

        lines = ["Here is the schedule available in the current fest context:"]
        for item in [item for item in items if item["time"] != "Time not specified"][:6]:
            lines.append(f"- {item['time']}: {item['event']} ({item['location']})")
        return "\n".join(lines) if len(lines) > 1 else None

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
        event_cards: list[EventCard],
        fields: dict[str, str],
        sentences: list[str],
    ) -> str | None:
        best_card = self._best_event_card(query_tokens, event_cards)
        if best_card and ("location" in best_card.fields or "venue" in best_card.fields):
            return self._format_event_card(best_card, heading=f"{best_card.title} Details:")

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

    def _answer_rules(
        self,
        query_tokens: set[str],
        event_cards: list[EventCard],
        fields: dict[str, str],
        sentences: list[str],
    ) -> str | None:
        best_card = self._best_event_card(query_tokens, event_cards)
        if best_card and any(key in best_card.fields for key in ("team size", "participation", "category", "rules")):
            return self._format_event_card(best_card, heading=f"{best_card.title} Details:")

        points = []
        for key in ("rules", "id requirement", "group event limit", "late entry", "judging"):
            if key in fields:
                points.append(f"- {self._field_label(key)}: {fields[key]}")
        if not points:
            rule_sentences = [
                sentence
                for sentence in sentences
                if any(term in sentence.lower() for term in ("participants", "judges", "late entry", "team", "id card"))
            ]
            points = [f"- {sentence}" for sentence in rule_sentences[:4]]
        if not points:
            return None
        return "Rules and Guidelines:\n" + "\n".join(points[:5])

    def _answer_beginner_events(
        self,
        schedule_items: list[dict[str, str]],
        event_cards: list[EventCard],
        sentences: list[str],
    ) -> str | None:
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
            for card in event_cards:
                lowered = card.title.lower()
                if any(term in lowered for term in preferred_terms):
                    suggestions.append(f"- {card.title}")
                if len(suggestions) >= 4:
                    break

        if not suggestions:
            return None

        intro = "Here are a few beginner-friendly options from the available fest context:"
        return intro + "\n" + "\n".join(suggestions[:4])

    def _collect_event_groups(
        self,
        items: list[dict[str, str]],
        event_cards: list[EventCard],
        sentences: list[str],
    ) -> dict[str, list[str]]:
        groups = {
            "workshops": [],
            "competitions": [],
            "activities": [],
        }
        seen: set[str] = set()

        def add_event(name: str) -> None:
            cleaned = normalize_text(name)
            if not cleaned:
                return
            normalized = cleaned.lower().strip(" .:-")
            if (
                not normalized
                or normalized in seen
                or normalized in IGNORED_EVENT_TITLES
                or normalized.startswith("spoorthi fest")
                or "coordinator" in normalized
                or "team" in normalized
                or "department" in normalized
                or normalized.startswith("history")
                or normalized.startswith("organization")
            ):
                return

            seen.add(normalized)

            if "workshop" in normalized:
                groups["workshops"].append(cleaned)
            elif any(
                term in normalized
                for term in ("hackathon", "treasure hunt", "ideathon", "code clutch", "logic combat", "quiz", "circuit", "posteriza")
            ):
                groups["competitions"].append(cleaned)
            elif any(term in normalized for term in ("flashmob", "art room", "tech room", "experience zone")):
                groups["activities"].append(cleaned)
            else:
                groups["activities"].append(cleaned)

        for item in items:
            add_event(item["event"])

        for card in event_cards:
            add_event(card.title)

        for sentence in sentences:
            candidate = sentence.strip()
            if len(candidate) > 120:
                continue
            match = EVENT_LINE_RE.match(candidate)
            if match:
                add_event(match.group("name"))

        return groups

    def _answer_event_specific(
        self,
        query_text: str,
        query_tokens: set[str],
        schedule_items: list[dict[str, str]],
        event_cards: list[EventCard],
        sentences: list[str],
    ) -> str | None:
        if "workshop" in query_text:
            workshop_sentences = [
                sentence
                for sentence in self._top_sentences(query_tokens, sentences, limit=5)
                if "workshop" in sentence.lower()
            ]
            if workshop_sentences:
                heading = "Here are the workshop details available in the current context:"
                return heading + "\n" + "\n".join(f"- {sentence}" for sentence in workshop_sentences[:4])

        best_card = self._best_event_card(query_tokens, event_cards)
        if best_card:
            return self._format_event_card(best_card, heading=f"{best_card.title} Details:")

        ranked_schedule = self._rank_schedule_items(query_tokens, schedule_items)
        if ranked_schedule and ranked_schedule[0][0] >= 0.4:
            lines = ["Here are the most relevant event details I found:"]
            for _, item in ranked_schedule[:3]:
                lines.append(f"- {item['event']}: {item['time']} ({item['location']})")
            return "\n".join(self._dedupe(lines))

        top_sentences = self._top_sentences(query_tokens, sentences, limit=4)
        if not top_sentences:
            return None

        heading = "Here are the most relevant event details I found:"
        return heading + "\n" + "\n".join(f"- {sentence}" for sentence in top_sentences)

    def _answer_overview(self, sentences: list[str]) -> str | None:
        overview_terms = ("spoorthi", "jntuh", "ece", "technical", "techno-cultural", "flagship", "2004", "2009")
        selected = [sentence for sentence in sentences if sum(term in sentence.lower() for term in overview_terms) >= 2]
        if not selected:
            return None
        lines = ["Here is a quick overview of Spoorthi:"]
        for sentence in self._dedupe(selected)[:5]:
            lines.append(f"- {sentence}")
        return "\n".join(lines)

    def _answer_generic(
        self,
        query_tokens: set[str],
        schedule_items: list[dict[str, str]],
        event_cards: list[EventCard],
        sentences: list[str],
    ) -> str | None:
        best_card = self._best_event_card(query_tokens, event_cards)
        if best_card:
            return self._format_event_card(best_card, heading=f"{best_card.title} Details:")

        ranked_schedule = self._rank_schedule_items(query_tokens, schedule_items)
        if ranked_schedule and ranked_schedule[0][0] >= 0.4:
            item = ranked_schedule[0][1]
            return (
                f"{item['event']} Details:\n"
                f"- Time: {item['time']}\n"
                f"- Location: {item['location']}"
            )

        top_sentences = self._top_sentences(query_tokens, sentences, limit=3)
        if not top_sentences:
            return None
        return "Here's what I found:\n" + "\n".join(f"- {sentence}" for sentence in top_sentences)

    def _rank_schedule_items(self, query_tokens: set[str], items: list[dict[str, str]]) -> list[tuple[float, dict[str, str]]]:
        ranked: list[tuple[float, dict[str, str]]] = []
        for item in items:
            haystack = normalize_query_text(f"{item['event']} {item['location']}")
            text_tokens = set(extract_keywords(haystack, keep_generic_terms=True))
            exact_hits, fuzzy_hits = fuzzy_token_hits(query_tokens, text_tokens)
            bonus = 0.2 if any(token in haystack for token in query_tokens if len(token) >= 4) else 0.0
            ranked.append((exact_hits + (fuzzy_hits * 0.65) + bonus, item))
        ranked.sort(key=lambda entry: entry[0], reverse=True)
        return ranked

    def _best_event_card(self, query_tokens: set[str], cards: list[EventCard]) -> EventCard | None:
        if not query_tokens or not cards:
            return None

        ranked: list[tuple[float, EventCard]] = []
        for card in cards:
            haystack = normalize_query_text(f"{card.title} {' '.join(f'{key} {value}' for key, value in card.fields.items())}")
            text_tokens = set(extract_keywords(haystack, keep_generic_terms=True))
            exact_hits, fuzzy_hits = fuzzy_token_hits(query_tokens, text_tokens)
            bonus = 0.2 if any(token in haystack for token in query_tokens if len(token) >= 4) else 0.0
            score = exact_hits + (fuzzy_hits * 0.65) + bonus
            if score > 0:
                ranked.append((score, card))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return ranked[0][1] if ranked else None

    def _merge_event_cards_into_schedule(self, items: list[dict[str, str]], cards: list[EventCard]) -> None:
        existing = {(item["event"].lower(), item["time"].lower()) for item in items}
        for card in cards:
            time = card.fields.get("time", "Time not specified")
            location = card.fields.get("location") or card.fields.get("venue") or "Location not specified"
            key = (card.title.lower(), time.lower())
            if key in existing:
                continue
            existing.add(key)
            items.append({"event": card.title, "time": time, "location": location})

    def _format_event_card(self, card: EventCard, *, heading: str) -> str:
        ordered_keys = (
            "location",
            "venue",
            "time",
            "team size",
            "participation",
            "category",
            "rules",
        )
        lines = [heading]
        used: set[str] = set()

        for key in ordered_keys:
            value = card.fields.get(key)
            if value:
                lines.append(f"- {self._field_label(key)}: {value}")
                used.add(key)

        for key, value in card.fields.items():
            if key in used:
                continue
            lines.append(f"- {self._field_label(key)}: {value}")
            if len(lines) >= 6:
                break

        return "\n".join(lines)

    def _field_label(self, key: str) -> str:
        normalized = normalize_text(key).lower()
        return FIELD_LABELS.get(normalized, normalized.title())

    def _resolve_field(self, fields: dict[str, str], *keys: str) -> str | None:
        for key in keys:
            normalized_key = FIELD_ALIASES.get(key, key)
            if normalized_key in fields:
                return fields[normalized_key]
        return None

    def _top_sentences(self, query_tokens: set[str], sentences: list[str], limit: int) -> list[str]:
        ranked: list[tuple[float, str]] = []
        for sentence in sentences:
            lowered = normalize_query_text(sentence)
            text_tokens = set(extract_keywords(lowered, keep_generic_terms=True))
            exact_hits, fuzzy_hits = fuzzy_token_hits(query_tokens, text_tokens)
            bonus = 0.2 if any(token in lowered for token in query_tokens if len(token) >= 4) else 0.0
            score = exact_hits + (fuzzy_hits * 0.65) + bonus
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

    async def generate_response(self, context: str, query: str) -> str:
        if not context or context == "NO_CONTEXT_FOUND":
            return FALLBACK_ANSWER

        answer = await self.local_provider.generate_response(context=context, query=query)
        cleaned = normalize_source_text(answer)
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned or FALLBACK_ANSWER

    async def stream_response(self, context: str, query: str):
        answer = await self.generate_response(context=context, query=query)
        tokens = re.findall(r"\S+\s*", answer)
        for token in tokens:
            yield token
            await asyncio.sleep(max(0, self.settings.response_stream_delay_ms) / 1000)
