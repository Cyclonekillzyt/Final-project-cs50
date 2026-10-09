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

async function checkDue() {
  if (Notification.permission !== "granted") return;

  const today = new Date().toISOString().slice(0, 10);
  const key = `notified-${today}`;

  const already = new Set(JSON.parse(localStorage.getItem(key)) || []);

  const response = await fetch("/api/due");
  const due = await response.json();

  due.forEach((item) => {
    if (already.has(item.id)) return;

    new Notification("Due Today", {
      body: item.title,
    });

    already.add(item.id);
  });

  localStorage.setItem(key, JSON.stringify([...already]));
}

setInterval(checkDue, 60000);
checkDue();

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
  if (!("Notification" in window)) return;

  await Notification.requestPermission();

  updateBellUI();
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
