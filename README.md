# AI Chatbot

A simple Claude-style chat app: Flask backend, streaming responses, and a clean
HTML/CSS/JS front end with Markdown rendering and conversation memory.

## Features
- Streaming replies (text appears as it is generated)
- Multi-turn conversations saved to a local SQLite database (`chats.db`)
- History sidebar: reopen, continue or delete past chats
- Markdown and code-block rendering
- Light and dark mode
- API key stays on the server (never exposed to the browser)

## Setup

1. Get an API key from https://console.anthropic.com
2. Install and configure:

   ```bash
   python -m venv venv
   venv\Scripts\activate        # Windows
   # source venv/bin/activate   # macOS / Linux
   pip install -r requirements.txt
   copy .env.example .env       # Windows  (cp on macOS / Linux)
   ```
3. Open `.env` and paste your key after `ANTHROPIC_API_KEY=`
4. Run:

   ```bash
   python app.py
   ```
5. Open http://127.0.0.1:5000

## Project structure

```
ai-chatbot/
├── app.py            # Flask server, SQLite storage, streaming /api/chat
├── requirements.txt
├── .env.example      # copy to .env (never commit .env)
└── static/
    ├── index.html
    ├── style.css
    └── app.js
```

## API
| Method | Route | Purpose |
|---|---|---|
| GET | `/api/conversations` | List chats |
| POST | `/api/conversations` | Create a chat |
| GET | `/api/conversations/<id>` | Load a chat's messages |
| DELETE | `/api/conversations/<id>` | Delete a chat |
| POST | `/api/chat` | Send a message (streamed reply, auto-saved) |

## Ideas to extend
- Add a model picker and a system-prompt editor
- File uploads (PDF / images)
- User login and per-user history
- Deploy on Render or Railway
