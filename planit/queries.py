import os
from cs50 import SQL

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
db = SQL("sqlite:///" + os.path.join(BASE_DIR, "planit.db"))

OWN_PROJECT = "(SELECT id FROM project WHERE owner_id = ?)"


def get_projects(owner_id):
    return db.execute(
        """
        SELECT project.*,
               (SELECT COUNT(*) FROM activity WHERE activity.project_id = project.id) AS activity_count
        FROM project
        WHERE owner_id = ?
        ORDER BY start_date
        """,
        owner_id,
    )


def get_project(project_id, owner_id):
    projects = db.execute(
        "SELECT * FROM project WHERE id = ? AND owner_id = ?", project_id, owner_id
    )
    return projects[0] if projects else None


def get_activities(project_id, owner_id):
    return db.execute(
        """
        SELECT activity.* FROM activity
        JOIN project ON project.id = activity.project_id
        WHERE activity.project_id = ? AND project.owner_id = ?
        ORDER BY due_date, start_time
        """,
        project_id,
        owner_id,
    )


def create_project(title, start_date, start_time, end_date, end_time, owner_id):
    return db.execute(
        "INSERT INTO project (title, start_date, start_time, end_date, end_time, owner_id) VALUES (?,?,?,?,?,?)",
        title,
        start_date,
        start_time,
        end_date,
        end_time,
        owner_id,
    )


def update_project(
    project_id, title, start_date, start_time, end_date, end_time, owner_id
):
    db.execute(
        "UPDATE project SET title=?, start_date=?, start_time=?, end_date=?, end_time=? WHERE id=? AND owner_id=?",
        title,
        start_date,
        start_time,
        end_date,
        end_time,
        project_id,
        owner_id,
    )


def delete_project(project_id, owner_id):
    db.execute(
        "DELETE FROM project WHERE id = ? AND owner_id = ?", project_id, owner_id
    )


def create_activity(project_id, title, description, due_date, start_time, end_time):
    # Callers must have already verified the project belongs to the visitor
    # (the routes do this with own_project_or_404).
    return db.execute(
        "INSERT INTO activity (project_id, title, description, due_date, start_time, end_time) VALUES (?,?,?,?,?,?)",
        project_id,
        title,
        description,
        due_date,
        start_time,
        end_time,
    )


def update_activity(
    activity_id, title, description, due_date, start_time, end_time, owner_id
):
    db.execute(
        f"UPDATE activity SET title=?, description=?, due_date=?, start_time=?, end_time=? "
        f"WHERE id=? AND project_id IN {OWN_PROJECT}",
        title,
        description,
        due_date,
        start_time,
        end_time,
        activity_id,
        owner_id,
    )


def delete_activity(activity_id, owner_id):
    db.execute(
        f"DELETE FROM activity WHERE id = ? AND project_id IN {OWN_PROJECT}",
        activity_id,
        owner_id,
    )


def get_activity(activity_id, owner_id):
    activities = db.execute(
        f"SELECT * FROM activity WHERE id = ? AND project_id IN {OWN_PROJECT}",
        activity_id,
        owner_id,
    )
    return activities[0] if activities else None


def get_projects_overlapping(start_date, end_date, owner_id):
    """The visitor's projects whose span touches [start_date, end_date]."""
    return db.execute(
        """
        SELECT * FROM project
        WHERE start_date <= ? AND end_date >= ? AND owner_id = ?
        ORDER BY start_date, start_time
        """,
        end_date,
        start_date,
        owner_id,
    )


def get_activities_between(start_date, end_date, owner_id):
    return db.execute(
        """
        SELECT activity.*, project.title AS project_title
        FROM activity
        JOIN project ON project.id = activity.project_id
        WHERE due_date BETWEEN ? AND ? AND project.owner_id = ?
        ORDER BY due_date, start_time
        """,
        start_date,
        end_date,
        owner_id,
    )


def get_due_projects(since, now, owner_id):
    """Projects whose end fell inside (since, now]."""
    return db.execute(
        """
        SELECT id, title, (end_date || 'T' || end_time) AS due_at
        FROM project
        WHERE owner_id = ?
          AND (end_date || 'T' || end_time) <= ?
          AND (end_date || 'T' || end_time) > ?
        """,
        owner_id,
        now,
        since,
    )


def get_due_activities(since, now, owner_id):
    """Tasks whose end fell inside (since, now]."""
    return db.execute(
        """
        SELECT activity.id, activity.title,
               (activity.due_date || 'T' || activity.end_time) AS due_at
        FROM activity
        JOIN project ON project.id = activity.project_id
        WHERE project.owner_id = ?
          AND (activity.due_date || 'T' || activity.end_time) <= ?
          AND (activity.due_date || 'T' || activity.end_time) > ?
        """,
        owner_id,
        now,
        since,
    )
