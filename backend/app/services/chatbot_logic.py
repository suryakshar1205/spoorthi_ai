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

    if not _has_fest_intent(normalized):
        small_talk_response = _small_talk_response(normalized)
        if small_talk_response:
            return small_talk_response

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


def _small_talk_response(normalized_query: str) -> str | None:
    greeting_terms = {"hi", "hello", "hey", "hii", "good morning", "good evening", "good afternoon"}
    gratitude_terms = {"thank you", "thanks", "thankyou"}
    closing_terms = {"bye", "goodbye", "see you"}
    checkin_terms = {"how are you", "how are u", "how r u", "what s up", "whats up", "who are you"}

    if normalized_query in greeting_terms:
        return (
            "Hello! I am Spoorthi Chatbot.\n"
            "I can help you with:\n"
            "- Event timings\n"
            "- Venue and location details\n"
            "- Registration and participation info"
        )
    if any(term in normalized_query for term in checkin_terms):
        return (
            "Hello! I am doing well.\n"
            "I am here to help with Spoorthi fest information like timings, venues, events, and registrations."
        )
    if any(term in normalized_query for term in gratitude_terms):
        return "You are welcome. If you need fest details, I am here to help."
    if any(term in normalized_query for term in closing_terms):
        return "Glad to help. See you soon at Spoorthi."

    words = normalized_query.split()
    if len(words) <= 4 and any(word in {"hi", "hello", "hey"} for word in words):
        return (
            "Hi there! I can help with Spoorthi event schedules, locations, and registrations.\n"
            "What would you like to know?"
        )
    return None


def _has_fest_intent(normalized_query: str) -> bool:
    fest_terms = {
        "spoorthi",
        "fest",
        "event",
        "events",
        "hackathon",
        "coding",
        "contest",
        "workshop",
        "robotics",
        "venue",
        "location",
        "timing",
        "schedule",
        "registration",
        "organizer",
        "coordinator",
        "rules",
    }
    return any(term in normalized_query.split() for term in fest_terms)


def _matches(normalized_query: str, phrase: str) -> bool:
    return phrase in normalized_query


def _matches_any(normalized_query: str, *phrases: str) -> bool:
    return any(phrase in normalized_query for phrase in phrases)
