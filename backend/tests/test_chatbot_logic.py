from __future__ import annotations

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
