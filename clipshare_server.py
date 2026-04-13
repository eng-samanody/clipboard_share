#!/usr/bin/env python3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


HOST = "0.0.0.0"
PORT = 8765
APP_DIR = Path(__file__).resolve().parent
DATA_FILE = APP_DIR / "clipshare.txt"


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
      --surface: rgba(255, 251, 245, 0.9);
      --surface-strong: #fffdf9;
      --ink: #1f1812;
      --muted: #6b5f55;
      --line: rgba(95, 69, 43, 0.16);
      --shadow: 0 24px 70px rgba(75, 45, 17, 0.14);
      --brand: #bd4f26;
      --brand-strong: #97371a;
      --brand-soft: #f7d7bf;
      --success: #1f7a52;
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
      width: min(1100px, calc(100% - 2rem));
      margin: 2rem auto;
      padding: 1.5rem;
      border: 1px solid rgba(255, 255, 255, 0.45);
      border-radius: 30px;
      background: linear-gradient(180deg, rgba(255, 251, 245, 0.88), rgba(255, 248, 241, 0.92));
      box-shadow: var(--shadow);
      backdrop-filter: blur(18px);
    }}
    .entries {{
      padding: 1rem;
      border-radius: 28px;
      background: rgba(255, 252, 248, 0.76);
      border: 1px solid rgba(95, 69, 43, 0.1);
    }}
    .toolbar {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 1rem;
      padding: 0.45rem 0.35rem 1rem;
      flex-wrap: wrap;
    }}
    .toolbar h2 {{
      margin: 0;
      font-size: 1.1rem;
      letter-spacing: -0.03em;
    }}
    .toolbar p {{
      margin: 0.25rem 0 0;
      color: var(--muted);
      font-size: 0.94rem;
    }}
    .status {{
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.55rem 0.8rem;
      border-radius: 999px;
      background: rgba(247, 215, 191, 0.45);
      color: #754123;
      font-size: 0.92rem;
      white-space: nowrap;
    }}
    .actions {{
      display: flex;
      gap: 0.75rem;
      flex-wrap: wrap;
    }}
    button, a.copy {{
      appearance: none;
      border: 1px solid transparent;
      border-radius: 999px;
      padding: 0.85rem 1.1rem;
      font: inherit;
      font-weight: 600;
      cursor: pointer;
      text-decoration: none;
      transition: transform 140ms ease, background 140ms ease, border-color 140ms ease, color 140ms ease, box-shadow 140ms ease;
    }}
    button:hover, a.copy:hover {{
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
    .entries-grid {{
      display: grid;
      gap: 0.85rem;
      margin-top: 1rem;
    }}
    .entry-actions {{
      display: flex;
      gap: 0.6rem;
      flex-wrap: wrap;
      justify-content: flex-end;
    }}
    .entry-card {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 0.85rem;
      align-items: start;
      padding: 0.95rem 1rem;
      border-radius: 20px;
      background: var(--surface-strong);
      border: 1px solid rgba(95, 69, 43, 0.1);
    }}
    .entry-label {{
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
    .entry-meta {{
      margin: 0;
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.5;
      word-break: break-word;
    }}
    .entry-copy {{
      padding-inline: 0.95rem;
      min-width: 6.2rem;
      text-align: center;
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
    @media (max-width: 640px) {{
      .shell {{
        width: min(100% - 1rem, 100%);
        margin: 0.5rem auto;
        padding: 0.75rem;
        border-radius: 22px;
      }}
      .entries {{
        padding: 1rem;
        border-radius: 22px;
      }}
      .actions,
      .add-row {{
        width: 100%;
      }}
      .actions > * {{
        flex: 1 1 calc(50% - 0.5rem);
        text-align: center;
      }}
      .add-row {{
        grid-template-columns: 1fr;
      }}
      .entry-card {{
        grid-template-columns: 1fr;
      }}
      .entry-copy,
      .entry-actions,
      .entry-actions > * {{
        width: 100%;
      }}
      .status {{
        width: 100%;
        justify-content: center;
      }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="entries">
      <div class="toolbar">
        <div>
          <h2>Entries</h2>
          <p>Text entries still work line by line. You can also add screenshots or other images from a file picker or paste directly from the clipboard.</p>
        </div>
        <div class="status" id="entriesStatus">Quick copy ready</div>
      </div>
      <div class="actions">
        <button type="button" class="secondary" id="copyAllBtn">Copy All</button>
        <button type="button" class="danger" id="clearAllBtn">Clear All</button>
      </div>
      <div class="add-row">
        <input type="text" id="addInput" class="add-input" placeholder="Add a new entry and save immediately">
        <button type="button" class="ghost" id="addImageBtn">Add Image</button>
        <button type="button" class="primary" id="addBtn">Add</button>
      </div>
      <input type="file" id="imageInput" accept="image/*" hidden>
      <div class="entries-grid" id="entriesList"></div>
    </section>
    <form method="post" action="/set" id="editorForm" hidden>
      <textarea name="text" id="editor">{text}</textarea>
    </form>
  </main>
  <script>
    const editor = document.getElementById("editor");
    const addInput = document.getElementById("addInput");
    const addImageBtn = document.getElementById("addImageBtn");
    const imageInput = document.getElementById("imageInput");
    const addBtn = document.getElementById("addBtn");
    const copyAllBtn = document.getElementById("copyAllBtn");
    const clearAllBtn = document.getElementById("clearAllBtn");
    const form = document.getElementById("editorForm");
    const entriesStatus = document.getElementById("entriesStatus");
    const entriesList = document.getElementById("entriesList");

    function setStatus(target, message, tone = "default") {{
      const tones = {{
        default: ["rgba(247, 215, 191, 0.45)", "#754123"],
        success: ["rgba(204, 239, 223, 0.8)", "#1f7a52"],
        active: ["rgba(255, 232, 209, 0.9)", "#8f3a19"]
      }};
      const [bg, fg] = tones[tone] || tones.default;
      target.textContent = message;
      target.style.background = bg;
      target.style.color = fg;
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

      if (copied) {{
        setStatus(entriesStatus, message, "success");
      }} else {{
        setStatus(entriesStatus, "Copy failed", "active");
      }}
    }}

    async function copyImage(entry) {{
      if (!entry || entry.type !== "image" || !entry.src) {{
        setStatus(entriesStatus, "Image missing", "active");
        return;
      }}

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

      setStatus(entriesStatus, "Copied image", "success");
    }}

    function buildEntries(value) {{
      return value
        .split("\\n")
        .map((entry) => entry.trim())
        .filter(Boolean)
        .map((entry) => {{
          if (entry.startsWith("@clipshare:image ")) {{
            const src = entry.slice("@clipshare:image ".length).trim();
            return {{
              type: "image",
              src,
              raw: entry
            }};
          }}

          return {{
            type: "text",
            text: entry,
            raw: entry
          }};
        }});
    }}

    function serializeEntry(entry) {{
      if (entry.type === "image") {{
        return "@clipshare:image " + entry.src;
      }}

      return entry.text;
    }}

    function persistEntries(entries) {{
      editor.value = entries.map(serializeEntry).join("\\n");
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

      const encoded = parts[1];
      return humanFileSize(Math.floor((encoded.length * 3) / 4));
    }}

    function describeImageSource(src) {{
      const size = estimateDataUrlSize(src);
      if (src.startsWith("data:")) {{
        return "Stored inline" + (size ? " • " + size : "");
      }}

      return src;
    }}

    function createImageEntry(src) {{
      return {{
        type: "image",
        src: src.trim()
      }};
    }}

    function addEntryObject(entry) {{
      const entries = buildEntries(editor.value);
      entries.push(entry);
      persistEntries(entries);
      renderEntries();
      return true;
    }}

    function readFileAsDataUrl(file) {{
      return new Promise((resolve, reject) => {{
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("Could not read image"));
        reader.readAsDataURL(file);
      }});
    }}

    function flattenEntriesForClipboard(entries) {{
      return entries.map((entry) => entry.type === "image" ? entry.src : entry.text).join("\\n");
    }}

    function renderEntries() {{
      const entries = buildEntries(editor.value);
      const orderedEntries = entries
        .map((entry, index) => ({{ entry, index }}))
        .reverse();
      entriesList.innerHTML = "";

      if (!orderedEntries.length) {{
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No entries yet. Add text above, choose an image, or paste a screenshot and quick actions will appear here.";
        entriesList.appendChild(empty);
        setStatus(entriesStatus, "No entries", "default");
        return;
      }}

      orderedEntries.forEach((item, displayIndex) => {{
        const entry = item.entry;
        const sourceIndex = item.index;
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
        deleteBtn.className = "danger entry-copy";
        deleteBtn.textContent = "Delete";
        deleteBtn.addEventListener("click", () => {{
          const nextEntries = buildEntries(editor.value).filter((_, itemIndex) => itemIndex !== sourceIndex);
          persistEntries(nextEntries);
          renderEntries();
          form.requestSubmit();
          setStatus(entriesStatus, "Deleting entry...", "active");
        }});

        const copyBtn = document.createElement("button");
        copyBtn.type = "button";
        copyBtn.className = "secondary entry-copy";
        copyBtn.textContent = entry.type === "image" ? "Copy Image" : "Copy";
        copyBtn.addEventListener("click", async () => {{
          if (entry.type === "image") {{
            await copyImage(entry);
            return;
          }}

          await copyText(entry.text, "Copied entry " + (entries.length - displayIndex));
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

      setStatus(entriesStatus, entries.length + (entries.length === 1 ? " entry" : " entries"), "default");
    }}

    function appendEntry(value) {{
      const entry = value.trim();
      if (!entry) {{
        setStatus(entriesStatus, "Nothing to add", "active");
        addInput.focus();
        return false;
      }}

      return addEntryObject({{ type: "text", text: entry }});
    }}

    async function appendImageFile(file) {{
      if (!file) {{
        return false;
      }}

      if (!file.type.startsWith("image/")) {{
        setStatus(entriesStatus, "Only image files are supported", "active");
        return false;
      }}

      setStatus(entriesStatus, "Reading image...", "active");

      try {{
        const src = await readFileAsDataUrl(file);
        addEntryObject(createImageEntry(src));
        setStatus(entriesStatus, "Saving image...", "active");
        form.requestSubmit();
        return true;
      }} catch (error) {{
        setStatus(entriesStatus, "Could not add image", "active");
        return false;
      }}
    }}

    addBtn.addEventListener("click", () => {{
      if (!appendEntry(addInput.value)) {{
        return;
      }}

      addInput.value = "";
      setStatus(entriesStatus, "Saving...", "active");
      form.requestSubmit();
    }});

    addImageBtn.addEventListener("click", () => {{
      imageInput.click();
    }});

    imageInput.addEventListener("change", async () => {{
      const [file] = imageInput.files || [];
      await appendImageFile(file);
      imageInput.value = "";
    }});

    addInput.addEventListener("keydown", (event) => {{
      if (event.key === "Enter") {{
        event.preventDefault();
        addBtn.click();
      }}
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
      await copyText(flattenEntriesForClipboard(buildEntries(editor.value)), "Copied all entries");
    }});

    clearAllBtn.addEventListener("click", () => {{
      if (!editor.value) {{
        setStatus(entriesStatus, "Already empty", "default");
        return;
      }}

      const confirmed = window.confirm("Clear the entire shared pad?");
      if (!confirmed) {{
        return;
      }}

      editor.value = "";
      renderEntries();
      setStatus(entriesStatus, "Clearing...", "active");
      form.requestSubmit();
    }});

    renderEntries();
  </script>
</body>
</html>
"""


def read_text() -> str:
    try:
        return DATA_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def write_text(value: str) -> None:
    DATA_FILE.write_text(value, encoding="utf-8")


def html_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/raw":
            body = read_text().encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        body = HTML.format(text=html_escape(read_text())).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path not in {"/set", "/"}:
            self.send_error(404)
            return

        length = int(self.headers.get("Content-Length", "0"))
        payload = self.rfile.read(length).decode("utf-8", errors="replace")
        content_type = self.headers.get("Content-Type", "")

        if "application/x-www-form-urlencoded" in content_type:
            text = parse_qs(payload, keep_blank_values=True).get("text", [""])[0]
        else:
            text = payload

        write_text(text)
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


if __name__ == "__main__":
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"ClipShare listening on http://{HOST}:{PORT}")
    server.serve_forever()
