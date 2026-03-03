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

// Futures backfill UI
const backfillModeLatest = document.getElementById("backfill-mode-latest");
const backfillModeHistorical = document.getElementById("backfill-mode-historical");
const backfillDateWrap = document.getElementById("backfill-date-wrap");
const backfillDateInput = document.getElementById("backfill-date");
const expiryNearLabel = document.getElementById("expiry-near-label");
const expiryNextLabel = document.getElementById("expiry-next-label");
const expiryFarLabel = document.getElementById("expiry-far-label");
const backfillSecretInput = document.getElementById("backfill-secret");
const btnBackfillFutures = document.getElementById("btn-backfill-futures");

// View all stock data
const navScanner = document.getElementById("nav-scanner");
const navViewAllData = document.getElementById("nav-view-all-data");
const scannerView = document.getElementById("scanner-view");
const viewAllDataView = document.getElementById("view-all-data-view");
const viewAllDateInput = document.getElementById("view-all-date");
const btnViewAllSubmit = document.getElementById("btn-view-all-submit");
const viewAllTableBody = document.querySelector("#view-all-table tbody");

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

// ——— Futures backfill ———
async function loadBackfillExpiries(mode, refDate) {
  let url = `${API_BASE_URL}/api/futures/expiries?mode=${encodeURIComponent(mode)}`;
  if (mode === "historical" && refDate) url += "&date=" + encodeURIComponent(refDate);
  try {
    const data = await fetchJSON(url);
    expiryNearLabel.textContent = data.near ? `Near (${data.near.label})` : "Near (—)";
    expiryNextLabel.textContent = data.next ? `Next (${data.next.label})` : "Next (—)";
    expiryFarLabel.textContent = data.far ? `Far (${data.far.label})` : "Far (—)";
  } catch (err) {
    console.error(err);
    expiryNearLabel.textContent = "Near (—)";
    expiryNextLabel.textContent = "Next (—)";
    expiryFarLabel.textContent = "Far (—)";
    showToast("Failed to load expiry options.");
  }
}

function updateBackfillModeUI() {
  const isHistorical = backfillModeHistorical.checked;
  backfillDateWrap.style.display = isHistorical ? "flex" : "none";
  if (isHistorical && !backfillDateInput.value) backfillDateInput.value = todayISO();
  const refDate = isHistorical ? backfillDateInput.value : null;
  loadBackfillExpiries(isHistorical ? "historical" : "latest", refDate || undefined);
}

async function submitBackfillFutures() {
  const mode = backfillModeLatest.checked ? "latest" : "historical";
  const contractEl = document.querySelector('input[name="backfill-contract"]:checked');
  const contract = contractEl ? contractEl.value : "near";
  if (mode === "historical" && !backfillDateInput.value) {
    showToast("Select a date for historical backfill.");
    return;
  }
  const secret = backfillSecretInput.value.trim();
  if (!secret) {
    showToast("Enter Refresh secret to run backfill.");
    return;
  }
  const body = { mode, contract };
  if (mode === "historical") body.date = backfillDateInput.value;
  try {
    btnBackfillFutures.disabled = true;
    const res = await fetch(`${API_BASE_URL}/api/backfill/futures`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-Refresh-Secret": secret,
      },
      body: JSON.stringify(body),
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      showToast(data.detail || data.message || "Backfill failed.");
      return;
    }
    const rows = data.rows_upserted != null ? data.rows_upserted : 0;
    showToast(data.status === "ok" ? `Futures backfill done. Rows: ${rows}` : (data.message || "Backfill failed."));
    if (data.status === "ok" && segmentSelect.value === "future") loadContracts();
  } catch (err) {
    console.error(err);
    showToast("Backfill request failed.");
  } finally {
    btnBackfillFutures.disabled = false;
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

  // Futures backfill: load latest expiries on load
  loadBackfillExpiries("latest");
  backfillModeLatest.addEventListener("change", updateBackfillModeUI);
  backfillModeHistorical.addEventListener("change", updateBackfillModeUI);
  backfillDateInput.addEventListener("change", () => {
    if (backfillModeHistorical.checked && backfillDateInput.value)
      loadBackfillExpiries("historical", backfillDateInput.value);
  });
  btnBackfillFutures.addEventListener("click", submitBackfillFutures);

  // View all stock data: nav switch
  navScanner.addEventListener("click", () => switchView("scanner"));
  navViewAllData.addEventListener("click", () => switchView("view-all-data"));
  if (!viewAllDateInput.value) viewAllDateInput.value = todayISO();
  btnViewAllSubmit.addEventListener("click", loadViewAllData);
}

function switchView(viewId) {
  const isScanner = viewId === "scanner";
  scannerView.classList.toggle("hidden", !isScanner);
  viewAllDataView.classList.toggle("hidden", isScanner);
  navScanner.classList.toggle("active", isScanner);
  navViewAllData.classList.toggle("active", !isScanner);
  if (viewId === "view-all-data" && !viewAllDateInput.value) viewAllDateInput.value = todayISO();
}

async function loadViewAllData() {
  const date = viewAllDateInput.value;
  if (!date) {
    showToast("Select a date.");
    return;
  }
  try {
    viewAllTableBody.innerHTML = "";
    const url = `${API_BASE_URL}/api/ohlc?date=${encodeURIComponent(date)}&segment=equity`;
    const data = await fetchJSON(url);
    for (const row of data) {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${row.symbol}</td>
        <td>${row.date}</td>
        <td>${row.open.toFixed(2)}</td>
        <td>${row.high.toFixed(2)}</td>
        <td>${row.low.toFixed(2)}</td>
        <td>${row.close.toFixed(2)}</td>
        <td>${row.volume != null ? Number(row.volume).toLocaleString() : "—"}</td>
      `;
      viewAllTableBody.appendChild(tr);
    }
    showToast(`Loaded ${data.length} records for ${date}.`);
  } catch (err) {
    console.error(err);
    showToast("Failed to load data. Check date and API.");
  }
}

document.addEventListener("DOMContentLoaded", init);

