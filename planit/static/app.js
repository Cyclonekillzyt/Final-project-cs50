async function refreshSlots(projectId, excludeId) {
  const date = document.getElementById("due-date").value;
  const duration = document.getElementById("duration").value;

  const res = await fetch(
    `/project/${projectId}/slots?date=${date}&duration=${duration}` +
      (excludeId ? `&exclude=${excludeId}` : ""),
  );

  const slots = await res.json();
  const container = document.getElementById("time-slots");

  container.innerHTML = slots
    .map(
      (s) => `
        <button
          type="button"
          class="time-slot ${!s.available ? "is-disabled" : ""}"
          data-time="${s.time}"
          ${!s.available ? "disabled" : ""}
        >
          ${s.label}
        </button>
      `,
    )
    .join("");

  container.querySelectorAll(".time-slot").forEach((btn) => {
    btn.addEventListener("click", () => {
      container
        .querySelectorAll(".time-slot")
        .forEach((b) => b.classList.remove("is-selected"));

      btn.classList.add("is-selected");
      document.getElementById("start-time").value = btn.dataset.time;
    });
  });
}

const appEl = document.querySelector(".app");

document
  .getElementById("due-date")
  ?.addEventListener("change", () => refreshSlots(PROJECT_ID, EXCLUDE_ID));

document
  .getElementById("duration")
  ?.addEventListener("change", () => refreshSlots(PROJECT_ID, EXCLUDE_ID));

/* ---------------- In-page toasts ---------------- */

// Works everywhere, even when OS/browser notifications are blocked.
function showToast(title, body) {
  let stack = document.getElementById("toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.id = "toast-stack";
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }

  const el = document.createElement("div");
  el.className = "toast";

  const strong = document.createElement("strong");
  strong.textContent = title;
  const span = document.createElement("span");
  span.textContent = body;

  el.append(strong, span);
  el.addEventListener("click", () => el.remove());
  stack.appendChild(el);
  setTimeout(() => el.remove(), 15000);
}

/* ---------------- Due notifications ---------------- */

const NOTIFIED_KEY = "planit-notified";

// Browser-local "now" as YYYY-MM-DDTHH:MM (no timezone), matching how the
// database stores dates and times.
function localNow() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  return (
    `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}` +
    `T${pad(d.getHours())}:${pad(d.getMinutes())}`
  );
}

function loadNotified() {
  try {
    return new Set(JSON.parse(localStorage.getItem(NOTIFIED_KEY)) || []);
  } catch {
    return new Set();
  }
}

function sendNotification(title, body, tag) {
  if (!("Notification" in window) || Notification.permission !== "granted") {
    return false;
  }
  try {
    new Notification(title, { body, tag });
    return true;
  } catch (err) {
    // e.g. Chrome on Android only allows notifications via a service worker
    console.error("Plan It: notification failed", err);
    return false;
  }
}

async function checkDue() {
  let due;
  try {
    const res = await fetch(`/api/due?now=${encodeURIComponent(localNow())}`);
    if (!res.ok) return;
    due = await res.json();
  } catch (err) {
    console.error("Plan It: could not fetch due items", err);
    return;
  }

  const already = loadNotified();

  due.forEach((item) => {
    const key = `${item.type}-${item.id}-${item.due_at}`;
    if (already.has(key)) return;

    const title = item.type === "project" ? "Project due" : "Task due";
    sendNotification(title, item.title, key); // OS notification, if allowed
    showToast(title, item.title); // always visible in the page
    already.add(key);
  });

  try {
    localStorage.setItem(
      NOTIFIED_KEY,
      JSON.stringify([...already].slice(-200)),
    );
  } catch (err) {
    console.error("Plan It: could not save notified list", err);
  }
}

/* ---------------- Live priority labels + "now" line ---------------- */

// Mirrors get_priority() / get_urgency_class() in timehelpers.py
function priorityFor(dueIso, now = new Date()) {
  const target = new Date(dueIso); // "YYYY-MM-DDTHH:MM" is parsed as local time
  if (isNaN(target)) return null;

  const diff = (target - now) / 1000;
  if (diff <= 0) return "OverDue";

  const mins = diff / 60;
  if (mins <= 60) return "Hour";
  if (target.toDateString() === now.toDateString()) return "Today";
  if (mins <= 60 * 24) return "Hours";

  const days = diff / 86400;
  if (days <= 7) return "Days";
  if (days <= 14) return "Week";
  if (days <= 30) return "Weeks";
  if (days <= 60) return "Month";
  if (days <= 180) return "Months";
  if (days <= 365) return "Year";
  return "Years";
}

function urgencyFor(priority) {
  if (["OverDue", "Hour", "Hours", "Today"].includes(priority)) {
    return "urgency--high";
  }
  if (["Days", "Week", "Weeks"].includes(priority)) return "urgency--mid";
  return "urgency--low";
}

function refreshPriorities() {
  const now = new Date();
  document.querySelectorAll("[data-due]").forEach((el) => {
    const priority = priorityFor(el.dataset.due, now);
    if (!priority) return;

    el.classList.remove("urgency--high", "urgency--mid", "urgency--low");
    el.classList.add(urgencyFor(priority));

    if (el.classList.contains("priority-badge")) {
      el.textContent = priority;
    } else {
      el.title = priority; // sidebar dots only show a tooltip
    }
  });
}

function updateNowLine() {
  const grid = document.getElementById("day-grid");
  const line = document.querySelector(".day-grid__now");
  if (!grid || !line) return;

  const hourPx = parseFloat(
    getComputedStyle(grid).getPropertyValue("--hour-px"),
  );
  if (!hourPx) return;

  const d = new Date();
  line.style.top = `${((d.getHours() * 60 + d.getMinutes()) * hourPx) / 60}px`;
}

const loadedOn = new Date().toDateString();

function tick() {
  // Day view left open past midnight: reload so "today" is correct again.
  if (
    document.getElementById("day-grid") &&
    new Date().toDateString() !== loadedOn
  ) {
    location.reload();
    return;
  }
  refreshPriorities();
  updateNowLine();
  checkDue();
}

setInterval(tick, 30000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) tick();
});
tick();

/* ---------------- Bell button ---------------- */

function updateBellUI() {
  const btn = document.getElementById("bell-btn");

  if (!btn || !("Notification" in window)) return;

  const granted = Notification.permission === "granted";

  btn.classList.toggle("is-on", granted);
  btn.textContent = granted ? "🔔" : "🔕";
  btn.title = granted
    ? "Notifications are on"
    : "Turn on due-date notifications";
}

async function requestNotifications() {
  if (!window.isSecureContext || !("Notification" in window)) {
    showToast(
      "Notifications unavailable",
      "Open the app on localhost or https. Plain http on another address can't use them.",
    );
    return;
  }

  if (Notification.permission === "denied") {
    showToast(
      "Notifications are blocked",
      "Allow them for this site in the browser's site settings (padlock icon), then click the bell again.",
    );
    return;
  }

  const result = await Notification.requestPermission();
  updateBellUI();

  if (result === "granted") {
    const ok = sendNotification("Plan It", "Notifications are working", "test");
    if (!ok) {
      showToast(
        "Permission granted, but the system didn't show it",
        "Check your OS notification / Focus settings.",
      );
    }
  }
  checkDue();
}

updateBellUI();

document.querySelectorAll("[data-url]").forEach((item) => {
  item.addEventListener("click", () => {
    window.location.href = item.dataset.url;
  });
});

function setSidebar(open) {
  appEl.classList.toggle("sidebar-open", open);
  document
    .getElementById("menu-btn")
    ?.setAttribute("aria-expanded", String(open));
}

document
  .getElementById("menu-btn")
  ?.addEventListener("click", () => setSidebar(true));
document
  .getElementById("sidebar-close")
  ?.addEventListener("click", () => setSidebar(false));
document
  .getElementById("sidebar-backdrop")
  ?.addEventListener("click", () => setSidebar(false));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") setSidebar(false);
});
