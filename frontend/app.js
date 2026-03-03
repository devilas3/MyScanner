// Use your Render API URL (replace with your Hostinger URL if you host the frontend there)
const API_BASE_URL = "https://myscanner-81ql.onrender.com";

const scanDateInput = document.getElementById("scan-date");
const segmentSelect = document.getElementById("segment");
const contractSelect = document.getElementById("contract");
const contractField = document.getElementById("contract-field");
const combineModeSelect = document.getElementById("combine-mode");
const addConditionBtn = document.getElementById("btn-add-condition");
const clearConditionsBtn = document.getElementById("btn-clear-conditions");
const runScanBtn = document.getElementById("btn-run-scan");
const r1BreakoutBtn = document.getElementById("btn-r1-breakout");
const loadPivotsBtn = document.getElementById("btn-load-pivots");
const conditionsContainer = document.getElementById("conditions-container");
const pivotsTableBody = document.querySelector("#pivots-table tbody");
const resultsTableBody = document.querySelector("#results-table tbody");
const toastEl = document.getElementById("toast");

function todayISO() {
  const d = new Date();
  const off = d.getTimezoneOffset();
  const local = new Date(d.getTime() - off * 60000);
  return local.toISOString().slice(0, 10);
}

function showToast(message) {
  toastEl.textContent = message;
  toastEl.classList.remove("hidden");
  toastEl.classList.add("visible");
  setTimeout(() => {
    toastEl.classList.remove("visible");
    setTimeout(() => toastEl.classList.add("hidden"), 180);
  }, 2600);
}

function addConditionRow(initial = "") {
  const row = document.createElement("div");
  row.className = "condition-row";
  const input = document.createElement("input");
  input.type = "text";
  input.placeholder = "e.g. high >= r1 and close > r1";
  input.value = initial;
  const removeBtn = document.createElement("button");
  removeBtn.textContent = "Remove";
  removeBtn.addEventListener("click", () => {
    conditionsContainer.removeChild(row);
  });
  row.appendChild(input);
  row.appendChild(removeBtn);
  conditionsContainer.appendChild(row);
}

function getConditions() {
  const inputs = conditionsContainer.querySelectorAll("input[type='text']");
  const conditions = [];
  inputs.forEach((el) => {
    const val = el.value.trim();
    if (val) conditions.push(val);
  });
  return conditions;
}

async function fetchJSON(url, options = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Request failed (${res.status}): ${text}`);
  }
  return res.json();
}

async function loadPivots() {
  const date = scanDateInput.value;
  const segment = segmentSelect.value;
  if (!date) {
    showToast("Select a date first.");
    return;
  }
  if (segment === "future" && !contractSelect.value) {
    showToast("Select a contract for futures.");
    return;
  }
  try {
    pivotsTableBody.innerHTML = "";
    let url = `${API_BASE_URL}/api/pivots?date=${encodeURIComponent(date)}&segment=${encodeURIComponent(segment)}`;
    if (segment === "future" && contractSelect.value)
      url += "&expiry_date=" + encodeURIComponent(contractSelect.value);
    const data = await fetchJSON(url);
    for (const row of data) {
      const tr = document.createElement("tr");
      const contract = row.expiry_date || "";
      tr.innerHTML = `
        <td>${row.symbol}</td>
        <td class="contract-col">${contract}</td>
        <td>${row.pivot.toFixed(2)}</td>
        <td>${row.r1.toFixed(2)}</td>
        <td>${row.r2.toFixed(2)}</td>
        <td>${row.s1.toFixed(2)}</td>
        <td>${row.s2.toFixed(2)}</td>
      `;
      pivotsTableBody.appendChild(tr);
    }
    showToast(`Loaded pivots for ${date}.`);
  } catch (err) {
    console.error(err);
    showToast("Failed to load pivots.");
  }
}

async function runScan(withPreset = false) {
  const date = scanDateInput.value;
  const segment = segmentSelect.value;
  if (!date) {
    showToast("Select a date first.");
    return;
  }
  if (segment === "future" && !contractSelect.value) {
    showToast("Select a contract for futures.");
    return;
  }

  let conditions;
  if (withPreset) {
    conditions = ["high >= r1 and close > r1"];
  } else {
    conditions = getConditions();
    if (!conditions.length) {
      showToast("Add at least one condition.");
      return;
    }
  }

  const body = {
    date,
    segment,
    conditions,
    combine: combineModeSelect.value,
  };
  if (segment === "future" && contractSelect.value)
    body.expiry_date = contractSelect.value;

  try {
    resultsTableBody.innerHTML = "";
    const data = await fetchJSON(`${API_BASE_URL}/api/scan`, {
      method: "POST",
      body: JSON.stringify(body),
    });
    for (const row of data) {
      const tr = document.createElement("tr");
      const contract = row.expiry_date || "";
      tr.innerHTML = `
        <td>${row.symbol}</td>
        <td class="contract-col">${contract}</td>
        <td>${row.date}</td>
        <td>${row.open.toFixed(2)}</td>
        <td>${row.high.toFixed(2)}</td>
        <td>${row.low.toFixed(2)}</td>
        <td>${row.close.toFixed(2)}</td>
        <td>${row.pivot != null ? row.pivot.toFixed(2) : "-"}</td>
        <td>${row.r1 != null ? row.r1.toFixed(2) : "-"}</td>
        <td>${row.volume != null ? row.volume.toFixed(0) : "-"}</td>
      `;
      resultsTableBody.appendChild(tr);
    }
    showToast(`Scan returned ${data.length} rows.`);
  } catch (err) {
    console.error(err);
    showToast("Scan failed. Check API_BASE_URL and backend.");
  }
}

async function loadContracts() {
  contractSelect.innerHTML = '<option value="">— Select contract —</option>';
  try {
    const data = await fetchJSON(`${API_BASE_URL}/api/contracts?segment=future`);
    for (const c of data) {
      const opt = document.createElement("option");
      opt.value = c.expiry_date;
      opt.textContent = `${c.symbol} (${c.expiry_date})`;
      contractSelect.appendChild(opt);
    }
  } catch (err) {
    console.error(err);
  }
}

function init() {
  scanDateInput.value = todayISO();
  addConditionRow("high >= r1 and close > r1");

  segmentSelect.addEventListener("change", () => {
    const isFuture = segmentSelect.value === "future";
    contractField.style.display = isFuture ? "flex" : "none";
    if (isFuture) loadContracts();
  });

  addConditionBtn.addEventListener("click", () => addConditionRow(""));
  clearConditionsBtn.addEventListener("click", () => {
    conditionsContainer.innerHTML = "";
    addConditionRow("");
  });
  loadPivotsBtn.addEventListener("click", () => loadPivots());
  runScanBtn.addEventListener("click", () => runScan(false));
  r1BreakoutBtn.addEventListener("click", () => runScan(true));
}

document.addEventListener("DOMContentLoaded", init);

