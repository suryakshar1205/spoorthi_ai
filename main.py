from __future__ import annotations

import logging
import os
import webbrowser
from pathlib import Path
from threading import Timer

from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from services.llm import FALLBACK_MESSAGE, LLMService
from services.retriever import RetrieverService


BASE_DIR = Path(__file__).resolve().parent
APP_PORT = int(os.environ.get("PORT", 5000))
APP_URL = f"http://127.0.0.1:{APP_PORT}"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("spoorthi_web")

app = Flask(
    __name__,
    template_folder=str(BASE_DIR / "templates"),
    static_folder=str(BASE_DIR / "static"),
)
CORS(
    app,
    resources={r"/chat": {"origins": ["http://localhost:5500", "http://127.0.0.1:5500"]}},
)

retriever: RetrieverService | None = None
llm_service = LLMService()


def create_services() -> None:
    global retriever
    data_dir = BASE_DIR / "data"
    retriever = RetrieverService(data_dir=data_dir)
    logger.info("Loaded %s chunks from %s", retriever.chunk_count, data_dir)


@app.get("/")
def index() -> str:
    return render_template("index.html")


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    return {"status": "ok"}, 200


@app.post("/chat")
def chat() -> tuple[object, int]:
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message", "")).strip()

    if not message:
        return jsonify({"answer": "Please enter a message to continue."}), 400

    if retriever is None:
        logger.error("Retriever is not initialized.")
        return jsonify({"answer": "Something went wrong. Please try again."}), 500

    try:
        matches = retriever.retrieve(message, top_k=3, final_k=3)
        answer = llm_service.generate_response(message=message, matches=matches)
        logger.info(
            "Query=%r | matches=%s | answer_preview=%r",
            message,
            [match["section"] for match in matches],
            answer[:120],
        )
        return (
            jsonify(
                {
                    "answer": answer or FALLBACK_MESSAGE,
                }
            ),
            200,
        )
    except Exception:
        logger.exception("Chat request failed for message=%r", message)
        return jsonify({"answer": "Something went wrong. Please try again."}), 500


def open_browser() -> None:
    try:
        webbrowser.open(APP_URL)
    except Exception:
        logger.exception("Failed to open the browser automatically.")


def main() -> None:
    create_services()
    if os.environ.get("PORT") is None and os.environ.get("SPOORTHI_OPEN_BROWSER", "true").lower() == "true":
        Timer(1.0, open_browser).start()
    logger.info("Starting Spoorthi Chatbot on %s", APP_URL)
    app.run(host="0.0.0.0", port=APP_PORT, debug=False, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
