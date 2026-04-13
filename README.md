# ClipShare

Small self-hosted clipboard sharing app for quick text snippets and images, with authenticated access, encrypted storage, and revision history.

## Features

- Add text entries one at a time
- Add image entries from a file picker
- Paste screenshots directly from the clipboard
- Copy individual entries quickly
- Clear the shared pad from the UI
- HTTP Basic authentication for all routes
- Encrypted at-rest vault using Fernet
- Revision snapshots with restore support
- Serialized write operations so concurrent users do not clobber each other

## Run

```bash
python3 clipshare_server.py
```

The server listens on `0.0.0.0:8765` over plain HTTP.

Open:

```text
http://<your-host>:8765
```

## Authentication

On first startup, ClipShare creates:

- `clipshare_secrets.json`: password hash and encryption key
- `clipshare_bootstrap.txt`: initial username and password

Read the bootstrap file once, store the password somewhere safe, then delete the bootstrap file.

You can also provide your own startup credentials:

```bash
CLIPSHARE_USERNAME=myuser CLIPSHARE_PASSWORD='strong-password' python3 clipshare_server.py
```

## Files

- `clipshare_server.py`: single-file HTTP server and UI
- `clipshare_vault.dat`: encrypted runtime data store
- `clipshare_secrets.json`: local auth and encryption material

## Notes

- Legacy plaintext `clipshare.txt` data is migrated into the encrypted vault on first secure startup.
- Image entries are stored inline so they survive page reloads.
- Runtime vault, bootstrap credentials, secrets, and local cert/key files are intentionally ignored by git.
