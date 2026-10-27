# AI DISCLOSURE
# Claude  (Anthropic's AI ) was used to write and modify this file.
# It was used throughout this project, including the calendar system, the toast
# system, the switch from browser notifications to toasts, per-browser sessions,
# the mobile sidebar drawer and the tests.

import uuid

import pytest
import queries
from app import app


@pytest.fixture
def browsers():
    app.config["TESTING"] = True
    # No `with` here: two clients both preserving request contexts at once
    # pop them out of order. Plain clients still keep their own cookie jars.
    return app.test_client(), app.test_client()


@pytest.fixture
def owned(browsers):
    a, _ = browsers
    a.get("/")
    with a.session_transaction() as s:
        uid = s["uid"]
    title = f"Iso {uuid.uuid4().hex[:8]}"
    resp = a.post(
        "/project/new",
        data={
            "title": title,
            "start_date": "2025-01-01",
            "start_time": "09:00",
            "end_date": "2025-01-10",
            "end_time": "17:00",
        },
    )
    pid = int(resp.headers["Location"].rstrip("/").split("/")[-1])
    yield {"id": pid, "title": title, "uid": uid}
    queries.delete_project(pid, uid)


def test_each_browser_gets_its_own_stable_id(browsers):
    a, b = browsers
    a.get("/")
    b.get("/")
    with a.session_transaction() as sa:
        first = sa["uid"]
    with b.session_transaction() as sb:
        assert sb["uid"] != first
    a.get("/calendar")
    with a.session_transaction() as sa:
        assert sa["uid"] == first


def test_owner_sees_their_project_other_browser_does_not(browsers, owned):
    a, b = browsers
    assert owned["title"].encode() in a.get("/").data
    assert owned["title"].encode() not in b.get("/").data
    assert owned["title"].encode() not in b.get(f"/project/{owned['id']}").data


def test_other_browser_gets_404_on_foreign_project_pages(browsers, owned):
    _, b = browsers
    pid = owned["id"]
    assert b.get(f"/project/{pid}/edit").status_code == 404
    assert b.get(f"/project/{pid}/activity/new").status_code == 404
    assert b.get(f"/project/{pid}/slots?date=2025-01-02&duration=30").status_code == 404


def test_other_browser_cannot_delete_or_edit(browsers, owned):
    _, b = browsers
    pid = owned["id"]
    b.post(f"/project/{pid}/delete")
    assert queries.get_project(pid, owned["uid"]) is not None

    resp = b.post(
        f"/project/{pid}/edit",
        data={
            "title": "hacked",
            "start_date": "2025-01-01",
            "start_time": "09:00",
            "end_date": "2025-01-10",
            "end_time": "17:00",
        },
    )
    assert resp.status_code == 404
    assert queries.get_project(pid, owned["uid"])["title"] == owned["title"]


def test_other_browser_cannot_touch_foreign_tasks(browsers, owned):
    a, b = browsers
    a.post(
        f"/project/{owned['id']}/activity/new",
        data={
            "title": "mine",
            "description": "",
            "due_date": "2025-01-02",
            "start_time": "10:00",
            "duration": "30",
        },
    )
    task = queries.get_activities(owned["id"], owned["uid"])[0]
    assert b.get(f"/activity/{task['id']}/edit").status_code == 404
    assert b.post(f"/activity/{task['id']}/delete").status_code == 404
    assert queries.get_activity(task["id"], owned["uid"]) is not None


def test_calendar_and_due_api_are_scoped(browsers, owned):
    a, b = browsers
    day = "/calendar/day/2025-01-05"
    assert owned["title"].encode() in a.get(day).data
    assert owned["title"].encode() not in b.get(day).data

    now = "?now=2025-01-10T18:00"
    assert owned["title"] in [i["title"] for i in a.get("/api/due" + now).get_json()]
    assert b.get("/api/due" + now).get_json() == []
