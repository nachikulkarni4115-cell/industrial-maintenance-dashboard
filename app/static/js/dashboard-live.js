(() => {
  "use strict";

  const scriptElement = document.currentScript;
  const telemetryUrl = scriptElement?.dataset.telemetryUrl;

  if (!telemetryUrl) {
    console.error("Live telemetry URL is missing from dashboard script configuration.");
  }
  const body = document.getElementById("latest-telemetry-body");
  const table = document.getElementById("latest-telemetry-table");
  const emptyMessage = document.getElementById("latest-telemetry-empty");
  const timeElement = document.getElementById("last-telemetry-time");
  const badgeElement = document.getElementById("last-telemetry-badge");
  const refreshStatus = document.getElementById("telemetry-refresh-status");

  if (!telemetryUrl) return;

  let requestInProgress = false;

  function displayValue(value) {
    return value === null || value === undefined || value === ""
      ? "—"
      : String(value);
  }

  function addCell(row, value, className) {
    const cell = document.createElement("td");

    if (className) {
      cell.className = className;
    }

    cell.textContent = displayValue(value);
    row.appendChild(cell);
  }

  let firstRender = true;
  const seen = new Set();
  const tempClass = v => (v >= 90 ? "hot" : v >= 75 ? "warm" : "");

  function renderReadings(readings) {
    const rows = [];
    for (const reading of readings) {
      const key = reading.timestamp + "|" + reading.asset_tag;
      const row = document.createElement("tr");
      if (!firstRender && !seen.has(key)) row.className = "row-new";
      seen.add(key);

      addCell(row, reading.timestamp, "meta");
      addCell(row, reading.asset_tag);
      addCell(row, reading.temperature_c, tempClass(reading.temperature_c));
      addCell(row, reading.vibration_mm_s);
      addCell(row, reading.rpm);
      addCell(row, reading.current_a);

      const sourceCell = document.createElement("td");
      const sourceBadge = document.createElement("span");
      sourceBadge.className = reading.is_simulated ? "badge badge-telemetry" : "badge badge-operational";
      sourceBadge.textContent = reading.is_simulated ? "stream" : "live";
      sourceCell.appendChild(sourceBadge);
      row.appendChild(sourceCell);
      rows.push(row);
    }
    body.replaceChildren(...rows);
    firstRender = false;

    const hasReadings = readings.length > 0;
    table.hidden = !hasReadings;
    emptyMessage.hidden = hasReadings;
    drawLive(readings);
  }

  // Rolling fleet-average temperature chart built from successive polls
  const lcBox = document.getElementById("live-chart");
  const lcVal = document.getElementById("live-avg");
  const history = [];
  function drawLive(readings) {
    if (!lcBox) return;
    const t = readings.map(r => Number(r.temperature_c)).filter(Number.isFinite);
    if (!t.length) return;
    const avg = t.reduce((a, b) => a + b, 0) / t.length;
    history.push(avg); if (history.length > 40) history.shift();
    if (lcVal) lcVal.textContent = avg.toFixed(1) + " °C";
    if (history.length < 2) return;
    const W = 600, H = 120, mn = Math.min(...history) - 2, mx = Math.max(...history) + 2;
    const pts = history.map((v, i) => [i * W / (history.length - 1), H - 8 - (v - mn) / (mx - mn || 1) * (H - 16)]);
    const d = pts.reduce((p, [x, y], i, a) => i
      ? p + ` C${(a[i-1][0] + x) / 2},${a[i-1][1]} ${(a[i-1][0] + x) / 2},${y} ${x},${y}` : `M${x},${y}`, "");
    lcBox.querySelector("svg")?.remove();
    lcBox.insertAdjacentHTML("afterbegin",
      `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none"><defs>
        <linearGradient id="lcg"><stop stop-color="#7c6cff"/><stop offset="1" stop-color="#38bdf8"/></linearGradient>
        <linearGradient id="lca" x1="0" y1="0" x2="0" y2="1"><stop stop-color="#7c6cff" stop-opacity=".35"/><stop offset="1" stop-color="#7c6cff" stop-opacity="0"/></linearGradient></defs>
        <path d="${d} L${W},${H} L0,${H}Z" fill="url(#lca)"/><path class="l" d="${d}"/></svg>`);
    const pt = lcBox.querySelector(".pt");
    if (pt) { pt.style.left = "100%"; pt.style.top = (pts[pts.length - 1][1] / H * 100) + "%"; }
  }

  function renderKpis(kpis) {
    if (!kpis) return;
    const values = {
      "kpi-total-assets": kpis.total_assets,
      "kpi-open-alerts": kpis.open_alerts,
      "kpi-critical-alerts": kpis.critical_alerts,
      "kpi-open-workorders": kpis.open_workorders
    };

    for (const [id, value] of Object.entries(values)) {
      const element = document.getElementById(id);
      if (element && value !== undefined && value !== null) {
        if (window.animateNumber) window.animateNumber(element, Number(value));
        else element.textContent = String(value);
      }
    }

    const totalCard = document.getElementById("kpi-total-assets")?.closest(".kpi-card");
    const alertsCard = document.getElementById("kpi-open-alerts")?.closest(".kpi-card");
    const criticalCard = document.getElementById("kpi-critical-alerts")?.closest(".kpi-card");
    const workordersCard = document.getElementById("kpi-open-workorders")?.closest(".kpi-card");

    if (totalCard) {
      totalCard.classList.toggle("ok", Number(kpis.total_assets) > 0);
    }
    if (alertsCard) {
      alertsCard.classList.remove("ok", "warning", "critical");
      alertsCard.classList.add(Number(kpis.critical_alerts) > 0
        ? "critical"
        : Number(kpis.open_alerts) > 0 ? "warning" : "ok");
    }
    if (criticalCard) {
      criticalCard.classList.toggle("critical", Number(kpis.critical_alerts) > 0);
      criticalCard.classList.toggle("ok", Number(kpis.critical_alerts) <= 0);
    }
    if (workordersCard) {
      workordersCard.classList.toggle("warning", Number(kpis.open_workorders) > 0);
      workordersCard.classList.toggle("ok", Number(kpis.open_workorders) <= 0);
    }
  }

  function renderLastReading(data) {
    if (data.last_reading) {
      timeElement.textContent = "Last telemetry: " + data.last_reading;
      badgeElement.textContent = data.is_stale
        ? `STALE (> ${data.stale_hours}h)`
        : "recent";

      badgeElement.className = data.is_stale
        ? "badge badge-warning"
        : "badge badge-operational";
    } else {
      timeElement.textContent = "No telemetry received yet";
      badgeElement.textContent = "waiting";
      badgeElement.className = "badge badge-info";
    }
  }

  const bar = document.querySelector("#livebar i");
  const dots = document.querySelectorAll(".live-dot");
  function pulse(ok) {
    dots.forEach(d => d.classList.toggle("off", !ok));
    if (!bar) return;
    bar.classList.remove("run"); void bar.offsetWidth; bar.classList.add("run");
  }

  async function refreshTelemetry() {
    if (requestInProgress || document.hidden) {
      return;
    }

    requestInProgress = true;
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), 10000);

    try {
      const response = await fetch(telemetryUrl, {
        method: "GET",
        credentials: "same-origin",
        cache: "no-store",
        signal: controller.signal,
        headers: {
          "Accept": "application/json"
        }
      });

      if (response.redirected || response.status === 401) {
        refreshStatus.textContent =
          "Your session may have expired. Please sign in again.";
        return;
      }

      if (!response.ok) {
        throw new Error("HTTP " + response.status);
      }

      const data = await response.json();

      renderReadings(data.readings || []);
      renderKpis(data.kpis);
      renderLastReading(data);

      pulse(true);
      refreshStatus.textContent =
        "Live updates enabled · checked at " +
        new Date().toLocaleTimeString();
    } catch (error) {
      console.error("Live telemetry refresh failed:", error);
      pulse(false);
      refreshStatus.textContent =
        "Unable to refresh telemetry. Retrying automatically.";
    } finally {
      window.clearTimeout(timeoutId);
      requestInProgress = false;
    }
  }

  // Load immediately, then poll every 2 seconds without a page reload.
  refreshTelemetry();
  window.setInterval(refreshTelemetry, 2000);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) refreshTelemetry();
  });

  const simulatorRunUrl = scriptElement?.dataset.simulatorRunUrl;
  const simulatorStatusUrl = scriptElement?.dataset.simulatorStatusUrl;
  const csrfToken = scriptElement?.dataset.csrfToken;
  const simulatorButton = document.getElementById("run-simulator-button");
  const simulatorStatus = document.getElementById("simulator-job-status");
  let simulatorPollTimer = null;

  async function pollSimulatorJob(jobName) {
    const url = simulatorStatusUrl.replace("JOB_NAME", encodeURIComponent(jobName));
    try {
      const response = await fetch(url, {
        credentials: "same-origin",
        cache: "no-store",
        headers: { "Accept": "application/json" }
      });
      if (response.redirected || response.status === 401) {
        simulatorStatus.textContent = "Your session expired. Sign in again to check the job.";
        simulatorButton.disabled = false;
        return true;
      }
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Unable to read simulator status.");
      const job = data.job;
      simulatorStatus.textContent = job.message;
      if (job.state === "succeeded" || job.state === "failed") {
        if (job.state === "succeeded") {
          simulatorStatus.textContent = "Simulator finished sending. Waiting for Azure IoT Hub, the bridge, and dashboard refresh…";
          window.setTimeout(refreshTelemetry, 2500);
          window.setTimeout(refreshTelemetry, 6000);
        }
        simulatorButton.disabled = false;
        return true;
      }
      return false;
    } catch (error) {
      simulatorStatus.textContent = error.message || "Unable to check simulator status.";
      simulatorButton.disabled = false;
      return true;
    }
  }

  if (simulatorButton && simulatorRunUrl && simulatorStatusUrl && csrfToken) {
    simulatorButton.addEventListener("click", async () => {
      if (simulatorButton.disabled) return;
      simulatorButton.disabled = true;
      simulatorStatus.textContent = "Requesting a Kubernetes Job…";
      try {
        const response = await fetch(simulatorRunUrl, {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "Accept": "application/json",
            "X-CSRFToken": csrfToken
          }
        });
        const data = await response.json();
        if (!response.ok) {
          simulatorStatus.textContent = data.job?.message || data.error || "Unable to start simulation.";
          if (response.status === 409 && data.job?.job_name) {
            const alreadyFinished = await pollSimulatorJob(data.job.job_name);
            if (!alreadyFinished) {
              simulatorPollTimer = window.setInterval(async () => {
                if (await pollSimulatorJob(data.job.job_name)) {
                  window.clearInterval(simulatorPollTimer);
                  simulatorPollTimer = null;
                }
              }, 2000);
            }
            return;
          }
          simulatorButton.disabled = false;
          return;
        }
        const jobName = data.job.job_name;
        simulatorStatus.textContent = data.job.message;
        const alreadyFinished = await pollSimulatorJob(jobName);
        if (!alreadyFinished) {
          simulatorPollTimer = window.setInterval(async () => {
            if (await pollSimulatorJob(jobName)) {
              window.clearInterval(simulatorPollTimer);
              simulatorPollTimer = null;
            }
          }, 2000);
        }
      } catch (error) {
        simulatorStatus.textContent = "Unable to start simulation. Please try again.";
        simulatorButton.disabled = false;
      }
    });
  }

})();
