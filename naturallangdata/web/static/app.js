const STORAGE_KEY = "nld_chats_v1";

const state = {
  chats: [],
  activeChatId: null,
  documents: [],
};

const els = {
  chatList: document.getElementById("chat-list"),
  chatCount: document.getElementById("chat-count"),
  newChatBtn: document.getElementById("new-chat-btn"),
  chatTitle: document.getElementById("chat-title"),
  chatSubtitle: document.getElementById("chat-subtitle"),
  messages: document.getElementById("messages"),
  questionInput: document.getElementById("question-input"),
  composer: document.getElementById("composer"),
  sourceType: document.getElementById("source-type"),
  documentSelect: document.getElementById("document-select"),
  uploadInput: document.getElementById("pdf-upload"),
  uploadBtn: document.getElementById("upload-btn"),
  uploadStatus: document.getElementById("upload-status"),
};

function uid() {
  return Math.random().toString(36).slice(2, 10);
}

function nowLabel() {
  return new Date().toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

function loadChats() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

function saveChats() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state.chats));
}

function getActiveChat() {
  return state.chats.find((c) => c.id === state.activeChatId) || null;
}

function createChat() {
  const chat = {
    id: uid(),
    title: "New Chat",
    createdAt: Date.now(),
    messages: [
      {
        role: "system",
        text: "Welcome. Upload a document, pick a source, and ask your first question.",
      },
    ],
  };
  state.chats.unshift(chat);
  state.activeChatId = chat.id;
  saveChats();
  render();
}

function setActiveChat(chatId) {
  state.activeChatId = chatId;
  render();
}

function updateChatTitleFromMessage(chat, message) {
  if (chat.title === "New Chat") {
    chat.title = message.slice(0, 44) + (message.length > 44 ? "..." : "");
  }
}

function addMessage(role, text, meta = "") {
  const chat = getActiveChat();
  if (!chat) return;
  chat.messages.push({ role, text, meta });
  saveChats();
  renderMessages();
}

function autoResizeTextarea() {
  els.questionInput.style.height = "auto";
  els.questionInput.style.height = `${Math.min(160, els.questionInput.scrollHeight)}px`;
}

function renderChatList() {
  els.chatList.innerHTML = "";
  state.chats.forEach((chat) => {
    const li = document.createElement("li");
    li.className = `chat-item ${chat.id === state.activeChatId ? "active" : ""}`;
    li.innerHTML = `<strong>${chat.title}</strong><small>${new Date(chat.createdAt).toLocaleDateString()}</small>`;
    li.onclick = () => setActiveChat(chat.id);
    els.chatList.appendChild(li);
  });
  els.chatCount.textContent = String(state.chats.length);
}

function renderMessages() {
  const chat = getActiveChat();
  els.messages.innerHTML = "";
  if (!chat) return;

  chat.messages.forEach((m) => {
    const node = document.createElement("article");
    node.className = `message ${m.role}`;
    node.textContent = m.text;
    if (m.meta) {
      const meta = document.createElement("span");
      meta.className = "meta";
      meta.textContent = m.meta;
      node.appendChild(meta);
    }
    els.messages.appendChild(node);
  });
  els.messages.scrollTop = els.messages.scrollHeight;

  els.chatTitle.textContent = chat.title;
  els.chatSubtitle.textContent = `Updated ${nowLabel()}`;
}

function renderDocumentOptions() {
  const selectedValue = els.documentSelect.value;
  els.documentSelect.innerHTML = "<option value=''>All Documents</option>";
  state.documents.forEach((doc) => {
    const opt = document.createElement("option");
    opt.value = doc.doc_id;
    opt.textContent = doc.name;
    els.documentSelect.appendChild(opt);
  });
  if (["", ...state.documents.map((d) => d.doc_id)].includes(selectedValue)) {
    els.documentSelect.value = selectedValue;
  }
}

function render() {
  renderChatList();
  renderMessages();
  renderDocumentOptions();
}

async function refreshDocuments() {
  const res = await fetch("/documents/");
  if (!res.ok) {
    throw new Error("Unable to fetch documents");
  }
  state.documents = await res.json();
  renderDocumentOptions();
}

async function uploadDocument() {
  const file = els.uploadInput.files?.[0];
  if (!file) {
    els.uploadStatus.textContent = "Please choose a document file first.";
    return;
  }

  const allowedTypes = new Set([
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  ]);
  const lowerName = file.name.toLowerCase();
  if (
    !allowedTypes.has(file.type)
    && !lowerName.endsWith(".docx")
    && !lowerName.endsWith(".pdf")
    && !lowerName.endsWith(".csv")
    && !lowerName.endsWith(".xlsx")
  ) {
    els.uploadStatus.textContent = "Only PDF, DOCX, CSV, and XLSX are supported right now.";
    return;
  }

  const fd = new FormData();
  fd.append("file", file);

  els.uploadStatus.textContent = "Ingesting... this can take a moment.";
  const res = await fetch("/documents/upload", {
    method: "POST",
    body: fd,
  });

  const data = await res.json();
  if (!res.ok) {
    const detail = data?.detail || "Upload failed";
    els.uploadStatus.textContent = `Error: ${detail}`;
    addMessage("system", `Upload failed: ${detail}`);
    return;
  }

  els.uploadStatus.textContent = `Indexed ${data.chunks_indexed} chunks from ${data.name}.`;
  els.uploadInput.value = "";
  await refreshDocuments();
  addMessage("system", `Document ready: ${data.name} (${data.doc_id}).`);
}

async function askQuestion(text) {
  const docId = els.documentSelect.value || null;
  const payload = {
    question: text,
    doc_id: docId,
  };

  addMessage("user", text, docId ? `Filtered to document: ${docId}` : "Using all document sources");
  addMessage("assistant", "Thinking...");

  const res = await fetch("/query/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const data = await res.json();

  const chat = getActiveChat();
  if (!chat) return;
  chat.messages.pop();

  if (!res.ok) {
    const detail = data?.detail || "Query failed";
    chat.messages.push({ role: "assistant", text: `I hit an error: ${detail}` });
    saveChats();
    renderMessages();
    return;
  }

  const sourceNames = [...new Set((data.sources || []).map((s) => s.doc_name))];
  chat.messages.push({
    role: "assistant",
    text: data.answer,
    meta: sourceNames.length ? `Sources: ${sourceNames.join(", ")}` : "No source chunks returned",
  });

  updateChatTitleFromMessage(chat, text);
  saveChats();
  render();
}

function wireEvents() {
  els.newChatBtn.onclick = () => createChat();
  els.uploadBtn.onclick = () => uploadDocument().catch((e) => {
    els.uploadStatus.textContent = `Error: ${e.message}`;
  });

  els.composer.onsubmit = (e) => {
    e.preventDefault();
    const text = els.questionInput.value.trim();
    if (!text) return;
    els.questionInput.value = "";
    autoResizeTextarea();
    askQuestion(text).catch((err) => {
      addMessage("assistant", `Unexpected error: ${err.message}`);
    });
  };

  els.questionInput.addEventListener("input", autoResizeTextarea);
}

async function init() {
  state.chats = loadChats();
  if (!state.chats.length) createChat();
  if (!state.activeChatId) state.activeChatId = state.chats[0].id;
  wireEvents();
  render();
  await refreshDocuments();
}

init().catch((e) => {
  addMessage("system", `Initialization error: ${e.message}`);
});
