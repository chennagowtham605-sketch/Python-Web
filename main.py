"""Serve the Python Innovation Club website and join-request API."""

from __future__ import annotations

import hmac
import json
import os
import re
import secrets
import shutil
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from http.cookies import CookieError, SimpleCookie
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

ROOT = Path(__file__).resolve().parent
SITE = "python-innovation-club.html"
DATA_DIR = Path(os.environ.get("DATA_DIR", ROOT / "data"))

JOIN_FILE = DATA_DIR / "join_applications.json"
EVENT_REGISTRATIONS_FILE = DATA_DIR / "event_registrations.json"
CLUB_CONTENT_FILE = DATA_DIR / "club_content.json"
EVENT_POSTER_FILES = {
    "/images/python-100-poster.jpg": ROOT / "images" / "python-100-poster.jpg",
    "/images/week-one-pyquest-2026.jpg": ROOT / "images" / "week-one-pyquest-2026.jpg",
}
TEAM_PHOTO_FILES = {
    f"/images/team/{filename}": ROOT / "images" / "team" / filename
    for filename in (
        "Gowtham C.jpg",
        "Iyappan s.png",
        "Jaswanth S.jpeg",
        "Madhan kumar.png",
        "Mo.png",
        "Niranjana S.png",
        "Poorana shri.png",
        "Pradeep kumar.jpeg",
        "Ravi kumar.jpg",
        "Revathi G.jpg",
        "Vijaya prasad R.png",
        "Yuvarani.jpg",
    )
}
if (ROOT / "images" / "team").is_dir():
    for _img in (ROOT / "images" / "team").iterdir():
        if _img.is_file() and _img.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
            TEAM_PHOTO_FILES[f"/images/team/{_img.name}"] = _img

FACULTY_PHOTO_FILES = {
    f"/images/faculty/{filename}": ROOT / "images" / "faculty" / filename
    for filename in (
        "Amirthalingam_V.jpg",
        "Nithya_M.jpg",
        "Geetha_T.jpg",
        "Gnanavel_N.jpg",
        "J.Dhayalan.jpg",
        "Jagadeeswaran_M.jpg",
        "Ilakiya.png",
        "Karthik G.jpg",
        "Loganathan_S.jpg",
        "Mahalakshmi_R.jpg",
        "Manoj kumar.jpg",
        "Muthunagai.jpg",
        "Rajaeswari.jpg",
        "Rajanarayanan_S.jpg",
        "Rajasekar_G.jpg",
        "Senthilkumar_s.jpg",
        "Shriidhar_PJ.jpg",
        "Shrinivas.jpg",
        "Subbulakshmi.jpg",
        "Suresh_M.jpg",
        "Tamilzhagan.jpg",
        "kasthuri_A.jpg",
    )
}
PROJECT_IMAGE_FILES = {
    f"/images/projects/{filename}": ROOT / "images" / "projects" / filename
    for filename in (
        "AI Resume Analyzer.jpg",
        "Eco sort.jpg",
        "plant disease Detection.jpg",
        "Smart Study Buddy.jpg",
        "Smart Traffic Management System.jpg",
    )
}
PUBLIC_IMAGE_FILES = {
    "/images/vmkvec-logo.png": ROOT / "images" / "vmkvec-logo.png",
    "/images/vmrf-logo.jpeg": ROOT / "images" / "vmrf-logo.jpeg",
    "/images/aicte-logo.png": ROOT / "images" / "aicte-logo.png",
    "/images/naac-a-grade.webp": ROOT / "images" / "naac-a-grade.webp",
    **EVENT_POSTER_FILES,
    **TEAM_PHOTO_FILES,
    **FACULTY_PHOTO_FILES,
    **PROJECT_IMAGE_FILES,
}
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8080"))

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
SESSION_SECONDS = 12 * 60 * 60
EVENT_REGISTRATION_LOCK = threading.Lock()
EVENT_CONTENT_LOCK = threading.Lock()
JOIN_LOCK = threading.Lock()
SESSION_LOCK = threading.Lock()
SESSIONS = {}


def _read_join_applications() -> list:
    try:
        data = json.loads(JOIN_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as error:
        raise OSError("Join applications are unavailable") from error
    if not isinstance(data, list):
        raise OSError("Join application data is invalid")
    return [item for item in data if isinstance(item, dict)]


def _read_event_registrations() -> list:
    try:
        data = json.loads(EVENT_REGISTRATIONS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, OSError) as error:
        raise OSError("Event registrations are unavailable") from error
    if not isinstance(data, list):
        raise OSError("Event registration data is invalid")
    return [item for item in data if isinstance(item, dict)]

def _load_joins() -> list:
    return _read_join_applications()


def _save_join(entry: dict) -> None:
    DATA_DIR.mkdir(exist_ok=True)
    with JOIN_LOCK:
        rows = _load_joins()
        rows.append(entry)
        JOIN_FILE.write_text(
            json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8"
        )


def _save_event_registration(entry: dict) -> bool:
    DATA_DIR.mkdir(exist_ok=True)
    with EVENT_REGISTRATION_LOCK:
        try:
            registrations = json.loads(EVENT_REGISTRATIONS_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            registrations = []
        except (json.JSONDecodeError, OSError) as error:
            raise OSError("Event registrations are unavailable") from error
        if not isinstance(registrations, list):
            raise OSError("Event registration data is invalid")

        if any(
            item.get("event") == entry["event"] and item.get("email") == entry["email"]
            for item in registrations
            if isinstance(item, dict)
        ):
            return False

        registrations.append(entry)
        EVENT_REGISTRATIONS_FILE.write_text(
            json.dumps(registrations, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True


def _delete_event_registration(event_title: str, email: str) -> bool:
    DATA_DIR.mkdir(exist_ok=True)
    with EVENT_REGISTRATION_LOCK:
        try:
            registrations = json.loads(EVENT_REGISTRATIONS_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False
        except (json.JSONDecodeError, OSError) as error:
            raise OSError("Event registrations are unavailable") from error
        if not isinstance(registrations, list):
            raise OSError("Event registration data is invalid")

        new_regs = [
            item
            for item in registrations
            if not (
                isinstance(item, dict)
                and item.get("event", "").strip().casefold() == event_title.strip().casefold()
                and item.get("email", "").strip().casefold() == email.strip().casefold()
            )
        ]
        if len(new_regs) == len(registrations):
            return False

        EVENT_REGISTRATIONS_FILE.write_text(
            json.dumps(new_regs, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True


def _delete_join_application(email: str) -> bool:
    DATA_DIR.mkdir(exist_ok=True)
    with JOIN_LOCK:
        try:
            applications = json.loads(JOIN_FILE.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return False
        except (json.JSONDecodeError, OSError) as error:
            raise OSError("Join applications are unavailable") from error
        if not isinstance(applications, list):
            raise OSError("Join application data is invalid")

        new_apps = [
            item
            for item in applications
            if not (
                isinstance(item, dict)
                and item.get("email", "").strip().casefold() == email.strip().casefold()
            )
        ]
        if len(new_apps) == len(applications):
            return False

        JOIN_FILE.write_text(
            json.dumps(new_apps, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return True



class ClubSiteHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def _json(self, code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _set_session_cookie(self, token: str, max_age: int = SESSION_SECONDS) -> None:
        cookie = f"club_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={max_age}"
        if os.environ.get("CLUB_COOKIE_SECURE") == "1":
            cookie += "; Secure"
        self.send_header("Set-Cookie", cookie)

    def _current_user(self) -> dict | None:
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie["club_session"].value
        except (KeyError, CookieError):
            return None

        now = datetime.now(timezone.utc).timestamp()
        with SESSION_LOCK:
            session = SESSIONS.get(token)
            if session is None:
                return None
            if session["expires_at"] <= now:
                del SESSIONS[token]
                return None
            return session["user"]

    def _require_role(self, *roles: str) -> dict | None:
        user = self._current_user()
        if user is None:
            self._json(401, {"error": "Please log in to continue"})
            return None
        if user["role"] not in roles:
            self._json(403, {"error": "You do not have permission to do that"})
            return None
        return user

    def _create_session(self, user: dict) -> None:
        token = secrets.token_urlsafe(32)
        with SESSION_LOCK:
            SESSIONS[token] = {
                "user": user,
                "expires_at": datetime.now(timezone.utc).timestamp() + SESSION_SECONDS,
            }
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self._set_session_cookie(token)
        body = json.dumps({"ok": True, "user": user}).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorize_event_management(self) -> bool:
        user = self._require_role("admin")
        return user is not None

    def _read_json_payload(self) -> dict | None:
        try:
            length = int(self.headers.get("Content-Length", "0") or "0")
        except ValueError:
            self._json(400, {"error": "Invalid request body"})
            return None
        if length <= 0 or length > 20_000:
            self._json(400, {"error": "Invalid request body"})
            return None

        try:
            raw = self.rfile.read(length)
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._json(400, {"error": "Invalid JSON"})
            return None

        if not isinstance(data, dict):
            self._json(400, {"error": "Invalid payload"})
            return None
        return data

    def _validated_event(self, data: dict) -> dict | None:
        event = {
            "title": str(data.get("title", "")).strip(),
            "description": str(data.get("description", "")).strip(),
            "date": str(data.get("date", "")).strip(),
            "venue": str(data.get("venue", "")).strip(),
        }
        if not all(event.values()):
            self._json(400, {"error": "Please fill in all event fields"})
            return None
        if (
            len(event["title"]) > 120
            or len(event["description"]) > 1000
            or len(event["date"]) > 120
            or len(event["venue"]) > 160
        ):
            self._json(400, {"error": "One or more event fields are too long"})
            return None
        return event

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path in PUBLIC_IMAGE_FILES:
            try:
                image = PUBLIC_IMAGE_FILES[path].read_bytes()
            except OSError:
                self._json(404, {"error": "Image not found"})
                return
            self.send_response(200)
            self.send_header(
                "Content-Type",
                {
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".png": "image/png",
                    ".webp": "image/webp",
                }[Path(path).suffix.lower()],
            )
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(image)))
            self.end_headers()
            self.wfile.write(image)
            return
        if path in ("/admin", "/admin/"):
            self.path = "/admin.html"
            return super().do_GET()
        if path == "/admin.html":
            return super().do_GET()
        if path == "/api/me":
            self._json(200, {"user": self._current_user()})
            return
        if path == "/api/data":
            try:
                content = json.loads(CLUB_CONTENT_FILE.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self._json(500, {"error": "Club content is unavailable"})
                return
            self._json(200, content)
            return
        if path in ("/api/admin/joins", "/api/events/registrations"):
            if not self._authorize_event_management():
                return
            if path == "/api/admin/joins":
                try:
                    with JOIN_LOCK:
                        applications = _read_join_applications()
                except OSError:
                    self._json(500, {"error": "Join applications are unavailable"})
                    return
                self._json(200, {"applications": applications})
                return
            else:
                try:
                    with EVENT_REGISTRATION_LOCK:
                        registrations = _read_event_registrations()
                except OSError:
                    self._json(500, {"error": "Event registrations are unavailable"})
                    return
                self._json(200, {"registrations": registrations})
                return
        if path in ("/", "/index.html", "/python-innovation-club.html"):
            self.path = f"/{SITE}"
        elif path in ("/site", "/home"):
            self.path = f"/{SITE}"
        elif path != f"/{SITE}":
            self._json(404, {"error": "Not found"})
            return
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in (
            "/api/join",
            "/api/login",
            "/api/logout",
            "/api/events/register",
            "/api/events",
        ):
            self._json(404, {"error": "Not found"})
            return

        if path == "/api/events":
            if not self._authorize_event_management():
                return

        if path == "/api/logout":
            cookie = SimpleCookie()
            cookie.load(self.headers.get("Cookie", ""))
            token = cookie["club_session"].value if "club_session" in cookie else None
            if token:
                with SESSION_LOCK:
                    SESSIONS.pop(token, None)
            body = json.dumps({"ok": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header(
                "Set-Cookie",
                "club_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
                + ("; Secure" if os.environ.get("CLUB_COOKIE_SECURE") == "1" else ""),
            )
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        data = self._read_json_payload()
        if data is None:
            return

        if path == "/api/login":
            email = str(data.get("email", "")).strip().casefold()
            password = str(data.get("password", ""))
            admin_username = os.environ.get("CLUB_ADMIN_USERNAME", "admin").strip().casefold()
            admin_password = os.environ.get("CLUB_ADMIN_TOKEN", "")
            if admin_password and hmac.compare_digest(email, admin_username) and hmac.compare_digest(password, admin_password):
                self._create_session(
                    {"email": admin_username, "name": "Website handler", "role": "admin"}
                )
                return
            self._json(401, {"error": "Website handler login failed"})
            return

        if path == "/api/events":
            event = self._validated_event(data)
            if event is None:
                return
            try:
                with EVENT_CONTENT_LOCK:
                    content = json.loads(CLUB_CONTENT_FILE.read_text(encoding="utf-8"))
                    events = content.get("events")
                    if not isinstance(events, list):
                        self._json(500, {"error": "Event list is unavailable"})
                        return
                    if any(
                        isinstance(existing, dict)
                        and existing.get("title", "").casefold() == event["title"].casefold()
                        for existing in events
                    ):
                        self._json(409, {"error": "An event with this title already exists"})
                        return
                    events.append(event)
                    CLUB_CONTENT_FILE.write_text(
                        json.dumps(content, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8",
                    )
            except (OSError, json.JSONDecodeError, AttributeError):
                self._json(500, {"error": "Could not save event"})
                return
            self._json(201, {"ok": True, "event": event})
            return

        if path == "/api/events/register":
            event_title = str(data.get("event", "")).strip()
            name = str(data.get("name", "")).strip()
            email = str(data.get("email", "")).strip().casefold()
            if not event_title or not name or not email:
                self._json(400, {"error": "Please fill in all fields"})
                return
            if len(name) > 120 or not EMAIL_RE.match(email):
                self._json(400, {"error": "Enter a valid name and email address"})
                return
            try:
                content = json.loads(CLUB_CONTENT_FILE.read_text(encoding="utf-8"))
                events = content.get("events", [])
            except (OSError, json.JSONDecodeError, AttributeError):
                self._json(500, {"error": "Events are unavailable"})
                return
            event = next(
                (
                    item
                    for item in events
                    if isinstance(item, dict) and item.get("title") == event_title
                ),
                None,
            )
            if event is None:
                self._json(404, {"error": "Event not found"})
                return
            if event.get("status") == "ended":
                self._json(410, {"error": "Registration for this event has ended"})
                return

            registration = {
                "event": event_title,
                "name": name,
                "email": email,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                saved = _save_event_registration(registration)
            except OSError:
                self._json(500, {"error": "Could not save registration"})
                return
            if not saved:
                self._json(409, {"error": "This email is already registered for this event"})
                return
            self._json(
                201,
                {
                    "ok": True,
                    "message": "Event registration saved",
                    "event": event,
                },
            )
            return

        name = str(data.get("name", "")).strip()
        email = str(data.get("email", "")).strip().lower()
        year = str(data.get("year", "")).strip()
        department = str(data.get("department", "")).strip()
        interest = str(data.get("interest", "")).strip()

        if not all([name, email, year, department, interest]):
            self._json(400, {"error": "Please fill in all fields"})
            return
        if not EMAIL_RE.match(email):
            self._json(400, {"error": "Enter a valid email address"})
            return

        entry = {
            "name": name,
            "email": email,
            "year": year,
            "department": department,
            "interest": interest,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            _save_join(entry)
        except OSError:
            self._json(500, {"error": "Could not save request"})
            return

        print(f"[join] {name} <{email}> — {department}, {year}", flush=True)
        self._json(201, {"ok": True, "message": "Join request saved"})

    def do_PATCH(self):
        path = urlparse(self.path).path
        if not path.startswith("/api/events/"):
            self._json(404, {"error": "Not found"})
            return
        if not self._authorize_event_management():
            return
        data = self._read_json_payload()
        if data is None:
            return
        event = self._validated_event(data)
        if event is None:
            return

        title = unquote(path.removeprefix("/api/events/"))
        if not title:
            self._json(404, {"error": "Event not found"})
            return
        try:
            with EVENT_CONTENT_LOCK:
                content = json.loads(CLUB_CONTENT_FILE.read_text(encoding="utf-8"))
                events = content.get("events")
                if not isinstance(events, list):
                    self._json(500, {"error": "Event list is unavailable"})
                    return
                event_index = next(
                    (
                        index
                        for index, existing in enumerate(events)
                        if isinstance(existing, dict) and existing.get("title") == title
                    ),
                    None,
                )
                if event_index is None:
                    self._json(404, {"error": "Event not found"})
                    return
                if any(
                    index != event_index
                    and isinstance(existing, dict)
                    and existing.get("title", "").casefold() == event["title"].casefold()
                    for index, existing in enumerate(events)
                ):
                    self._json(409, {"error": "An event with this title already exists"})
                    return
                events[event_index] = event
                CLUB_CONTENT_FILE.write_text(
                    json.dumps(content, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        except (OSError, json.JSONDecodeError, AttributeError):
            self._json(500, {"error": "Could not save event"})
            return
        self._json(200, {"ok": True, "event": event})

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if not (
            path.startswith("/api/events/")
            or path in ("/api/events/registrations", "/api/admin/registrations", "/api/admin/joins")
        ):
            self._json(404, {"error": "Not found"})
            return
        if not self._authorize_event_management():
            return

        if path in ("/api/events/registrations", "/api/admin/registrations"):
            query = parse_qs(parsed.query)
            event_title = query.get("event", [""])[0]
            email = query.get("email", [""])[0]
            if not (event_title and email):
                data = self._read_json_payload() or {}
                event_title = event_title or data.get("event", "")
                email = email or data.get("email", "")
            if not (event_title and email):
                self._json(400, {"error": "Please provide both event title and email"})
                return
            try:
                deleted = _delete_event_registration(str(event_title), str(email))
            except OSError:
                self._json(500, {"error": "Could not delete registration"})
                return
            if not deleted:
                self._json(404, {"error": "Registration not found"})
                return
            self._json(200, {"ok": True, "message": "Registration deleted successfully"})
            return

        if path == "/api/admin/joins":
            query = parse_qs(parsed.query)
            email = query.get("email", [""])[0]
            if not email:
                data = self._read_json_payload() or {}
                email = data.get("email", "")
            if not email:
                self._json(400, {"error": "Please provide student email"})
                return
            try:
                deleted = _delete_join_application(str(email))
            except OSError:
                self._json(500, {"error": "Could not delete join application"})
                return
            if not deleted:
                self._json(404, {"error": "Join application not found"})
                return
            self._json(200, {"ok": True, "message": "Join application deleted successfully"})
            return

        title = unquote(path.removeprefix("/api/events/"))
        if not title:
            self._json(404, {"error": "Event not found"})
            return
        try:
            with EVENT_CONTENT_LOCK:
                content = json.loads(CLUB_CONTENT_FILE.read_text(encoding="utf-8"))
                events = content.get("events")
                if not isinstance(events, list):
                    self._json(500, {"error": "Event list is unavailable"})
                    return
                updated_events = [
                    event
                    for event in events
                    if not isinstance(event, dict) or event.get("title") != title
                ]
                if len(updated_events) == len(events):
                    self._json(404, {"error": "Event not found"})
                    return
                content["events"] = updated_events
                CLUB_CONTENT_FILE.write_text(
                    json.dumps(content, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
        except (OSError, json.JSONDecodeError, AttributeError):
            self._json(500, {"error": "Could not delete event"})
            return
        self._json(200, {"ok": True})

    def log_message(self, format: str, *args) -> None:
        print(f"[{self.log_date_time_string()}] {args[0]}")


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not JOIN_FILE.exists():
        JOIN_FILE.write_text("[]\n", encoding="utf-8")

    server = ThreadingHTTPServer((HOST, PORT), ClubSiteHandler)
    url = f"http://{HOST}:{PORT}"
    print(f"Python Innovation Club -> {url}", flush=True)
    print("The club site and join form are open to visitors.", flush=True)
    print(f"Applications saved to: {JOIN_FILE}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
