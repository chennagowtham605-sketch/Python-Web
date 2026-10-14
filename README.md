# Python Innovation Club

Club website for the School of Computer Science, VMKV Engineering College, Salem.

## Run locally

```bash
uv run main.py
```

Open [http://127.0.0.1:8080](http://127.0.0.1:8080) to visit the club site.
Event details and event registration are public; members do not need accounts
or login.

Join requests from the site form are saved to `data/join_applications.json`.
Event registrations are saved separately to `data/event_registrations.json`.
Visitors can register using their name and email. Duplicate registrations for
the same event and email address are rejected. The public website has no
website-handler login or management controls. After an event registration,
the confirmation shows the event's date and venue.

The separate join and event-registration lists are available in the private
admin dashboard at [http://127.0.0.1:8080/admin](http://127.0.0.1:8080/admin).
Only the website handler can sign in and view either list. The event
create/edit/delete and registration-list endpoints are likewise protected.
Set a private key before starting the server in PowerShell:

```powershell
$env:CLUB_ADMIN_TOKEN = "your-long-private-key"; uv run main.py
```

The default handler username is `admin`; set `CLUB_ADMIN_USERNAME` to change
it. The key is the handler password. Do not publish or commit it.

Event information and public club content are served by `GET /api/data`. Join
applications are stored in `data/join_applications.json`; event registrations
are stored in `data/event_registrations.json`. Handler sessions last 12 hours
and are held in memory, so the handler must sign in again after a server
restart. For HTTPS deployments, set
`CLUB_COOKIE_SECURE=1` before starting the server.

Student team photos are stored in `images/team/` with their original filenames.
Each student's photo path is set in `data/club_content.json`; clicking a
student's name on the website opens their photo.

Faculty photos are stored in `images/faculty/` with their original filenames.
Filename matches, including uniquely matching spelling variants, are linked in
`data/club_content.json`; clicking a matched faculty member's name opens their
photo. Names with conflicting initials or no corresponding file are left
unlinked.

Project idea photos are stored in `images/projects/`. Their titles, short
descriptions, and image paths are listed in `data/club_content.json`; clicking
a project title opens its image.

The VMKV Engineering College wordmark, AICTE logo, and NAAC badge are stored in
`images/` and displayed in the website header beside the club identity.
