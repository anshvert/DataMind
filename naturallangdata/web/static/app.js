const STORAGE_KEY = "nld_chats_v2";

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
  engineFilter: document.getElementById("engine-filter"),
  uploadInput: document.getElementById("pdf-upload"),
  uploadLabel: document.getElementById("upload-label"),
  uploadBtn: document.getElementById("upload-btn"),
  uploadStatus: document.getElementById("upload-status"),
  stepper: document.getElementById("execution-stepper"),
  stepperEvents: document.getElementById("stepper-events"),
  stepperStatus: document.getElementById("stepper-status"),
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
        text: "Welcome to DataMind. Ingest documents (PDF/DOCX) or analytics datasets (CSV/Parquet for DuckDB), or query operational SQLite data directly.",
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

function addMessage(role, text, meta = "", extra = null) {
  const chat = getActiveChat();
  if (!chat) return;
  chat.messages.push({ role, text, meta, extra });
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

function downloadRowsAsCsv(rows, filename) {
  if (!rows || !rows.length) return;
  const headers = Object.keys(rows[0]);
  const lines = [];
  lines.push(headers.map((h) => `"${String(h).replace(/"/g, '""')}"`).join(","));

  for (const r of rows) {
    const vals = headers.map((h) => {
      const v = r[h] !== null && r[h] !== undefined ? String(r[h]) : "";
      return `"${v.replace(/"/g, '""')}"`;
    });
    lines.push(vals.join(","));
  }

  const blob = new Blob([lines.join("\n")], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename || "query_export.csv";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function renderMessages() {
  const chat = getActiveChat();
  els.messages.innerHTML = "";
  if (!chat) return;

  chat.messages.forEach((m, idx) => {
    const node = document.createElement("article");
    node.className = `message ${m.role}`;

    const textElem = document.createElement("div");
    textElem.textContent = m.text;
    node.appendChild(textElem);

    if (m.extra) {
      if (m.extra.summary) {
        const sumCard = document.createElement("div");
        sumCard.className = "bi-summary-card";
        sumCard.innerHTML = `
          <span class="bi-summary-badge">⚡ Executive Summary</span>
          <div class="bi-summary-text">${m.extra.summary}</div>
        `;
        node.appendChild(sumCard);
      }

      if (m.extra.chartSpec && window.echarts && m.extra.chartSpec.chartType && m.extra.chartSpec.chartType !== "empty" && m.extra.chartSpec.chartType !== "none") {
        const chartDiv = document.createElement("div");
        chartDiv.id = `chart-${chat.id}-${idx}`;
        chartDiv.className = "chart-box";
        node.appendChild(chartDiv);

        setTimeout(() => {
          const chartDom = document.getElementById(`chart-${chat.id}-${idx}`);
          if (chartDom) {
            const chart = echarts.init(chartDom, null, { backgroundColor: "transparent" });
            chart.setOption(m.extra.chartSpec);
          }
        }, 50);
      }

      if (m.extra.sql || (m.extra.rows && m.extra.rows.length > 0)) {
        const totalRows = (m.extra.rows || []).length;
        const details = document.createElement("details");
        details.className = "bi-accordion";

        const summaryEl = document.createElement("summary");
        summaryEl.innerHTML = `<span>▶ View SQL & Raw Data (${(m.extra.engine || "duckdb").toUpperCase()} • ${totalRows} rows)</span> <span>🔍</span>`;
        details.appendChild(summaryEl);

        const content = document.createElement("div");
        content.className = "bi-accordion-content";

        if (m.extra.sql) {
          const sqlPre = document.createElement("pre");
          sqlPre.className = "sql-box";
          sqlPre.textContent = `-- AST-Validated SQL (${m.extra.engine || "duckdb"})\n${m.extra.sql}`;
          content.appendChild(sqlPre);
        }

        if (totalRows > 0) {
          const metaBar = document.createElement("div");
          metaBar.className = "table-meta-bar";
          metaBar.innerHTML = `<span>Showing first ${Math.min(10, totalRows)} of ${totalRows} rows</span>`;

          const downloadBtn = document.createElement("button");
          downloadBtn.className = "download-csv-btn";
          downloadBtn.innerHTML = `⬇ Download CSV (${totalRows} rows)`;
          downloadBtn.onclick = (e) => {
            e.preventDefault();
            downloadRowsAsCsv(m.extra.rows, `querymind_export_${Date.now()}.csv`);
          };
          metaBar.appendChild(downloadBtn);
          content.appendChild(metaBar);

          const tableBox = document.createElement("div");
          tableBox.className = "result-table-box";

          const table = document.createElement("table");
          table.className = "result-table";

          const thead = document.createElement("thead");
          const headerRow = document.createElement("tr");
          const cols = Object.keys(m.extra.rows[0]);
          cols.forEach((col) => {
            const th = document.createElement("th");
            th.textContent = col;
            headerRow.appendChild(th);
          });
          thead.appendChild(headerRow);
          table.appendChild(thead);

          const tbody = document.createElement("tbody");
          m.extra.rows.slice(0, 10).forEach((row) => {
            const tr = document.createElement("tr");
            cols.forEach((col) => {
              const td = document.createElement("td");
              td.textContent = row[col] !== null ? row[col] : "-";
              tr.appendChild(td);
            });
            tbody.appendChild(tr);
          });
          table.appendChild(tbody);
          tableBox.appendChild(table);
          content.appendChild(tableBox);
        }

        details.appendChild(content);
        node.appendChild(details);
      }
    }

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

function render() {
  renderChatList();
  renderMessages();
}

function handleSourceTypeChange() {
  const val = els.sourceType.value;
  if (val === "document") {
    els.uploadInput.accept = ".pdf,.docx,application/pdf";
    if (els.uploadLabel) els.uploadLabel.textContent = "Upload Document (PDF, DOCX)";
  } else if (val === "analytics") {
    els.uploadInput.accept = ".csv,.parquet,text/csv";
    if (els.uploadLabel) els.uploadLabel.textContent = "Upload Analytics File (CSV, Parquet)";
  }
}

async function uploadDocument() {
  const file = els.uploadInput.files?.[0];
  if (!file) {
    els.uploadStatus.textContent = "Please choose a file first.";
    return;
  }

  const fd = new FormData();
  fd.append("file", file);

  els.uploadStatus.textContent = "Ingesting file...";
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

  els.uploadStatus.textContent = data.message || `Ingested ${data.name}.`;
  els.uploadInput.value = "";
  addMessage("system", `File ingested successfully: ${data.name} (${data.message || ""})`);
}

function isBiQuery(text) {
  const selectedEngine = els.engineFilter ? els.engineFilter.value : "";
  if (selectedEngine === "duckdb" || selectedEngine === "sqlite") {
    return true;
  }
  if (selectedEngine === "document") {
    return false;
  }
  if (els.sourceType && els.sourceType.value === "analytics") {
    return true;
  }
  const chat = getActiveChat();
  if (chat && chat.messages) {
    const hasPriorBi = chat.messages.some((m) => m.extra && (m.extra.sql || m.extra.chartSpec || m.extra.engine));
    if (hasPriorBi) {
      return true;
    }
  }
  const q = text.toLowerCase();
  const keywords = [
    "arr", "revenue", "churn", "inventory", "stock", "sku",
    "customer", "order", "signup", "trend", "sum", "average", "avg", "top", "count",
    "gross", "net", "select", "group by", "sales", "quarterly", "environmental", "expenditure",
    "data", "give me", "from", "to", "between", "how many", "year", "201", "202"
  ];
  return keywords.some((k) => q.includes(k));
}

function appendStepperEvent(event) {
  els.stepper.classList.remove("hidden");
  const div = document.createElement("div");
  div.className = "stepper-event-item";
  div.textContent = `[${(event.node || "STEP").toUpperCase()}] ${event.message || JSON.stringify(event)}`;
  els.stepperEvents.appendChild(div);
  els.stepperEvents.scrollTop = els.stepperEvents.scrollHeight;
}

async function askBiQuestion(text, engine = "") {
  const chat = getActiveChat();
  const historyTurns = (chat && chat.messages)
    ? chat.messages
        .filter((m) => m.role === "user" || m.role === "assistant")
        .slice(-4)
        .map((m) => ({ role: m.role, text: m.text }))
    : [];

  const engineBadge = engine ? engine.toUpperCase() : "DuckDB / SQLite";
  addMessage("user", text, `Query Engine: ${engineBadge}`);
  addMessage("assistant", "Synthesizing SQL, executing analytics, and generating summary...");

  els.stepperEvents.innerHTML = "";
  els.stepperStatus.textContent = "Running";
  els.stepper.classList.remove("hidden");

  let generatedSql = "";
  let targetEngine = engine || "";
  let dataRows = [];
  let chartSpec = null;
  let summaryText = "";
  let hasError = null;

  return new Promise((resolve) => {
    let url = `/bi/stream?q=${encodeURIComponent(text)}`;
    if (engine) url += `&engine=${encodeURIComponent(engine)}`;
    if (historyTurns.length) url += `&history=${encodeURIComponent(JSON.stringify(historyTurns))}`;
    const es = new EventSource(url);

    es.addEventListener("trace", (e) => {
      try {
        const trace = JSON.parse(e.data);
        appendStepperEvent(trace);
      } catch {}
    });

    es.addEventListener("sql", (e) => {
      try {
        const data = JSON.parse(e.data);
        generatedSql = data.sql || "";
        targetEngine = data.engine || targetEngine;
      } catch {}
    });

    es.addEventListener("data", (e) => {
      try {
        const data = JSON.parse(e.data);
        dataRows = data.rows || [];
      } catch {}
    });

    es.addEventListener("visualization", (e) => {
      try {
        chartSpec = JSON.parse(e.data);
      } catch {}
    });

    es.addEventListener("summary", (e) => {
      try {
        const data = JSON.parse(e.data);
        summaryText = data.summary || summaryText;
      } catch {}
    });

    es.addEventListener("done", (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.status === "failed") {
          hasError = data.error;
        }
        if (data.summary) {
          summaryText = data.summary;
        }
      } catch {}
      es.close();
      finish();
    });

    es.onerror = () => {
      es.close();
      finish();
    };

    function finish() {
      els.stepperStatus.textContent = hasError ? "Failed" : "Completed";
      setTimeout(() => els.stepper.classList.add("hidden"), 3500);

      const activeChat = getActiveChat();
      if (!activeChat) return resolve();
      activeChat.messages.pop();

      if (hasError) {
        addMessage("assistant", `Execution failed: ${hasError}`);
      } else {
        const metaStr = `Engine: ${(targetEngine || "duckdb").toUpperCase()} | ${dataRows.length} rows returned`;
        addMessage("assistant", `Query executed successfully on ${(targetEngine || "duckdb").toUpperCase()}:`, metaStr, {
          sql: generatedSql,
          engine: targetEngine,
          rows: dataRows,
          chartSpec: chartSpec,
          summary: summaryText,
        });
      }

      updateChatTitleFromMessage(activeChat, text);
      saveChats();
      render();
      resolve();
    }
  });
}

async function askDocumentQuestion(text) {
  const payload = {
    question: text,
    doc_id: null,
  };

  addMessage("user", text, "Document RAG Pipeline");
  addMessage("assistant", "Searching document vector store...");

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

async function askQuestion(text) {
  const selectedEngine = els.engineFilter ? els.engineFilter.value : "";
  if (selectedEngine === "document") {
    await askDocumentQuestion(text);
  } else if (selectedEngine === "duckdb" || selectedEngine === "sqlite") {
    await askBiQuestion(text, selectedEngine);
  } else if (isBiQuery(text)) {
    await askBiQuestion(text);
  } else {
    await askDocumentQuestion(text);
  }
}

function wireEvents() {
  els.newChatBtn.onclick = () => createChat();
  els.sourceType.onchange = handleSourceTypeChange;

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
  handleSourceTypeChange();
  render();
}

init().catch((e) => {
  addMessage("system", `Initialization error: ${e.message}`);
});
