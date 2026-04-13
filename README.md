# ClipShare

Small self-hosted clipboard sharing app for quick text snippets and images.

## Features

- Add text entries one at a time
- Add image entries from a file picker
- Paste screenshots directly from the clipboard
- Copy individual entries quickly
- Clear the shared pad from the UI

## Run

```bash
python3 clipshare_server.py
```

The server listens on `0.0.0.0:8765`.

Open:

```text
http://<your-host>:8765
```

## Files

- `clipshare_server.py`: single-file HTTP server and UI
- `clipshare.txt`: runtime data store for shared entries

## Notes

- Text entries are stored line by line.
- Image entries are stored inline so they survive page reloads.
- `clipshare.txt` is intentionally ignored by git because it contains live clipboard content.
