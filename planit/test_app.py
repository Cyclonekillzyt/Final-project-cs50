"""
Full pytest suite for Plan It.

Run with:
    pip install pytest
    pytest test_app.py -v

Notes:
- These tests hit the real planit.db (same as the app does — there's no
  separate test database configured), so every fixture creates its own
  uniquely-named data and tears it down afterward. Don't run this against
  a database with data you care about without checking DB_PATH first.
- Tests are grouped into classes by feature area; each has its own fixtures
  so you can run a single class in isolation, e.g.
      pytest test_app.py::TestActivityCRUD -v
"""

import uuid

import pytest
import timehelpers as th
import queries
from app import app


# ---------------------------------------------------------------------------
# shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def _unique_title(prefix):
    return f"{prefix} {uuid.uuid4().hex[:8]}"


@pytest.fixture
def project(client):
    """Create a project (Jan 1-10 2025, 09:00-17:00) and clean it up after."""
    title = _unique_title("Pytest Project")
    resp = client.post(
        "/project/new",
        data={
            "title": title,
            "start_date": "2025-01-01",
            "start_time": "09:00",
            "end_date": "2025-01-10",
            "end_time": "17:00",
        },
    )
    assert resp.status_code == 302
    project_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

    yield {"id": project_id, "title": title}

    queries.delete_project(project_id)


@pytest.fixture
def activity(client, project):
    """A task inside `project`, due 2025-01-02 10:00-10:30."""
    title = _unique_title("Pytest Task")
    resp = client.post(
        f"/project/{project['id']}/activity/new",
        data={
            "title": title,
            "description": "created by pytest",
            "due_date": "2025-01-02",
            "start_time": "10:00",
            "duration": "30",
        },
    )
    assert resp.status_code == 302
    activities = queries.get_activities(project["id"])
    activity_row = next(a for a in activities if a["title"] == title)

    yield {"id": activity_row["id"], "title": title, "project_id": project["id"]}

    # project fixture's own teardown will cascade-delete this, but if the
    # activity was already deleted mid-test that's fine too
    queries.delete_activity(activity_row["id"])


# ---------------------------------------------------------------------------
# page rendering / layout
# ---------------------------------------------------------------------------


class TestPageRendering:
    def test_index_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Plan It" in resp.data  # sidebar logo

    def test_index_empty_state_when_no_project_selected(self, client):
        resp = client.get("/")
        assert b"Pick a project from the sidebar" in resp.data

    def test_index_shows_selected_project(self, client, project):
        resp = client.get(f"/project/{project['id']}")
        assert resp.status_code == 200
        assert project["title"].encode() in resp.data

    def test_index_nonexistent_project_falls_back_to_empty_state(self, client):
        resp = client.get("/project/999999999")
        assert resp.status_code == 200
        text = " ".join(resp.data.decode().split())
        assert "Select a project" in text
        assert "Pick a project from the sidebar" in text

    def test_sidebar_lists_created_project(self, client, project):
        resp = client.get("/")
        assert project["title"].encode() in resp.data

    def test_sidebar_has_close_button_for_mobile_drawer(self, client):
        resp = client.get("/")
        assert b'id="sidebar-close"' in resp.data
        assert b'id="menu-btn"' in resp.data

    def test_header_view_toggle_present_on_every_page(self, client, project):
        for path in (
            "/",
            f"/project/{project['id']}",
            "/calendar",
            "/calendar/day/2025-01-02",
            "/project/new",
            f"/project/{project['id']}/edit",
        ):
            resp = client.get(path)
            assert resp.status_code == 200
            assert b"List" in resp.data
            assert b"Calendar" in resp.data
            assert b"menu-btn" in resp.data  
            assert b"sidebar-backdrop" in resp.data

    def test_task_count_badge_reflects_activities(self, client, project, activity):
        resp = client.get("/")
        # the project row in the sidebar should show a count of 1
        assert project["title"].encode() in resp.data
        assert b">1<" in resp.data


# ---------------------------------------------------------------------------
# project CRUD
# ---------------------------------------------------------------------------


class TestProjectCRUD:
    def test_create_project_redirects_to_it(self, client):
        title = _unique_title("Create Test")
        resp = client.post(
            "/project/new",
            data={
                "title": title,
                "start_date": "2025-02-01",
                "start_time": "08:00",
                "end_date": "2025-02-05",
                "end_time": "16:00",
            },
        )
        assert resp.status_code == 302
        assert "/project/" in resp.headers["Location"]

        project_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        try:
            view = client.get(f"/project/{project_id}")
            assert title.encode() in view.data
        finally:
            queries.delete_project(project_id)

    def test_reject_end_before_start(self, client):
        resp = client.post(
            "/project/new",
            data={
                "title": "Bad Project",
                "start_date": "2025-01-10",
                "start_time": "09:00",
                "end_date": "2025-01-01",
                "end_time": "17:00",
            },
        )
        assert resp.status_code == 200
        assert b"has to be after the start" in resp.data

    def test_reject_same_day_end_time_not_after_start_time(self, client):
        resp = client.post(
            "/project/new",
            data={
                "title": "Bad Project 2",
                "start_date": "2025-01-05",
                "start_time": "10:00",
                "end_date": "2025-01-05",
                "end_time": "09:00",
            },
        )
        assert resp.status_code == 200
        assert b"has to be after the start" in resp.data

    def test_edit_project_form_prefills_existing_values(self, client, project):
        resp = client.get(f"/project/{project['id']}/edit")
        assert resp.status_code == 200
        assert project["title"].encode() in resp.data
        assert b"2025-01-01" in resp.data
        assert b"2025-01-10" in resp.data

    def test_edit_project_saves_changes(self, client, project):
        new_title = _unique_title("Renamed")
        resp = client.post(
            f"/project/{project['id']}/edit",
            data={
                "title": new_title,
                "start_date": "2025-01-01",
                "start_time": "09:00",
                "end_date": "2025-01-15",
                "end_time": "17:00",
            },
        )
        assert resp.status_code == 302
        updated = queries.get_project(project["id"])
        assert updated["title"] == new_title
        assert updated["end_date"] == "2025-01-15"

    def test_shrinking_window_rejected_when_it_strands_a_task(
        self, client, project, activity
    ):
        # activity is due 2025-01-02 10:00-10:30; try to shrink the project
        # to start 2025-01-05, which leaves that task outside the window
        resp = client.post(
            f"/project/{project['id']}/edit",
            data={
                "title": project["title"],
                "start_date": "2025-01-05",
                "start_time": "09:00",
                "end_date": "2025-01-10",
                "end_time": "17:00",
            },
        )
        assert resp.status_code == 200
        assert b"would leave" in resp.data
        assert activity["title"].encode() in resp.data

        # and the project itself should be untouched
        unchanged = queries.get_project(project["id"])
        assert unchanged["start_date"] == "2025-01-01"

    def test_shrinking_window_allowed_when_tasks_still_fit(
        self, client, project, activity
    ):
        resp = client.post(
            f"/project/{project['id']}/edit",
            data={
                "title": project["title"],
                "start_date": "2025-01-01",
                "start_time": "09:00",
                "end_date": "2025-01-03",  # activity is on 01-02, still fits
                "end_time": "17:00",
            },
        )
        assert resp.status_code == 302
        updated = queries.get_project(project["id"])
        assert updated["end_date"] == "2025-01-03"

    def test_delete_project(self, client):
        resp = client.post(
            "/project/new",
            data={
                "title": "To Delete",
                "start_date": "2025-03-01",
                "start_time": "09:00",
                "end_date": "2025-03-02",
                "end_time": "17:00",
            },
        )
        project_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])

        del_resp = client.post(f"/project/{project_id}/delete")
        assert del_resp.status_code == 302
        assert queries.get_project(project_id) is None

    def test_delete_project_cascades_to_its_activities(self, client, project, activity):
        client.post(f"/project/{project['id']}/delete")
        assert queries.get_project(project["id"]) is None
        assert queries.get_activity(activity["id"]) is None


# ---------------------------------------------------------------------------
# activity CRUD
# ---------------------------------------------------------------------------


class TestActivityCRUD:
    def test_new_activity_form_shows_project_context(self, client, project):
        resp = client.get(f"/project/{project['id']}/activity/new")
        assert resp.status_code == 200
        assert project["title"].encode() in resp.data

    def test_create_activity_redirects_to_project(self, client, project):
        title = _unique_title("New Task")
        resp = client.post(
            f"/project/{project['id']}/activity/new",
            data={
                "title": title,
                "description": "",
                "due_date": "2025-01-03",
                "start_time": "11:00",
                "duration": "30",
            },
        )
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith(f"/project/{project['id']}")

        view = client.get(f"/project/{project['id']}")
        assert title.encode() in view.data

    def test_double_booked_slot_rejected(self, client, project, activity):
        resp = client.post(
            f"/project/{project['id']}/activity/new",
            data={
                "title": "Conflicting Task",
                "description": "",
                "due_date": "2025-01-02",
                "start_time": "10:00",  # same slot as `activity`
                "duration": "30",
            },
        )
        assert resp.status_code == 200
        assert b"Pick a free time slot" in resp.data

    def test_partial_overlap_rejected(self, client, project, activity):
        # activity occupies 10:00-10:30; a task starting 10:15 overlaps it
        resp = client.post(
            f"/project/{project['id']}/activity/new",
            data={
                "title": "Overlapping Task",
                "description": "",
                "due_date": "2025-01-02",
                "start_time": "10:15",
                "duration": "30",
            },
        )
        assert resp.status_code == 200
        assert b"Pick a free time slot" in resp.data

    def test_back_to_back_slots_allowed(self, client, project, activity):
        # activity ends at 10:30 - a task starting exactly then should be fine
        resp = client.post(
            f"/project/{project['id']}/activity/new",
            data={
                "title": "Back To Back Task",
                "description": "",
                "due_date": "2025-01-02",
                "start_time": "10:30",
                "duration": "30",
            },
        )
        assert resp.status_code == 302

    def test_edit_activity_form_prefills_values(self, client, activity):
        resp = client.get(f"/activity/{activity['id']}/edit")
        assert resp.status_code == 200
        assert activity["title"].encode() in resp.data

    def test_edit_activity_can_keep_its_own_slot(self, client, project, activity):
        # editing an activity shouldn't conflict with itself
        resp = client.post(
            f"/activity/{activity['id']}/edit",
            data={
                "title": activity["title"],
                "description": "updated",
                "due_date": "2025-01-02",
                "start_time": "10:00",
                "duration": "30",
            },
        )
        assert resp.status_code == 302
        updated = queries.get_activity(activity["id"])
        assert updated["description"] == "updated"

    def test_delete_activity(self, client, project, activity):
        resp = client.post(f"/activity/{activity['id']}/delete")
        assert resp.status_code == 302
        assert queries.get_activity(activity["id"]) is None


# ---------------------------------------------------------------------------
# /project/<id>/slots  (JSON, used by the time-slot picker)
# ---------------------------------------------------------------------------


class TestSlotsEndpoint:
    def test_returns_json_list_of_slots(self, client, project):
        resp = client.get(f"/project/{project['id']}/slots?date=2025-01-02&duration=30")
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert {"time", "label", "available"} <= data[0].keys()

    def test_occupied_slot_marked_unavailable(self, client, project, activity):
        resp = client.get(f"/project/{project['id']}/slots?date=2025-01-02&duration=30")
        data = resp.get_json()
        ten_am = next(s for s in data if s["time"] == "10:00")
        assert ten_am["available"] is False

    def test_free_slot_marked_available(self, client, project, activity):
        resp = client.get(f"/project/{project['id']}/slots?date=2025-01-02&duration=30")
        data = resp.get_json()
        eleven_am = next(s for s in data if s["time"] == "11:00")
        assert eleven_am["available"] is True

    def test_exclude_param_frees_up_the_activity_being_edited(
        self, client, project, activity
    ):
        without_exclude = client.get(
            f"/project/{project['id']}/slots?date=2025-01-02&duration=30"
        ).get_json()
        with_exclude = client.get(
            f"/project/{project['id']}/slots?date=2025-01-02&duration=30&exclude={activity['id']}"
        ).get_json()

        ten_am_excluded = next(s for s in without_exclude if s["time"] == "10:00")
        ten_am_included = next(s for s in with_exclude if s["time"] == "10:00")
        assert ten_am_excluded["available"] is False
        assert ten_am_included["available"] is True


# ---------------------------------------------------------------------------
# /calendar (month view) and /calendar/day/<date> (day view)
# ---------------------------------------------------------------------------


class TestCalendarView:
    def test_calendar_loads(self, client):
        resp = client.get("/calendar?year=2025&month=1")
        assert resp.status_code == 200
        assert b"January 2025" in resp.data

    def test_calendar_shows_weekday_headers(self, client):
        resp = client.get("/calendar?year=2025&month=1")
        for wd in (b"Sun", b"Mon", b"Tue", b"Wed", b"Thu", b"Fri", b"Sat"):
            assert wd in resp.data

    def test_calendar_prev_next_links_present(self, client):
        resp = client.get("/calendar?year=2025&month=6")
        assert (
            b"year=2025&amp;month=5" in resp.data or b"year=2025&month=5" in resp.data
        )
        assert (
            b"year=2025&amp;month=7" in resp.data or b"year=2025&month=7" in resp.data
        )

    def test_invalid_month_is_clamped_instead_of_crashing(self, client):
        resp = client.get("/calendar?year=2025&month=13")
        assert resp.status_code == 200
        assert b"December 2025" in resp.data

    def test_dates_with_items_get_a_dot(self, client, project):
        resp = client.get("/calendar?year=2025&month=1")
        assert b"calendar__dot" in resp.data

    def test_dots_cover_every_day_of_a_multi_day_project(self, client, project):
        # project spans Jan 1-10, so a mid-span day (Jan 5) should have a dot too
        resp = client.get("/calendar?year=2025&month=1")
        html = resp.data.decode()
        cell = html.split('href="/calendar/day/2025-01-05"')[1].split("</a>")[0]
        assert "calendar__dot" in cell

    def test_day_without_items_has_no_dot(self, client, project):
        resp = client.get("/calendar?year=2025&month=1")
        html = resp.data.decode()
        cell = html.split('href="/calendar/day/2025-01-20"')[1].split("</a>")[0]
        assert "calendar__dot" not in cell

    def test_day_cells_link_to_day_view(self, client, project):
        resp = client.get("/calendar?year=2025&month=1")
        assert b"/calendar/day/2025-01-10" in resp.data

    def test_legend_lists_projects_in_the_month(self, client, project):
        resp = client.get("/calendar?year=2025&month=1")
        assert b"calendar__legend" in resp.data
        assert project["title"].encode() in resp.data


class TestDayView:
    def test_day_view_loads(self, client):
        resp = client.get("/calendar/day/2025-01-02")
        assert resp.status_code == 200
        assert b"Thursday, 02 January 2025" in resp.data

    def test_day_view_shows_task_and_project(self, client, project, activity):
        resp = client.get("/calendar/day/2025-01-02")
        assert resp.status_code == 200
        assert activity["title"].encode() in resp.data
        assert project["title"].encode() in resp.data
        assert b"cal-event" in resp.data
        assert b"cal-band" in resp.data

    def test_task_block_shows_time_range_and_duration(self, client, project, activity):
        resp = client.get("/calendar/day/2025-01-02")
        assert b"10:00 AM" in resp.data
        assert b"10:30 AM" in resp.data
        assert b"30 min" in resp.data

    def test_task_block_links_to_edit_page(self, client, project, activity):
        resp = client.get("/calendar/day/2025-01-02")
        assert f"/activity/{activity['id']}/edit".encode() in resp.data

    def test_project_chip_links_to_project(self, client, project, activity):
        resp = client.get("/calendar/day/2025-01-02")
        assert f'href="/project/{project["id"]}"'.encode() in resp.data

    def test_mid_span_project_is_labelled_all_day(self, client, project):
        resp = client.get("/calendar/day/2025-01-05")
        assert b"All day" in resp.data

    def test_project_start_and_end_days_are_labelled(self, client, project):
        assert b"Starts today" in client.get("/calendar/day/2025-01-01").data
        assert b"Ends today" in client.get("/calendar/day/2025-01-10").data

    def test_single_day_project_shows_its_duration(self, client):
        title = _unique_title("Two Hour Project")
        resp = client.post(
            "/project/new",
            data={
                "title": title,
                "start_date": "2025-04-01",
                "start_time": "09:00",
                "end_date": "2025-04-01",
                "end_time": "11:00",
            },
        )
        project_id = int(resp.headers["Location"].rstrip("/").split("/")[-1])
        try:
            page = client.get("/calendar/day/2025-04-01")
            assert title.encode() in page.data
            assert b"2 hr project" in page.data
        finally:
            queries.delete_project(project_id)

    def test_day_view_does_not_show_other_days_tasks(self, client, project, activity):
        resp = client.get("/calendar/day/2025-01-03")
        assert activity["title"].encode() not in resp.data

    def test_empty_day_shows_nothing_message(self, client):
        resp = client.get("/calendar/day/2099-01-15")
        assert resp.status_code == 200
        assert b"Nothing scheduled" in resp.data

    def test_invalid_day_redirects_to_month_view(self, client):
        resp = client.get("/calendar/day/not-a-date", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/calendar")

    def test_prev_and_next_day_links(self, client):
        resp = client.get("/calendar/day/2025-01-02")
        assert b"/calendar/day/2025-01-01" in resp.data
        assert b"/calendar/day/2025-01-03" in resp.data

    def test_prev_next_cross_month_boundary(self, client):
        resp = client.get("/calendar/day/2025-01-01")
        assert b"/calendar/day/2024-12-31" in resp.data

    def test_back_to_month_link(self, client):
        resp = client.get("/calendar/day/2025-01-02")
        assert b"year=2025&amp;month=1" in resp.data or b"year=2025&month=1" in resp.data

    def test_today_gets_a_now_line(self, client):
        resp = client.get(f"/calendar/day/{app_today()}")
        assert b"day-grid__now" in resp.data

    def test_past_day_has_no_now_line(self, client):
        resp = client.get("/calendar/day/2025-01-02")
        assert b"day-grid__now" not in resp.data

    def test_calendar_toggle_active_on_day_view(self, client):
        resp = client.get("/calendar/day/2025-01-02")
        html = resp.data.decode()
        calendar_btn = html.split('href="/calendar"')[0].rsplit("<a", 1)[1]
        assert "is-active" in calendar_btn


def app_today():
    from app import today

    return today()


# ---------------------------------------------------------------------------
# th.build_day_layout / th.format_duration (pure functions, no client needed)
# ---------------------------------------------------------------------------


def _project_row(pid=1, start_date="2025-01-01", start_time="09:00",
                 end_date="2025-01-01", end_time="17:00", title="P"):
    return {
        "id": pid, "title": title,
        "start_date": start_date, "start_time": start_time,
        "end_date": end_date, "end_time": end_time,
    }


def _task_row(tid, start, end, pid=1, day="2025-01-01"):
    return {
        "id": tid, "title": f"T{tid}", "project_id": pid, "project_title": "P",
        "due_date": day, "start_time": start, "end_time": end,
    }


class TestDayLayout:
    def test_format_duration(self):
        assert th.format_duration(30) == "30 min"
        assert th.format_duration(60) == "1 hr"
        assert th.format_duration(120) == "2 hr"
        assert th.format_duration(90) == "1 hr 30 min"

    def test_project_color_is_stable_per_project(self):
        assert th.project_color(3) == th.project_color(3)
        assert th.project_color(1) != th.project_color(2)

    def test_task_position_and_height_match_time(self):
        layout = th.build_day_layout(
            "2025-01-01", [_project_row()], [_task_row(1, "10:00", "12:00")]
        )
        task = layout["tasks"][0]
        assert task["top"] == 10 * th.HOUR_PX
        assert task["height"] == 2 * th.HOUR_PX
        assert task["duration"] == "2 hr"

    def test_short_task_gets_minimum_height_and_short_flag(self):
        layout = th.build_day_layout(
            "2025-01-01", [_project_row()], [_task_row(1, "10:00", "10:15")]
        )
        task = layout["tasks"][0]
        assert task["height"] >= th.MIN_BLOCK_PX
        assert task["short"] is True

    def test_overlapping_tasks_are_placed_side_by_side(self):
        layout = th.build_day_layout(
            "2025-01-01",
            [_project_row(1), _project_row(2)],
            [_task_row(1, "10:00", "11:00", pid=1), _task_row(2, "10:30", "11:30", pid=2)],
        )
        a, b = layout["tasks"]
        assert a["cols"] == b["cols"] == 2
        assert {a["col"], b["col"]} == {0, 1}

    def test_back_to_back_tasks_are_not_side_by_side(self):
        layout = th.build_day_layout(
            "2025-01-01",
            [_project_row()],
            [_task_row(1, "10:00", "10:30"), _task_row(2, "10:30", "11:00")],
        )
        assert all(t["cols"] == 1 and t["col"] == 0 for t in layout["tasks"])

    def test_non_overlapping_cluster_after_overlap_resets_columns(self):
        layout = th.build_day_layout(
            "2025-01-01",
            [_project_row(1), _project_row(2)],
            [
                _task_row(1, "09:00", "10:00", pid=1),
                _task_row(2, "09:30", "10:30", pid=2),
                _task_row(3, "14:00", "15:00", pid=1),
            ],
        )
        last = next(t for t in layout["tasks"] if t["id"] == 3)
        assert last["cols"] == 1

    def test_task_past_midnight_is_clipped_to_end_of_day(self):
        # add_minutes wraps, so 23:45 + 30 min is stored as end_time "00:15"
        layout = th.build_day_layout(
            "2025-01-01", [_project_row()], [_task_row(1, "23:45", "00:15")]
        )
        task = layout["tasks"][0]
        assert task["end"] == 1440
        assert task["height"] > 0

    def test_multi_day_project_bands_are_clipped_to_the_day(self):
        project = _project_row(start_date="2025-01-01", end_date="2025-01-03",
                               start_time="09:00", end_time="17:00")
        first = th.build_day_layout("2025-01-01", [project], [])["bands"][0]
        middle = th.build_day_layout("2025-01-02", [project], [])["bands"][0]
        last = th.build_day_layout("2025-01-03", [project], [])["bands"][0]

        assert first["top"] == 9 * th.HOUR_PX and first["note"] == "Starts today"
        assert middle["top"] == 0 and middle["height"] == 24 * th.HOUR_PX
        assert middle["note"] == "All day"
        assert last["top"] == 0 and last["height"] == 17 * th.HOUR_PX
        assert last["note"] == "Ends today"

    def test_single_day_project_note_includes_duration(self):
        project = _project_row(start_time="09:00", end_time="11:00")
        band = th.build_day_layout("2025-01-01", [project], [])["bands"][0]
        assert band["note"] == "2 hr project"

    def test_first_px_points_at_earliest_task(self):
        layout = th.build_day_layout(
            "2025-01-01", [_project_row(start_time="00:00")], [_task_row(1, "13:00", "14:00")]
        )
        assert layout["first_px"] == 13 * th.HOUR_PX

    def test_first_px_defaults_to_8am_when_empty(self):
        layout = th.build_day_layout("2025-01-01", [], [])
        assert layout["first_px"] == 8 * th.HOUR_PX

# ---------------------------------------------------------------------------
# /api/due
# ---------------------------------------------------------------------------


class TestDueEndpoint:
    def test_due_endpoint_returns_json_list(self, client):
        resp = client.get("/api/due")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_past_due_activity_appears(self, client, project):
        title = _unique_title("Overdue Task")
        client.post(
            f"/project/{project['id']}/activity/new",
            data={
                "title": title,
                "description": "",
                "due_date": "2025-01-01",  # long past
                "start_time": "09:00",
                "duration": "30",
            },
        )
        resp = client.get("/api/due")
        titles = [item["title"] for item in resp.get_json()]
        assert title in titles

    def test_future_activity_outside_project_span_is_rejected(self, client, project):
        title = _unique_title("Future Task")

        resp = client.post(
            f"/project/{project['id']}/activity/new",
            data={"title": title,"description": "","due_date": "2099-01-01","start_time": "09:00","duration": "30",},
        )

        assert resp.status_code == 200
        assert b"outside the project span" in resp.data


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
