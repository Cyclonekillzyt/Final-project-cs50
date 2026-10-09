from datetime import datetime, timedelta


def to_minutes(time_str):
    h, m = map(int, time_str.split(":"))
    return h * 60 + m


def minutes_to_time(mins):
    wrapped = mins % 1440

    h = str(wrapped // 60).zfill(2)
    m = str(wrapped % 60).zfill(2)

    return f"{h}:{m}"


def add_minutes(time_str, mins):
    return minutes_to_time(to_minutes(time_str) + mins)


def format_time_label(time_str):
    if not time_str:
        return ""

    h, m = map(int, time_str.split(":"))

    period = "PM" if h >= 12 else "AM"
    hour_12 = 12 if h % 12 == 0 else h % 12

    return f"{hour_12}:{m:02d} {period}"


def generate_time_slots(window_start, window_end, step=30):
    slots = []

    start = to_minutes(window_start)
    end = to_minutes(window_end)

    for t in range(start, end, step):
        slots.append(minutes_to_time(t))

    return slots


def generate_time_slots_for_date(
    project_start,
    project_end,
    selected_date,
    step=30,
):
    project_start_dt = datetime.fromisoformat(project_start)
    project_end_dt = datetime.fromisoformat(project_end)
    selected_date_dt = datetime.fromisoformat(selected_date)

    day_start = datetime.combine(
        selected_date_dt.date(),
        datetime.min.time(),
    )
    day_end = day_start + timedelta(days=1)

    visible_start = max(project_start_dt, day_start)
    visible_end = min(project_end_dt, day_end)

    slots = []

    current = visible_start

    # Round up to the next slot boundary.
    minutes = current.hour * 60 + current.minute
    remainder = minutes % step

    if remainder:
        current += timedelta(minutes=step - remainder)

    current = current.replace(second=0, microsecond=0)

    while current < visible_end:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=step)

    return slots

def ranges_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


def is_slot_available(
    activities,
    date,
    start_time,
    duration_minutes,
    project_start,
    project_end,
    exclude_activity_id=None,
):
    if not start_time:
        return False

    slot_start = datetime.fromisoformat(f"{date}T{start_time}")
    slot_end = slot_start + timedelta(minutes=duration_minutes)

    project_start_dt = datetime.fromisoformat(project_start)
    project_end_dt = datetime.fromisoformat(project_end)

    if slot_start < project_start_dt or slot_end > project_end_dt:
        return False

    for activity in activities:
        if activity["id"] == exclude_activity_id or activity["due_date"] != date:
            continue

        activity_start = datetime.fromisoformat(
            f'{activity["due_date"]}T{activity["start_time"]}'
        )
        activity_end = datetime.fromisoformat(
            f'{activity["due_date"]}T{activity["end_time"]}'
        )

        if ranges_overlap(
            slot_start,
            slot_end,
            activity_start,
            activity_end,
        ):
            return False

    return True


def get_priority(date_str, time_str):
    if not date_str:
        return "Weeks"
    target = datetime.fromisoformat(f"{date_str}T{time_str or '23:59'}:00")
    now = datetime.now()  # noqa: DTZ005
    diff = (target - now).total_seconds()
    if diff <= 0:
        return "OverDue"
    diff_mins = diff / 60
    if diff_mins <= 60:
        return "Hour"
    if target.date() == now.date():
        return "Today"
    if diff_mins <= 60 * 24:
        return "Hours"
    diff_days = diff / 86400
    if diff_days <= 7:
        return "Days"
    if diff_days <= 14:
        return "Week"
    if diff_days <= 30:
        return "Weeks"
    if diff_days <= 60:
        return "Month"
    if diff_days <= 180:
        return "Months"
    if diff_days <= 365:
        return "Year"
    return "Years"


def get_urgency_class(priority):
    if priority in ("OverDue", "Hour", "Hours", "Today"):
        return "urgency--high"
    if priority in ("Days", "Week", "Weeks"):
        return "urgency--mid"
    return "urgency--low"


def find_activities_outside_project_span(
    activities,
    project_start_date,
    project_end_date,
    project_start_time,
    project_end_time,
):
    project_start = datetime.fromisoformat(
        f"{project_start_date}T{project_start_time}"
    )
    project_end = datetime.fromisoformat(
        f"{project_end_date}T{project_end_time}"
    )

    outside = []

    for activity in activities:
        activity_start = datetime.fromisoformat(
            f'{activity["due_date"]}T{activity["start_time"]}'
        )
        activity_end = datetime.fromisoformat(
            f'{activity["due_date"]}T{activity["end_time"]}'
        )

        if activity_start < project_start or activity_end > project_end:
            outside.append(activity)

    return outside


HOUR_PX = 56          # height of one hour in the day grid
MIN_BLOCK_PX = 22     # so 15-min tasks are still clickable

PROJECT_COLORS = [
    "#6f5bff", "#e0575b", "#34a771", "#e8a33d",
    "#2f9bd6", "#d6509a", "#14a3a3", "#8d6e63",
]


def project_color(project_id):
    return PROJECT_COLORS[project_id % len(PROJECT_COLORS)]


def format_duration(mins):
    h, m = divmod(mins, 60)
    if h and m:
        return f"{h} hr {m} min"
    if h:
        return f"{h} hr"
    return f"{m} min"


def _range_label(start, end):
    return f"{format_time_label(minutes_to_time(start))} – {format_time_label(minutes_to_time(end))}"


def build_day_layout(day, projects, activities):
    """Turn a day's projects/tasks into positioned blocks for the day grid."""
    scale = HOUR_PX / 60

    bands = []
    for i, p in enumerate(projects):
        starts_today = p["start_date"] == day
        ends_today = p["end_date"] == day
        start = to_minutes(p["start_time"]) if starts_today else 0
        end = to_minutes(p["end_time"]) if ends_today else 1440

        if starts_today and ends_today:
            note = f"{format_duration(end - start)} project"
        elif starts_today:
            note = "Starts today"
        elif ends_today:
            note = "Ends today"
        else:
            note = "All day"

        bands.append(
            {
                "id": p["id"],
                "title": p["title"],
                "color": project_color(p["id"]),
                "top": round(start * scale, 1),
                "height": round((end - start) * scale, 1),
                "label": _range_label(start, end),
                "note": note,
                "index": i,
            }
        )

    tasks = []
    for a in activities:
        start = to_minutes(a["start_time"])
        end = to_minutes(a["end_time"])
        if end <= start:  # task that runs past midnight: clip to end of day
            end = 1440
        height = max((end - start) * scale, MIN_BLOCK_PX)
        tasks.append(
            {
                "id": a["id"],
                "title": a["title"],
                "project_title": a["project_title"],
                "color": project_color(a["project_id"]),
                "start": start,
                "end": end,
                "top": round(start * scale, 1),
                "height": round(height, 1),
                "short": height < 44,
                "label": _range_label(start, end),
                "duration": format_duration(end - start),
            }
        )

    # Side-by-side columns for tasks from different projects that overlap.
    tasks.sort(key=lambda t: (t["start"], t["end"]))

    def flush(cluster):
        col_ends = []
        for t in cluster:
            for ci, ce in enumerate(col_ends):
                if ce <= t["start"]:
                    t["col"] = ci
                    col_ends[ci] = t["end"]
                    break
            else:
                t["col"] = len(col_ends)
                col_ends.append(t["end"])
        for t in cluster:
            t["cols"] = len(col_ends)

    cluster, cluster_end = [], 0
    for t in tasks:
        if cluster and t["start"] >= cluster_end:
            flush(cluster)
            cluster, cluster_end = [], 0
        cluster.append(t)
        cluster_end = max(cluster_end, t["end"])
    if cluster:
        flush(cluster)

    tops = [t["top"] for t in tasks] + [b["top"] for b in bands if b["top"] > 0]
    first_px = min(tops) if tops else 8 * HOUR_PX

    return {"bands": bands, "tasks": tasks, "first_px": first_px}