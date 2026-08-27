const socket = io();

let temperatureChart = null;
let temperatureRange = "1h";

function formatTime(seconds) {
    if (seconds === null || seconds === undefined) return "--";

    seconds = Math.max(0, Number(seconds));

    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    return (
        String(hours).padStart(2, "0") + ":" +
        String(minutes).padStart(2, "0") + ":" +
        String(secs).padStart(2, "0")
    );
}

function formatRemaining(minutes) {
    if (minutes === null || minutes === undefined) return "--";

    minutes = Math.max(0, Number(minutes));
    const hours = Math.floor(minutes / 60);
    const mins = minutes % 60;

    return hours > 0 ? `${hours}h ${mins}m` : `${mins}m`;
}

function temperature(value) {
    if (value === null || value === undefined || Number.isNaN(Number(value))) {
        return "--";
    }
    return `${Number(value).toFixed(2)}°C`;
}

function setConnectionStatus(printer) {
    const element = document.getElementById("connection");
    const text = document.getElementById("connection-text");

    element.classList.remove("online", "busy", "offline");

    if (!printer.connected) {
        element.classList.add("offline");
        text.innerText = "OFFLINE";
        return;
    }

    const busyStates = [
        "PREPARE", "RUNNING", "SLICING", "INIT", "PAUSE"
    ];

    if (busyStates.includes(printer.state)) {
        element.classList.add("busy");
        text.innerText = printer.state === "PAUSE" ? "PAUSED" : "BUSY";
    } else {
        element.classList.add("online");
        text.innerText = "ONLINE";
    }
}

function updateDashboard(data) {
    const printer = data.printer;
    const fan = data.fan;

    setConnectionStatus(printer);

    document.getElementById("printer-activity").innerText =
        printer.activity || "Unknown";

    document.getElementById("printer-state").innerText =
        printer.state_label || printer.state || "UNKNOWN";

    document.getElementById("filename").innerText =
        printer.filename || "No print";

    const progress = Math.max(0, Math.min(100, Number(printer.progress || 0)));

    document.getElementById("progress").style.width = `${progress}%`;
    document.getElementById("progress-text").innerText = `${progress}%`;

    document.getElementById("nozzle").innerText =
        temperature(printer.nozzle_temperature);

    document.getElementById("bed").innerText =
        temperature(printer.bed_temperature);

    document.getElementById("chamber").innerText =
        temperature(printer.chamber_temperature);

    if (printer.current_layer !== null && printer.total_layers !== null) {
        document.getElementById("layer").innerText =
            `${printer.current_layer} / ${printer.total_layers}`;
    } else {
        document.getElementById("layer").innerText = "--";
    }

    document.getElementById("remaining").innerText =
        formatRemaining(printer.remaining_minutes);

    document.getElementById("wifi").innerText =
        printer.wifi_signal || "--";

    document.getElementById("print-speed").innerText =
        printer.print_speed !== null && printer.print_speed !== undefined
            ? `${printer.print_speed}`
            : "--";

    const finishElement = document.getElementById("finish-time");

    if (printer.estimated_end_time) {
        const finish = new Date(printer.estimated_end_time);
        finishElement.innerText = finish.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit"
        });
    } else {
        finishElement.innerText = "--";
    }

    document.getElementById("resume-button").disabled =
        printer.state !== "PAUSE";

    document.getElementById("pause-button").disabled =
        printer.state !== "RUNNING";

    document.getElementById("stop-button").disabled =
        !["RUNNING", "PAUSE", "PREPARE"].includes(printer.state);

    const fanIndicator = document.getElementById("fan-indicator");

    fanIndicator.className =
        fan.on ? "fan-indicator on" : "fan-indicator off";

    fanIndicator.innerText = fan.on ? "ON" : "OFF";

    document.getElementById("fan-status").innerText =
        fan.on ? "ON" : "OFF";

    document.getElementById("fan-mode").innerText =
        fan.mode.toUpperCase();

    updateModeButtons(
        fan.mode === "bambu" || fan.mode === "cooldown"
            ? "bambu"
            : "manual"
    );

    document.getElementById("timer-display").innerText =
        formatTime(fan.timer_remaining);
}

socket.on("status", updateDashboard);

async function api(url, options = {}) {
    const response = await fetch(url, options);

    let data = {};
    try {
        data = await response.json();
    } catch (_) {}

    if (!response.ok) {
        throw new Error(data.error || `Request failed: ${response.status}`);
    }

    return data;
}

async function setMode(mode) {
    try {
        await api("/api/mode", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({mode})
        });

        updateModeButtons(mode);
    } catch (error) {
        alert(error.message);
    }
}

function updateModeButtons(mode) {
    document.getElementById("manual-mode")
        .classList.toggle("active", mode === "manual");

    document.getElementById("bambu-mode")
        .classList.toggle("active", mode === "bambu");
}

async function loadStatus() {
    try {
        updateDashboard(await api("/api/status"));
    } catch (error) {
        console.error(error);
    }
}

async function fanOn() {
    try { await api("/api/fan/on", {method: "POST"}); }
    catch (error) { alert(error.message); }
}

async function fanOff() {
    try { await api("/api/fan/off", {method: "POST"}); }
    catch (error) { alert(error.message); }
}

async function startTimer() {
    const hours = Number(document.getElementById("hours").value);
    const minutes = Number(document.getElementById("minutes").value);
    const seconds = Number(document.getElementById("seconds").value);

    try {
        await api("/api/timer", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({hours, minutes, seconds})
        });
    } catch (error) {
        alert(error.message);
    }
}

async function cancelTimer() {
    try { await api("/api/timer", {method: "DELETE"}); }
    catch (error) { alert(error.message); }
}

async function resumePrint() {
    if (!confirm("Resume the printer?")) return;

    try { await api("/api/printer/resume", {method: "POST"}); }
    catch (error) { alert(error.message); }
}

async function pausePrint() {
    try { await api("/api/printer/pause", {method: "POST"}); }
    catch (error) { alert(error.message); }
}

async function stopPrint() {
    if (!confirm("STOP the current print? This cannot be undone.")) return;

    try { await api("/api/printer/stop", {method: "POST"}); }
    catch (error) { alert(error.message); }
}

async function saveSettings() {
    const data = {
        automation_enabled:
            document.getElementById("automation-enabled").checked ? 1 : 0,
        fan_while_printing:
            document.getElementById("fan-printing").checked ? 1 : 0,
        fan_on_error:
            document.getElementById("fan-error").checked ? 1 : 0,
        cooldown_minutes:
            Number(document.getElementById("cooldown").value)
    };

    try {
        await api("/api/settings", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(data)
        });

        alert("Settings saved.");
    } catch (error) {
        alert(error.message);
    }
}

async function loadSettings() {
    try {
        const data = await api("/api/settings");

        document.getElementById("automation-enabled").checked =
            data.automation_enabled;

        document.getElementById("fan-printing").checked =
            data.fan_while_printing;

        document.getElementById("fan-error").checked =
            data.fan_on_error;

        document.getElementById("cooldown").value =
            data.cooldown_minutes;
    } catch (error) {
        console.error(error);
    }
}

async function loadEvents() {
    try {
        const events = await api("/api/events?limit=10");
        const container = document.getElementById("events");

        container.innerHTML = "";

        if (!events.length) {
            container.innerHTML = "<div class='event'>No events yet.</div>";
            return;
        }

        events.forEach(event => {
            const element = document.createElement("div");
            element.className = "event";

            const date = new Date(event.timestamp * 1000);

            element.innerHTML = `
                <span class="event-time">${date.toLocaleTimeString()}</span>
                <span class="event-type">${escapeHtml(event.event_type)}</span>
                <span>${escapeHtml(event.message)}</span>
            `;

            container.appendChild(element);
        });
    } catch (error) {
        console.error(error);
    }
}

function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

async function loadPrintHistory() {
    try {
        const prints = await api("/api/prints?limit=10");
        const container = document.getElementById("print-history");

        if (!prints.length) {
            container.innerHTML = "No print history yet.";
            return;
        }

        container.innerHTML = prints.map(print => {
            const duration = print.duration_seconds
                ? formatTime(print.duration_seconds)
                : "--";

            const started = print.started_at
                ? new Date(print.started_at * 1000).toLocaleString()
                : "--";

            return `
                <div class="print-row">
                    <strong>${escapeHtml(print.filename || "Unknown")}</strong>
                    <span>${escapeHtml(print.final_state || "--")}</span>
                    <span>${duration}</span>
                    <span>${started}</span>
                </div>
            `;
        }).join("");
    } catch (error) {
        console.error(error);
    }
}

function setTemperatureRange(range) {
    temperatureRange = range;

    document.querySelectorAll(".range-buttons button")
        .forEach(button => button.classList.remove("active"));

    [...document.querySelectorAll(".range-buttons button")]
        .find(button => button.innerText === range)
        ?.classList.add("active");

    loadTemperatureChart();
}

async function loadTemperatureChart() {
    try {
        const data = await api(
            `/api/temperature?range=${encodeURIComponent(temperatureRange)}`
        );

        const labels = data.map(item =>
            new Date(item.timestamp * 1000).toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit"
            })
        );

        const nozzle = data.map(item => item.nozzle);
        const bed = data.map(item => item.bed);
        const chamber = data.map(item => item.chamber);

        const context =
            document.getElementById("temperature-chart").getContext("2d");

        if (temperatureChart) temperatureChart.destroy();

        temperatureChart = new Chart(context, {
            type: "line",
            data: {
                labels,
                datasets: [
                    {label: "Nozzle", data: nozzle, tension: 0.3, spanGaps: true},
                    {label: "Bed", data: bed, tension: 0.3, spanGaps: true},
                    {label: "Chamber", data: chamber, tension: 0.3, spanGaps: true}
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: false,
                interaction: {
                    mode: "index",
                    intersect: false
                },
                scales: {
                    y: {beginAtZero: false}
                }
            }
        });
    } catch (error) {
        console.error(error);
    }
}

function formatUptime(seconds) {
    if (seconds === null || seconds === undefined) return "--";

    seconds = Number(seconds);
    const days = Math.floor(seconds / 86400);
    seconds %= 86400;
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);

    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
}

async function loadSystem() {
    try {
        const data = await api("/api/system");

        document.getElementById("cpu").innerText =
            data.cpu_percent !== null ? `${Number(data.cpu_percent).toFixed(1)}%` : "--";

        document.getElementById("memory").innerText =
            data.memory_percent !== null ? `${Number(data.memory_percent).toFixed(1)}%` : "--";

        document.getElementById("disk").innerText =
            data.disk_percent !== null ? `${Number(data.disk_percent).toFixed(1)}%` : "--";

        document.getElementById("pi-temp").innerText =
            data.temperature !== null ? `${Number(data.temperature).toFixed(1)}°C` : "--";

        document.getElementById("uptime").innerText =
            formatUptime(data.uptime_seconds);

        document.getElementById("mqtt-health").innerText =
            (await api("/api/status")).printer.connected ? "Connected" : "Offline";

        document.getElementById("system-health").innerText = "Healthy";
    } catch (error) {
        document.getElementById("system-health").innerText = "Unavailable";
        console.error(error);
    }
}

loadStatus();
loadSettings();
loadEvents();
loadPrintHistory();
loadTemperatureChart();
loadSystem();

setInterval(loadEvents, 10000);
setInterval(loadPrintHistory, 30000);
setInterval(loadTemperatureChart, 30000);
setInterval(loadSystem, 10000);
