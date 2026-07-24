const BACKEND = "http://localhost:8000";

async function get(endpoint) {
  try {
    const r = await fetch(`${BACKEND}/${endpoint}`);
    return await r.json();
  } catch { return null; }
}

async function post(endpoint, body) {
  try {
    const r = await fetch(`${BACKEND}/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    return await r.json();
  } catch { return null; }
}

function setStatus(dotId, textId, color, text) {
  const dot = document.getElementById(dotId);
  const label = document.getElementById(textId);
  dot.className = `indicator ${color}`;
  label.textContent = text;
}

async function checkStatus() {
  const root = await get("");
  if (root) {
    setStatus("backend-dot", "backend-status", "green", "Connected ✓");
    setStatus("api-dot", "api-status",
      root.api_key_set ? "green" : "orange",
      root.api_key_set ? "Ready ✓" : "Not set ⚙"
    );
  } else {
    setStatus("backend-dot", "backend-status", "red", "Offline ✗");
    setStatus("api-dot", "api-status", "gray", "N/A");
  }
}

async function detectMeeting() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  const url = tab?.url || "";
  let platform = null;
  if (url.includes("meet.google.com")) platform = "Google Meet";
  else if (url.includes("zoom.us"))    platform = "Zoom";
  else if (url.includes("teams.microsoft")) platform = "Teams";
  else if (url.includes("discord.com"))    platform = "Discord";

  if (platform) {
    setStatus("meeting-dot", "meeting-status", "green", platform + " ✓");
  } else {
    setStatus("meeting-dot", "meeting-status", "gray", "Not in meeting");
  }
}

document.getElementById("ask-btn").addEventListener("click", async () => {
  const q = document.getElementById("quick-question").value.trim();
  if (!q) return;
  const btn = document.getElementById("ask-btn");
  btn.textContent = "⏳ Thinking...";
  btn.disabled = true;

  const box = document.getElementById("answer-box");
  box.textContent = "";
  box.classList.add("visible");
  box.textContent = "Asking AI...";

  const result = await post("api/ask", { question: q });
  box.textContent = result?.answer || result?.error || "No response";
  btn.textContent = "✨ Ask AI";
  btn.disabled = false;
});

document.getElementById("summarize-btn").addEventListener("click", async () => {
  const box = document.getElementById("answer-box");
  box.classList.add("visible");
  box.textContent = "⏳ Summarizing...";
  const result = await post("api/summarize");
  box.textContent = result?.summary || result?.error || "No result";
});

document.getElementById("action-items-btn").addEventListener("click", async () => {
  const box = document.getElementById("answer-box");
  box.classList.add("visible");
  box.textContent = "⏳ Extracting...";
  const result = await post("api/action-items");
  box.textContent = result?.items || result?.error || "No result";
});

// Init
checkStatus();
detectMeeting();
