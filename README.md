# ClipShare

Small self-hosted clipboard sharing app for quick text snippets and images, with encrypted local storage.

## Features

- Add text entries one at a time
- Add image entries from a file picker
- Paste screenshots directly from the clipboard
- Copy individual entries quickly
- Clear the shared pad from the UI
- Encrypted at-rest vault using Fernet
- Serialized write operations so concurrent users do not clobber each other

## Run

```bash
python3 clipshare_server.py
```

The server listens on `0.0.0.0:8765` over HTTPS when `clipshare_cert.pem`
and `clipshare_key.pem` are present. It also starts a plain HTTP fallback on
`0.0.0.0:8768` and an alternate HTTPS listener on `0.0.0.0:8767`, but browser
image-copy support requires an HTTPS URL.

If the cert/key files are missing, ClipShare starts only the plain HTTP listener
on `0.0.0.0:8768`.

Open:

```text
https://<your-host>:8765
```

## Security

On first startup, ClipShare creates `clipshare_secrets.json` with the Fernet
encryption key used for the local vault.

ClipShare does not currently require login credentials. Run it only on a
trusted network or put it behind an authenticating reverse proxy if other users
can reach the host.

## Files

- `clipshare_server.py`: single-file HTTP server and UI
- `clipshare_vault.dat`: encrypted runtime data store
- `clipshare_secrets.json`: local encryption material

## Notes

- Legacy plaintext `clipshare.txt` data is migrated into the encrypted vault on first startup.
- Image entries are stored inline so they survive page reloads.
- Runtime vault, secrets, and local cert/key files are intentionally ignored by git.
