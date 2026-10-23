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

/* ---------------- Toasts ---------------- */

const TOAST_ICONS = { success: "✓", error: "!", info: "i", due: "⏰" };
const TOAST_LIMIT = 5;

function toastStack() {
  let stack = document.getElementById("toast-stack");
  if (!stack) {
    stack = document.createElement("div");
    stack.id = "toast-stack";
    stack.className = "toast-stack";
    document.body.appendChild(stack);
  }
  return stack;
}

// type: "success" | "error" | "info" | "due"
// duration: ms before it dismisses itself; 0 keeps it until dismissed.
function showToast({
  title,
  body = "",
  type = "info",
  duration = 5000,
  href = null,
}) {
  const stack = toastStack();
  while (stack.children.length >= TOAST_LIMIT) {
    stack.firstElementChild.remove();
  }

  const el = document.createElement("div");
  el.className = `toast toast--${type}`;
  el.setAttribute(
    "role",
    type === "error" || type === "due" ? "alert" : "status",
  );

  const icon = document.createElement("span");
  icon.className = "toast__icon";
  icon.setAttribute("aria-hidden", "true");
  icon.textContent = TOAST_ICONS[type] || TOAST_ICONS.info;

  const text = document.createElement("span");
  text.className = "toast__text";

  const heading = document.createElement("strong");
  heading.textContent = title; // textContent: titles are user input
  text.append(heading);

  if (body) {
    const detail = document.createElement("span");
    detail.textContent = body;
    text.append(detail);
  }

  if (href) {
    const link = document.createElement("a");
    link.className = "toast__link";
    link.href = href;
    link.textContent = "View";
    text.append(link);
  }

  const close = document.createElement("button");
  close.type = "button";
  close.className = "toast__close";
  close.setAttribute("aria-label", "Dismiss");
  close.textContent = "✕";

  el.append(icon, text, close);
  stack.appendChild(el);

  let timer = null;
  let remaining = duration;
  let startedAt = 0;
  let gone = false;

  function dismiss() {
    if (gone) return;
    gone = true;
    clearTimeout(timer);
    el.classList.add("is-leaving");
    setTimeout(() => el.remove(), 220);
  }

  function resume() {
    if (gone) return;
    startedAt = Date.now();
    timer = setTimeout(dismiss, remaining);
  }

  function pause() {
    if (gone) return;
    clearTimeout(timer);
    remaining -= Date.now() - startedAt;
  }

  close.addEventListener("click", dismiss);

  if (duration > 0) {
    el.classList.add("has-progress");
    el.style.setProperty("--toast-duration", `${duration}ms`);
    el.addEventListener("mouseenter", pause); // hover holds it open
    el.addEventListener("mouseleave", resume);
    resume();
  }

  return dismiss;
}

/* ---------------- Due alerts ---------------- */

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

function dueKey(item) {
  return `${item.type}-${item.id}-${item.due_at}`;
}

function dueHref(item) {
  return item.type === "project"
    ? `/project/${item.id}`
    : `/activity/${item.id}/edit`;
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
  const fresh = due.filter((item) => {
    const key = dueKey(item);
    if (already.has(key)) return false;
    already.add(key);
    return true;
  });

  if (fresh.length > 3) {
    // e.g. coming back after a long absence: one toast instead of a pile
    showToast({
      title: `${fresh.length} items are overdue`,
      body: "Open your projects to review them.",
      type: "due",
      duration: 0,
      href: "/",
    });
  } else {
    fresh.forEach((item) =>
      showToast({
        title: item.type === "project" ? "Project overdue" : "Task overdue",
        body: item.title,
        type: "due",
        duration: 0, // stays until you dismiss it
        href: dueHref(item),
      }),
    );
  }

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

/* ---------------- Exact-time timer for the next due item ---------------- */

let dueTimer = null;

// Asks the server when the next project/task ends and sleeps until then,
// so the toast and the OverDue badge land at that moment instead of waiting
// for the next poll. Re-arms itself after every fire.
async function armDueTimer() {
  clearTimeout(dueTimer);
  try {
    const res = await fetch(
      `/api/next-due?now=${encodeURIComponent(localNow())}`,
    );
    if (!res.ok) return;
    const { next } = await res.json();
    if (!next) return;

    const delay = new Date(next) - Date.now();
    if (delay > 2147483647) return; // setTimeout caps at ~24.8 days; the 60s tick re-arms later

    clearTimeout(dueTimer); // another arm may have finished while we waited
    dueTimer = setTimeout(
      async () => {
        refreshPriorities();
        await checkDue();
        armDueTimer();
      },
      Math.max(delay, 0) + 250,
    );
  } catch (err) {
    console.error("Plan It: could not schedule due timer", err);
  }
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
  armDueTimer();
}

// The timer does the precise work; this is the safety net for sleeping
// laptops and throttled background tabs.
setInterval(tick, 60000);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) tick();
});
tick();

/* ---------------- Flask flash() messages ---------------- */

(window.PLANIT_FLASH || []).forEach(([category, message]) => {
  const type =
    category === "success" || category === "error" ? category : "info";
  showToast({
    title: message,
    type,
    duration: type === "error" ? 8000 : 4500,
  });
});

/* ---------------- Navigation + sidebar ---------------- */

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
