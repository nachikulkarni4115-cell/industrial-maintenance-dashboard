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

  function renderReadings(readings) {
    body.replaceChildren();

    for (const reading of readings) {
      const row = document.createElement("tr");

      addCell(row, reading.timestamp, "meta");
      addCell(row, reading.asset_tag);
      addCell(row, reading.temperature_c);
      addCell(row, reading.vibration_mm_s);
      addCell(row, reading.rpm);
      addCell(row, reading.current_a);

      const sourceCell = document.createElement("td");
      const sourceBadge = document.createElement("span");

      if (reading.is_simulated) {
        sourceBadge.className = "badge badge-simulated";
        sourceBadge.textContent = "sim";
      } else {
        sourceBadge.className = "badge badge-operational";
        sourceBadge.textContent = "live";
      }

      sourceCell.appendChild(sourceBadge);
      row.appendChild(sourceCell);
      body.appendChild(row);
    }

    const hasReadings = readings.length > 0;
    table.hidden = !hasReadings;
    emptyMessage.hidden = hasReadings;
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
        element.textContent = String(value);
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

      refreshStatus.textContent =
        "Live updates enabled · checked at " +
        new Date().toLocaleTimeString();
    } catch (error) {
      console.error("Live telemetry refresh failed:", error);
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
})();
