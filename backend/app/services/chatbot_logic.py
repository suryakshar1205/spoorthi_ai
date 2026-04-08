from __future__ import annotations

from difflib import SequenceMatcher
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

PREDEFINED_EVENT_DETAILS = {
    "PCB Workshop": {
        "details": (
            "PCB Workshop Details:\n"
            "- Dates: March 16-17\n"
            "- Duration: 2 days\n"
            "- Focus: PCB design, schematic creation, layout design, and fabrication\n"
            "- Coordinators: Yamini, Rajanna, Srinath, Tanveer\n"
            "- Outcome: Hands-on technical learning in circuit design and fabrication"
        ),
        "location": "Not specified in the current context.",
    },
    "AI and IoT Workshop": {
        "details": (
            "AI and IoT Workshop Details:\n"
            "- Duration: 2 days\n"
            "- Day 1: AI-based image processing using MATLAB\n"
            "- Day 2: Internet of Things (IoT) hands-on workshop\n"
            "- Expert Support: MathWorks speakers\n"
            "- Outcome: Practical exposure to emerging technologies and real-world applications"
        ),
        "location": "Not specified in the current context.",
    },
    "Hackathon": {
        "details": (
            "Hackathon Details:\n"
            "- Duration: 2 days\n"
            "- Focus: Solving real-world problems through teamwork, prototyping, and innovation\n"
            "- Skills Highlighted: Problem solving, teamwork, time management, technical creativity\n"
            "- Coordinators: Aditya, Naveen, Eswar, Veda, Nikhitha, Phaneendra, Vinay"
        ),
        "location": "Not specified in the current context.",
    },
    "Flashmob": {
        "details": (
            "Flashmob Details:\n"
            "- Location: Sarath City Capital Mall\n"
            "- Purpose: Promote the fest in a fun and engaging way\n"
            "- Participants: Students from 1st year to 4th year\n"
            "- Coordinators: Adithya Singh, Greeshmitha, Zoyan, Lasya"
        ),
        "location": "Sarath City Capital Mall",
    },
    "Art Room": {
        "details": (
            "Art Room Details:\n"
            "- Purpose: Decorations, paintings, themes, and visual design for the department during the fest\n"
            "- Coordinators: Veda, Akanksha, Rishikesh, Sindhuja"
        ),
        "location": "Not specified in the current context.",
    },
    "Tech Room": {
        "details": (
            "Tech Room Details:\n"
            "- Purpose: Technical games, electronics-based activities, working models, and project demonstrations\n"
            "- Coordinators: Surya, Srinidhi, Meghana, Neshitha, Sainag"
        ),
        "location": "Not specified in the current context.",
    },
    "Tech Treasure Hunt": {
        "details": (
            "Tech Treasure Hunt Details:\n"
            "- Description: A technical treasure hunt that combines clues, teamwork, and problem solving\n"
            "- Coordinators: Bhavana, Gagan, Sonal, Mahesh"
        ),
        "location": "Not specified in the current context.",
    },
    "IDEATHON": {
        "details": (
            "IDEATHON Details:\n"
            "- Description: An innovation-focused event where students present ideas and solutions to real-world challenges\n"
            "- Coordinators: Shashank, Akshay, Divya, Anuhya"
        ),
        "location": "Not specified in the current context.",
    },
    "Code Clutch": {
        "details": (
            "Code Clutch Details:\n"
            "- Description: A coding event that focuses on programming skill, logical thinking, and problem solving\n"
            "- Coordinators: Jithendra, Sharan, Sowmya Sri, Sravanthi"
        ),
        "location": "Not specified in the current context.",
    },
    "Logic Combat": {
        "details": (
            "Logic Combat Details:\n"
            "- Description: An event centered on analytical reasoning and challenging logic-based problems\n"
            "- Coordinators: Suraj, Srujith, Bhargavi, Rajeswari"
        ),
        "location": "Not specified in the current context.",
    },
    "Tech Quiz": {
        "details": (
            "Tech Quiz Details:\n"
            "- Description: A technical quiz covering multiple engineering and technology domains\n"
            "- Coordinators: Hrushikesh Reddy, Vaishnav, Ravali Sri, Harika"
        ),
        "location": "Not specified in the current context.",
    },
    "Proto Circuit": {
        "details": (
            "Proto Circuit Details:\n"
            "- Description: A circuit-based technical event encouraging practical electronics involvement\n"
            "- Coordinators: Swetha, Abhinikshith, Navya Sri, Mani Vivek"
        ),
        "location": "Not specified in the current context.",
    },
    "Posteriza": {
        "details": (
            "Posteriza Details:\n"
            "- Description: A creative poster presentation event for ideas, concepts, and research showcases\n"
            "- Coordinators: Maheshwar, Pavan, Mounika, Sadvi"
        ),
        "location": "Not specified in the current context.",
    },
}

PREDEFINED_EVENT_ALIASES = {
    "PCB Workshop": ("pcb workshop", "pcbworkshop", "pcb"),
    "AI and IoT Workshop": ("ai and iot workshop", "ai iot workshop", "ai workshop", "iot workshop", "aiiot workshop"),
    "Hackathon": ("hackathon", "hack athon", "hackthon"),
    "Flashmob": ("flashmob", "flash mob"),
    "Art Room": ("art room", "artroom"),
    "Tech Room": ("tech room", "techroom"),
    "Tech Treasure Hunt": ("tech treasure hunt", "treasure hunt", "techtreasurehunt"),
    "IDEATHON": ("ideathon", "idea thon", "ideaathon"),
    "Code Clutch": ("code clutch", "codeclutch", "coding contest", "coding event", "codng contest"),
    "Logic Combat": ("logic combat", "logiccombat"),
    "Tech Quiz": ("tech quiz", "technical quiz", "techquiz"),
    "Proto Circuit": ("proto circuit", "protocircuit"),
    "Posteriza": ("posteriza", "poster presentation", "poster event"),
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

    event_response = _event_response(normalized)
    if event_response:
        return event_response

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


def _event_response(normalized_query: str) -> str | None:
    match = _best_event_match(normalized_query)
    if not match:
        return None

    event_name = match
    event_details = PREDEFINED_EVENT_DETAILS[event_name]
    if _wants_location_details(normalized_query):
        return f"{event_name} Location Details:\n- Location: {event_details['location']}"

    return event_details["details"]


def _best_event_match(normalized_query: str) -> str | None:
    compact_query = normalized_query.replace(" ", "")
    query_tokens = normalized_query.split()

    best_name = None
    best_score = 0.0

    for event_name, aliases in PREDEFINED_EVENT_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize_query(alias)
            compact_alias = normalized_alias.replace(" ", "")

            if normalized_alias in normalized_query or compact_alias in compact_query:
                return event_name

            alias_tokens = normalized_alias.split()
            window_lengths = {max(1, len(alias_tokens) - 1), len(alias_tokens), len(alias_tokens) + 1}
            for window_length in window_lengths:
                if window_length > len(query_tokens):
                    continue
                for start in range(0, len(query_tokens) - window_length + 1):
                    window = " ".join(query_tokens[start : start + window_length])
                    score = SequenceMatcher(None, window.replace(" ", ""), compact_alias).ratio()
                    if score > best_score:
                        best_score = score
                        best_name = event_name

            whole_query_score = SequenceMatcher(None, compact_query, compact_alias).ratio()
            if whole_query_score > best_score:
                best_score = whole_query_score
                best_name = event_name

    if best_score >= 0.84:
        return best_name
    return None


def _wants_location_details(normalized_query: str) -> bool:
    return any(term in normalized_query for term in ("where is", "location", "venue", "held at", "happening at"))
