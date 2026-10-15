const pageSize = 25;
let page = 0;
let tickets = [];
let currentFilters = {};

const listElement = document.querySelector("#ticket-list");
const messageElement = document.querySelector("#ticket-message");

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function statusBadge(status) {
  const styles = {
    new: "bg-amber-100 text-amber-900",
    in_progress: "bg-blue-100 text-blue-900",
    done: "bg-emerald-100 text-emerald-900",
    rejected: "bg-rose-100 text-rose-900",
  };
  const labels = {
    new: "New",
    in_progress: "In progress",
    done: "Done",
    rejected: "Rejected",
  };
  return `<span class="inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${styles[status] ?? "bg-slate-100 text-slate-700"}">${labels[status] ?? escapeHtml(status)}</span>`;
}

function urgencyBadge(urgency) {
  const normalized = urgency.toLowerCase();
  const styles = normalized === "high"
    ? "bg-rose-50 text-rose-700"
    : normalized === "medium"
      ? "bg-orange-50 text-orange-700"
      : "bg-slate-100 text-slate-600";
  return `<span class="font-bold ${styles} rounded-md px-2 py-1 text-xs">${escapeHtml(urgency)}</span>`;
}

function formatDate(value) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(parsed);
}

function renderTickets() {
  document.querySelector("#stat-total").textContent = String(tickets.length);
  document.querySelector("#stat-new").textContent = String(tickets.filter((ticket) => ticket.status === "new").length);
  document.querySelector("#stat-progress").textContent = String(tickets.filter((ticket) => ticket.status === "in_progress").length);
  document.querySelector("#stat-done").textContent = String(tickets.filter((ticket) => ticket.status === "done").length);
  document.querySelector("#page-label").textContent = `Page ${page + 1}`;
  document.querySelector("#previous-page").disabled = page === 0;
  document.querySelector("#next-page").disabled = tickets.length < pageSize;

  if (tickets.length === 0) {
    listElement.innerHTML = '<tr><td colspan="6" class="px-5 py-14 text-center"><span class="mx-auto grid size-11 place-items-center rounded-full bg-slate-100 text-xl text-slate-400">▦</span><p class="mt-3 font-semibold text-slate-700">No tickets found</p><p class="mt-1 text-xs text-slate-500">Try another date range or create a new ticket.</p></td></tr>';
    return;
  }

  listElement.innerHTML = tickets.map((ticket) => `
    <tr class="transition hover:bg-slate-50/80">
      <td class="max-w-[280px] px-5 py-4">
        <div class="font-bold text-slate-900">#${ticket.id} · ${escapeHtml(ticket.issue_summary)}</div>
        <div class="mt-1 line-clamp-1 text-xs text-slate-500">${escapeHtml(ticket.action_required)}</div>
      </td>
      <td class="px-4 py-4"><span class="font-semibold">${escapeHtml(ticket.customer_id)}</span><div class="mt-1 text-[11px] text-slate-500">${escapeHtml(ticket.database_status.replaceAll("_", " ").toLowerCase())}</div></td>
      <td class="px-4 py-4">${urgencyBadge(ticket.urgency)}</td>
      <td class="px-4 py-4">${statusBadge(ticket.status)}</td>
      <td class="whitespace-nowrap px-4 py-4 text-xs text-slate-600">${formatDate(ticket.processed_at)}</td>
      <td class="px-5 py-4 text-right">
        <label class="sr-only" for="status-${ticket.id}">Update status for ticket ${ticket.id}</label>
        <select id="status-${ticket.id}" data-ticket-id="${ticket.id}" class="max-w-32 rounded-lg border border-slate-300 bg-white px-2 py-2 text-xs font-semibold outline-none focus:border-indigo-500 focus:ring-4 focus:ring-indigo-100" aria-label="Update ticket ${ticket.id} status">
          <option value="" disabled selected>Update status</option>
          <option value="in_progress">In progress</option>
          <option value="done">Done</option>
          <option value="rejected">Rejected</option>
        </select>
      </td>
    </tr>`).join("");
}

async function loadTickets() {
  const params = new URLSearchParams({ limit: String(pageSize), offset: String(page * pageSize) });
  for (const [key, value] of Object.entries(currentFilters)) {
    if (value) params.set(key, value);
  }
  listElement.innerHTML = '<tr><td colspan="6" class="px-5 py-12 text-center text-slate-500">Loading tickets…</td></tr>';
  setMessage("");
  try {
    const response = await fetch(`/api/tickets?${params.toString()}`);
    if (!response.ok) throw new Error(`Could not load tickets (${response.status})`);
    tickets = await response.json();
    renderTickets();
    document.querySelector("#last-updated").textContent = `Updated ${new Intl.DateTimeFormat(undefined, { timeStyle: "short" }).format(new Date())}`;
    document.querySelector("#filter-caption").textContent = currentFilters.date_from || currentFilters.date_to
      ? `Filtered ${currentFilters.date_from || "…"} to ${currentFilters.date_to || "…"}`
      : "Showing the latest tickets";
  } catch (error) {
    listElement.innerHTML = '<tr><td colspan="6" class="px-5 py-12 text-center text-rose-700">Unable to load tickets. Check that the API and database are available.</td></tr>';
    setMessage(error.message, true);
  }
}

function setMessage(message, isError = false) {
  messageElement.textContent = message;
  messageElement.classList.toggle("hidden", !message);
  messageElement.classList.toggle("bg-rose-50", isError);
  messageElement.classList.toggle("text-rose-800", isError);
  messageElement.classList.toggle("bg-emerald-50", !isError && Boolean(message));
  messageElement.classList.toggle("text-emerald-800", !isError && Boolean(message));
}

document.querySelector("#refresh-button").addEventListener("click", () => loadTickets());
document.querySelector("#date-filter").addEventListener("submit", (event) => {
  event.preventDefault();
  currentFilters = {
    date_from: document.querySelector("#date-from").value,
    date_to: document.querySelector("#date-to").value,
  };
  page = 0;
  loadTickets();
});
document.querySelector("#clear-filter").addEventListener("click", () => {
  document.querySelector("#date-from").value = "";
  document.querySelector("#date-to").value = "";
  currentFilters = {};
  page = 0;
  loadTickets();
});
document.querySelector("#today-filter").addEventListener("click", () => {
  const today = new Date();
  const localDate = [
    today.getFullYear(),
    String(today.getMonth() + 1).padStart(2, "0"),
    String(today.getDate()).padStart(2, "0"),
  ].join("-");
  document.querySelector("#date-from").value = localDate;
  document.querySelector("#date-to").value = localDate;
  currentFilters = { date_from: localDate, date_to: localDate };
  page = 0;
  loadTickets();
});
document.querySelector("#previous-page").addEventListener("click", () => {
  if (page > 0) {
    page -= 1;
    loadTickets();
  }
});
document.querySelector("#next-page").addEventListener("click", () => {
  if (tickets.length === pageSize) {
    page += 1;
    loadTickets();
  }
});
document.querySelector("#new-ticket-toggle").addEventListener("click", () => {
  document.querySelector("#new-ticket-panel").classList.toggle("hidden");
});
document.querySelector("#close-ticket-panel").addEventListener("click", () => {
  document.querySelector("#new-ticket-panel").classList.add("hidden");
});
document.querySelector("#new-ticket-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = document.querySelector("#create-ticket-button");
  const message = document.querySelector("#create-message");
  button.disabled = true;
  message.textContent = "Analyzing email and creating ticket…";
  message.className = "text-sm text-slate-500";
  try {
    const response = await fetch("/api/tickets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email_content: document.querySelector("#email-content").value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail ?? `Request failed (${response.status})`);
    message.textContent = `Ticket #${result.id} created successfully.`;
    message.className = "text-sm font-semibold text-emerald-700";
    document.querySelector("#new-ticket-form").reset();
    currentFilters = {};
    document.querySelector("#date-from").value = "";
    document.querySelector("#date-to").value = "";
    page = 0;
    await loadTickets();
  } catch (error) {
    message.textContent = error.message;
    message.className = "text-sm font-semibold text-rose-700";
  } finally {
    button.disabled = false;
  }
});
listElement.addEventListener("change", async (event) => {
  const select = event.target.closest("select[data-ticket-id]");
  if (!select || !select.value) return;
  const ticketId = select.dataset.ticketId;
  select.disabled = true;
  try {
    const response = await fetch(`/api/tickets/${ticketId}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: select.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail ?? `Request failed (${response.status})`);
    setMessage(`Ticket #${ticketId} marked ${result.status.replaceAll("_", " ")}.`);
    await loadTickets();
  } catch (error) {
    setMessage(error.message, true);
    select.disabled = false;
    select.value = "";
  }
});

loadTickets();
