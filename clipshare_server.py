#!/usr/bin/env python3
import base64
import copy
import ipaddress
import json
import os
import secrets
import socket
import ssl
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import bcrypt
from cryptography import x509
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


HOST = "0.0.0.0"
PORT = 8765
APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "clipshare_vault.dat"
LEGACY_TEXT_FILE = APP_DIR / "clipshare.txt"
SECRETS_FILE = APP_DIR / "clipshare_secrets.json"
BOOTSTRAP_FILE = APP_DIR / "clipshare_bootstrap.txt"
TLS_CERT_FILE = APP_DIR / "clipshare_cert.pem"
TLS_KEY_FILE = APP_DIR / "clipshare_key.pem"
HISTORY_LIMIT = 12
STATE_LOCK = threading.Lock()


HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>ClipShare</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6efe5;
      --bg-accent: #efe0ca;
      --surface-strong: #fffdf9;
      --ink: #1f1812;
      --muted: #6b5f55;
      --shadow: 0 24px 70px rgba(75, 45, 17, 0.14);
      --brand: #bd4f26;
      --brand-strong: #97371a;
      --brand-soft: #f7d7bf;
      --success: #1f7a52;
      --warn: #8f3a19;
      --card: rgba(255, 252, 248, 0.76);
      --line: rgba(95, 69, 43, 0.1);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(255, 255, 255, 0.75), transparent 34%),
        radial-gradient(circle at bottom right, rgba(189, 79, 38, 0.12), transparent 30%),
        linear-gradient(160deg, var(--bg) 0%, var(--bg-accent) 100%);
      color: var(--ink);
    }}
    .shell {{
      width: min(1120px, calc(100% - 2rem));
      margin: 2rem auto;
      padding: 1.5rem;
      border: 1px solid rgba(255, 255, 255, 0.45);
      border-radius: 30px;
      background: linear-gradient(180deg, rgba(255, 251, 245, 0.88), rgba(255, 248, 241, 0.92));
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .stack {{
      display: grid;
      gap: 1rem;
    }}
    .panel {{
      padding: 1rem;
      border-radius: 28px;
      background: var(--card);
      border: 1px solid var(--line);
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      padding: 0.45rem 0.35rem 1rem;
      flex-wrap: wrap;
    }}
    .toolbar-copy {{
      display: flex;
      align-items: center;
      justify-content: flex-end;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .toolbar h2,
    .history-head h2 {{
      margin: 0;
      font-size: 1.1rem;
      letter-spacing: -0.03em;
    }}
    .toolbar p,
    .history-head p {{
      margin: 0.25rem 0 0;
      color: var(--muted);
      font-size: 0.94rem;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 0.45rem;
      min-height: 3rem;
      padding: 0.85rem 1.1rem;
      border-radius: 999px;
      background: rgba(247, 215, 191, 0.45);
      color: #754123;
      font-size: 0.92rem;
      font-weight: 600;
      white-space: nowrap;
    }}
    .security-note {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.55rem 0.8rem;
      border-radius: 999px;
      background: rgba(204, 239, 223, 0.68);
      color: var(--success);
      font-size: 0.88rem;
      font-weight: 700;
    }}
    .actions {{
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    .toolbar .actions {{
      justify-content: flex-end;
    }}
    button {{
      appearance: none;
      border: 1px solid transparent;
      border-radius: 999px;
      min-height: 3rem;
      padding: 0.85rem 1.1rem;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      transition: transform 140ms ease, background 140ms ease, border-color 140ms ease, color 140ms ease, box-shadow 140ms ease;
    }}
    button:hover {{
      transform: translateY(-1px);
    }}
    .primary {{
      background: linear-gradient(180deg, var(--brand), var(--brand-strong));
      color: #fffaf5;
      box-shadow: 0 10px 24px rgba(151, 55, 26, 0.24);
    }}
    .secondary {{
      background: #fff6ee;
      color: #7d4327;
      border-color: rgba(189, 79, 38, 0.18);
    }}
    .danger {{
      background: #fff0ec;
      color: #a1371d;
      border-color: rgba(161, 55, 29, 0.18);
    }}
    .ghost {{
      background: transparent;
      color: var(--muted);
      border-color: rgba(95, 69, 43, 0.12);
    }}
    .mini {{
      min-height: auto;
      padding: 0.55rem 0.8rem;
      font-size: 0.9rem;
    }}
    .add-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto auto;
      gap: 0.75rem;
      align-items: center;
    }}
    .add-input {{
      width: 100%;
      min-width: 0;
      border: 1px solid rgba(95, 69, 43, 0.13);
      border-radius: 999px;
      padding: 0.9rem 1rem;
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 251, 247, 0.96));
      color: #241b14;
      font: inherit;
    }}
    .add-input:focus {{
      outline: 2px solid rgba(189, 79, 38, 0.28);
      border-color: rgba(189, 79, 38, 0.35);
    }}
    .entries-grid,
    .history-list {{
      display: grid;
      gap: 0.85rem;
      margin-top: 1rem;
    }}
    .entry-actions,
    .history-actions {{
      display: flex;
      gap: 0.6rem;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .entry-card,
    .history-card {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 0.85rem;
      align-items: start;
      padding: 0.95rem 1rem;
      border-radius: 20px;
      background: var(--surface-strong);
      border: 1px solid var(--line);
    }}
    .entry-label,
    .history-label {{
      margin: 0 0 0.45rem;
      font-size: 0.8rem;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: #9a7154;
    }}
    .entry-value {{
      margin: 0;
      color: var(--ink);
      font: 14px/1.55 "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .entry-media {{
      display: grid;
      gap: 0.8rem;
    }}
    .entry-kind {{
      display: inline-flex;
      align-items: center;
      width: fit-content;
      margin-bottom: 0.7rem;
      padding: 0.3rem 0.55rem;
      border-radius: 999px;
      background: var(--brand-soft);
      color: #8f3a19;
      font-size: 0.76rem;
      font-weight: 700;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}
    .entry-image {{
      display: block;
      max-width: min(100%, 420px);
      max-height: 280px;
      border-radius: 16px;
      border: 1px solid rgba(95, 69, 43, 0.12);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(248, 241, 232, 0.94));
      box-shadow: 0 16px 28px rgba(75, 45, 17, 0.08);
      object-fit: contain;
    }}
    .entry-meta,
    .history-meta {{
      margin: 0;
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.5;
      word-break: break-word;
    }}
    .empty-state {{
      padding: 1rem;
      border-radius: 18px;
      background: rgba(247, 215, 191, 0.2);
      border: 1px dashed rgba(189, 79, 38, 0.24);
      color: var(--muted);
    }}
    .pulse {{
      width: 0.55rem;
      height: 0.55rem;
      border-radius: 999px;
      background: var(--success);
      box-shadow: 0 0 0 0 rgba(31, 122, 82, 0.35);
      animation: pulse 2.2s infinite;
    }}
    @keyframes pulse {{
      0% {{ box-shadow: 0 0 0 0 rgba(31, 122, 82, 0.35); }}
      70% {{ box-shadow: 0 0 0 12px rgba(31, 122, 82, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(31, 122, 82, 0); }}
    }}
    @media (max-width: 720px) {{
      .shell {{
        width: min(100% - 1rem, 100%);
        margin: 0.5rem auto;
        padding: 0.75rem;
        border-radius: 22px;
      }}
      .panel {{
        padding: 1rem;
        border-radius: 22px;
      }}
      .toolbar-copy,
      .actions,
      .add-row {{
        width: 100%;
      }}
      .toolbar-copy {{
        justify-content: stretch;
      }}
      .toolbar-copy > *,
      .actions > * {{
        flex: 1 1 calc(50% - 0.5rem);
        text-align: center;
      }}
      .add-row {{
        grid-template-columns: 1fr;
      }}
      .entry-card,
      .history-card {{
        grid-template-columns: 1fr;
      }}
      .entry-actions,
      .entry-actions > *,
      .history-actions,
      .history-actions > * {{
        width: 100%;
      }}
      .status,
      .security-note {{
        width: 100%;
        justify-content: center;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <div class="stack">
      <section class="panel">
        <div class="toolbar">
          <div>
            <h2>Entries</h2>
            <p>Authenticated access, encrypted storage, serialized writes, and revision history are active.</p>
          </div>
          <div class="toolbar-copy">
            <div class="security-note"><span class="pulse"></span> Secure Mode</div>
            <div class="status" id="entriesStatus">Loading vault…</div>
            <div class="actions">
              <button type="button" class="secondary" id="copyAllBtn">Copy All</button>
              <button type="button" class="danger" id="clearAllBtn">Clear All</button>
            </div>
          </div>
        </div>
        <div class="add-row">
          <input type="text" id="addInput" class="add-input" placeholder="Add a new entry">
          <button type="button" class="ghost" id="addImageBtn">Add Image</button>
          <button type="button" class="primary" id="addBtn">Add</button>
        </div>
        <input type="file" id="imageInput" accept="image/*" hidden>
        <div class="entries-grid" id="entriesList"></div>
      </section>

      <section class="panel">
        <div class="history-head">
          <h2>Recent Versions</h2>
          <p>Every mutation is stored as an encrypted revision snapshot. You can restore an earlier state if needed.</p>
        </div>
        <div class="history-list" id="historyList"></div>
      </section>
    </div>
  </main>

  <script>
    const addInput = document.getElementById("addInput");
    const addImageBtn = document.getElementById("addImageBtn");
    const imageInput = document.getElementById("imageInput");
    const addBtn = document.getElementById("addBtn");
    const copyAllBtn = document.getElementById("copyAllBtn");
    const clearAllBtn = document.getElementById("clearAllBtn");
    const entriesStatus = document.getElementById("entriesStatus");
    const entriesList = document.getElementById("entriesList");
    const historyList = document.getElementById("historyList");

    let currentState = {{
      revision: 0,
      updated_at: "",
      entries: [],
      history: []
    }};

    function setStatus(message, tone = "default") {{
      const tones = {{
        default: ["rgba(247, 215, 191, 0.45)", "#754123"],
        success: ["rgba(204, 239, 223, 0.8)", "#1f7a52"],
        active: ["rgba(255, 232, 209, 0.9)", "#8f3a19"]
      }};
      const [bg, fg] = tones[tone] || tones.default;
      entriesStatus.textContent = message;
      entriesStatus.style.background = bg;
      entriesStatus.style.color = fg;
    }}

    function legacyCopyText(value) {{
      const helper = document.createElement("textarea");
      helper.value = value;
      helper.setAttribute("readonly", "");
      helper.style.position = "fixed";
      helper.style.top = "-1000px";
      helper.style.opacity = "0";
      document.body.appendChild(helper);
      helper.focus();
      helper.select();
      helper.setSelectionRange(0, helper.value.length);

      let copied = false;
      try {{
        copied = document.execCommand("copy");
      }} catch (error) {{
        copied = false;
      }}

      document.body.removeChild(helper);
      return copied;
    }}

    async function copyText(value, message = "Copied to clipboard") {{
      let copied = false;

      if (navigator.clipboard && window.isSecureContext) {{
        try {{
          await navigator.clipboard.writeText(value);
          copied = true;
        }} catch (error) {{
          copied = false;
        }}
      }}

      if (!copied) {{
        copied = legacyCopyText(value);
      }}

      setStatus(copied ? message : "Copy failed", copied ? "success" : "active");
    }}

    async function copyImage(entry) {{
      let copied = false;
      if (navigator.clipboard && window.isSecureContext && window.ClipboardItem) {{
        try {{
          const response = await fetch(entry.src);
          const blob = await response.blob();
          await navigator.clipboard.write([
            new ClipboardItem({{ [blob.type || "image/png"]: blob }})
          ]);
          copied = true;
        }} catch (error) {{
          copied = false;
        }}
      }}

      if (!copied) {{
        await copyText(entry.src, "Copied image data URL");
        return;
      }}

      setStatus("Copied image", "success");
    }}

    function humanFileSize(size) {{
      if (!Number.isFinite(size) || size <= 0) {{
        return "";
      }}

      const units = ["B", "KB", "MB", "GB"];
      let value = size;
      let unitIndex = 0;

      while (value >= 1024 && unitIndex < units.length - 1) {{
        value /= 1024;
        unitIndex += 1;
      }}

      const precision = value >= 10 || unitIndex === 0 ? 0 : 1;
      return value.toFixed(precision) + " " + units[unitIndex];
    }}

    function estimateDataUrlSize(src) {{
      const parts = src.split(",", 2);
      if (parts.length !== 2) {{
        return "";
      }}

      return humanFileSize(Math.floor((parts[1].length * 3) / 4));
    }}

    function describeImageSource(src) {{
      const size = estimateDataUrlSize(src);
      if (src.startsWith("data:")) {{
        return "Stored inline" + (size ? " • " + size : "");
      }}

      return src;
    }}

    function flattenEntriesForClipboard(entries) {{
      return entries.map((entry) => entry.type === "image" ? entry.src : entry.text).join("\\n");
    }}

    function formatTimestamp(value) {{
      if (!value) {{
        return "Unknown time";
      }}

      const date = new Date(value);
      if (Number.isNaN(date.getTime())) {{
        return value;
      }}

      return new Intl.DateTimeFormat(undefined, {{
        dateStyle: "medium",
        timeStyle: "short"
      }}).format(date);
    }}

    function renderEntries() {{
      const entries = currentState.entries || [];
      const orderedEntries = [...entries].reverse();
      entriesList.innerHTML = "";

      if (!orderedEntries.length) {{
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No entries yet. Add text above, choose an image, or paste a screenshot.";
        entriesList.appendChild(empty);
        return;
      }}

      orderedEntries.forEach((entry, displayIndex) => {{
        const card = document.createElement("article");
        card.className = "entry-card";

        const content = document.createElement("div");

        const label = document.createElement("p");
        label.className = "entry-label";
        label.textContent = "Entry " + (entries.length - displayIndex);

        const kind = document.createElement("div");
        kind.className = "entry-kind";
        kind.textContent = entry.type;

        let value;
        if (entry.type === "image") {{
          value = document.createElement("div");
          value.className = "entry-media";

          const image = document.createElement("img");
          image.className = "entry-image";
          image.src = entry.src;
          image.alt = "Shared image entry";
          image.loading = "lazy";

          const meta = document.createElement("p");
          meta.className = "entry-meta";
          meta.textContent = describeImageSource(entry.src);

          value.appendChild(image);
          value.appendChild(meta);
        }} else {{
          value = document.createElement("pre");
          value.className = "entry-value";
          value.textContent = entry.text;
        }}

        const actions = document.createElement("div");
        actions.className = "entry-actions";

        const deleteBtn = document.createElement("button");
        deleteBtn.type = "button";
        deleteBtn.className = "danger";
        deleteBtn.textContent = "Delete";
        deleteBtn.addEventListener("click", async () => {{
          await mutate("/api/delete", {{ entry_id: entry.id }}, "Deleting entry...");
        }});

        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "secondary";
        copyBtn.textContent = entry.type === "image" ? "Copy Image" : "Copy";
        copyBtn.addEventListener("click", async () => {{
          if (entry.type === "image") {{
            await copyImage(entry);
            return;
          }}

          await copyText(entry.text, "Copied entry");
        }});

        content.appendChild(label);
        content.appendChild(kind);
        content.appendChild(value);
        actions.appendChild(deleteBtn);
        actions.appendChild(copyBtn);
        card.appendChild(content);
        card.appendChild(actions);
        entriesList.appendChild(card);
      }});
    }}

    function renderHistory() {{
      const history = currentState.history || [];
      historyList.innerHTML = "";

      if (!history.length) {{
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No revisions yet.";
        historyList.appendChild(empty);
        return;
      }}

      history.forEach((item) => {{
        const card = document.createElement("article");
        card.className = "history-card";

        const content = document.createElement("div");

        const label = document.createElement("p");
        label.className = "history-label";
        label.textContent = "Revision " + item.revision;

        const meta = document.createElement("p");
        meta.className = "history-meta";
        meta.textContent = item.summary + " • " + item.entry_count + (item.entry_count === 1 ? " entry" : " entries") + " • " + formatTimestamp(item.updated_at);

        content.appendChild(label);
        content.appendChild(meta);

        const actions = document.createElement("div");
        actions.className = "history-actions";

        if (item.revision !== currentState.revision) {{
          const restoreBtn = document.createElement("button");
          restoreBtn.type = "button";
          restoreBtn.className = "ghost mini";
          restoreBtn.textContent = "Restore";
          restoreBtn.addEventListener("click", async () => {{
            const confirmed = window.confirm("Restore revision " + item.revision + "? This creates a new revision.");
            if (!confirmed) {{
              return;
            }}

            await mutate("/api/restore", {{ revision: item.revision }}, "Restoring revision...");
          }});
          actions.appendChild(restoreBtn);
        }}

        card.appendChild(content);
        card.appendChild(actions);
        historyList.appendChild(card);
      }});
    }}

    function renderAll() {{
      renderEntries();
      renderHistory();
      const count = currentState.entries.length;
      const suffix = count === 1 ? "entry" : "entries";
      const updated = currentState.updated_at ? " • " + formatTimestamp(currentState.updated_at) : "";
      setStatus(count + " " + suffix + " • rev " + currentState.revision + updated, "default");
    }}

    async function api(path, options = {{}}) {{
      const response = await fetch(path, {{
        credentials: "same-origin",
        headers: {{
          "Content-Type": "application/json"
        }},
        cache: "no-store",
        ...options
      }});

      let payload = {{}};
      try {{
        payload = await response.json();
      }} catch (error) {{
        payload = {{}};
      }}

      if (!response.ok) {{
        const message = payload.error || "Request failed";
        throw new Error(message);
      }}

      return payload;
    }}

    async function fetchState(silent = false) {{
      try {{
        const payload = await api("/api/state", {{ method: "GET" }});
        const nextState = payload.state;
        const changed = nextState.revision !== currentState.revision;
        currentState = nextState;
        renderAll();
        if (changed && !silent) {{
          setStatus("Synced revision " + currentState.revision, "success");
        }}
      }} catch (error) {{
        setStatus(error.message, "active");
      }}
    }}

    async function mutate(path, body, pendingMessage) {{
      setStatus(pendingMessage, "active");
      try {{
        const payload = await api(path, {{
          method: "POST",
          body: JSON.stringify(body)
        }});
        currentState = payload.state;
        renderAll();
      }} catch (error) {{
        setStatus(error.message, "active");
      }}
    }}

    function readFileAsDataUrl(file) {{
      return new Promise((resolve, reject) => {{
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("Could not read image"));
        reader.readAsDataURL(file);
      }});
    }}

    async function appendText() {{
      const text = addInput.value.trim();
      if (!text) {{
        setStatus("Nothing to add", "active");
        addInput.focus();
        return;
      }}

      await mutate("/api/add-text", {{ text }}, "Adding entry...");
      addInput.value = "";
    }}

    async function appendImageFile(file) {{
      if (!file) {{
        return;
      }}

      if (!file.type.startsWith("image/")) {{
        setStatus("Only image files are supported", "active");
        return;
      }}

      setStatus("Reading image...", "active");
      try {{
        const src = await readFileAsDataUrl(file);
        await mutate("/api/add-image", {{ src }}, "Saving image...");
      }} catch (error) {{
        setStatus("Could not add image", "active");
      }}
    }}

    addBtn.addEventListener("click", appendText);

    addInput.addEventListener("keydown", (event) => {{
      if (event.key === "Enter") {{
        event.preventDefault();
        addBtn.click();
      }}
    }});

    addImageBtn.addEventListener("click", () => {{
      imageInput.click();
    }});

    imageInput.addEventListener("change", async () => {{
      const [file] = imageInput.files || [];
      await appendImageFile(file);
      imageInput.value = "";
    }});

    document.addEventListener("paste", async (event) => {{
      const items = Array.from(event.clipboardData?.items || []);
      const imageItem = items.find((item) => item.type.startsWith("image/"));
      if (!imageItem) {{
        return;
      }}

      const file = imageItem.getAsFile();
      if (!file) {{
        return;
      }}

      event.preventDefault();
      await appendImageFile(file);
    }});

    copyAllBtn.addEventListener("click", async () => {{
      await copyText(flattenEntriesForClipboard(currentState.entries), "Copied all entries");
    }});

    clearAllBtn.addEventListener("click", async () => {{
      if (!currentState.entries.length) {{
        setStatus("Already empty", "default");
        return;
      }}

      const confirmed = window.confirm("Clear the entire shared vault?");
      if (!confirmed) {{
        return;
      }}

      await mutate("/api/clear", {{}}, "Clearing vault...");
    }});

    window.addEventListener("focus", () => fetchState(true));
    document.addEventListener("visibilitychange", () => {{
      if (!document.hidden) {{
        fetchState(true);
      }}
    }});
    window.setInterval(() => {{
      if (!document.hidden) {{
        fetchState(true);
      }}
    }}, 5000);

    fetchState(true);
  </script>
</body>
</html>
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def secure_write_text(path: Path, value: str) -> None:
    path.write_text(value, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def secure_write_bytes(path: Path, value: bytes, mode: int = 0o600) -> None:
    path.write_bytes(value)
    try:
        os.chmod(path, mode)
    except OSError:
        pass


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def build_auth_header() -> str:
    return 'Basic realm="ClipShare", charset="UTF-8"'


def parse_basic_auth(header: str | None) -> tuple[str | None, str | None]:
    if not header or not header.startswith("Basic "):
        return None, None

    encoded = header.split(" ", 1)[1].strip()
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return None, None

    if ":" not in decoded:
        return None, None

    username, password = decoded.split(":", 1)
    return username, password


def local_addresses() -> tuple[list[str], list[str]]:
    hostnames = {"localhost", socket.gethostname(), socket.getfqdn()}
    ip_values = {"127.0.0.1", "::1"}

    for host in list(hostnames):
        if not host:
            continue
        try:
            for family, _, _, _, sockaddr in socket.getaddrinfo(host, None):
                if family in {socket.AF_INET, socket.AF_INET6}:
                    ip_values.add(sockaddr[0])
        except socket.gaierror:
            continue

    return sorted(name for name in hostnames if name), sorted(ip_values)


def generate_self_signed_cert() -> None:
    if TLS_CERT_FILE.exists() and TLS_KEY_FILE.exists():
        return

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "ClipShare Local")]
    )
    hostnames, ip_values = local_addresses()
    san_values: list[x509.GeneralName] = [x509.DNSName(name) for name in hostnames]

    for value in ip_values:
        try:
            san_values.append(x509.IPAddress(ipaddress.ip_address(value)))
        except ValueError:
            continue

    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc) - timedelta(minutes=5))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365 * 2))
        .add_extension(x509.SubjectAlternativeName(san_values), critical=False)
        .sign(private_key, hashes.SHA256())
    )

    secure_write_bytes(
        TLS_KEY_FILE,
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        ),
        mode=0o600,
    )
    secure_write_bytes(
        TLS_CERT_FILE,
        certificate.public_bytes(serialization.Encoding.PEM),
        mode=0o644,
    )


def ensure_secrets() -> dict[str, str]:
    if SECRETS_FILE.exists():
        return json.loads(SECRETS_FILE.read_text(encoding="utf-8"))

    username = os.environ.get("CLIPSHARE_USERNAME", "clipshare")
    password = os.environ.get("CLIPSHARE_PASSWORD") or secrets.token_urlsafe(18)
    secrets_payload = {
        "username": username,
        "password_hash": bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
        "fernet_key": Fernet.generate_key().decode("utf-8"),
    }
    secure_write_text(SECRETS_FILE, json.dumps(secrets_payload, indent=2))

    if "CLIPSHARE_PASSWORD" not in os.environ:
        secure_write_text(
            BOOTSTRAP_FILE,
            (
                "ClipShare bootstrap credentials\n"
                f"username: {username}\n"
                f"password: {password}\n"
                "Delete this file after copying the password somewhere safe.\n"
            ),
        )
        print(f"Bootstrap credentials written to {BOOTSTRAP_FILE}")

    return secrets_payload


SECRETS = ensure_secrets()
FERNET = Fernet(SECRETS["fernet_key"].encode("utf-8"))


def entry_from_legacy_line(line: str) -> dict[str, Any]:
    if line.startswith("@clipshare:image "):
        return {
            "id": secrets.token_hex(8),
            "type": "image",
            "src": line.split(" ", 1)[1].strip(),
            "created_at": now_iso(),
        }

    return {
        "id": secrets.token_hex(8),
        "type": "text",
        "text": line.strip(),
        "created_at": now_iso(),
    }


def snapshot_for_state(state: dict[str, Any], summary: str) -> dict[str, Any]:
    return {
        "revision": state["revision"],
        "updated_at": state["updated_at"],
        "entry_count": len(state["entries"]),
        "summary": summary,
        "entries": copy.deepcopy(state["entries"]),
    }


def create_state(entries: list[dict[str, Any]], summary: str) -> dict[str, Any]:
    state = {
        "revision": 1,
        "updated_at": now_iso(),
        "entries": entries,
        "history": [],
    }
    state["history"].append(snapshot_for_state(state, summary))
    return state


def persist_state(state: dict[str, Any]) -> None:
    encrypted = FERNET.encrypt(json.dumps(state, separators=(",", ":")).encode("utf-8"))
    secure_write_bytes(DATA_FILE, encrypted, mode=0o600)


def migrate_legacy_state() -> dict[str, Any]:
    text = LEGACY_TEXT_FILE.read_text(encoding="utf-8")
    entries = [
        entry_from_legacy_line(line.strip())
        for line in text.splitlines()
        if line.strip()
    ]
    state = create_state(entries, "Imported legacy plaintext store")
    persist_state(state)
    try:
        LEGACY_TEXT_FILE.unlink()
    except FileNotFoundError:
        pass
    return state


def load_state() -> dict[str, Any]:
    if DATA_FILE.exists():
        encrypted = DATA_FILE.read_bytes()
        try:
          decrypted = FERNET.decrypt(encrypted)
        except InvalidToken as exc:
          raise RuntimeError("Encrypted vault could not be decrypted") from exc
        return json.loads(decrypted.decode("utf-8"))

    if LEGACY_TEXT_FILE.exists():
        return migrate_legacy_state()

    state = create_state([], "Initialized secure vault")
    persist_state(state)
    return state


def flatten_entries(entries: list[dict[str, Any]]) -> str:
    flattened: list[str] = []
    for entry in entries:
        if entry["type"] == "image":
            flattened.append(entry["src"])
        else:
            flattened.append(entry["text"])
    return "\n".join(flattened)


def public_state(state: dict[str, Any]) -> dict[str, Any]:
    history = list(reversed(state.get("history", [])))
    return {
        "revision": state["revision"],
        "updated_at": state["updated_at"],
        "entries": copy.deepcopy(state["entries"]),
        "history": [
            {
                "revision": item["revision"],
                "updated_at": item["updated_at"],
                "entry_count": item["entry_count"],
                "summary": item["summary"],
            }
            for item in history
        ],
    }


def mutate_state(summary: str, mutator) -> dict[str, Any]:
    with STATE_LOCK:
        state = load_state()
        changed = mutator(state)
        if not changed:
            return public_state(state)

        state["revision"] += 1
        state["updated_at"] = now_iso()
        state["history"].append(snapshot_for_state(state, summary))
        state["history"] = state["history"][-HISTORY_LIMIT:]
        persist_state(state)
        return public_state(state)


def require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} is required")
    return value.strip()


class Handler(BaseHTTPRequestHandler):
    server_version = "ClipShare/2.0"

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_unauthorized(self) -> None:
        self.send_response(401)
        self.send_header("WWW-Authenticate", build_auth_header())
        self.send_header("Content-Length", "0")
        self.end_headers()

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        if not raw:
            return {}
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid JSON body") from exc

    def is_authorized(self) -> bool:
        username, password = parse_basic_auth(self.headers.get("Authorization"))
        if not username or not password:
            return False

        if username != SECRETS["username"]:
            return False

        return bcrypt.checkpw(
            password.encode("utf-8"),
            SECRETS["password_hash"].encode("utf-8"),
        )

    def require_auth(self) -> bool:
        if self.is_authorized():
            return True
        self.send_unauthorized()
        return False

    def do_GET(self) -> None:
        if not self.require_auth():
            return

        path = urlparse(self.path).path

        if path == "/raw":
            with STATE_LOCK:
                body = flatten_entries(load_state()["entries"]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if path == "/api/state":
            with STATE_LOCK:
                state = public_state(load_state())
            self.send_json({"state": state})
            return

        if path != "/":
            self.send_error(404)
            return

        body = HTML.format().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if not self.require_auth():
            return

        path = urlparse(self.path).path

        try:
            payload = self.read_json_body()

            if path == "/api/add-text":
                text = require_string(payload.get("text"), "text")
                state = mutate_state(
                    "Added text entry",
                    lambda state: state["entries"].append(
                        {
                            "id": secrets.token_hex(8),
                            "type": "text",
                            "text": text,
                            "created_at": now_iso(),
                        }
                    )
                    or True,
                )
                self.send_json({"state": state})
                return

            if path == "/api/add-image":
                src = require_string(payload.get("src"), "src")
                if not src.startswith("data:image/"):
                    raise ValueError("Only inline image data URLs are accepted")
                state = mutate_state(
                    "Added image entry",
                    lambda state: state["entries"].append(
                        {
                            "id": secrets.token_hex(8),
                            "type": "image",
                            "src": src,
                            "created_at": now_iso(),
                        }
                    )
                    or True,
                )
                self.send_json({"state": state})
                return

            if path == "/api/delete":
                entry_id = require_string(payload.get("entry_id"), "entry_id")

                def delete_entry(state: dict[str, Any]) -> bool:
                    before = len(state["entries"])
                    state["entries"] = [
                        entry for entry in state["entries"] if entry["id"] != entry_id
                    ]
                    return len(state["entries"]) != before

                state = mutate_state("Deleted entry", delete_entry)
                self.send_json({"state": state})
                return

            if path == "/api/clear":
                state = mutate_state(
                    "Cleared vault",
                    lambda state: bool(state["entries"]) and not state["entries"].clear(),
                )
                self.send_json({"state": state})
                return

            if path == "/api/restore":
                revision = payload.get("revision")
                if not isinstance(revision, int):
                    raise ValueError("revision must be an integer")

                def restore_revision(state: dict[str, Any]) -> bool:
                    for snapshot in state["history"]:
                        if snapshot["revision"] == revision:
                            state["entries"] = copy.deepcopy(snapshot["entries"])
                            return True
                    raise ValueError(f"Revision {revision} was not found")

                state = mutate_state(f"Restored revision {revision}", restore_revision)
                self.send_json({"state": state})
                return

            self.send_error(404)
        except ValueError as exc:
            self.send_json({"error": str(exc)}, status=400)
        except RuntimeError as exc:
            self.send_json({"error": str(exc)}, status=500)


def build_server() -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    return httpd


def main() -> None:
    with STATE_LOCK:
        load_state()
    httpd = build_server()
    print(f"ClipShare listening on http://{HOST}:{PORT}")
    httpd.serve_forever()


if __name__ == "__main__":
    main()
