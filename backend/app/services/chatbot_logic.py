from __future__ import annotations

import re


FALLBACK_ANSWER = "I don’t have that information. Please contact the organizers."

STARTER_QUESTIONS = (
    "Where is Hackathon?",
    "What are the event timings?",
    "List all events",
    "Where is Robotics Workshop?",
)


def normalize_query(query: str) -> str:
    lowered = query.lower().strip()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def route_predefined_query(query: str) -> str | None:
    normalized = normalize_query(query)

    if not normalized:
        return None

    if _matches(normalized, "hackathon") and _matches_any(normalized, "where", "location", "venue"):
        return (
            "Hackathon Details:\n"
            "- Location: Block A Lab 3\n"
            "- Time: 10 AM to 6 PM\n"
            "- Team Size: 2 to 4 members"
        )

    if _matches(normalized, "robotics workshop") and _matches_any(normalized, "where", "location", "venue"):
        return (
            "Robotics Workshop Details:\n"
            "- Location: Block B Room 101\n"
            "- Time: 11 AM to 1 PM\n"
            "- Participation: Open to registered students"
        )

    if _matches(normalized, "coding contest") and _matches_any(normalized, "time", "timing", "when", "schedule"):
        return (
            "Coding Contest Details:\n"
            "- Time: 2 PM to 5 PM\n"
            "- Location: Seminar Hall\n"
            "- Participation: Individual"
        )

    if normalized in {
        "what are the event timings",
        "what are event timings",
        "show event timings",
        "show me the event timings",
        "what is the event timing",
    }:
        return (
            "Event Timings:\n"
            "- Hackathon: 10 AM to 6 PM\n"
            "- Coding Contest: 2 PM to 5 PM\n"
            "- Robotics Workshop: 11 AM to 1 PM"
        )

    if normalized in {
        "list all events",
        "show all events",
        "what are the events",
        "suggest events available",
        "suggest events",
    }:
        return (
            "Available Events:\n"
            "- Hackathon\n"
            "- Coding Contest\n"
            "- Robotics Workshop"
        )

    return None


def _matches(normalized_query: str, phrase: str) -> bool:
    return phrase in normalized_query


def _matches_any(normalized_query: str, *phrases: str) -> bool:
    return any(phrase in normalized_query for phrase in phrases)
