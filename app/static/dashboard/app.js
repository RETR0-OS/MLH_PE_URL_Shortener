/**
 * app.js — main dashboard logic
 * ES Module. Imported by index.html as type="module".
 */
import { api, ApiError } from "./api.js";

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function escHtml(str) {
  if (str == null) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function relativeTime(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 5) return "just now";
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function formatDate(ts) {
  if (!ts) return "—";
  try {
    return new Date(ts).toISOString().slice(0, 19).replace("T", " ");
  } catch {
    return ts;
  }
}

function syntaxHighlightJson(obj) {
  const str =
    typeof obj === "string"
      ? obj
      : JSON.stringify(obj, null, 2);
  return escHtml(str)
    .replace(
      /("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+-]?\d+)?)/g,
      (match) => {
        let cls = "json-num";
        if (/^"/.test(match)) {
          cls = /:$/.test(match) ? "json-key" : "json-str";
        } else if (/true|false/.test(match)) {
          cls = "json-bool";
        } else if (/null/.test(match)) {
          cls = "json-null";
        }
        return `<span class="${cls}">${match}</span>`;
      }
    );
}

function showToast(message, type = "info") {
  const container = document.getElementById("toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.setAttribute("role", "status");
  toast.setAttribute("aria-live", "polite");
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("toast-visible"));
  setTimeout(() => {
    toast.classList.remove("toast-visible");
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const state = {
  users: [],
  urls: [],
  events: [],
  activeUserId: null,
  dashboardStartTime: Date.now(),
  lastHealthCheck: null,
  urlFilter: { userId: "", isActive: null },
  userSort: { col: "id", dir: "asc" },
  urlSort: { col: "id", dir: "asc" },
  eventsNewCount: 0,
  eventsPaused: false,
  eventsScrolledDown: false,
  lastSeenEventId: null,
};

// ---------------------------------------------------------------------------
// API Key persistence
// ---------------------------------------------------------------------------
const apiKeyInput = document.getElementById("api-key-input");
if (apiKeyInput) {
  apiKeyInput.value = localStorage.getItem("x-api-key") || "";
  apiKeyInput.addEventListener("blur", () => {
    const v = apiKeyInput.value.trim();
    if (v) {
      localStorage.setItem("x-api-key", v);
    } else {
      localStorage.removeItem("x-api-key");
    }
  });
}

// ---------------------------------------------------------------------------
// Health polling
// ---------------------------------------------------------------------------
async function checkHealth() {
  let healthOk = false;
  let readyOk = false;
  try {
    const h = await api.get("/health");
    healthOk = h?.status === "ok" || h?.status === "healthy";
  } catch {}
  try {
    await api.get("/health/ready");
    readyOk = true;
  } catch {}

  state.lastHealthCheck = Date.now();
  const pill = document.getElementById("health-pill");
  if (!pill) return;

  pill.className = "health-pill";
  if (healthOk && readyOk) {
    pill.classList.add("health-ok");
    pill.textContent = "Operational";
  } else if (healthOk) {
    pill.classList.add("health-degraded");
    pill.textContent = "Degraded";
  } else {
    pill.classList.add("health-down");
    pill.textContent = "Down";
  }
}

// ---------------------------------------------------------------------------
// Stats
// ---------------------------------------------------------------------------
async function refreshStats() {
  try {
    state.users = await api.get("/users?per_page=500") || [];
  } catch {}
  try {
    state.urls = await api.get("/urls?per_page=500") || [];
  } catch {}
  try {
    const evts = await api.get("/events?per_page=500") || [];
    // Backend orders events ASC by id; we want newest first.
    state.events = [...evts].sort((a, b) => (b.id ?? 0) - (a.id ?? 0));
  } catch {}

  const usersEl = document.getElementById("stat-users");
  const urlsEl = document.getElementById("stat-urls");
  const eventsEl = document.getElementById("stat-events");
  const uptimeEl = document.getElementById("stat-uptime");

  if (usersEl) usersEl.textContent = state.users.length;
  if (urlsEl) urlsEl.textContent = state.urls.length;
  if (eventsEl) {
    eventsEl.textContent =
      state.events.length >= 500
        ? "500+"
        : String(state.events.length);
  }
  if (uptimeEl) {
    const secs = Math.floor((Date.now() - state.dashboardStartTime) / 1000);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    const lastTs = state.lastHealthCheck
      ? relativeTime(state.lastHealthCheck)
      : "—";
    uptimeEl.innerHTML = `${m}m ${s}s<br><small>checked ${lastTs}</small>`;
  }

  renderUsersTable();
  renderUrlsTable();
  populateUserDropdown();
}

// ---------------------------------------------------------------------------
// Users panel
// ---------------------------------------------------------------------------
function renderUsersTable() {
  const tbody = document.getElementById("users-tbody");
  if (!tbody) return;

  let rows = [...state.users];
  const { col, dir } = state.userSort;
  rows.sort((a, b) => {
    const av = a[col] ?? "";
    const bv = b[col] ?? "";
    return dir === "asc"
      ? av > bv ? 1 : av < bv ? -1 : 0
      : av < bv ? 1 : av > bv ? -1 : 0;
  });

  tbody.innerHTML = rows.map((u) => `
    <tr class="table-row ${state.activeUserId === u.id ? "row-active" : ""}"
        data-user-id="${escHtml(String(u.id))}"
        tabindex="0"
        role="row"
        aria-selected="${state.activeUserId === u.id}">
      <td class="mono">${escHtml(String(u.id))}</td>
      <td>${escHtml(u.username)}</td>
      <td>${escHtml(u.email)}</td>
      <td>${formatDate(u.created_at)}</td>
    </tr>`).join("");

  tbody.querySelectorAll("tr[data-user-id]").forEach((row) => {
    const handler = () => setActiveUser(Number(row.dataset.userId));
    row.addEventListener("click", handler);
    row.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") handler(); });
  });

  // Update sort indicators
  document.querySelectorAll("#users-table th[data-col]").forEach((th) => {
    th.setAttribute("aria-sort", th.dataset.col === col ? (dir === "asc" ? "ascending" : "descending") : "none");
    th.querySelector(".sort-icon").textContent =
      th.dataset.col === col ? (dir === "asc" ? " ▲" : " ▼") : " ⬍";
  });
}

function setActiveUser(userId) {
  state.activeUserId = state.activeUserId === userId ? null : userId;
  const user = state.users.find((u) => u.id === state.activeUserId);
  const chip = document.getElementById("active-user-chip");
  const userIdInput = document.getElementById("url-user-id");
  if (chip) {
    if (user) {
      chip.textContent = `Filtered by: ${user.username}`;
      chip.style.display = "inline-block";
    } else {
      chip.style.display = "none";
    }
  }
  if (userIdInput && user) {
    userIdInput.value = String(user.id);
    state.urlFilter.userId = String(user.id);
    const dropdown = document.getElementById("url-filter-user");
    if (dropdown) dropdown.value = String(user.id);
  } else if (!user) {
    state.urlFilter.userId = "";
    const dropdown = document.getElementById("url-filter-user");
    if (dropdown) dropdown.value = "";
  }
  renderUsersTable();
  renderUrlsTable();
}

document.getElementById("create-user-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const username = form.querySelector('[name="username"]').value.trim();
  const email = form.querySelector('[name="email"]').value.trim();
  if (!username || !email) return;
  try {
    await api.post("/users", { username, email });
    form.reset();
    showToast("User created.", "success");
    await refreshStats();
  } catch (err) {
    showToast(err.message, "error");
  }
});

document.querySelectorAll("#users-table th[data-col]").forEach((th) => {
  th.addEventListener("click", () => {
    const col = th.dataset.col;
    if (state.userSort.col === col) {
      state.userSort.dir = state.userSort.dir === "asc" ? "desc" : "asc";
    } else {
      state.userSort.col = col;
      state.userSort.dir = "asc";
    }
    renderUsersTable();
  });
});

// ---------------------------------------------------------------------------
// URLs panel
// ---------------------------------------------------------------------------
function renderUrlsTable() {
  const tbody = document.getElementById("urls-tbody");
  if (!tbody) return;

  let rows = [...state.urls];
  if (state.urlFilter.userId) {
    rows = rows.filter((u) => String(u.user_id) === String(state.urlFilter.userId));
  }
  if (state.urlFilter.isActive !== null) {
    rows = rows.filter((u) => u.is_active === state.urlFilter.isActive);
  }

  const { col, dir } = state.urlSort;
  rows.sort((a, b) => {
    const av = a[col] ?? "";
    const bv = b[col] ?? "";
    return dir === "asc"
      ? av > bv ? 1 : av < bv ? -1 : 0
      : av < bv ? 1 : av > bv ? -1 : 0;
  });

  if (rows.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="empty-row">No URLs found.</td></tr>`;
    return;
  }

  tbody.innerHTML = rows.map((u) => {
    // Redirect endpoint lives at /urls/<short_code>/redirect (see app/routes/urls.py).
    const shortUrl = `${window.location.origin}/urls/${escHtml(u.short_code)}/redirect`;
    const truncated =
      u.original_url?.length > 45
        ? escHtml(u.original_url.slice(0, 45)) + "…"
        : escHtml(u.original_url || "");
    return `
    <tr class="table-row" id="url-row-${u.id}">
      <td>
        <span class="mono code-chip">${escHtml(u.short_code)}</span>
        <button class="icon-btn copy-btn"
          data-copy="${shortUrl}"
          title="Copy shortened URL (Demo: redirect handler separate)"
          aria-label="Copy shortened URL for ${escHtml(u.short_code)}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
          </svg>
        </button>
      </td>
      <td>
        <span class="url-truncated" title="${escHtml(u.original_url)}">${truncated}</span>
      </td>
      <td>${escHtml(u.title || "—")}</td>
      <td>
        <button class="toggle-btn ${u.is_active ? "toggle-on" : "toggle-off"}"
          data-url-id="${u.id}"
          data-active="${u.is_active}"
          aria-label="${u.is_active ? "Deactivate" : "Activate"} URL ${escHtml(u.short_code)}"
          title="${u.is_active ? "Active — click to deactivate" : "Inactive — click to activate"}">
          ${u.is_active ? "Active" : "Inactive"}
        </button>
      </td>
      <td>${formatDate(u.created_at)}</td>
      <td>
        <button class="icon-btn delete-btn" data-url-id="${u.id}" aria-label="Delete URL ${escHtml(u.short_code)}">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        </button>
      </td>
    </tr>`;
  }).join("");

  // Copy buttons
  tbody.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      navigator.clipboard.writeText(btn.dataset.copy).then(() => {
        showToast("Copied to clipboard.", "info");
      }).catch(() => {
        showToast("Clipboard access denied.", "error");
      });
    });
  });

  // Toggle active
  tbody.querySelectorAll(".toggle-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.urlId;
      const current = btn.dataset.active === "true";
      try {
        await api.put(`/urls/${id}`, { is_active: !current });
        showToast(`URL ${current ? "deactivated" : "activated"}.`, "success");
        await refreshStats();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });

  // Delete buttons
  tbody.querySelectorAll(".delete-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.dataset.urlId;
      try {
        await api.del(`/urls/${id}`);
        showToast("URL deleted.", "success");
        await refreshStats();
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  });

  // Sort indicators
  document.querySelectorAll("#urls-table th[data-col]").forEach((th) => {
    th.setAttribute("aria-sort", th.dataset.col === col ? (dir === "asc" ? "ascending" : "descending") : "none");
    const icon = th.querySelector(".sort-icon");
    if (icon) icon.textContent = th.dataset.col === col ? (dir === "asc" ? " ▲" : " ▼") : " ⬍";
  });
}

document.getElementById("create-url-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const user_id = Number(form.querySelector('[name="user_id"]').value.trim());
  const original_url = form.querySelector('[name="original_url"]').value.trim();
  const title = form.querySelector('[name="title"]').value.trim();
  if (!user_id || !original_url) {
    showToast("User ID and URL are required.", "error");
    return;
  }
  // `title` is required by the API (see app/utils/validation.py:59).
  // Send an empty string when the user leaves it blank.
  const body = { user_id, original_url, title: title || "" };
  try {
    const created = await api.post("/urls", body);
    form.reset();
    if (state.activeUserId) {
      form.querySelector('[name="user_id"]').value = String(state.activeUserId);
    }
    showToast("URL created.", "success");
    await refreshStats();
    // Flash new row
    if (created?.id) {
      const row = document.getElementById(`url-row-${created.id}`);
      if (row) {
        row.classList.add("row-flash");
        setTimeout(() => row.classList.remove("row-flash"), 1500);
      }
    }
  } catch (err) {
    showToast(err.message, "error");
  }
});

// URL filter controls
document.getElementById("url-filter-user")?.addEventListener("change", (e) => {
  state.urlFilter.userId = e.target.value;
  renderUrlsTable();
});

document.getElementById("url-filter-active")?.addEventListener("change", (e) => {
  if (e.target.value === "") state.urlFilter.isActive = null;
  else state.urlFilter.isActive = e.target.value === "true";
  renderUrlsTable();
});

document.querySelectorAll("#urls-table th[data-col]").forEach((th) => {
  th.addEventListener("click", () => {
    const col = th.dataset.col;
    if (state.urlSort.col === col) {
      state.urlSort.dir = state.urlSort.dir === "asc" ? "desc" : "asc";
    } else {
      state.urlSort.col = col;
      state.urlSort.dir = "asc";
    }
    renderUrlsTable();
  });
});

function populateUserDropdown() {
  const sel = document.getElementById("url-filter-user");
  if (!sel) return;
  const current = sel.value;
  sel.innerHTML = `<option value="">All users</option>` +
    state.users.map((u) => `<option value="${u.id}" ${current === String(u.id) ? "selected" : ""}>${escHtml(u.username)} (#${u.id})</option>`).join("");
}

// ---------------------------------------------------------------------------
// Events panel
// ---------------------------------------------------------------------------
// Backend writes these event_type values (see app/routes/urls.py log_event calls):
//   "created" — URL created
//   "updated" — URL updated
//   "redirect" — short code resolved
// User-create and URL-delete currently don't emit events.
const EVENT_TYPE_CLASS = {
  created: "evt-cyan",
  updated: "evt-blue",
  redirect: "evt-green",
  deleted: "evt-amber",
  user_created: "evt-green",
  error: "evt-red",
};

function eventTypeClass(t) {
  return EVENT_TYPE_CLASS[t] || "evt-gray";
}

async function pollEvents() {
  if (state.eventsPaused) return;
  try {
    const raw = await api.get("/events?per_page=500") || [];
    if (!raw.length) {
      renderEvents([]);
      return;
    }
    // Backend returns ASC by id — reverse so newest is first.
    const events = [...raw].sort((a, b) => (b.id ?? 0) - (a.id ?? 0));

    const newestId = events[0]?.id ?? null;
    const newEvents = state.lastSeenEventId != null
      ? events.filter((e) => e.id > state.lastSeenEventId)
      : [];

    if (newEvents.length > 0 && state.eventsScrolledDown) {
      state.eventsNewCount += newEvents.length;
      const badge = document.getElementById("events-new-badge");
      if (badge) {
        badge.textContent = `+${state.eventsNewCount} new`;
        badge.style.display = "inline-block";
      }
    }

    state.lastSeenEventId = newestId;
    renderEvents(events.slice(0, 100));
  } catch {}
}

function renderEvents(events) {
  const list = document.getElementById("events-list");
  if (!list) return;
  if (!events.length) {
    list.innerHTML = `<div class="empty-row">No events yet.</div>`;
    return;
  }

  list.innerHTML = events.map((ev) => {
    const cls = eventTypeClass(ev.event_type);
    const detailStr = ev.details
      ? typeof ev.details === "object"
        ? JSON.stringify(ev.details)
        : String(ev.details)
      : "";
    const truncDetail = detailStr.length > 60 ? detailStr.slice(0, 60) + "…" : detailStr;
    return `
    <div class="event-item" data-event-id="${ev.id}">
      <span class="event-time">${relativeTime(ev.timestamp || ev.created_at)}</span>
      <span class="event-type-pill ${cls}">${escHtml(ev.event_type || "unknown")}</span>
      <span class="event-detail" title="${escHtml(detailStr)}">${escHtml(truncDetail)}</span>
      ${detailStr.length > 60 ? `<button class="expand-btn" aria-label="Expand event details" data-full="${escHtml(detailStr)}">expand</button>` : ""}
    </div>`;
  }).join("");

  list.querySelectorAll(".expand-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const full = btn.getAttribute("data-full");
      const item = btn.closest(".event-item");
      if (!item) return;
      const existing = item.querySelector(".event-expanded");
      if (existing) {
        existing.remove();
        btn.textContent = "expand";
      } else {
        let parsed;
        try { parsed = JSON.parse(full); } catch { parsed = full; }
        const pre = document.createElement("pre");
        pre.className = "event-expanded";
        pre.innerHTML = syntaxHighlightJson(parsed);
        item.appendChild(pre);
        btn.textContent = "collapse";
      }
    });
  });

  if (!state.eventsScrolledDown) {
    list.scrollTop = 0;
  }
}

// Events scroll tracking
document.getElementById("events-list")?.addEventListener("scroll", function () {
  const atBottom = this.scrollHeight - this.scrollTop - this.clientHeight < 40;
  state.eventsScrolledDown = !atBottom;
  if (atBottom) {
    state.eventsNewCount = 0;
    const badge = document.getElementById("events-new-badge");
    if (badge) badge.style.display = "none";
  }
});

document.getElementById("events-new-badge")?.addEventListener("click", () => {
  const list = document.getElementById("events-list");
  if (list) list.scrollTop = 0;
  state.eventsScrolledDown = false;
  state.eventsNewCount = 0;
  const badge = document.getElementById("events-new-badge");
  if (badge) badge.style.display = "none";
});

document.getElementById("pause-events-btn")?.addEventListener("click", () => {
  state.eventsPaused = !state.eventsPaused;
  const btn = document.getElementById("pause-events-btn");
  btn.textContent = state.eventsPaused ? "Resume" : "Pause";
  btn.classList.toggle("btn-paused", state.eventsPaused);
});

// ---------------------------------------------------------------------------
// API Tester
// ---------------------------------------------------------------------------
const testerHeader = document.getElementById("tester-header");
const testerBody = document.getElementById("tester-body");

testerHeader?.addEventListener("click", () => {
  const expanded = testerBody.style.display !== "none";
  testerBody.style.display = expanded ? "none" : "block";
  testerHeader.setAttribute("aria-expanded", String(!expanded));
  testerHeader.querySelector(".tester-toggle").textContent = expanded ? "▼" : "▲";
});

const methodSelect = document.getElementById("tester-method");
const bodyWrapper = document.getElementById("tester-body-wrapper");

methodSelect?.addEventListener("change", () => {
  const m = methodSelect.value;
  if (bodyWrapper) {
    bodyWrapper.style.display = ["POST", "PUT"].includes(m) ? "block" : "none";
  }
});

async function runApiTest() {
  const method = methodSelect?.value || "GET";
  const path = document.getElementById("tester-path")?.value.trim() || "/health";
  const bodyText = document.getElementById("tester-body-input")?.value.trim() || "";
  let body;
  if (["POST", "PUT"].includes(method) && bodyText) {
    try { body = JSON.parse(bodyText); } catch {
      showToast("Invalid JSON in request body.", "error");
      return;
    }
  }

  const responseSection = document.getElementById("tester-response");
  responseSection.innerHTML = `<span class="muted">Sending...</span>`;

  try {
    const result = await api.raw(method, path, body);
    const statusClass = result.status < 300 ? "status-ok" : result.status < 500 ? "status-warn" : "status-err";
    const headersArr = [];
    result.headers.forEach((v, k) => headersArr.push(`${k}: ${v}`));

    responseSection.innerHTML = `
      <div class="response-meta">
        <span class="status-pill ${statusClass}">${result.status} ${result.statusText}</span>
        <span class="response-time">${result.duration}ms</span>
        <button class="link-btn" id="toggle-headers">Headers</button>
      </div>
      <div id="response-headers" style="display:none" class="response-headers">
        <pre>${escHtml(headersArr.join("\n"))}</pre>
      </div>
      <pre class="response-body">${syntaxHighlightJson(result.data)}</pre>`;

    document.getElementById("toggle-headers")?.addEventListener("click", () => {
      const h = document.getElementById("response-headers");
      h.style.display = h.style.display === "none" ? "block" : "none";
    });
  } catch (err) {
    responseSection.innerHTML = `<span class="toast-error">${escHtml(err.message)}</span>`;
  }
}

document.getElementById("tester-send-btn")?.addEventListener("click", runApiTest);

document.getElementById("tester-path")?.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") runApiTest();
});

document.getElementById("tester-body-input")?.addEventListener("keydown", (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key === "Enter") runApiTest();
});

// ---------------------------------------------------------------------------
// Refresh all button
// ---------------------------------------------------------------------------
document.getElementById("refresh-all-btn")?.addEventListener("click", async () => {
  await Promise.all([checkHealth(), refreshStats(), pollEvents()]);
  showToast("Refreshed.", "info");
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
async function init() {
  await checkHealth();
  await refreshStats();
  await pollEvents();
}

init();

// Polling intervals
setInterval(checkHealth, 5000);
setInterval(refreshStats, 5000);
setInterval(pollEvents, 3000);

// Uptime counter updates every second
setInterval(() => {
  const uptimeEl = document.getElementById("stat-uptime");
  if (!uptimeEl) return;
  const secs = Math.floor((Date.now() - state.dashboardStartTime) / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  const lastTs = state.lastHealthCheck ? relativeTime(state.lastHealthCheck) : "—";
  uptimeEl.innerHTML = `${m}m ${String(s).padStart(2, "0")}s<br><small>checked ${lastTs}</small>`;
}, 1000);
