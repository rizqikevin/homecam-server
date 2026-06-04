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
- **Service Worker**: Custom `sw.js` in the `public` directory using a dynamic **Cache-First** strategy for static files and bypassing caching for the `/api/camera/stream` endpoint.
- **PWA Manifest**: Configured in `public/manifest.webmanifest`.
- **API Proxy/Target**: Centralized in `src/api.ts`, using environment variable `VITE_API_BASE_URL` with a default fallback of `https://api.e-prostock.com`.

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

The production build runs in a multi-stage Docker environment and is served by a Node static server (not using Nginx/Vite preview) on port `3000`.

- Build Stage: Uses `pnpm` to compile TypeScript and create a optimized production build in `dist/`.
- Production Stage: Runs a lightweight Alpine Node environment using the `serve` library.

### Port Mappings
- Container Port: `3000`
- Host Port Mapping: `3005` (Accessible at `http://192.168.1.10:3005`)
