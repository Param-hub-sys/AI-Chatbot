const messagesEl = document.getElementById("messages");
const emptyEl = document.getElementById("empty");
const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const newChatBtn = document.getElementById("newChat");
const chatListEl = document.getElementById("chatList");

let currentId = null; // id of the open conversation (null = nothing saved yet)
let busy = false;

const render = (md) => DOMPurify.sanitize(marked.parse(md));

async function api(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).error || msg; } catch {}
    throw new Error(msg);
  }
  return res.status === 204 ? null : res.json();
}

// ---------- sidebar ----------
async function loadChatList() {
  const chats = await api("/api/conversations");
  chatListEl.innerHTML = "";
  for (const chat of chats) {
    const row = document.createElement("div");
    row.className = "chat-item" + (chat.id === currentId ? " active" : "");

    const open = document.createElement("button");
    open.className = "chat-open";
    open.type = "button";
    open.textContent = chat.title;
    open.title = chat.title;
    open.addEventListener("click", () => openChat(chat.id));

    const del = document.createElement("button");
    del.className = "chat-delete";
    del.type = "button";
    del.textContent = "×";
    del.setAttribute("aria-label", `Delete chat: ${chat.title}`);
    del.addEventListener("click", () => deleteChat(chat.id));

    row.append(open, del);
    chatListEl.appendChild(row);
  }
}

async function openChat(id) {
  if (busy) return;
  const chat = await api(`/api/conversations/${id}`);
  currentId = chat.id;
  clearMessages();
  chat.messages.forEach((m) => addMessage(m.role, m.content));
  await loadChatList();
}

async function deleteChat(id) {
  if (busy) return;
  await api(`/api/conversations/${id}`, { method: "DELETE" });
  if (id === currentId) startNewChat();
  await loadChatList();
}

function startNewChat() {
  if (busy) return;
  currentId = null;
  clearMessages();
  inputEl.focus();
  loadChatList();
}

// ---------- messages ----------
function clearMessages() {
  messagesEl.querySelectorAll(".msg").forEach((n) => n.remove());
  emptyEl.style.display = "";
}

function addMessage(role, text = "") {
  emptyEl.style.display = "none";
  const wrap = document.createElement("div");
  wrap.className = `msg ${role}`;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (role === "user") bubble.textContent = text;
  else bubble.innerHTML = render(text);
  wrap.appendChild(bubble);
  messagesEl.appendChild(wrap);
  messagesEl.scrollTop = messagesEl.scrollHeight;
  return bubble;
}

async function send() {
  const text = inputEl.value.trim();
  if (!text || busy) return;

  busy = true;
  sendBtn.disabled = true;
  inputEl.value = "";
  inputEl.style.height = "auto";

  addMessage("user", text);
  const bubble = addMessage("assistant", "…");
  let reply = "";

  try {
    if (currentId === null) {
      currentId = (await api("/api/conversations", { method: "POST" })).id;
    }

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: currentId, message: text }),
    });
    if (!res.ok) throw new Error((await res.json()).error || res.statusText);

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop();

      for (const evt of events) {
        const payload = evt.replace(/^data: /, "");
        if (payload === "[DONE]") continue;
        const data = JSON.parse(payload);
        if (data.error) throw new Error(data.error);
        reply += data.text;
        bubble.innerHTML = render(reply);
        messagesEl.scrollTop = messagesEl.scrollHeight;
      }
    }
  } catch (err) {
    bubble.innerHTML = `<span class="error">Request failed: ${DOMPurify.sanitize(err.message)}</span>`;
  } finally {
    busy = false;
    sendBtn.disabled = false;
    inputEl.focus();
    loadChatList().catch(() => {});
  }
}

sendBtn.addEventListener("click", send);
inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});
inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = inputEl.scrollHeight + "px";
});
newChatBtn.addEventListener("click", startNewChat);

loadChatList().catch(() => {});
