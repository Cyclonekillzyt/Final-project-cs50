from datetime import datetime


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


def ranges_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and end_a > start_b


def is_slot_available(
    activities,
    date,
    start_time,
    duration_minutes,
    window_start,
    window_end,
    exclude_activity_id=None,
):
    if not start_time:
        return False

    slot_start = to_minutes(start_time)
    slot_end = slot_start + duration_minutes

    if slot_start < to_minutes(window_start) or slot_end > to_minutes(window_end):
        return False

    for activity in activities:
        if activity["id"] == exclude_activity_id or activity["due_date"] != date:
            continue

        if ranges_overlap(
            slot_start,
            slot_end,
            to_minutes(activity["start_time"]),
            to_minutes(activity["end_time"]),
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
        return "Asap"
    diff_mins = diff / 60
    if diff_mins <= 60:
        return "Hour"
    if diff_mins <= 60 * 24:
        return "Hours"
    if target.date() == now.date():
        return "Today"
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
    if priority in ("Asap", "Hour", "Hours", "Today"):
        return "urgency--high"
    if priority in ("Days", "Week", "Weeks"):
        return "urgency--mid"
    return "urgency--low"


def find_activities_outside_window(
    activities, start_date, end_date, start_time, end_time
):
    win_start, win_end = to_minutes(start_time), to_minutes(end_time)
    out = []
    for a in activities:
        if a["due_date"] < start_date or a["due_date"] > end_date:
            out.append(a)
            continue
        if (
            to_minutes(a["start_time"]) < win_start
            or to_minutes(a["end_time"]) > win_end
        ):
            out.append(a)
    return out
