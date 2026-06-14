# FirmShake API

Flask backend for [FirmShake](https://github.com/) — image hosting, meetup ETA computation, payment webhooks, and admin operations.

The Ionic Vue client lives in a separate repo: **`firmshake`** (sibling directory `../firmshake`).

## Stack

- Python 3.11+
- Flask 3
- Local image storage (`storage/images/`)
- Firebase ID token verification (planned for protected routes)

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Server runs at `http://localhost:5001`.

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/api/images` | POST | Upload image (multipart `file`) |
| `/api/images/<filename>` | GET | Serve image |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_HOST` | `0.0.0.0` | Bind host |
| `FLASK_PORT` | `5001` | Bind port |
| `FLASK_DEBUG` | `true` | Debug mode |

## Mobile / device testing

Physical devices cannot reach `localhost`. Run a tunnel and point the app's `VITE_API_BASE_URL` at it:

```bash
ngrok http 5001
```

## Client configuration

In the **firmshake** app repo, set:

```bash
# firmshake/.env.local
VITE_API_BASE_URL=http://localhost:5001
```

Use the ngrok URL when testing on a phone.

## Roadmap (API-owned milestones)

- [x] Health check
- [x] Image upload + serve
- [ ] Firebase token verification on uploads
- [ ] Meetup location ETA endpoints (privacy-preserving)
- [ ] Stripe deposit + penalty webhooks
- [ ] Admin community seeding endpoints

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design.

## Related repo

| Repo | Purpose |
|---|---|
| **firmshake** | Ionic Vue + Capacitor client |
| **firmshake-api** | This Flask server |
