
import json
import os
import threading
import time

from flask import Flask, jsonify, request, render_template_string
import paho.mqtt.client as mqtt

app = Flask(__name__)

PREFIX = "dh_smarthelmet_demo"
BROKER = "broker.hivemq.com"
PORT = 1883

lock = threading.Lock()
state = {
    "helmet": {},
    "bike": {},
    "last_update": None,
    "mqtt_connected": False,
    "call_status": "No call requested"
}

def on_connect(client, userdata, flags, reason_code, properties):
    connected = (reason_code == 0)
    with lock:
        state["mqtt_connected"] = connected

    if connected:
        client.subscribe([
            (f"{PREFIX}/helmet/data", 0),
            (f"{PREFIX}/bike/data", 0)
        ])
        print("MQTT connected and subscribed")
    else:
        print("MQTT connection failed:", reason_code)

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except (ValueError, UnicodeDecodeError):
        print("Invalid MQTT JSON:", msg.topic)
        return

    with lock:
        if msg.topic == f"{PREFIX}/helmet/data":
            state["helmet"] = data
        elif msg.topic == f"{PREFIX}/bike/data":
            state["bike"] = data
        state["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")

mqtt_client = mqtt.Client(
    mqtt.CallbackAPIVersion.VERSION2,
    client_id="smarthelmet-dashboard"
)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

def mqtt_worker():
    while True:
        try:
            mqtt_client.connect(BROKER, PORT, 60)
            mqtt_client.loop_forever()
        except Exception as exc:
            with lock:
                state["mqtt_connected"] = False
            print("MQTT reconnect:", exc)
            time.sleep(5)

threading.Thread(target=mqtt_worker, daemon=True).start()

@app.route("/")
def index():
    return render_template_string(PAGE)

@app.route("/api/state")
def api_state():
    with lock:
        return jsonify(state)

@app.route("/api/call", methods=["POST"])
def api_call():
    with lock:
        speed = state["bike"].get("speed_kmh")
        connected = state["mqtt_connected"]

    if not connected:
        return jsonify(ok=False, message="MQTT is disconnected"), 503

    if speed is None or float(speed) >= 1.0:
        return jsonify(ok=False, message="Call allowed only at zero speed"), 400

    result = mqtt_client.publish(
        f"{PREFIX}/dashboard/command",
        json.dumps({"action": "call"}),
        qos=0
    )

    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        return jsonify(ok=False, message="MQTT publish failed"), 503

    with lock:
        state["call_status"] = "Demo call request published"

    return jsonify(ok=True, message="Demo call request sent")

PAGE = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Helmet Dashboard</title>
<style>
body {font-family:Arial,sans-serif;max-width:950px;margin:24px auto;
padding:0 14px;background:#f4f6f8;color:#17202a}
h1 {margin-bottom:6px}
.cards {display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:14px}
.card {background:white;padding:18px;border-radius:12px;
box-shadow:0 2px 8px #0001}
.value {font-size:1.15rem;font-weight:bold}
button {padding:12px 18px;border:0;border-radius:8px;
background:#1769aa;color:white;font-size:1rem}
small {color:#555}
</style>
</head>
<body>
<h1>Smart Helmet Dashboard</h1>
<p>MQTT-connected simulation · <span id="connection">Connecting...</span></p>
<div class="cards">
  <div class="card">
    <h2>Helmet</h2>
    <p>Alcohol raw: <span id="alcohol">--</span></p>
    <p>Buckle: <span id="buckle">--</span></p>
    <p>RFID authorized: <span id="rfid">--</span></p>
    <p>Engine permit: <span id="permit" class="value">--</span></p>
    <p>Crash detected: <span id="crash">--</span></p>
  </div>
  <div class="card">
    <h2>Vitals (simulated)</h2>
    <p>Temperature: <span id="temp">--</span> °C</p>
    <p>Heart rate: <span id="hr">--</span> bpm</p>
    <p>SpO₂: <span id="spo2">--</span>%</p>
  </div>
  <div class="card">
    <h2>Bike</h2>
    <p>Left obstacle: <span id="left">--</span> cm</p>
    <p>Right obstacle: <span id="right">--</span> cm</p>
    <p>Speed: <span id="speed">--</span> km/h</p>
    <p>Coordinates: <span id="gps">--</span></p>
    <p>Blind spot: <span id="blind">--</span></p>
  </div>
  <div class="card">
    <h2>Alerts and demo call</h2>
    <p id="callstatus">No call requested</p>
    <button id="callbutton" onclick="requestCall()">Request demo call</button>
    <p><small>Enabled only when reported speed is zero.</small></p>
    <p>Last update: <span id="updated">--</span></p>
  </div>
</div>
<script>
const el = id => document.getElementById(id);
const show = (id, value) => el(id).textContent =
  value === undefined || value === null ? "--" : value;

async function refresh() {
  try {
    const r = await fetch("/api/state", {cache:"no-store"});
    if (!r.ok) throw new Error("HTTP " + r.status);
    const s = await r.json();
    const h = s.helmet || {}, b = s.bike || {};

    show("connection", s.mqtt_connected ? "MQTT connected" : "MQTT disconnected");
    show("alcohol", h.alcohol_raw);
    show("buckle", h.buckle_closed === undefined ? "--" : h.buckle_closed ? "Fastened" : "Open");
    show("rfid", h.rfid_authorized);
    show("permit", h.engine_permit);
    show("crash", h.crash_detected);
    show("temp", h.temperature_c);
    show("hr", h.heart_rate_bpm);
    show("spo2", h.spo2_percent);
    show("left", b.left_distance_cm);
    show("right", b.right_distance_cm);
    show("speed", b.speed_kmh);
    show("gps", b.latitude === undefined ? "--" : b.latitude + ", " + b.longitude);
    show("blind", b.blind_spot_signal_to_helmet);
    show("updated", s.last_update);
    show("callstatus", s.call_status || "No call requested");

    el("callbutton").disabled =
      !s.mqtt_connected || b.speed_kmh === undefined || Number(b.speed_kmh) >= 1;
    el("callbutton").style.opacity = el("callbutton").disabled ? "0.5" : "1";
  } catch (e) {
    show("connection", "Dashboard API error");
    el("callbutton").disabled = true;
  }
}

async function requestCall() {
  el("callbutton").disabled = true;
  try {
    const r = await fetch("/api/call", {method:"POST"});
    const d = await r.json();
    show("callstatus", d.message || "Request complete");
  } catch (e) {
    show("callstatus", "Could not send request");
  }
  refresh();
}

refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
