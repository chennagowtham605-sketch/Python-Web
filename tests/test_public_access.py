import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import main


class PublicAccessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), main.ClubSiteHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method, path, payload=None, headers=None):
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers=request_headers,
            method=method,
        )
        try:
            return urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            error.close()
            return error

    def post(self, path, payload, headers=None):
        return self.request("POST", path, payload, headers)

    def login_headers(self, email, password):
        response = self.post("/api/login", {"email": email, "password": password})
        self.assertEqual(response.status, 200)
        return {"Cookie": response.headers["Set-Cookie"].split(";", 1)[0]}

    def test_root_and_site_are_public(self):
        for path in ("/", "/site", "/python-innovation-club.html", "/admin"):
            with self.subTest(path=path):
                response = urllib.request.urlopen(self.base_url + path)
                self.assertEqual(response.status, 200)
                page = response.read()
                if path == "/admin":
                    self.assertIn(b"Website handler sign in", page)
                    self.assertIn(b"/api/admin/joins", page)
                else:
                    self.assertIn(b"Python Innovation Club", page)
                    self.assertNotIn(b"Website handler", page)
                    self.assertNotIn(b'id="loginForm"', page)
                    self.assertNotIn(b'id="organizerTools"', page)
                    self.assertIn(b'id="eventRegistrationForm"', page)
                    for logo_path in (
                        b"/images/vmkvec-logo.png",
                        b"/images/aicte-logo.png",
                        b"/images/naac-a-grade.webp",
                    ):
                        self.assertIn(logo_path, page)
                    self.assertNotIn(b"/images/vmrf-logo.jpeg", page)

    def test_institution_logos_are_served(self):
        expected_types = {
            "/images/vmkvec-logo.png": "image/png",
            "/images/vmrf-logo.jpeg": "image/jpeg",
            "/images/aicte-logo.png": "image/png",
            "/images/naac-a-grade.webp": "image/webp",
        }
        for path, expected_type in expected_types.items():
            with self.subTest(path=path):
                response = urllib.request.urlopen(self.base_url + path)
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    response.headers.get_content_type(), expected_type
                )
                self.assertTrue(response.read())

    def test_public_dataset_contains_site_content(self):
        response = urllib.request.urlopen(self.base_url + "/api/data")
        dataset = json.loads(response.read())

        self.assertEqual(response.headers.get_content_type(), "application/json")
        self.assertEqual(set(dataset), {"pillars", "events", "projects", "team"})
        self.assertTrue(dataset["pillars"])
        self.assertEqual(
            [
                (event["title"], event["date"], event.get("status"))
                for event in dataset["events"]
            ],
            [
                ("Python 100", "2025", "ended"),
                ("Week one Pyquest 2026", "16/10/2026", None),
            ],
        )
        self.assertEqual(dataset["events"][0]["venue"], "HITECH 2")
        self.assertEqual(dataset["events"][1]["venue"], "AILAB")
        self.assertEqual(
            dataset["events"][0]["image"], "/images/python-100-poster.jpg"
        )
        self.assertEqual(
            dataset["events"][1]["image"], "/images/week-one-pyquest-2026.jpg"
        )
        self.assertTrue(dataset["projects"])
        self.assertTrue(dataset["team"])

    def test_event_posters_are_served_as_jpegs(self):
        for path in (
            "/images/python-100-poster.jpg",
            "/images/week-one-pyquest-2026.jpg",
        ):
            with self.subTest(path=path):
                response = urllib.request.urlopen(self.base_url + path)

                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                self.assertTrue(response.read().startswith(b"\xff\xd8\xff"))

    def test_student_team_photos_are_served_with_their_original_names(self):
        dataset = json.loads(
            urllib.request.urlopen(self.base_url + "/api/data").read()
        )
        members = dataset["team"]["studentMembers"]
        self.assertEqual(len(members), 12)

        for member in members:
            with self.subTest(member=member["name"]):
                photo_path = member["image"]
                self.assertIn("/images/team/", photo_path)
                response = urllib.request.urlopen(self.base_url + photo_path)
                self.assertEqual(response.status, 200)
                self.assertTrue(response.headers.get_content_type().startswith("image/"))
                self.assertTrue(response.read())

    def test_only_clearly_matched_faculty_photos_are_served(self):
        dataset = json.loads(
            urllib.request.urlopen(self.base_url + "/api/data").read()
        )
        faculty = dataset["team"]["facultyMembers"]
        self.assertEqual(len(faculty), 21)
        photo_names = {
            member["name"].strip(): member["image"]
            for member in faculty
            if member.get("image")
        }
        self.assertEqual(
            photo_names,
            {
                "Dr. Amirthalingam V": "/images/faculty/Amirthalingam_V.jpg",
                "Dr. Senthilkumar S": "/images/faculty/Senthilkumar_s.jpg",
                "Dr. Rajanarayanan S": "/images/faculty/Rajanarayanan_S.jpg",
                "Dr. G. Karthik": "/images/faculty/Karthik%20G.jpg",
                "Miss. Ilakiya": "/images/faculty/Ilakiya.png",
                "Mrs. Geetha T.": "/images/faculty/Geetha_T.jpg",
                "Mr. Shriidhar PJ": "/images/faculty/Shriidhar_PJ.jpg",
                "Mr. Loganathan S": "/images/faculty/Loganathan_S.jpg",
                "Mrs. Mahalakshmi R": "/images/faculty/Mahalakshmi_R.jpg",
                "Mr. Jagadeeswaran M": "/images/faculty/Jagadeeswaran_M.jpg",
                "Mr. Suresh M": "/images/faculty/Suresh_M.jpg",
                "Mrs. Kasthuri A": "/images/faculty/kasthuri_A.jpg",
                "Mr. Rajasekar G": "/images/faculty/Rajasekar_G.jpg",
                "Mr. Gnanavel N": "/images/faculty/Gnanavel_N.jpg",
                "Mrs. Subbulakshmi": "/images/faculty/Subbulakshmi.jpg",
                "Mr. Manoj Kumar": "/images/faculty/Manoj%20kumar.jpg",
                "Mr. Shrinivas": "/images/faculty/Shrinivas.jpg",
                "Mr.J.Dhayalan": "/images/faculty/J.Dhayalan.jpg",
                "Mr. Tamilazhagan": "/images/faculty/Tamilzhagan.jpg",
                "Mrs. Muthunangai": "/images/faculty/Muthunagai.jpg",
                "Miss. Rajeswari": "/images/faculty/Rajaeswari.jpg",
            },
        )
        for member in faculty:
            if not member.get("image"):
                continue
            with self.subTest(member=member["name"]):
                response = urllib.request.urlopen(
                    self.base_url + member["image"]
                )
                self.assertEqual(response.status, 200)
                expected_type = (
                    "image/png"
                    if member["image"].endswith(".png")
                    else "image/jpeg"
                )
                self.assertEqual(response.headers.get_content_type(), expected_type)
                self.assertTrue(response.read())

    def test_project_idea_images_are_served(self):
        dataset = json.loads(
            urllib.request.urlopen(self.base_url + "/api/data").read()
        )
        projects = [
            project for project in dataset["projects"] if project.get("image")
        ]

        self.assertEqual(
            [project["title"] for project in dataset["projects"]],
            [
                "AI Resume Analyzer",
                "Eco Sort",
                "Plant Disease Detection",
                "Smart Study Buddy",
                "Smart Traffic Management System",
            ],
        )
        self.assertEqual(len(projects), 5)
        for project in projects:
            with self.subTest(project=project["title"]):
                self.assertTrue(project["description"])
                response = urllib.request.urlopen(
                    self.base_url + project["image"]
                )
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "image/jpeg")
                self.assertTrue(response.read().startswith(b"\xff\xd8\xff"))

    def test_private_data_files_are_not_served_as_static_files(self):
        for path in (
            "/data/club_content.json",
            "/data/event_registrations.json",
            "/data/join_applications.json",
            "/main.py",
            "/data%5cclub_content.json",
        ):
            with self.subTest(path=path):
                response = self.request("GET", path)
                self.assertEqual(response.status, 404)

    def test_join_request_does_not_require_login(self):
        payload = {
            "name": "Test Member",
            "email": "member@example.com",
            "year": "I Year",
            "department": "Computer Science",
            "interest": "Python projects",
        }
        with patch.object(main, "_save_join") as save_join:
            response = self.post("/api/join", payload)

        self.assertEqual(response.status, 201)
        save_join.assert_called_once()

    def test_join_applications_are_saved_separately_and_admin_only(self):
        payload = {
            "name": "Test Member",
            "email": "member@example.com",
            "year": "I Year",
            "department": "Computer Science",
            "interest": "Python projects",
        }
        with tempfile.TemporaryDirectory() as directory:
            join_file = Path(directory) / "join_applications.json"
            event_file = Path(directory) / "event_registrations.json"
            with (
                patch.object(main, "JOIN_FILE", join_file),
                patch.object(main, "EVENT_REGISTRATIONS_FILE", event_file),
                patch.dict(os.environ, {"CLUB_ADMIN_TOKEN": "test-organizer-key"}),
            ):
                submitted = self.post("/api/join", payload)
                denied = self.request("GET", "/api/admin/joins")
                admin_headers = self.login_headers("admin", "test-organizer-key")
                response = self.request("GET", "/api/admin/joins", headers=admin_headers)
                applications = json.loads(response.read())["applications"]
                join_exists = join_file.exists()
                event_exists = event_file.exists()

        self.assertEqual(submitted.status, 201)
        self.assertEqual(denied.status, 401)
        self.assertEqual(len(applications), 1)
        self.assertEqual(applications[0]["email"], "member@example.com")
        self.assertTrue(join_exists)
        self.assertFalse(event_exists)

    def test_event_registration_is_saved_and_duplicates_are_rejected(self):
        payload = {
            "event": "Week one Pyquest 2026",
            "name": "Test Member",
            "email": "MEMBER@example.com",
        }
        with tempfile.TemporaryDirectory() as directory:
            registration_file = Path(directory) / "event_registrations.json"
            with patch.object(main, "EVENT_REGISTRATIONS_FILE", registration_file):
                response = self.post("/api/events/register", payload)
                duplicate = self.post("/api/events/register", payload)
                saved = json.loads(registration_file.read_text(encoding="utf-8"))

        self.assertEqual(response.status, 201)
        self.assertEqual(duplicate.status, 409)
        self.assertEqual(saved[0]["name"], "Test Member")
        self.assertEqual(saved[0]["email"], "member@example.com")
        response_data = json.loads(response.read())
        self.assertEqual(response_data["event"]["title"], payload["event"])
        self.assertIn("date", response_data["event"])
        self.assertIn("venue", response_data["event"])

    def test_event_registration_rejects_unknown_event(self):
        response = self.post(
            "/api/events/register",
            {
                "event": "Not a real event",
                "name": "Test Member",
                "email": "member@example.com",
            },
        )

        self.assertEqual(response.status, 404)

    def test_registration_is_closed_for_ended_event_but_open_for_upcoming_event(self):
        payload = {
            "name": "Test Member",
            "email": "member@example.com",
        }
        ended = {
            "title": "Python 100",
            "description": "The first event of the Python Club.",
            "date": "2025",
            "venue": "To be announced",
            "status": "ended",
        }
        upcoming = {
            "title": "Week one Pyquest 2026",
            "description": "Week one of Pyquest 2026.",
            "date": "To be announced",
            "venue": "To be announced",
        }
        with tempfile.TemporaryDirectory() as directory:
            content_file = Path(directory) / "club_content.json"
            registrations_file = Path(directory) / "event_registrations.json"
            content_file.write_text(
                json.dumps({"events": [ended, upcoming]}), encoding="utf-8"
            )
            with (
                patch.object(main, "CLUB_CONTENT_FILE", content_file),
                patch.object(main, "EVENT_REGISTRATIONS_FILE", registrations_file),
            ):
                ended_response = self.post(
                    "/api/events/register", {**payload, "event": ended["title"]}
                )
                upcoming_response = self.post(
                    "/api/events/register", {**payload, "event": upcoming["title"]}
                )

        self.assertEqual(ended_response.status, 410)
        self.assertEqual(upcoming_response.status, 201)

    def test_event_details_are_public_but_registration_list_is_handler_only(self):
        with tempfile.TemporaryDirectory() as directory:
            content_file = Path(directory) / "club_content.json"
            registrations_file = Path(directory) / "event_registrations.json"
            content_file.write_text(
                json.dumps({"events": [{"title": "Private event", "description": "Secret"}]}),
                encoding="utf-8",
            )
            registrations_file.write_text(
                json.dumps(
                    [
                        {
                            "event": "Private event",
                            "name": "Test Member",
                            "email": "member@example.com",
                            "registered_at": "2026-10-13T00:00:00+00:00",
                        },
                        {
                            "event": "Private event",
                            "name": "Another Member",
                            "email": "other@example.com",
                            "registered_at": "2026-10-13T00:00:00+00:00",
                        },
                    ]
                ),
                encoding="utf-8",
            )
            with (
                patch.object(main, "CLUB_CONTENT_FILE", content_file),
                patch.object(main, "EVENT_REGISTRATIONS_FILE", registrations_file),
                patch.dict(os.environ, {"CLUB_ADMIN_TOKEN": "test-organizer-key"}),
            ):
                guest_data = json.loads(
                    urllib.request.urlopen(self.base_url + "/api/data").read()
                )
                guest_list = self.request("GET", "/api/events/registrations")
                admin_headers = self.login_headers("admin", "test-organizer-key")
                admin_list = json.loads(
                    self.request(
                        "GET", "/api/events/registrations", headers=admin_headers
                    ).read()
                )

        self.assertEqual(guest_data["events"][0]["title"], "Private event")
        self.assertEqual(guest_list.status, 401)
        self.assertEqual(len(admin_list["registrations"]), 2)

    def test_event_creation_requires_organizer_key_and_persists_event(self):
        payload = {
            "title": "New Python Meetup",
            "description": "An evening of Python projects.",
            "date": "October 30",
            "venue": "VMKVEC Salem",
        }
        with tempfile.TemporaryDirectory() as directory:
            content_file = Path(directory) / "club_content.json"
            content_file.write_text(json.dumps({"events": []}), encoding="utf-8")
            with (
                patch.object(main, "CLUB_CONTENT_FILE", content_file),
                patch.dict(os.environ, {"CLUB_ADMIN_TOKEN": "test-organizer-key"}),
            ):
                denied = self.post("/api/events", payload)
                admin_headers = self.login_headers("admin", "test-organizer-key")
                created = self.post("/api/events", payload, admin_headers)
                duplicate = self.post("/api/events", payload, admin_headers)
                stored = json.loads(content_file.read_text(encoding="utf-8"))

        self.assertEqual(denied.status, 401)
        self.assertEqual(created.status, 201)
        self.assertEqual(duplicate.status, 409)
        self.assertEqual(stored["events"], [payload])

    def test_newly_created_event_can_be_registered_for(self):
        event = {
            "title": "New Python Meetup",
            "description": "An evening of Python projects.",
            "date": "October 30",
            "venue": "VMKVEC Salem",
        }
        registration = {
            "event": event["title"],
            "name": "Test Member",
            "email": "member@example.com",
        }
        with tempfile.TemporaryDirectory() as directory:
            content_file = Path(directory) / "club_content.json"
            registration_file = Path(directory) / "event_registrations.json"
            content_file.write_text(json.dumps({"events": []}), encoding="utf-8")
            with (
                patch.object(main, "CLUB_CONTENT_FILE", content_file),
                patch.object(main, "EVENT_REGISTRATIONS_FILE", registration_file),
                patch.dict(os.environ, {"CLUB_ADMIN_TOKEN": "test-organizer-key"}),
            ):
                admin_headers = self.login_headers("admin", "test-organizer-key")
                created = self.post("/api/events", event, admin_headers)
                registered = self.post("/api/events/register", registration)
                saved_registrations = json.loads(
                    registration_file.read_text(encoding="utf-8")
                )

        self.assertEqual(created.status, 201)
        self.assertEqual(registered.status, 201)
        self.assertEqual(saved_registrations[0]["event"], event["title"])
        self.assertEqual(saved_registrations[0]["email"], "member@example.com")

    def test_event_updates_and_deletes_require_organizer_key(self):
        original = {
            "title": "Designer Event",
            "description": "Original description.",
            "date": "October 30",
            "venue": "VMKVEC Salem",
        }
        updated = {
            "title": "Updated Designer Event",
            "description": "Updated description.",
            "date": "November 1",
            "venue": "Online",
        }
        with tempfile.TemporaryDirectory() as directory:
            content_file = Path(directory) / "club_content.json"
            content_file.write_text(json.dumps({"events": [original]}), encoding="utf-8")
            with (
                patch.object(main, "CLUB_CONTENT_FILE", content_file),
                patch.dict(os.environ, {"CLUB_ADMIN_TOKEN": "test-organizer-key"}),
            ):
                denied_update = self.request("PATCH", "/api/events/Designer%20Event", updated)
                denied_delete = self.request("DELETE", "/api/events/Designer%20Event")
                admin_headers = self.login_headers("admin", "test-organizer-key")
                changed = self.request(
                    "PATCH",
                    "/api/events/Designer%20Event",
                    updated,
                    admin_headers,
                )
                missing = self.request("DELETE", "/api/events/Designer%20Event", headers=admin_headers)
                deleted = self.request(
                    "DELETE",
                    "/api/events/Updated%20Designer%20Event",
                    headers=admin_headers,
                )
                stored = json.loads(content_file.read_text(encoding="utf-8"))

        self.assertEqual(denied_update.status, 401)
        self.assertEqual(denied_delete.status, 401)
        self.assertEqual(changed.status, 200)
        self.assertEqual(missing.status, 404)
        self.assertEqual(deleted.status, 200)
        self.assertEqual(stored["events"], [])

    def test_admin_can_delete_event_registration(self):
        initial = [{"event": "PyQuest 2026", "name": "Alice", "email": "alice@example.com"}]
        with tempfile.TemporaryDirectory() as directory:
            reg_file = Path(directory) / "event_registrations.json"
            reg_file.write_text(json.dumps(initial), encoding="utf-8")
            with (
                patch.object(main, "EVENT_REGISTRATIONS_FILE", reg_file),
                patch.dict(os.environ, {"CLUB_ADMIN_TOKEN": "test-key"}),
            ):
                unauth = self.request("DELETE", "/api/events/registrations?event=PyQuest%202026&email=alice@example.com")
                admin_headers = self.login_headers("admin", "test-key")
                res = self.request("DELETE", "/api/events/registrations?event=PyQuest%202026&email=alice@example.com", headers=admin_headers)
                data = json.loads(res.read())
                rem = json.loads(reg_file.read_text(encoding="utf-8"))

        self.assertEqual(unauth.status, 401)
        self.assertEqual(res.status, 200)
        self.assertTrue(data.get("ok"))
        self.assertEqual(rem, [])

    def test_admin_can_delete_join_application(self):
        initial = [{"name": "Bob", "email": "bob@example.com", "year": "II Year", "department": "CSE", "interest": "AI"}]
        with tempfile.TemporaryDirectory() as directory:
            join_file = Path(directory) / "join_applications.json"
            join_file.write_text(json.dumps(initial), encoding="utf-8")
            with (
                patch.object(main, "JOIN_FILE", join_file),
                patch.dict(os.environ, {"CLUB_ADMIN_TOKEN": "test-key"}),
            ):
                unauth = self.request("DELETE", "/api/admin/joins?email=bob@example.com")
                admin_headers = self.login_headers("admin", "test-key")
                res = self.request("DELETE", "/api/admin/joins?email=bob@example.com", headers=admin_headers)
                data = json.loads(res.read())
                rem = json.loads(join_file.read_text(encoding="utf-8"))

        self.assertEqual(unauth.status, 401)
        self.assertEqual(res.status, 200)
        self.assertTrue(data.get("ok"))
        self.assertEqual(rem, [])

    def test_site_has_team_photo_design_and_no_charts(self):
        response = urllib.request.urlopen(self.base_url + "/python-innovation-club.html")
        page = response.read()
        self.assertNotIn(b"chart.umd.min.js", page)
        self.assertNotIn(b'id="analytics"', page)
        self.assertNotIn(b"Club Stats", page)
        self.assertIn(b"team-avatar-frame", page)
        self.assertIn(b"team-card", page)
        self.assertIn(b"team-role-badge", page)