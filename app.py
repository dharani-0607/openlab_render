
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime
from threading import Lock

app = Flask(__name__)
lock = Lock()

state = {
    "helmet": {
        "alcohol_raw": None,
        "alcohol_ok": False,
        "buckle_closed": False,
        "rfid_authorized": False,
        "engine_permit": False,
        "temperature_c": None,
        "heart_rate_bpm": None,
        "spo2_percent": None,
        "vitals_simulated": True,
        "crash_detected": False,
        "g_force": None,
        "mpu_available": False,
        "blind_spot": False
    },
    "bike": {
        "left_distance_cm": None,
        "right_distance_cm": None,
        "left_blind_spot": False,
        "right_blind_spot": False,
        "blind_spot_signal_to_helmet": False,
        "latitude": None,
        "longitude": None,
        "speed_kmh": None,
        "call_allowed": False,
        "engine_permit_received": False,
        "helmet_crash_received": False,
        "gps_simulated": True
    },
    "updated": "Waiting for ESP32 nodes"
}

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Helmet Dashboard</title>
<style>
body{font-family:Arial;background:#f1f5f9;color:#172033;margin:0}
header{background:#13243b;color:white;padding:22px}
main{max-width:1100px;margin:auto;padding:20px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:15px}
.card{background:white;border-radius:12px;padding:18px;box-shadow:0 3px 12px #0001}
h2{font-size:18px}
.item{display:flex;justify-content:space-between;gap:10px;padding:9px 0;border-bottom:1px solid #eee}
.value{font-weight:bold;text-align:right}
.pill{padding:8px;border-radius:8px;font-weight:bold;display:inline-block}
.ok{background:#dcfce7;color:#166534}
.bad{background:#fee2e2;color:#991b1b}
.warn{background:#fef3c7;color:#92400e}
button{padding:12px 16px;background:#2563eb;color:white;border:0;border-radius:8px;font-weight:bold}
button:disabled{background:#9ca3af}
small{color:#64748b}
</style>
</head>
<body>
<header>
<h1>Smart Helmet & Bike Monitoring</h1>
<p>ESP32 simulation dashboard</p>
</header>
<main>
<div class="grid">
<section class="card">
<h2>Vehicle Interlock</h2>
<div id="engine" class="pill bad">LOCKED</div>
<div class="item"><span>Alcohol</span><b id="alcoholOK">Waiting</b></div>
<div class="item"><span>Buckle</span><b id="buckle">Waiting</b></div>
<div class="item"><span>RFID</span><b id="rfid">Waiting</b></div>
<p><small>All three conditions must pass.</small></p>
</section>

<section class="card">
<h2>Helmet Sensors</h2>
<div class="item"><span>MQ-3 raw value</span><b id="alcohol">--</b></div>
<div class="item"><span>Temperature</span><b id="temp">--</b></div>
<div class="item"><span>Heart rate</span><b id="hr">--</b></div>
<div class="item"><span>SpO2</span><b id="spo2">--</b></div>
<div class="item"><span>Acceleration</span><b id="gforce">--</b></div>
<div class="item"><span>Crash status</span><b id="crash">--</b></div>
<p><small>Heart rate, SpO2 and temperature are simulated.</small></p>
</section>

<section class="card">
<h2>Bike Sensors</h2>
<div class="item"><span>Left distance</span><b id="left">--</b></div>
<div class="item"><span>Right distance</span><b id="right">--</b></div>
<div class="item"><span>Blind-spot signal</span><b id="blind">--</b></div>
<div class="item"><span>GPS coordinates</span><b id="gps">--</b></div>
<div class="item"><span>Speed</span><b id="speed">--</b></div>
<p><small>GPS coordinates and speed are simulated.</small></p>
</section>

<section class="card">
<h2>Call Control</h2>
<p>Request a call only when speed is below 1 km/h.</p>
<button id="callBtn" disabled onclick="requestCall()">Call locked</button>
<p id="callMessage">Waiting for bike speed</p>
<small>This button does not place a real phone call.</small>
</section>

<section class="card">
<h2>Crash Recording</h2>
<div id="recording" class="pill warn">STANDBY</div>
<p id="recordingText">Camera simulation only; no video is recorded.</p>
</section>
</div>
<p><small>Last update: <span id="updated">--</span></small></p>
</main>

<script>
const el = id => document.getElementById(id);
const show = (id, value) => {
  el(id).textContent =
    value === null || value === undefined ? "--" : value;
};

async function refresh() {
  try {
    const response = await fetch("/api/state");
    const s = await response.json();
    const h = s.helmet, b = s.bike;

    show("engine", h.engine_permit ? "ENGINE PERMIT" : "LOCKED");
    el("engine").className = "pill " +
      (h.engine_permit ? "ok" : "bad");

    show("alcoholOK", h.alcohol_ok ? "PASS" : "FAIL / UNKNOWN");
    show("buckle", h.buckle_closed ? "FASTENED" : "OPEN");
    show("rfid", h.rfid_authorized ? "AUTHORIZED" : "NOT AUTHORIZED");

    show("alcohol", h.alcohol_raw);
    show("temp", h.temperature_c === null ? "--" :
      Number(h.temperature_c).toFixed(1) + " °C");
    show("hr", h.heart_rate_bpm === null ? "--" :
      h.heart_rate_bpm + " bpm");
    show("spo2", h.spo2_percent === null ? "--" :
      Number(h.spo2_percent).toFixed(1) + "%");
    show("gforce", h.g_force === null ? "--" :
      Number(h.g_force).toFixed(2) + " g");
    show("crash", h.crash_detected ? "CRASH ALERT" : "No alert");

    show("left", b.left_distance_cm === null ? "--" :
      Number(b.left_distance_cm).toFixed(1) + " cm");
    show("right", b.right_distance_cm === null ? "--" :
      Number(b.right_distance_cm).toFixed(1) + " cm");

    show("blind", b.blind_spot_signal_to_helmet ?
      "ACTIVE — LED ON" : "CLEAR — LED OFF");

    show("gps", b.latitude === null || b.longitude === null ? "--" :
      Number(b.latitude).toFixed(5) + ", " +
      Number(b.longitude).toFixed(5));

    show("speed", b.speed_kmh === null ? "--" :
      Number(b.speed_kmh).toFixed(1) + " km/h");

    const stopped = b.speed_kmh !== null &&
      b.speed_kmh !== undefined && Number(b.speed_kmh) < 1;

    el("callBtn").disabled = !stopped;
    el("callBtn").textContent = stopped ?
      "Request call" : "Call locked — bike moving";

    show("recording", h.crash_detected ?
      "CRASH EVENT (SIMULATED)" : "STANDBY");

    el("recording").className = "pill " +
      (h.crash_detected ? "bad" : "warn");

    show("recordingText", h.crash_detected ?
      "Crash event detected; actual video is not recorded." :
      "Camera simulation only; no video is recorded.");

    show("updated", s.updated);
  } catch (error) {
    show("updated", "Backend unavailable");
  }
}

async function requestCall() {
  const response = await fetch("/api/call", {method: "POST"});
  const data = await response.json();
  show("callMessage", data.message);
  await refresh();
}

refresh();
setInterval(refresh, 1000);
</script>
</body>
</html>
"""

@app.get("/")
def home():
    return render_template_string(HTML)

@app.get("/api/state")
def get_state():
    with lock:
        return jsonify(state)

@app.get("/api/helmet")
def get_helmet():
    with lock:
        return jsonify(state["helmet"])

@app.post("/api/helmet")
def update_helmet():
    data = request.get_json(silent=True) or {}

    required = [
        "alcohol_raw", "alcohol_ok", "buckle_closed",
        "rfid_authorized", "engine_permit"
    ]

    if any(key not in data for key in required):
        return jsonify({"error": "Missing required fields"}), 400

    # Recalculate the interlock on the server as well.
    alcohol_ok = data["alcohol_ok"] is True
    buckle_ok = data["buckle_closed"] is True
    rfid_ok = data["rfid_authorized"] is True

    data["engine_permit"] = alcohol_ok and buckle_ok and rfid_ok

    with lock:
        state["helmet"].update(data)
        state["updated"] = datetime.now().strftime("%H:%M:%S")

    return jsonify({"success": True})

@app.post("/api/bike")
def update_bike():
    data = request.get_json(silent=True) or {}

    required = ["speed_kmh", "blind_spot_signal_to_helmet"]
    if any(key not in data for key in required):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        speed = float(data["speed_kmh"])
        if not 0 <= speed <= 120:
            raise ValueError()
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid speed"}), 400

    with lock:
        state["bike"].update(data)
        state["updated"] = datetime.now().strftime("%H:%M:%S")

    return jsonify({"success": True})

@app.post("/api/call")
def request_call():
    with lock:
        speed = state["bike"].get("speed_kmh")

        if speed is not None and float(speed) < 1:
            return jsonify({
                "success": True,
                "message": "Call request accepted (simulation only)."
            })

    return jsonify({
        "success": False,
        "message": "Call blocked: speed is not confirmed below 1 km/h."
    }), 403

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
