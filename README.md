# FirmShake API

Flask backend for [FirmShake](https://github.com/lucasmun09/firmshake) — image hosting, meetup ETA computation, payment webhooks, and admin operations.

The Ionic Vue client lives in a separate repo: **`firmshake`** (sibling directory `../firmshake`).

## Stack

- Python 3.11+
- Flask 3
- Firebase Admin SDK (token verification + Firestore ETA updates)
- Local image storage (`storage/images/`)

## Quick start

```bash
./start.sh
```

`start.sh` creates `.venv` on first run, installs dependencies, loads `.env`, and starts the server.

Manual setup (optional):

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
| `/api/images` | POST | Upload listing photo (auth + rate limit) |
| `/api/images/<image_id>` | GET | Stream listing photo (auth + community check) |
| `/api/meetups/<agreement_id>/location` | POST | Update user location; compute ETA (auth required) |
| `/api/notifications/push` | POST | Send FCM push to recipient (auth required) |

### Meetup location request

```json
POST /api/meetups/{agreement_id}/location
Authorization: Bearer <Firebase ID token>
{ "lat": 37.77, "lng": -122.42 }
```

Response (coordinates never returned to the other party):

```json
{
  "role": "buyer",
  "etaMinutes": 12,
  "progressPercent": 45,
  "otherParty": { "etaMinutes": 8, "progressPercent": 60 }
}
```

ETA fields are written to the Firestore `agreements/{id}` document by this API.

## Firebase service account (required for meetups)

Meetup ETA updates require a Firebase service account:

1. [Firebase Console](https://console.firebase.google.com/project/firmshake-dev/settings/serviceaccounts/adminsdk) → **Project settings → Service accounts**
2. **Generate new private key** → save JSON outside the repo
3. Export env vars before starting the API:

```bash
export FIREBASE_PROJECT_ID=firmshake-dev
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/serviceAccountKey.json
python app.py
```

Or copy `.env.example` to `.env` and load via `python-dotenv` (already enabled in `app.py`).

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_HOST` | `0.0.0.0` | Bind host |
| `FLASK_PORT` | `5001` | Bind port |
| `FLASK_DEBUG` | `true` | Debug mode |
| `FIREBASE_PROJECT_ID` | `firmshake-dev` | Firebase project ID |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Path to service account JSON (required for meetups) |
| `ETA_SPEED_MPH` | `25` | Assumed travel speed for ETA fallback |
| `ARRIVAL_RADIUS_METERS` | `100` | Distance considered "arrived" |
| `GCS_BUCKET` | — | Private bucket for listing images (empty = local disk) |
| `IMAGE_UPLOAD_RATE_LIMIT` | `20` | Max uploads per user per window |
| `IMAGE_UPLOAD_RATE_WINDOW_SECONDS` | `3600` | Upload rate-limit window (seconds) |

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```


Physical devices cannot reach `localhost`. Run a tunnel and point the app's `VITE_API_BASE_URL` at it:

```bash
ngrok http 5001
```

## Client configuration

In the **firmshake** app repo:

```bash
# firmshake/.env.local
VITE_API_BASE_URL=http://localhost:5001
```

Use the ngrok URL when testing on a phone.

## Roadmap (API-owned milestones)

- [x] Health check
- [x] Image upload + serve
- [x] Meetup location ETA endpoints (privacy-preserving)
- [x] FCM push notification delivery
- [ ] Firebase token verification on image uploads
- [ ] Stripe deposit + penalty webhooks
- [ ] Admin community seeding endpoints

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for system design.

## Related repo

| Repo | Purpose |
|---|---|
| **firmshake** | Ionic Vue + Capacitor client |
| **firmshake-api** | This Flask server |
