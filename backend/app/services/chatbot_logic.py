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

PREDEFINED_FEST_FAQ = {
    "What is Spoorthi Fest?": (
        "Spoorthi Fest is an annual techno-cultural symposium organized by the ECE department of JNTUH. "
        "It brings students together for technical events, workshops, and creative activities."
    ),
    "Where is Spoorthi Fest conducted?": (
        "Spoorthi Fest is conducted at the main engineering campus of JNTUH. "
        "It is hosted by the ECE department with participation from students across various colleges."
    ),
    "What type of events are there in Spoorthi?": (
        "Spoorthi includes technical events, workshops, hackathons, and cultural activities. "
        "It offers a mix of learning, competition, and creative engagement for students."
    ),
    "Why should I participate in Spoorthi Fest?": (
        "Participating in Spoorthi helps students develop technical skills, teamwork, and creativity. "
        "It also provides exposure to real-world challenges and collaborative learning experiences."
    ),
    "How is Spoorthi different from other college fests?": (
        "Spoorthi stands out by combining technical, cultural, and industry-oriented activities. "
        "It focuses on innovation, collaboration, and hands-on learning, making it more engaging and practical."
    ),
    "Who is the coordinator of Spoorthi Fest?": (
        "Dr. Anitha Sheela Kancharla is the faculty coordinator of Spoorthi Fest. "
        "She is a professor in the ECE department and also Director of the University Industry Interaction Centre."
    ),
    "Who are the student coordinators?": (
        "The student coordinators include Naveen, Nikitha, Aditya Singh, and Yashashwini. "
        "They manage event execution, coordination, and participant support during the fest."
    ),
    "How is Spoorthi Fest organized?": (
        "Spoorthi Fest is organized through teamwork between faculty and students. "
        "Students handle planning, coordination, and execution under the guidance of faculty members."
    ),
    "What roles do students play in organizing the fest?": (
        "Students take responsibility for planning, logistics, coordination, finance, and on-ground management. "
        "This involvement ensures smooth execution of all events and activities."
    ),
    "How does organizing Spoorthi help students gain experience?": (
        "Organizing the fest helps students gain practical experience in leadership, teamwork, communication, and event management. "
        "It prepares them for real-world professional challenges."
    ),
    "What workshops are conducted in Spoorthi?": (
        "Spoorthi features workshops like PCB Design and AI & IoT. "
        "These workshops focus on practical learning and exposure to industry-relevant technologies."
    ),
    "What is the PCB workshop about?": (
        "The PCB workshop covers schematic design, layout creation, and fabrication. "
        "It provides hands-on experience in circuit design and practical electronics applications."
    ),
    "What is the AI and IoT workshop?": (
        "This 2-day workshop includes AI-based image processing using MATLAB and IoT applications. "
        "It gives students practical exposure to modern technologies and real-world use cases."
    ),
    "What is the hackathon and how does it work?": (
        "The hackathon is a 2-day event where teams solve real-world problems. "
        "Participants build prototypes, collaborate, and present innovative solutions within a limited time."
    ),
    "What skills can I gain from workshops and hackathons?": (
        "Students gain skills in problem-solving, teamwork, technical design, and innovation. "
        "These events also improve time management and practical application of concepts."
    ),
    "What is the flashmob about?": (
        "The flashmob is a promotional activity conducted to attract attention and create excitement. "
        "It involves student participation and helps spread awareness about the fest."
    ),
    "What happens in the Tech Room?": (
        "The Tech Room features technical games, electronics-based activities, and working models. "
        "It allows students to explore practical engineering concepts interactively."
    ),
    "What is the Art Room?": (
        "The Art Room showcases decorations, paintings, and creative designs. "
        "It enhances the visual appeal of the fest and highlights students' artistic talents."
    ),
    "What fun activities are there in Spoorthi?": (
        "Spoorthi includes fun activities like flashmob, interactive tech games, and creative displays. "
        "These activities make the fest lively and engaging for participants."
    ),
    "What can I explore apart from technical events?": (
        "Apart from technical events, students can explore creative zones, cultural activities, and experience areas like Art Room and Tech Room."
    ),
    "What are the main technical events in Spoorthi?": (
        "Major events include Tech Treasure Hunt, IDEATHON, Code Clutch, Logic Combat, Tech Quiz, Proto Circuit, and Posteriza. "
        "These cover various technical and creative skills."
    ),
    "What is Code Clutch?": (
        "Code Clutch is a coding competition focused on programming, logical thinking, and problem-solving. "
        "It challenges participants to solve coding problems efficiently."
    ),
    "What is IDEATHON?": (
        "IDEATHON is an innovation-based event where participants present ideas and solutions to real-world challenges. "
        "It encourages creativity and problem-solving."
    ),
    "What is Tech Treasure Hunt?": (
        "Tech Treasure Hunt is a problem-solving event that combines clues, teamwork, and technical thinking. "
        "It makes learning interactive and engaging."
    ),
    "Which events are best for beginners?": (
        "Events like Tech Quiz, Posteriza, and Tech Treasure Hunt are beginner-friendly. "
        "They allow students to participate without requiring advanced technical skills."
    ),
    "How long has Spoorthi Fest been conducted?": (
        "Spoorthi Fest has been conducted for over 20 years. "
        "It has grown into a well-established event with increasing participation and impact."
    ),
    "Why is Spoorthi considered a flagship event?": (
        "Spoorthi is a flagship event of the ECE department due to its scale, diversity of events, and strong student participation."
    ),
    "What impact does Spoorthi have on students?": (
        "Spoorthi enhances technical knowledge, creativity, teamwork, and leadership skills. "
        "It also builds confidence and real-world exposure."
    ),
    "What social activities are part of Spoorthi?": (
        "Social initiatives include food donation drives and road safety awareness campaigns. "
        "These activities promote social responsibility among students."
    ),
    "Why do students participate in Spoorthi every year?": (
        "Students participate to learn new skills, compete, and gain exposure. "
        "It also provides opportunities for networking and personal development."
    ),
    "Who are the sponsors of Spoorthi Fest?": (
        "Sponsors include ECE Alumni, ICICI Bank, IEEE Student Branch JNTUH, OHM Institute, MathWorks, Physitech Electronics, and BrainOVision."
    ),
    "How do sponsors support the fest?": (
        "Sponsors provide financial support, technical resources, and expert guidance. "
        "Their contribution ensures smooth organization and better learning opportunities."
    ),
    "What is the role of IEEE in Spoorthi?": (
        "IEEE Student Branch JNTUH provides funding and technical support. "
        "It helps promote innovation and professional development among students."
    ),
    "How does industry collaboration help students?": (
        "Industry collaborations provide real-world exposure, expert mentorship, and access to tools and technologies used in professional environments."
    ),
    "Which companies are involved in the fest?": (
        "Companies like MathWorks, Physitech Electronics, BrainOVision, and ICICI Bank are involved. "
        "They support workshops, hackathons, and overall fest activities."
    ),
}


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


PREDEFINED_FEST_FAQ_BY_NORMALIZED_QUERY = {
    normalize_query(question): answer for question, answer in PREDEFINED_FEST_FAQ.items()
}


def route_predefined_query(query: str) -> str | None:
    normalized = normalize_query(query)
    if not normalized:
        return None

    small_talk_response = _small_talk_response(normalized)
    if small_talk_response:
        return small_talk_response

    predefined_faq_response = PREDEFINED_FEST_FAQ_BY_NORMALIZED_QUERY.get(normalized)
    if predefined_faq_response:
        return predefined_faq_response

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
