import os
import sqlite3
import sys
from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path


def _base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).parent


DB_PATH = _base_dir() / "learning.db"


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def cursor():
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with cursor() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS cards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                lang TEXT NOT NULL DEFAULT 'en',
                status TEXT NOT NULL DEFAULT 'new',
                repetitions INTEGER NOT NULL DEFAULT 0,
                ease REAL NOT NULL DEFAULT 2.5,
                interval INTEGER NOT NULL DEFAULT 0,
                due TEXT NOT NULL DEFAULT 'today'
            );

            CREATE TABLE IF NOT EXISTS chats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                lang TEXT NOT NULL DEFAULT 'en',
                title TEXT NOT NULL DEFAULT '',
                created TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created TEXT NOT NULL,
                FOREIGN KEY (chat_id) REFERENCES chats(id)
            );
            """
        )


def today_str():
    return date.today().isoformat()


def add_card(word, translation, lang="en"):
    with cursor() as conn:
        cur = conn.execute(
            "INSERT INTO cards (word, translation, lang, due) VALUES (?,?,?,?)",
            (word, translation, lang, today_str()),
        )
        return cur.lastrowid


def list_cards(lang="en"):
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM cards WHERE lang=? ORDER BY id", (lang,)
        ).fetchall()
        return [dict(r) for r in rows]


def delete_card(card_id):
    with cursor() as conn:
        conn.execute("DELETE FROM cards WHERE id=?", (card_id,))


def due_cards(lang="en"):
    with cursor() as conn:
        rows = conn.execute(
            "SELECT * FROM cards WHERE lang=? AND due <= ? ORDER BY due",
            (lang, today_str()),
        ).fetchall()
        return [dict(r) for r in rows]


def review_card(card_id, quality):
    with cursor() as conn:
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
        if not row:
            return None
        ease = row["ease"]
        reps = row["repetitions"]
        interval = row["interval"]

        if quality < 3:
            reps = 0
            interval = 0
            due = today_str()
        else:
            reps += 1
            if reps == 1:
                interval = 1
            elif reps == 2:
                interval = 6
            else:
                interval = round(interval * ease)
            ease = max(1.3, ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)))
            due = (date.today() + timedelta(days=interval)).isoformat()

        status = "new" if reps == 0 else "learning"
        conn.execute(
            "UPDATE cards SET ease=?, repetitions=?, interval=?, due=?, status=? WHERE id=?",
            (ease, reps, interval, due, status, card_id),
        )
        return dict(
            row,
            ease=ease,
            repetitions=reps,
            interval=interval,
            due=due,
            status=status,
        )


def create_chat(lang="en", title=""):
    with cursor() as conn:
        cur = conn.execute(
            "INSERT INTO chats (lang, title, created) VALUES (?,?,?)",
            (lang, title, today_str()),
        )
        return cur.lastrowid


def list_chats():
    with cursor() as conn:
        rows = conn.execute("SELECT * FROM chats ORDER BY id DESC").fetchall()
        return [dict(r) for r in rows]


def get_chat(chat_id):
    with cursor() as conn:
        return dict(conn.execute("SELECT * FROM chats WHERE id=?", (chat_id,)).fetchone())


def add_message(chat_id, role, content):
    with cursor() as conn:
        conn.execute(
            "INSERT INTO chat_messages (chat_id, role, content, created) VALUES (?,?,?,?)",
            (chat_id, role, content, today_str()),
        )


def chat_history(chat_id):
    with cursor() as conn:
        rows = conn.execute(
            "SELECT role, content FROM chat_messages WHERE chat_id=? ORDER BY id",
            (chat_id,),
        ).fetchall()
        return [dict(r) for r in rows]