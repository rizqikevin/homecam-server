# HomeCam Server — PWA Frontend

This is the lightweight Progressive Web App (PWA) dashboard for HomeCam Server, designed to monitor and control local home CCTV webcam streams.

## Features

- **PWA Installability**: Fully installable on Android, iOS, and Desktop devices with correct branding (`HomeCam Server`).
- **Offline Shell**: Static assets are cached locally using a custom Service Worker, allowing the app to load instantly even without network.
- **Smart Stream Handling**: Live camera streams are never cached by the Service Worker, ensuring real-time playback.
- **Dynamic Connection Management**: Displaying explicit "Backend offline" indicators and retry procedures if the API is unreachable.
- **Responsive Layout**: Adapts perfectly to various screen sizes.
  - **Desktop**: A persistent sidebar with system logs and navigation links.
  - **Mobile/PWA**: Bottom navigation tabs and a top status header conforming to safe-areas (notches/home indicators).
- **Fullscreen Immersive View**: Double-tap the live stream or click the fullscreen button to view the CCTV feed in full screen overlay HUD.

## Technical Architecture

- **Framework**: React 19 + TypeScript + Vite 8
- **Routing**: React Router 7
- **Style System**: Modern Vanilla CSS with HSL variables (dark mode first).
- **Service Worker**: Static shell is cached; all `/api/` requests use the network and never fall back to cached private data.
- **PWA Manifest**: Configured in `public/manifest.webmanifest`.
- **API Proxy/Target**: `src/api.ts` defaults to same-origin `/api`. Vite proxies to `127.0.0.1:8005`; production Nginx proxies to the backend container. Optional `VITE_API_BASE_URL` must be a same-site API origin because session cookies use `SameSite=Strict`.

## Development & Build

### Prerequisites
- Node.js 22+
- `pnpm` (Package Manager)

### Install dependencies
```bash
pnpm install
```

### Dev Server
```bash
pnpm run dev
```

### Build Production Bundle
```bash
pnpm run build
```

## Docker Production Deployment

Production uses Nginx on container port `80`, serving the bundle and proxying `/api/` to the backend. The build uses `npm ci` and `npm run build`.

### Port Mappings
- Container port: `80`
- Host port: `3005`

## Administrator login

Login protects camera status, streams, recordings, settings, and diagnostics. `/api/health` remains public; API documentation endpoints are disabled. There is one administrator account, with no registration or password-reset endpoint.

From the repository root, generate a salted scrypt hash with a hidden password prompt:

```bash
python3 -m backend.app.auth
```

Copy the output into a root `.env` file (ignored by Git), alongside your chosen username and exact browser origin. Do not put a password or hash in frontend environment variables.

```dotenv
HOMECAM_ADMIN_USERNAME=your-admin-name
HOMECAM_ADMIN_PASSWORD_HASH=your-generated-scrypt-hash
HOMECAM_ALLOWED_ORIGINS=https://your-homecam-host.example
HOMECAM_COOKIE_SECURE=true
HOMECAM_SESSION_SECONDS=28800
```

The values above are placeholders, not working credentials. Use HTTPS for deployment. For local HTTP only, set `HOMECAM_COOKIE_SECURE=false` and set the origin to the exact browser address, for example `http://localhost:3005`. Multiple trusted origins may be comma-separated; wildcards are rejected. Origins contain scheme, hostname, and optional port, but no path. Both login and every other mutation require an allowed `Origin` header, including command-line clients.

```bash
docker compose up --build -d
```

Compose requires credentials and origins. Direct backend startup without all three settings leaves private endpoints unavailable with HTTP 503; health still works. Invalid hashes or origins fail startup. Root `.env` is read by Compose, not automatically by Uvicorn.

For development, export configuration in the backend terminal (hash prompt keeps the password out of shell history):

```bash
export HOMECAM_ADMIN_USERNAME=homecam-admin
export HOMECAM_ADMIN_PASSWORD_HASH="$(python3 -m backend.app.auth)"
export HOMECAM_ALLOWED_ORIGINS=http://localhost:5173
export HOMECAM_COOKIE_SECURE=false
MOCK_CAMERA=true python3 - <<'PY'
from pathlib import Path
import uvicorn
from backend.app import main

storage = Path("/tmp/homecam-dev-recordings")
storage.mkdir(exist_ok=True)
main.SETTINGS_PATH = str(storage / "settings.json")
if not Path(main.SETTINGS_PATH).exists():
    main.save_settings(main.Settings(recordings_dir=str(storage)))
uvicorn.run(main.app, host="127.0.0.1", port=8005)
PY
```

The local command redirects the existing hardcoded `/recordings/settings.json` path into temporary development storage. `RECORDINGS_DIR` does not override that path. Production Compose uses the `/recordings` volume.

In another terminal:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open `http://localhost:5173`. Use that hostname consistently; `localhost` and `127.0.0.1` are different origins. Leave `VITE_API_BASE_URL` empty to use the proxy.

Sessions use opaque HttpOnly cookies and expire after eight hours by default (configurable from 60 to 604800 seconds). Sign out revokes the session server-side and stops its live stream. Sessions are process-local: use one Uvicorn worker; restarting the backend signs everyone out. Rotate credentials by replacing the environment hash and restarting. Browser logout does not stop camera recording or erase files already downloaded. Downloads authorized before logout may finish.

Login is limited to ten attempts per minute across this single-admin server. For public exposure, also apply network-level access controls and rate limits at your HTTPS reverse proxy. A shared limit can temporarily block legitimate login after repeated attempts. Cross-site frontend/API hosting is not supported; deploy same-origin or same-site HTTPS hosts with exact allowed origins.

The login page retains the dark CCTV palette and Inter typography to match the dashboard, with one centered form and a blue sign-in action. Spacing separates credentials from feedback; native labels and focus rings keep keyboard use clear. Design dials: energy 1, rhythm 1, motion 1. No additional illustrations or animation.
