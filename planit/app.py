import calendar as cal
from datetime import date, datetime

import queries
import timehelpers as th
from flask import Flask, jsonify, redirect, render_template, request, url_for

app = Flask(__name__)

app.config["TESTING"] = True

DEFAULT_START, DEFAULT_END, DEFAULT_DURATION = "09:00", "17:00", 30


def today():
    return date.today().isoformat()  # noqa: DTZ011

@app.context_processor
def inject_globals():
    return {"projects": queries.get_projects(), "th": th}


@app.route("/")
@app.route("/project/<int:project_id>")
def index(project_id=None):
    current = queries.get_project(project_id) if project_id else None
    activities = queries.get_activities(project_id) if current else []
    enriched = [
        {
            **dict(a),
            "priority": th.get_priority(a["due_date"], a["end_time"]),
            "urgency": th.get_urgency_class(
                th.get_priority(a["due_date"], a["end_time"])
            ),
        }
        for a in activities
    ]
    return render_template(
        "index.html",
        view="list",
        current=current,
        activities=enriched,
    )


@app.route("/project/new", methods=["GET", "POST"])
def new_project():
    if request.method == "POST":
        return _save_project(None)
    return render_template("project_form.html", project=None, today=today())


@app.route("/project/<int:project_id>/edit", methods=["GET", "POST"])
def edit_project(project_id):
    project = queries.get_project(project_id)
    if request.method == "POST":
        return _save_project(project_id)
    return render_template("project_form.html", project=project, today=today())


def _save_project(project_id):
    title = request.form["title"]
    start_date, start_time = request.form["start_date"], request.form["start_time"]
    end_date, end_time = request.form["end_date"], request.form["end_time"]

    if end_date < start_date or (end_date == start_date and end_time <= start_time):
        return render_template(
            "project_form.html",
            project=queries.get_project(project_id) if project_id else None,
            error="The end of the project has to be after the start.",
            today=today(),
        )

    if project_id:
        activities = queries.get_activities(project_id)
        out_of_bounds = th.find_activities_outside_window(
            activities, start_date, end_date, start_time, end_time
        )
        if out_of_bounds:
            names = ", ".join(f'"{a["title"]}"' for a in out_of_bounds[:3])
            extra = (
                f" and {len(out_of_bounds) - 3} more" if len(out_of_bounds) > 3 else ""
            )
            error = (
                f"That window would leave {len(out_of_bounds)} task(s) outside it: "
                f"{names}{extra}. Reschedule or delete those tasks first, then try again."
            )
            return render_template(
                "project_form.html",
                project=queries.get_project(project_id),
                error=error,
                today=today(),
            )
        queries.update_project(
            project_id, title, start_date, start_time, end_date, end_time
        )
    else:
        project_id = queries.create_project(
            title, start_date, start_time, end_date, end_time
        )

    return redirect(url_for("index", project_id=project_id))


@app.route("/project/<int:project_id>/delete", methods=["POST"])
def delete_project(project_id):
    queries.delete_project(project_id)
    return redirect(url_for("index"))


@app.route("/project/<int:project_id>/slots")
def get_slots(project_id):
    project = queries.get_project(project_id)
    current_date = request.args.get("date")
    duration = int(request.args.get("duration", DEFAULT_DURATION))
    exclude_id = request.args.get("exclude", type=int)
    activities = queries.get_activities(project_id)

    slots = th.generate_time_slots(project["start_time"], project["end_time"])
    result = [
        {
            "time": s,
            "label": th.format_time_label(s),
            "available": th.is_slot_available(
                activities,
                current_date,
                s,
                duration,
                project["start_time"],
                project["end_time"],
                exclude_id,
            ),
        }
        for s in slots
    ]
    return jsonify(result)


@app.route("/project/<int:project_id>/activity/new", methods=["GET", "POST"])
def new_activity(project_id):
    project = queries.get_project(project_id)
    if request.method == "POST":
        return _save_activity(project_id, None)

    activities = queries.get_activities(project_id)
    slots = th.generate_time_slots(project["start_time"], project["end_time"])
    first_free = next(
        (
            s
            for s in slots
            if th.is_slot_available(
                activities,
                project["start_date"],
                s,
                DEFAULT_DURATION,
                project["start_time"],
                project["end_time"],
            )
        ),
        "",
    )
    return render_template(
        "activity_form.html",
        project=project,
        activity=None,
        due_date=project["start_date"],
        start_time=first_free,
        duration=DEFAULT_DURATION,
        slots=slots,
        activities=activities,
    )


@app.route("/activity/<int:activity_id>/edit", methods=["GET", "POST"])
def edit_activity(activity_id):
    activity = queries.get_activity(activity_id)
    project = queries.get_project(activity["project_id"])
    if request.method == "POST":
        return _save_activity(activity["project_id"], activity_id)

    activities = queries.get_activities(project["id"])
    slots = th.generate_time_slots(project["start_time"], project["end_time"])
    duration = th.to_minutes(activity["end_time"]) - th.to_minutes(
        activity["start_time"]
    )
    return render_template(
        "activity_form.html",
        project=project,
        activity=activity,
        due_date=activity["due_date"],
        start_time=activity["start_time"],
        duration=max(15, duration),
        slots=slots,
        activities=activities,
    )


def _save_activity(project_id, activity_id):
    project = queries.get_project(project_id)
    activities = queries.get_activities(project_id)
    title = request.form["title"]
    description = request.form.get("description", "")
    due_date = request.form["due_date"]
    start_time = request.form["start_time"]
    duration = int(request.form["duration"])
    end_time = th.add_minutes(start_time, duration)

    if not th.is_slot_available(
        activities,
        due_date,
        start_time,
        duration,
        project["start_time"],
        project["end_time"],
        exclude_activity_id=activity_id,
    ):
        # re-render form with an error instead of trusting the client
        slots = th.generate_time_slots(project["start_time"], project["end_time"])
        return render_template(
            "activity_form.html",
            project=project,
            activity=queries.get_activity(activity_id) if activity_id else None,
            due_date=due_date,
            start_time=start_time,
            duration=duration,
            slots=slots,
            activities=activities,
            error="Pick a free time slot to continue.",
        )

    if activity_id:
        queries.update_activity(
            activity_id, title, description, due_date, start_time, end_time
        )
    else:
        queries.create_activity(
            project_id, title, description, due_date, start_time, end_time
        )

    return redirect(url_for("index", project_id=project_id))


@app.route("/activity/<int:activity_id>/delete", methods=["POST"])
def delete_activity(activity_id):
    activity = queries.get_activity(activity_id)
    queries.delete_activity(activity_id)
    return redirect(url_for("index", project_id=activity["project_id"]))


@app.route("/calendar")
def calendar_view():
    year = request.args.get("year", type=int, default=date.today().year)  # noqa: DTZ011
    month = request.args.get("month", type=int, default=date.today().month)  # noqa: DTZ011
    selected_date = request.args.get("date")

    dated_projects = queries.get_calendar_projects(year, month)
    dated_activities = queries.get_calendar_activities(year, month)

    dates_with_items = (
        {p["start_date"] for p in dated_projects}
        | {p["end_date"] for p in dated_projects}
        | {a["due_date"] for a in dated_activities}
    )

    agenda = None
    if selected_date:
        day_projects = [p for p in dated_projects if p["end_date"] == selected_date]
        day_activities = [a for a in dated_activities if a["due_date"] == selected_date]
        project_ids = {p["id"] for p in day_projects} | {
            a["project_id"] for a in day_activities
        }

        if len(project_ids) == 1:
            return redirect(url_for("index", project_id=next(iter(project_ids))))

        agenda = {"projects": day_projects, "activities": day_activities}

    # month-grid data the calendar template needs (weekday offset, day count,
    # human label, and prev/next links) - Jinja can't do date math on its own.
    first_weekday_mon0, days_in_month = cal.monthrange(year, month)
    first_weekday = (first_weekday_mon0 + 1) % 7  # convert Mon=0 -> Sun=0

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    return render_template(
        "calendar.html",
        year=year,
        month=month,
        month_label=date(year, month, 1).strftime("%B %Y"),
        first_weekday=first_weekday,
        days_in_month=days_in_month,
        prev_month=prev_month,
        prev_year=prev_year,
        next_month=next_month,
        next_year=next_year,
        today_str=today(),
        dates_with_items=dates_with_items,
        selected_date=selected_date,
        agenda=agenda,
    )


@app.route("/api/due")
def due_items():
    now = datetime.now().isoformat(timespec="minutes")  # noqa: DTZ005
    projects = queries.get_due_projects(now)
    activities = queries.get_due_activities(now)
    return jsonify(projects + activities)
