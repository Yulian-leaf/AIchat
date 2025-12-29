function getOrCreateSessionId() {
  const key = "ai_companion_session_id";
  const existing = localStorage.getItem(key);
  if (existing && existing.trim()) return existing;
  const created = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
  localStorage.setItem(key, created);
  return created;
}

function nowTime() {
  const d = new Date();
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function appendMessage({ role, content }) {
  const container = document.getElementById("messages");

  const wrapper = document.createElement("div");
  wrapper.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;

  const meta = document.createElement("div");
  meta.className = "meta";
  meta.textContent = `${role === "user" ? "你" : "AI"} · ${nowTime()}`;

  wrapper.appendChild(bubble);
  wrapper.appendChild(meta);
  container.appendChild(wrapper);

  container.scrollTop = container.scrollHeight;

  return { wrapper, bubble };
}

async function sendViaHttp(message, sessionId, systemPrompt) {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, session_id: sessionId, system_prompt: systemPrompt || "" }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return await res.json();
}

async function loadSession(sessionId) {
  const res = await fetch(`/api/session?session_id=${encodeURIComponent(sessionId)}`);
  if (!res.ok) return null;
  return await res.json();
}

function connectWebSocket(onAssistantMessage) {
  const scheme = location.protocol === "https:" ? "wss" : "ws";
  // 默认连接到后端提供的 WS_PORT（通过 /api/config 获取）；若失败则回退同源 /ws
  const fallbackUrl = `${scheme}://${location.host}/ws`;

  const ws = new WebSocket(fallbackUrl);

  ws.addEventListener("message", (evt) => {
    try {
      const data = JSON.parse(evt.data);
      if (data.type === "assistant_delta" || data.type === "assistant_message") {
        onAssistantMessage(data);
      }
      if (data.type === "session" && data.session_id) {
        localStorage.setItem("ai_companion_session_id", data.session_id);
      }
    } catch {
      // ignore
    }
  });

  return ws;
}

async function connectWebSocketFromConfig(onAssistantMessage) {
  try {
    const res = await fetch("/api/config");
    if (!res.ok) return connectWebSocket(onAssistantMessage);
    const cfg = await res.json();
    const wsPort = Number(cfg.ws_port);
    const wsPath = String(cfg.ws_path || "/ws");
    if (!wsPort) return connectWebSocket(onAssistantMessage);

    const scheme = location.protocol === "https:" ? "wss" : "ws";
    const url = `${scheme}://${location.hostname}:${wsPort}${wsPath}`;
    const ws = new WebSocket(url);

    ws.addEventListener("message", (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === "assistant_delta" || data.type === "assistant_message") {
          onAssistantMessage(data);
        }
        if (data.type === "session" && data.session_id) {
          localStorage.setItem("ai_companion_session_id", data.session_id);
        }
      } catch {
        // ignore
      }
    });

    return ws;
  } catch {
    return connectWebSocket(onAssistantMessage);
  }

  const ws = new WebSocket(url);

  ws.addEventListener("message", (evt) => {
    try {
      const data = JSON.parse(evt.data);
      if (data.type === "assistant_delta" || data.type === "assistant_message") {
        onAssistantMessage(data);
      }
      if (data.type === "session" && data.session_id) {
        localStorage.setItem("ai_companion_session_id", data.session_id);
      }
    } catch {
      // ignore
    }
  });

  return ws;
}

(async function main() {
  const form = document.getElementById("composer");
  const input = document.getElementById("input");
  const systemPromptEl = document.getElementById("systemPrompt");

  let sessionId = getOrCreateSessionId();
  let ws = null;

  const promptKey = "ai_companion_system_prompt";
  if (systemPromptEl) {
    systemPromptEl.value = localStorage.getItem(promptKey) || "";
    systemPromptEl.addEventListener("input", () => {
      localStorage.setItem(promptKey, systemPromptEl.value || "");
    });
  }

  // Load persisted history/prompt (best-effort)
  loadSession(sessionId)
    .then((data) => {
      if (!data) return;
      if (systemPromptEl && (data.system_prompt || "").trim()) {
        systemPromptEl.value = String(data.system_prompt);
        localStorage.setItem(promptKey, systemPromptEl.value || "");
      }
      const msgs = Array.isArray(data.messages) ? data.messages : [];
      for (const m of msgs) {
        if (!m || !m.role) continue;
        appendMessage({ role: m.role === "assistant" ? "assistant" : "user", content: String(m.content ?? "") });
      }
    })
    .catch(() => {
      // ignore
    });

  let streamingAssistant = null;
  let streamingText = "";

  try {
    ws = await connectWebSocketFromConfig((data) => {
      if (data.session_id) sessionId = data.session_id;

      if (data.type === "assistant_delta") {
        if (!streamingAssistant) {
          streamingText = "";
          streamingAssistant = appendMessage({ role: "assistant", content: "" });
        }
        streamingText += String(data.content ?? "");
        streamingAssistant.bubble.textContent = streamingText;
        return;
      }

      // final
      if (streamingAssistant) {
        streamingAssistant.bubble.textContent = String(data.content ?? streamingText ?? "");
        streamingAssistant = null;
        streamingText = "";
      } else {
        appendMessage({ role: "assistant", content: String(data.content ?? "") });
      }
    });
  } catch {
    ws = null;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = (input.value || "").trim();
    if (!text) return;

    input.value = "";
    appendMessage({ role: "user", content: text });

    const systemPrompt = systemPromptEl ? (systemPromptEl.value || "").trim() : "";

    // Prefer WebSocket, fallback to HTTP
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(
        JSON.stringify({
          type: "user_message",
          content: text,
          session_id: sessionId,
          system_prompt: systemPrompt,
          stream: true,
        })
      );
      return;
    }

    try {
      const data = await sendViaHttp(text, sessionId, systemPrompt);
      if (data.session_id) sessionId = data.session_id;
      appendMessage({ role: "assistant", content: String(data.reply ?? "") });
    } catch {
      appendMessage({ role: "assistant", content: "发送失败，请稍后重试。" });
    }
  });
})();
