CREATE TABLE IF NOT EXISTS project (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id TEXT NOT NULL,
  title TEXT NOT NULL,
  start_date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_date TEXT NOT NULL,
  end_time TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS activity (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES project(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  description TEXT,
  due_date TEXT NOT NULL,
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_activity_project ON activity(project_id);
CREATE INDEX IF NOT EXISTS idx_activity_due_date ON activity(due_date);
CREATE INDEX IF NOT EXISTS idx_project_dates ON project(start_date, end_date);
CREATE INDEX IF NOT EXISTS idx_project_owner ON project(owner_id);