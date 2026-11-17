import json
import os
import sqlite3
from contextlib import closing

from anthropic import Anthropic
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request, send_from_directory

load_dotenv()

MODEL = os.getenv("MODEL", "claude-sonnet-5-5")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT",
    "You are a helpful, honest and concise AI assistant. Use Markdown when it helps.",
)
DB_PATH = os.getenv("DB_PATH", "chats.db")
MAX_HISTORY = 40  # most recent messages sent to the model

app = Flask(__name__, static_folder="static", static_url_path="/static")
client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment


# ---------- database ----------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with closing(get_db()) as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS conversations (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                title      TEXT NOT NULL DEFAULT 'New chat',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS messages (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id INTEGER NOT NULL
                                REFERENCES conversations(id) ON DELETE CASCADE,
                role            TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                content         TEXT NOT NULL,
                created_at      TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id);
            """
        )
        db.commit()


init_db()


# ---------- pages ----------
@app.get("/")
def index():
    return send_from_directory("static", "index.html")


# ---------- conversation API ----------
@app.get("/api/conversations")
def list_conversations():
    with closing(get_db()) as db:
        rows = db.execute(
            "SELECT id, title, updated_at FROM conversations ORDER BY updated_at DESC, id DESC"
        ).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/conversations")
def create_conversation():
    with closing(get_db()) as db:
        cur = db.execute("INSERT INTO conversations DEFAULT VALUES")
        db.commit()
        return jsonify(id=cur.lastrowid, title="New chat"), 201


@app.get("/api/conversations/<int:conv_id>")
def get_conversation(conv_id):
    with closing(get_db()) as db:
        conv = db.execute(
            "SELECT id, title FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if not conv:
            return jsonify(error="Conversation not found."), 404
        msgs = db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,),
        ).fetchall()
    return jsonify(id=conv["id"], title=conv["title"], messages=[dict(m) for m in msgs])


@app.delete("/api/conversations/<int:conv_id>")
def delete_conversation(conv_id):
    with closing(get_db()) as db:
        db.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        db.commit()
    return "", 204


# ---------- chat (streaming) ----------
@app.post("/api/chat")
def chat():
    data = request.get_json(silent=True) or {}
    conv_id = data.get("conversation_id")
    text = (data.get("message") or "").strip()
    if not conv_id or not text:
        return jsonify(error="conversation_id and message are required."), 400

    with closing(get_db()) as db:
        conv = db.execute(
            "SELECT id, title FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        if not conv:
            return jsonify(error="Conversation not found."), 404

        db.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
            (conv_id, text),
        )
        if conv["title"] == "New chat":  # name the chat after its first message
            title = text.replace("\n", " ")[:50]
            db.execute("UPDATE conversations SET title = ? WHERE id = ?", (title, conv_id))
        db.commit()

        rows = db.execute(
            "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id",
            (conv_id,),
        ).fetchall()

    history = [{"role": r["role"], "content": r["content"]} for r in rows][-MAX_HISTORY:]

    def generate():
        reply = ""
        try:
            with client.messages.stream(
                model=MODEL,
                max_tokens=1500,
                system=SYSTEM_PROMPT,
                messages=history,
            ) as stream:
                for chunk in stream.text_stream:
                    reply += chunk
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as exc:  # surface API errors to the UI
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        finally:
            with closing(get_db()) as db:
                if reply:
                    db.execute(
                        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
                        (conv_id, reply),
                    )
                else:
                    # the request failed: remove the unanswered user message
                    db.execute(
                        "DELETE FROM messages WHERE id = (SELECT MAX(id) FROM messages "
                        "WHERE conversation_id = ? AND role = 'user')",
                        (conv_id,),
                    )
                db.execute(
                    "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (conv_id,),
                )
                db.commit()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


if __name__ == "__main__":
    app.run(debug=True, port=5000)
