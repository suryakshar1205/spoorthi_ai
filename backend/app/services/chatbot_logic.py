from __future__ import annotations

import re

from app.utils.text import normalize_query_text


FALLBACK_ANSWER = "I don't have that information. Please contact the organizers."

STARTER_QUESTIONS = (
    "What is Spoorthi Fest?",
    "Who is the coordinator of Spoorthi Fest?",
    "What workshops are conducted in Spoorthi?",
    "Who are the sponsors of Spoorthi Fest?",
)


def normalize_query(query: str) -> str:
    lowered = normalize_query_text(query)
    lowered = re.sub(r"\bcoordinator\s+s\b", " coordinators ", lowered)
    replacements = {
        "facult": "faculty",
        "coord": "coordinator",
        "coords": "coordinators",
        "organisers": "organizers",
    }
    for source, target in replacements.items():
        lowered = re.sub(rf"\b{source}\b", target, lowered)
    lowered = re.sub(r"\s+", " ", lowered)
    return lowered.strip()


def route_predefined_query(query: str) -> str | None:
    normalized = normalize_query(query)
    if not normalized:
        return None

    small_talk_response = _small_talk_response(normalized)
    if small_talk_response:
        return small_talk_response

    # Fest-specific questions should be answered from the current bundled/admin knowledge,
    # not from hardcoded shortcut text, so context file changes are reflected immediately
    # after backend restart.
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
            "- Event schedules and timings\n"
            "- Venue and registration details\n"
            "- Coordinator and organizer information"
        )
    if any(term in normalized_query for term in checkin_terms):
        return (
            "Hello! I am doing well.\n"
            "I am here to help with Spoorthi fest details like timings, venues, registrations, and organizer contacts."
        )
    if any(term in normalized_query for term in gratitude_terms):
        return "You are welcome. If you need any Spoorthi fest details, I am here to help."
    if any(term in normalized_query for term in closing_terms):
        return "Glad to help. See you soon at Spoorthi."

    words = normalized_query.split()
    if len(words) <= 4 and any(word in {"hi", "hello", "hey"} for word in words):
        return (
            "Hi there! I can help with Spoorthi schedules, locations, registrations, and organizer details.\n"
            "What would you like to know?"
        )
    return None


def _has_fest_intent(normalized_query: str) -> bool:
    fest_terms = {
        "spoorthi",
        "fest",
        "event",
        "events",
        "workshop",
        "registration",
        "paper",
        "presentation",
        "schedule",
        "timing",
        "venue",
        "location",
        "coordinator",
        "coordinators",
        "coord",
        "faculty",
        "student",
        "organizer",
        "rules",
        "symposium",
        "prize",
    }
    return any(term in normalized_query.split() for term in fest_terms)


def _matches_any(normalized_query: str, *phrases: str) -> bool:
    return any(phrase in normalized_query for phrase in phrases)
