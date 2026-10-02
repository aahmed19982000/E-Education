# E-Education Academy — Django site

A bilingual (Arabic/English) site for an English-learning academy: home, about,
courses, teacher workshop, a free placement quiz, articles, a
contact form, and login/registration.

## Apps

- `core` — home, about, teacher-track pages; language toggle; shared UI copy (`core/translations.py`)
- `articles` — `Article` model, list + detail pages
- `quiz` — `Question` model, session-driven placement test (intro → question → result)
- `contact_us` — `ContactMessage` model + contact form
- `accounts` — registration/login (email-based) backed by Django's `User` + a `Profile` (phone)

All admin-editable content (articles, quiz questions, contact
messages) is managed from `/admin/`. Static interface strings (nav, buttons,
headings) live in `core/translations.py` as AR/EN dictionaries, selected by
`request.lang` (stored in the session, toggled via `/lang/<ar|en>/`).

## Run locally

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_content   # loads the articles/quiz data
python manage.py createsuperuser
python manage.py runserver
```

Visit http://localhost:8000/ and http://localhost:8000/admin/.
