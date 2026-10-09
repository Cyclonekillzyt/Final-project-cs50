import os
from cs50 import SQL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db = SQL("sqlite:///" + os.path.join(BASE_DIR, "planit.db"))


def get_projects():
    return db.execute(
        """
        SELECT project.*,
               (SELECT COUNT(*) FROM activity WHERE activity.project_id = project.id) AS activity_count
        FROM project
        ORDER BY start_date
        """
    )


def get_project(project_id):
    projects = db.execute("SELECT * FROM project WHERE id = ?", project_id)

    if not projects:
        return None

    return projects[0]


def get_activities(project_id):
    return db.execute(
        "SELECT * FROM activity WHERE project_id = ? ORDER BY due_date, start_time",
        project_id,
    )


def create_project(title, start_date, start_time, end_date, end_time):
    return db.execute(
        "INSERT INTO project (title,start_date, start_time,end_date,end_time) VALUES (?,?,?,?,?)",
        title,
        start_date,
        start_time,
        end_date,
        end_time,
    )


def update_project(project_id, title, start_date, start_time, end_date, end_time):
    db.execute(
        "UPDATE project SET title=?, start_date=?, start_time=?, end_date=?, end_time=? WHERE id=?",
        title,
        start_date,
        start_time,
        end_date,
        end_time,
        project_id,
    )


def delete_project(project_id):
    db.execute("DELETE FROM project WHERE id = ?", project_id)


def create_activity(project_id, title, description, due_date, start_time, end_time):
    return db.execute(
        "INSERT INTO activity (project_id, title, description, due_date, start_time, end_time) VALUES (?,?,?,?,?,?)",
        project_id,
        title,
        description,
        due_date,
        start_time,
        end_time,
    )


def update_activity(activity_id, title, description, due_date, start_time, end_time):
    db.execute(
        "UPDATE activity SET title=?, description=?, due_date=?, start_time=?, end_time=? WHERE id=?",
        title,
        description,
        due_date,
        start_time,
        end_time,
        activity_id,
    )


def delete_activity(activity_id):
    db.execute("DELETE FROM activity WHERE id = ?", activity_id)


def get_activity(activity_id):
    activities = db.execute("SELECT * FROM activity WHERE id = ?", activity_id)

    if not activities:
        return None

    return activities[0]


def get_projects_overlapping(start_date, end_date):
    """Projects whose span touches [start_date, end_date]."""
    return db.execute(
        """
        SELECT * FROM project
        WHERE start_date <= ? AND end_date >= ?
        ORDER BY start_date, start_time
        """,
        end_date,
        start_date,
    )


def get_activities_between(start_date, end_date):
    return db.execute(
        """
        SELECT activity.*, project.title AS project_title
        FROM activity
        JOIN project ON project.id = activity.project_id
        WHERE due_date BETWEEN ? AND ?
        ORDER BY due_date, start_time
        """,
        start_date,
        end_date,
    )
def get_due_projects(now):
    return db.execute(
        """
        SELECT id, title FROM project
        WHERE (end_date || 'T' || end_time) <= ?
        """,
        now,
    )


def get_due_activities(now):
    return db.execute(
        """
        SELECT id, title FROM activity
        WHERE (due_date || 'T' || end_time) <= ?
        """,
        now,
    )
