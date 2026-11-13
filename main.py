"""Сервер чата LegalBot и закрытой статистики."""

import argparse
import json
import os
import secrets
import sqlite3
from collections import Counter
from contextlib import closing
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from wsgiref.simple_server import make_server

from knowledge import CARDS, TOPICS
from lookup import find_cards


ROOT = Path(__file__).resolve().parent
SITE = ROOT / "site"
MOSCOW = timezone(timedelta(hours=3))
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/admin.html": ("admin.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/config.js": ("config.js", "text/javascript; charset=utf-8"),
    "/chat.js": ("chat.js", "text/javascript; charset=utf-8"),
    "/admin.js": ("admin.js", "text/javascript; charset=utf-8"),
}
BY_ID = {card.id: card for card in CARDS}
UNCATEGORIZED = "Тема не определена"
API = {"/api/catalog", "/api/ask", "/api/statistics"}


def initialize_database(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            """CREATE TABLE IF NOT EXISTS request_counts (
                day TEXT NOT NULL, topic TEXT NOT NULL, card_id TEXT NOT NULL,
                outcome TEXT NOT NULL, total INTEGER NOT NULL,
                PRIMARY KEY (day, topic, card_id, outcome)
            )"""
        )


def count_request(path, topic, card_id, outcome):
    today = datetime.now(MOSCOW).date().isoformat()
    with closing(sqlite3.connect(path)) as db, db:
        db.execute(
            """INSERT INTO request_counts VALUES (?, ?, ?, ?, 1)
               ON CONFLICT (day, topic, card_id, outcome)
               DO UPDATE SET total = total + 1""",
            (today, topic, card_id, outcome),
        )


def get_statistics(path):
    topics, days, cases, outcomes = Counter(), Counter(), Counter(), Counter()
    with closing(sqlite3.connect(path)) as db:
        for day, topic, card_id, outcome, count in db.execute(
            "SELECT day, topic, card_id, outcome, total FROM request_counts"
        ):
            topics[topic] += count
            days[day] += count
            outcomes[outcome] += count
            if card_id in BY_ID:
                cases[BY_ID[card_id].title] += count

    return {
        "total": sum(outcomes.values()),
        "answered": outcomes["answer"],
        "clarified": outcomes["clarify"],
        "unmatched": outcomes["unmatched"],
        "topics": [(topic, topics[topic]) for topic in (*TOPICS, UNCATEGORIZED)],
        "days": sorted(days.items()),
        "cases": cases.most_common(),
    }


def card_choice(card):
    return {"id": card.id, "title": card.title, "example": card.example}


def answer_question(payload, path):
    selection = payload.get("card_id")
    if selection is not None:
        if not isinstance(selection, str) or selection not in BY_ID:
            raise ValueError("Не удалось найти выбранную карточку.")
        matches = (BY_ID[selection],)
    else:
        question = payload.get("question")
        if not isinstance(question, str) or not 3 <= len(question.strip()) <= 1200:
            raise ValueError("Введите вопрос длиной от 3 до 1200 символов.")
        matches = find_cards(question, CARDS)

    if len(matches) == 1:
        card = matches[0]
        count_request(path, card.topic, card.id, "answer")
        result = asdict(card)
        result.pop("rules")
        return {"status": "answer", "card": result}

    if matches:
        topics = {card.topic for card in matches}
        topic = matches[0].topic if len(topics) == 1 else UNCATEGORIZED
        count_request(path, topic, "", "clarify")
        return {
            "status": "clarify",
            "message": "Подходит несколько ситуаций. Уточните, о какой из них ваш вопрос.",
            "choices": [card_choice(card) for card in matches],
        }

    count_request(path, UNCATEGORIZED, "", "unmatched")
    return {
        "status": "unmatched",
        "message": "В базе пока нет точного ответа. Уточните, что произошло, или выберите пример по своей теме.",
    }


def read_payload(environ):
    if environ.get("CONTENT_TYPE", "").split(";")[0].strip() != "application/json":
        raise ValueError("Ожидается запрос в формате JSON.")
    try:
        size = int(environ.get("CONTENT_LENGTH") or 0)
        if not 1 <= size <= 16384:
            raise ValueError
        payload = json.loads(environ["wsgi.input"].read(size))
    except (ValueError, RecursionError):
        raise ValueError("Не удалось прочитать запрос.") from None
    if not isinstance(payload, dict):
        raise ValueError("Не удалось прочитать запрос.")
    return payload


def create_app(db_path=None, admin_password=None, pages_origin=None):
    """Точка входа WSGI для размещения на Python-хостинге."""
    path = Path(db_path or os.environ.get("LEGALBOT_DB", ROOT / "data" / "statistics.sqlite3"))
    password = (admin_password or os.environ.get("LEGALBOT_ADMIN_PASSWORD", "")).encode("utf-8")
    origin = (pages_origin or os.environ.get("LEGALBOT_PAGES_ORIGIN", "")).rstrip("/")
    initialize_database(path)

    def application(environ, start_response):
        route = environ.get("PATH_INFO")
        method = environ.get("REQUEST_METHOD")
        headers = [("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer")]
        if route in API:
            headers.extend([("Cache-Control", "no-store"), ("Vary", "Origin")])
            if origin and environ.get("HTTP_ORIGIN") == origin:
                headers.append(("Access-Control-Allow-Origin", origin))

        def send(status, body, content_type="application/json; charset=utf-8"):
            start_response(status, headers + [
                ("Content-Type", content_type), ("Content-Length", str(len(body)))
            ])
            return [b"" if method == "HEAD" else body]

        def send_json(status, data):
            return send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"))

        if route in STATIC and method in ("GET", "HEAD"):
            file, content_type = STATIC[route]
            return send("200 OK", (SITE / file).read_bytes(), content_type)

        if route not in API:
            return send_json("404 Not Found", {"error": "Страница не найдена."})

        if method == "OPTIONS" and origin and environ.get("HTTP_ORIGIN") == origin:
            headers.extend([
                ("Access-Control-Allow-Methods", "GET, POST, OPTIONS"),
                ("Access-Control-Allow-Headers", "Content-Type"),
            ])
            return send("204 No Content", b"")

        if route == "/api/catalog" and method == "GET":
            return send_json("200 OK", {
                "topics": [
                    {"name": topic, "examples": [card_choice(card) for card in CARDS if card.topic == topic]}
                    for topic in TOPICS
                ]
            })

        if method != "POST" or route == "/api/catalog":
            return send_json("405 Method Not Allowed", {"error": "Этот метод не поддерживается."})

        try:
            payload = read_payload(environ)
            if route == "/api/ask":
                return send_json("200 OK", answer_question(payload, path))

            submitted = payload.get("password")
            if not password:
                return send_json("503 Service Unavailable", {"error": "Доступ к статистике не настроен."})
            if not isinstance(submitted, str) or not secrets.compare_digest(
                submitted.encode("utf-8", errors="replace"), password
            ):
                return send_json("403 Forbidden", {"error": "Неверный пароль."})
            return send_json("200 OK", get_statistics(path))
        except ValueError as exc:
            return send_json("400 Bad Request", {"error": str(exc)})
        except sqlite3.Error:
            return send_json("503 Service Unavailable", {"error": "База временно недоступна."})

    return application


def main():
    parser = argparse.ArgumentParser(description="Локальный запуск LegalBot")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--db", type=Path, help="Путь к файлу статистики")
    args = parser.parse_args()
    configured_password = os.environ.get("LEGALBOT_ADMIN_PASSWORD")
    password = configured_password or secrets.token_urlsafe(18)
    app = create_app(db_path=args.db, admin_password=password)

    with make_server("127.0.0.1", args.port, app) as server:
        address = f"http://127.0.0.1:{server.server_port}"
        print(f"LegalBot: {address}", flush=True)
        print(f"Статистика: {address}/admin.html", flush=True)
        if not configured_password:
            print(f"Пароль для текущего запуска: {password}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
