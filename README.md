# E-Education Academy — Django site

A bilingual (Arabic/English) site for an English-learning academy: home, about,
live courses (group and private), a teacher workshop, a team page with student
reviews, a free placement quiz, articles, a contact form, login/registration,
a student area and a staff dashboard.

## Apps

- `core` — home, about, teacher-track pages; language toggle; shared UI copy (`core/translations.py`); seed commands
- `articles` — `Article` model, list + detail pages
- `team` — `TeamMember` (owner, teachers, specialties, YouTube profiles), `TeamReview` (text/YouTube/uploaded video), `TeacherAvailability` (weekly windows)
- `courses` — `Course` (audience: students/teachers, group/private, per-course prices), `Cohort` (teacher + schedule), `CohortSlot`, `Lesson` (sessions), `LessonAttachment`, `Enrollment`, `Attendance`, `EnrollmentRequest`; public catalog, request forms, student area
- `quiz` — questions, categories, grading and time limits, session-driven placement test (intro → question → result)
- `contact_us` — `ContactMessage` model + contact form
- `accounts` — email-based registration/login on Django's `User` + a `Profile` (phone, member role)
- `dashboard` — staff dashboard at `/dashboard/` (articles, team and reviews, quiz questions, courses and cohorts, sessions, enrollment requests, messages, users); access is role-based (`dashboard/permissions.py`)
- `levels` — **migrations only**. The `Level` model was removed, but older `quiz` and `courses` migrations depend on it, so the app stays in `INSTALLED_APPS`. Do not add models; drop it only after squashing those migrations.

Static interface strings (nav, buttons, headings) live in `core/translations.py`
as AR/EN dictionaries, selected by `request.lang` (stored in the session,
toggled via `/lang/<ar|en>/`). Content is managed from `/dashboard/` (and `/admin/`).

## Roles

Defined in `dashboard/permissions.py`: super admin, manager, content staff,
support, and teacher. Each role gets `read`/`write`/no access per dashboard section.

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_content        # articles and quiz data
python manage.py seed_demo_team      # demo team members and reviews
python manage.py seed_demo_courses   # demo courses, cohorts, sessions, requests, a student
python manage.py createsuperuser
python manage.py runserver
```

Visit http://localhost:8000/, http://localhost:8000/dashboard/ and http://localhost:8000/admin/.

`seed_demo_courses` needs the demo team first (run `seed_demo_team` before it).
Both demo commands are safe to re-run. `seed_demo_team --remove` and `seed_demo_courses --reset` delete only the demo data they created.

## Tests

```bash
python manage.py test
```

## Production

Settings support PostgreSQL, Gunicorn and WhiteNoise, with HTTPS-only hardening
independent of `DEBUG`. Run `python manage.py collectstatic` on deploy.
