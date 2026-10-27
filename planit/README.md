# Plan It
#### Video Demo: https://youtu.be/KC1uz4NDdZw
#### Description:

Plan It is a web based project planner built with Flask, SQLite and plain JavaScript. The idea is simple. Every project has a continuous time span (a start date and time, and an end date and time), and every task inside that project is booked into a real time slot within that span, the same way you would book a meeting in a calendar app. You cannot put two tasks on top of each other, you cannot put a task outside its project, and you can see all of it in a list view or in a calendar that works like the Google and Apple calendars, with a month overview and a day view where tasks sit at their exact times in colored blocks.

There are no accounts and no sign in. Every browser gets its own anonymous identity, so you open the site and start planning, and nobody else can see or touch your projects.

## What you can do

1. Create, edit and delete projects with a start and end date and time.
2. Add tasks to a project by picking a date, a duration (15 minutes up to 2 hours) and a free 30 minute slot from a time picker. Slots that are already taken or outside the project are disabled.
3. See every task with a live priority label (OverDue, Hour, Today, Hours, Days, Week, Weeks, Month, Months, Year, Years) that is colored red, amber or green depending on how urgent it is.
4. Switch to the calendar view, see which days have projects and tasks as colored dots (one color per project), click a day and get a full 24 hour day view with project spans as tinted bands and tasks as blocks placed at their exact times. Click any block to jump to that task or project.
5. Get an in app toast when a task or project becomes overdue, at the exact minute it happens, without refreshing the page.
6. Use the whole thing on a phone. On small screens the sidebar turns into a hamburger menu drawer.

## How to run it

FROM THE PROJECT FOLDER:

1. `python -m venv venv` then activate it (`source venv/bin/activate`)
2. `pip install -r requirements.txt`
3. `sqlite3 planit.db < schema.sql` (this creates the database, the `cs50` SQL library expects the file to already exist)
4. `flask run`

Open the address Flask prints. Optionally set `SECRET_KEY` as an environment variable. If you do not, the app generates a random one the first time it starts and saves it to `instance/secret_key`.

## The files

### app.py
The Flask application and every route. It has the project routes (list, new, edit, delete), the task routes (new, edit, delete), the calendar routes (month view and day view) and three JSON endpoints: `/project/<id>/slots` for the time slot picker, `/api/due` for tasks that just became overdue and `/api/next-due` for the time of the next thing that will become overdue. It also holds the identity logic. A `before_request` function gives every visitor a random id stored in a signed session cookie, and two helpers, `own_project_or_404` and `own_activity_or_404`, are used on every route that touches data so you can only reach things you own.

### queries.py
Every SQL statement in the project lives here, so `app.py` never contains raw SQL. It uses the `cs50` SQL library. Every query takes an `owner_id` and filters by it. Tasks do not have an owner column of their own, they belong to a project, so task queries check ownership with a subquery (`OWN_PROJECT`) that only returns the visitor's project ids.

### timehelpers.py
All the time logic, kept separate from Flask so it can be tested on its own. It converts between `HH:MM` strings and minutes, generates the 30 minute slots for a date, checks whether a slot is free (inside the project, not overlapping another task), works out the priority label and urgency class for a due date, finds tasks that would be stranded if a project span is shrunk, and builds the layout for the day view. `build_day_layout` turns a day's projects and tasks into pixel positions, and handles tasks that overlap by sorting them into clusters and giving each task a column inside its cluster so they sit side by side.

### schema.sql
Two tables, `project` (with an `owner_id`, a title and a start and end date and time) and `activity` (the tasks, linked to a project with `ON DELETE CASCADE` so deleting a project deletes its tasks), plus indexes on the columns the app searches by most (owner, project, due date).

### templates/
`base.html` is the page shell. It includes the sidebar and header, loads the script, and passes Flask flash messages to JavaScript as JSON. `sidebar.html` lists the projects and turns into a drawer on mobile. `header.html` is the top bar with the List and Calendar toggle. `index.html` and `body.html` are the list view and its task cards. `project_form.html` and `activity_form.html` are the forms (the task form renders the slot picker). `calendar.html` is the month view and `calendar_day.html` is the day view.

### static/app.js
All the client side behavior. It refreshes the time slots when you change the date or duration, runs the toast system, checks for due items, updates the priority labels and the red "now" line in the day view every minute without a page refresh, sets an exact time timer for the next thing that is due, and handles the mobile sidebar drawer.

### static/style.css
All styling, including the color variables, the calendar and day grid, the toasts and their animations (with a reduced motion fallback), and the responsive rules for small screens.

### test_app.py and test_isolation.py
The pytest suites. `test_app.py` covers page rendering, project and task create, edit and delete, the slots endpoint, both calendar views, the day layout functions and the due endpoint. `test_isolation.py` uses two separate browser clients and checks that one can never see, edit or delete the other's projects and tasks.

### requirements.txt and .gitignore
The dependencies (Flask and cs50) and the files that should never be committed (the database, virtual environments, caches).

## Design choices and why

THE TIME SLOT PICKER AND VALIDATION. The slot picker only stops you from clicking a bad slot, it does not actually protect the data. A user could send any form data they like. So the same checks (is the task inside the project, does it overlap another task) run again on the server in `_save_activity`, and shrinking a project is rejected if it would leave tasks outside the new span. The browser is for convenience, the server is the one that decides.

DATES AS TEXT. Dates and times are stored as ISO strings (`2025-01-02` and `10:00`). SQLite has no real date type anyway, and in this format comparing strings gives the same result as comparing dates. That makes queries like "which projects touch this month" and "what ended in the last 24 hours" simple, and it means no timezone is ever stored.

NO TIMEZONES, SO THE BROWSER SENDS ITS OWN CLOCK. Since nothing is stored with a timezone, a server in another timezone would think things are overdue at the wrong time. So the browser sends its own local "now" to `/api/due` and `/api/next-due`, and the server just compares strings.

ANONYMOUS SESSIONS INSTEAD OF ACCOUNTS. The first version had one shared database, so everybody saw everybody's tasks. Real accounts felt like too much for a planner, so each browser gets a random id in a signed cookie that lasts two years, and everything is scoped to it. If you open another person's project URL you get a 404 and not a 403, so the app does not even confirm that the project exists. The tradeoff is that clearing your cookies means losing access to your data.

TOASTS INSTEAD OF BROWSER NOTIFICATIONS. I started with browser notifications and in my testing they never showed up reliably when something became overdue. In app toasts live inside the page, so there is no permission prompt and nothing for the browser or the operating system to block. Overdue toasts stay until dismissed, normal ones dismiss themselves with a progress bar and pause when hovered, and if you come back after a long time and ten things are overdue you get one summary toast and not a pile of ten. Titles are inserted with `textContent` because they are user input. Flask `flash()` messages go through the same system, so there is one look for every message. Already shown alerts are remembered in `localStorage` so a refresh does not repeat them.

EXACT TIME TIMER PLUS A SAFETY NET. Polling once a minute means an overdue toast can be up to a minute late. So the page asks the server when the next thing is due and sleeps until that exact moment. A 60 second tick is still there as a backup for sleeping laptops and background tabs that browsers slow down.

PRIORITY LOGIC LIVES IN TWO PLACES. `get_priority` in Python draws the first page, and `priorityFor` in JavaScript keeps the labels fresh without a reload. They are written to match each other on purpose, and the comment in `app.js` says so.

DAY VIEW IS BUILT FROM PURE FUNCTIONS. The hard part of a calendar day view is positioning, not drawing. Keeping `build_day_layout` as a plain function that takes data and returns positions made it easy to test (tasks starting at the same time, back to back tasks, tasks near midnight, multi day projects clipped to a single day).

## Testing

Run `pytest test_app.py test_isolation.py -v`. Note that the tests use the real `planit.db`, because the app has no separate test database. Each test creates uniquely named data and cleans up after itself.

## Known limitations

1. A task that runs past midnight is stored with an end time that wraps around, and the day view clips it to the end of that day.
2. Clearing browser cookies loses access to your data, because there are no accounts.
3. Forms do not have CSRF tokens. For an anonymous planner with no sensitive data this was an accepted tradeoff, but it would be the first thing to add before any real deployment.
4. Tasks cannot be marked as done, and there are no recurring tasks.

## How AI was used

AI was used heavily in this project and I want to be clear about that. I used Claude  (Anthropic's AI) to write and modify some of the code in this project, and I used it for most of it. Every python file in the project has a comment at the top saying so. In short, Claude was used for modifying the calendar system to look and behave like advanced calenders you would find on your phones (giving us month view and the day view), the toast system and the switch from browser notifications to in app toasts, modifying the timing on the live priority labels so they work us intended and the "now" line on the calender, the exact time due timer, the per browser session isolation, the mobile sidebar drawer and the test suites, along with some bug identification and fixes across the rest of the app.

This README was first drafted by Claude  (Anthropic's AI), then reviewed and adjusted by me to suit the needs of this project.

I decided what got built, modified, I tested the app in the browser myself, and I fixed bugs i could and reported the bugs i could not fix and got fixes along the way (for example, due notifications not appearing, and priority labels only updating after a refresh), but some of the code itself was written and modified by AI and this README says so honestly.
