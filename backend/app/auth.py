"""Single-admin authentication with process-local, revocable cookie sessions."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from collections import deque
from urllib.parse import urlsplit


COOKIE_NAME = "homecam_session"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)
    return f"scrypt:{salt.hex()}:{digest.hex()}"


class AuthManager:
    def __init__(self):
        self.username = os.getenv("HOMECAM_ADMIN_USERNAME", "")
        encoded = os.getenv("HOMECAM_ADMIN_PASSWORD_HASH", "")
        self.origins = [value.strip().rstrip("/") for value in os.getenv("HOMECAM_ALLOWED_ORIGINS", "").split(",") if value.strip()]
        self.secure = os.getenv("HOMECAM_COOKIE_SECURE", "true").lower() != "false"
        self.ttl = int(os.getenv("HOMECAM_SESSION_SECONDS", "28800"))
        self.salt = b""
        self.digest = b""
        if encoded:
            try:
                algorithm, salt, digest = encoded.split(":")
                self.salt, self.digest = bytes.fromhex(salt), bytes.fromhex(digest)
                if algorithm != "scrypt" or len(self.salt) != 16 or len(self.digest) != 32:
                    raise ValueError
            except ValueError as exc:
                raise ValueError("Invalid HOMECAM_ADMIN_PASSWORD_HASH; generate with python -m app.auth") from exc
        for origin in self.origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.path or parsed.query or parsed.fragment or parsed.username or "*" in origin:
                raise ValueError("HOMECAM_ALLOWED_ORIGINS must contain exact HTTP(S) origins")
        if not 60 <= self.ttl <= 604800:
            raise ValueError("HOMECAM_SESSION_SECONDS must be between 60 and 604800")
        self.configured = bool(self.username and self.digest and self.origins)
        self.sessions: dict[str, float] = {}
        self.attempts: deque[float] = deque()
        self.lock = threading.Lock()

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        key = hashlib.sha256(token.encode()).hexdigest()
        with self.lock:
            expiry = self.sessions.get(key, 0)
            if expiry <= time.monotonic():
                self.sessions.pop(key, None)
                return False
            return True

    def revoke(self, token: str | None):
        if token:
            with self.lock:
                self.sessions.pop(hashlib.sha256(token.encode()).hexdigest(), None)

    def verify(self, username: str, password: str) -> bool:
        digest = hashlib.scrypt(password.encode(), salt=self.salt, n=16384, r=8, p=1, dklen=32)
        return hmac.compare_digest(digest, self.digest) & hmac.compare_digest(username.encode(), self.username.encode())

    def issue(self) -> str:
        token = secrets.token_urlsafe(32)
        now = time.monotonic()
        with self.lock:
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            if len(self.sessions) >= 128:
                self.sessions.pop(next(iter(self.sessions)))
            self.sessions[hashlib.sha256(token.encode()).hexdigest()] = now + self.ttl
        return token

    def allow_attempt(self) -> bool:
        now = time.monotonic()
        with self.lock:
            while self.attempts and self.attempts[0] <= now - 60:
                self.attempts.popleft()
            if len(self.attempts) >= 10:
                return False
            self.attempts.append(now)
            return True


class AuthMiddleware:
    def __init__(self, app, auth: AuthManager):
        self.app = app
        self.auth = auth

    async def __call__(self, scope, receive, send):
        from starlette.requests import Request
        from starlette.responses import JSONResponse

        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope, receive)
        path = scope["path"]
        if path == "/api/health" or scope["method"] == "OPTIONS":
            await self.app(scope, receive, send)
            return

        async def respond(status, detail):
            await JSONResponse({"detail": detail}, status_code=status, headers={"Cache-Control": "no-store"})(scope, receive, send)

        if not self.auth.configured:
            await respond(503, "Administrator login is not configured")
            return
        if scope["method"] not in ("GET", "HEAD") and request.headers.get("origin") not in self.auth.origins:
            await respond(403, "Request origin is not allowed")
            return
        token = request.cookies.get(COOKIE_NAME)
        if path == "/api/auth/login" and scope["method"] == "POST":
            if not self.auth.allow_attempt():
                await respond(429, "Too many login attempts. Try again in one minute.")
                return
            body = bytearray()
            async for chunk in request.stream():
                body.extend(chunk)
                if len(body) > 4096:
                    await respond(413, "Login request is too large")
                    return
            try:
                payload = json.loads(body)
                username, password = payload["username"], payload["password"]
                if not isinstance(username, str) or not isinstance(password, str) or not username or not password:
                    raise ValueError
            except (ValueError, KeyError, TypeError):
                await respond(400, "Username and password are required")
                return
            if not await asyncio.to_thread(self.auth.verify, username, password):
                await respond(401, "Invalid username or password")
                return
            self.auth.revoke(token)
            response = JSONResponse({"username": self.auth.username}, headers={"Cache-Control": "no-store"})
            response.set_cookie(COOKIE_NAME, self.auth.issue(), max_age=self.auth.ttl, httponly=True, secure=self.auth.secure, samesite="strict", path="/api")
            await response(scope, receive, send)
            return
        if path == "/api/auth/logout" and scope["method"] == "POST":
            self.auth.revoke(token)
            response = JSONResponse({"message": "Logged out"}, headers={"Cache-Control": "no-store"})
            response.delete_cookie(COOKIE_NAME, path="/api", httponly=True, secure=self.auth.secure, samesite="strict")
            await response(scope, receive, send)
            return
        if not self.auth.valid(token):
            await respond(401, "Login required")
            return
        if path == "/api/auth/session" and scope["method"] == "GET":
            await JSONResponse({"username": self.auth.username}, headers={"Cache-Control": "no-store"})(scope, receive, send)
            return

        async def protected_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = [(key, value) for key, value in message.get("headers", []) if key.lower() != b"cache-control"] + [(b"cache-control", b"no-store")]
            await send(message)

        await self.app(scope, receive, protected_send)


if __name__ == "__main__":
    from getpass import getpass

    password = getpass("Admin password (at least 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Use at least 12 characters")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    print(hash_password(password))
