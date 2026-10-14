"""Create, move and cancel Zoom meetings for sessions (Zoom Server-to-Server OAuth).

Everything here is a no-op until ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID and
ZOOM_CLIENT_SECRET are set, and a Zoom failure never breaks saving a session:
the error is logged and returned so the caller can show it.

A link that staff pasted by hand (a `zoom_url` with no `zoom_meeting_id`) is
never replaced. Only meetings this module created are updated or deleted.
"""
import base64
import datetime
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.utils import timezone

log = logging.getLogger(__name__)

API = "https://api.zoom.us/v2"
TOKEN_URL = "https://zoom.us/oauth/token"
TIMEOUT = 10

_token = {"value": "", "expires": 0.0}


class ZoomError(Exception):
    pass


def is_configured():
    return all(getattr(settings, name, "") for name in ("ZOOM_ACCOUNT_ID", "ZOOM_CLIENT_ID", "ZOOM_CLIENT_SECRET"))


def _send(req):
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "ignore")[:300]
        raise ZoomError(f"Zoom {exc.code}: {detail}") from exc
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise ZoomError(f"Zoom unreachable: {exc}") from exc


def _access_token():
    if _token["value"] and _token["expires"] > time.time() + 60:
        return _token["value"]
    creds = base64.b64encode(f"{settings.ZOOM_CLIENT_ID}:{settings.ZOOM_CLIENT_SECRET}".encode()).decode()
    query = urllib.parse.urlencode({"grant_type": "account_credentials", "account_id": settings.ZOOM_ACCOUNT_ID})
    req = urllib.request.Request(f"{TOKEN_URL}?{query}", data=b"", method="POST",
                                 headers={"Authorization": f"Basic {creds}"})
    payload = _send(req)
    _token["value"] = payload.get("access_token", "")
    _token["expires"] = time.time() + int(payload.get("expires_in", 3600))
    if not _token["value"]:
        raise ZoomError("Zoom returned no access token")
    return _token["value"]


def _api(path, payload=None, method="GET"):
    headers = {"Authorization": f"Bearer {_access_token()}"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    return _send(urllib.request.Request(f"{API}{path}", data=body, method=method, headers=headers))


def _payload(lesson):
    course = lesson.cohort.course
    return {
        "topic": f"{course.title_en or course.title_ar} - Session {lesson.number}"[:200],
        "type": 2,
        "start_time": lesson.starts_at.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "duration": lesson.duration_minutes,
        "timezone": "UTC",
        "settings": {"join_before_host": False, "waiting_room": True, "mute_upon_entry": True},
    }


def sync_lesson(lesson):
    """Make the session's Zoom meeting match the session. Returns (changed, error)."""
    if not is_configured():
        return False, "Zoom is not configured"
    try:
        if lesson.zoom_meeting_id:
            _api(f"/meetings/{lesson.zoom_meeting_id}", _payload(lesson), "PATCH")
            return True, ""
        if lesson.zoom_url:
            return False, ""
        data = _api("/users/me/meetings", _payload(lesson), "POST")
    except ZoomError as exc:
        log.warning("Zoom sync failed for lesson %s: %s", lesson.pk, exc)
        return False, str(exc)
    lesson.zoom_meeting_id = str(data["id"])
    lesson.zoom_url = data.get("join_url", "")
    lesson.save(update_fields=["zoom_meeting_id", "zoom_url"])
    return True, ""


def delete_lesson_meeting(lesson):
    """Cancel the meeting this module created for the session, if any."""
    if not (lesson.zoom_meeting_id and is_configured()):
        return
    try:
        _api(f"/meetings/{lesson.zoom_meeting_id}", method="DELETE")
    except ZoomError as exc:
        log.warning("Zoom delete failed for lesson %s: %s", lesson.pk, exc)


def sync_cohort(cohort):
    """Create meetings for every upcoming session of the cohort that has no link. Returns (created, errors)."""
    if not is_configured():
        return 0, []
    created, errors = 0, []
    lessons = cohort.lessons.filter(starts_at__gte=timezone.now(), zoom_url="", zoom_meeting_id="")
    for lesson in lessons.select_related("cohort__course"):
        changed, error = sync_lesson(lesson)
        created += changed
        if error:
            errors.append(error)
            break  # same credentials for every call; stop at the first failure
    return created, errors
