from __future__ import annotations

import pytest

from app.services.chatbot_logic import route_predefined_query


def test_prefetched_questions_return_exact_answers() -> None:
    assert route_predefined_query("What is Spoorthi Fest?") == (
        "Spoorthi Fest is an annual techno-cultural symposium organized by the ECE department of JNTUH. "
        "It brings students together for technical events, workshops, and creative activities."
    )
    assert route_predefined_query("what is spoorthi fest") == (
        "Spoorthi Fest is an annual techno-cultural symposium organized by the ECE department of JNTUH. "
        "It brings students together for technical events, workshops, and creative activities."
    )
    assert route_predefined_query("Who are the student coordinators?") == (
        "The student coordinators include Naveen, Nikitha, Aditya Singh, and Yashashwini. "
        "They manage event execution, coordination, and participant support during the fest."
    )
    assert route_predefined_query("What is the role of IEEE in Spoorthi?") == (
        "IEEE Student Branch JNTUH provides funding and technical support. "
        "It helps promote innovation and professional development among students."
    )
    assert route_predefined_query("Which companies are involved in the fest?") == (
        "Companies like MathWorks, Physitech Electronics, BrainOVision, and ICICI Bank are involved. "
        "They support workshops, hackathons, and overall fest activities."
    )


@pytest.mark.parametrize(
    ("query", "expected_heading"),
    [
        ("PCB Workshop", "PCB Workshop Details"),
        ("AI and IoT Workshop", "AI and IoT Workshop Details"),
        ("Hackathon", "Hackathon Details"),
        ("Flashmob", "Flashmob Details"),
        ("Art Room", "Art Room Details"),
        ("Tech Room", "Tech Room Details"),
        ("Tech Treasure Hunt", "Tech Treasure Hunt Details"),
        ("IDEATHON", "IDEATHON Details"),
        ("Code Clutch", "Code Clutch Details"),
        ("Logic Combat", "Logic Combat Details"),
        ("Tech Quiz", "Tech Quiz Details"),
        ("Proto Circuit", "Proto Circuit Details"),
        ("Posteriza", "Posteriza Details"),
    ],
)
def test_event_names_return_details(query: str, expected_heading: str) -> None:
    response = route_predefined_query(query)
    assert response is not None
    assert expected_heading in response


@pytest.mark.parametrize(
    ("query", "expected_heading"),
    [
        (" pcb   workshop details ", "PCB Workshop Details"),
        ("aiiot workshop", "AI and IoT Workshop Details"),
        ("hackthon", "Hackathon Details"),
        ("flash mob details", "Flashmob Details"),
        ("artroom", "Art Room Details"),
        ("techroom", "Tech Room Details"),
        ("tech treasure hant", "Tech Treasure Hunt Details"),
        ("idea thon", "IDEATHON Details"),
        ("codng contest", "Code Clutch Details"),
        ("logic combt", "Logic Combat Details"),
        ("technical quizz", "Tech Quiz Details"),
        ("proto circuut", "Proto Circuit Details"),
        ("poster presentation", "Posteriza Details"),
    ],
)
def test_event_queries_tolerate_minor_typos_and_spacing(query: str, expected_heading: str) -> None:
    response = route_predefined_query(query)
    assert response is not None
    assert expected_heading in response


def test_location_queries_return_location_fallback_when_not_specified() -> None:
    response = route_predefined_query("Where is hackthon?")
    assert response == "Hackathon Location Details:\n- Location: Not specified in the current context."


@pytest.mark.parametrize(
    ("query", "expected_answer"),
    [
        (
            "Who is Veda?",
            "Veda is the Coordinator of Hackathon and Coordinator of Art Room.",
        ),
        (
            "who is surya coordinator",
            "Surya is the Coordinator of Tech Room.",
        ),
        (
            "tell me about jithendra",
            "Jithendra is the Coordinator of Code Clutch.",
        ),
        (
            "adithya singh",
            "Adithya Singh is the Coordinator of Flashmob.",
        ),
        (
            "who is srujth",
            "Srujith is the Coordinator of Logic Combat.",
        ),
    ],
)
def test_coordinator_name_queries_return_event_roles(query: str, expected_answer: str) -> None:
    assert route_predefined_query(query) == expected_answer
