
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime, timezone
from threading import Lock

app = Flask(__name__)
lock = Lock()

state = {
    "helmet": {},
    "bike": {},
    "updated_at": None,
    "call_status": "No demo call requested"
}

def timestamp():
    return datetime.now(timezone.utc).isoformat()

@app.get("/")
def dashboard():
    return render_template_string(PAGE)

@app.get("/api/state")
def get_state():
    with lock:
        return jsonify(state)

@app.get("/api/helmet")
def get_helmet():
    with lock:
        return jsonify(state["helmet"])

@app.get("/api/bike")
def get_bike():
    with lock:
        return jsonify(state["bike"])

@app.post("/api/helmet")
def post_helmet():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, error="Expected JSON object"), 400

    with lock:
        state["helmet"] = data
        state["helmet"]["received_at"] = timestamp()
        state["updated_at"] = timestamp()

    return jsonify(ok=True, message="Helmet data received")

@app.post("/api/bike")
def post_bike():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(ok=False, error="Expected JSON object"), 400

    with lock:
        state["bike"] = data
        state["bike"]["received_at"] = timestamp()
        state["updated_at"] = timestamp()

    return jsonify(ok=True, message="Bike data received")

@app.post("/api/call")
def request_demo_call():
    with lock:
        speed = state["bike"].get("speed_kmh")

        if speed is None:
            return jsonify(ok=False,
                           message="Waiting for bike speed data"), 400

        try:
            stopped = float(speed) < 1.0
        except (TypeError, ValueError):
            stopped = False

        if not stopped:
            return jsonify(ok=False,
                           message="Demo call allowed only at zero speed"), 400

        state["call_status"] = (
            "Demo call request accepted (no actual call is made)"
        )

    return jsonify(ok=True, message=state["call_status"])

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Helmet Dashboard</title>
<style>
body{font-family:Arial,sans-serif;max-width:1000px;margin:25px auto;
padding:0 15px;background:#f3f5f7;color:#17202a}
h1{margin-bottom:5px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));
gap:14px}
.card{background:white;border-radius:12px;padding:18px;
box-shadow:0 2px 8px #0001}
h2{margin-top:0}
p{line-height:1.5}
button{padding:12px 18px;border:0;border-radius:7px;
background:#1769aa;color:white;font-size:16px}
button:disabled{opacity:.45}
small{color:#555}
</style>
</head>
<body>
<h1>Smart Helmet Dashboard</h1>
<p>Connection: <b id="connection">Waiting for data</b></p>

<div class="grid">
<div class="card">
<h2>Helmet Safety</h2>
<p>Alcohol raw: <b id="alcohol">--</b></p>
<p>Alcohol safe: <b id="alcoholok">--</b></p>
<p>Buckle: <b id="buckle">--</b></p>
<p>RFID: <b id="rfid">--</b></p>
<p>Engine permit: <b id="permit">--</b></p>
<p>Crash: <b id="crash">--</b></p>
<p>Acceleration: <b id="gforce">--</b> g</p>
</div>

<div class="card">
<h2>Simulated Vitals</h2>
<p>Temperature: <b id="temp">--</b> °C</p>
<p>Heart rate: <b id="hr">--</b> bpm</p>
<p>SpO₂: <b id="spo2">--</b>%</p>
<small>These values are simulated, not medical measurements.</small>
</div>

<div class="card">
<h2>Bike Status</h2>
<p>Left distance: <b id="left">--</b> cm</p>
<p>Right distance: <b id="right">--</b> cm</p>
<p>Left blind spot: <b id="leftblind">--</b></p>
<p>Right blind spot: <b id="rightblind">--</b></p>
<p>Speed: <b id="speed">--</b> km/h</p>
<p>GPS: <b id="gps">--</b></p>
<p>Helmet warning LED: <b id="warning">--</b></p>
</div>

<div class="card">
<h2>Demo Call</h2>
<p id="callstatus">No demo call requested</p>
<button id="callbutton" onclick="requestCall()" disabled>
Request demo call
</button>
<p><small>Only enabled when reported speed is below 1 km/h.</small></p>
<p>Last update: <b id="updated">--</b></p>
</div>
</div>

<script>
const el = id => document.getElementById(id);
const show = (id,v) => {
  el(id).textContent = v === undefined || v === null ? "--" : v;
};
const yesNo = v => v === true ? "Yes" : v === false ? "No" : "--";

async function refresh(){
  try{
    const response = await fetch("/api/state", {cache:"no-store"});
    if(!response.ok) throw new Error("HTTP " + response.status);
    const s = await response.json();
    const h = s.helmet || {};
    const b = s.bike || {};

    show("connection", "Website reachable");
    show("alcohol", h.alcohol_raw);
    show("alcoholok", yesNo(h.alcohol_ok));
    show("buckle", h.buckle_closed === undefined ? "--" :
      (h.buckle_closed ? "Fastened" : "Open"));
    show("rfid", yesNo(h.rfid_authorized));
    show("permit", yesNo(h.engine_permit));
    show("crash", yesNo(h.crash_detected));
    show("gforce", h.g_force);
    show("temp", h.temperature_c);
    show("hr", h.heart_rate_bpm);
    show("spo2", h.spo2_percent);
    show("left", b.left_distance_cm);
    show("right", b.right_distance_cm);
    show("leftblind", yesNo(b.left_blind));
    show("rightblind", yesNo(b.right_blind));
    show("speed", b.speed_kmh);
    show("gps", b.latitude === undefined ? "--" :
      b.latitude + ", " + b.longitude);
    show("warning", yesNo(b.blind_spot_signal_to_helmet));
    show("updated", s.updated_at);
    show("callstatus", s.call_status);

    const speed = Number(b.speed_kmh);
    el("callbutton").disabled =
      !Number.isFinite(speed) || speed >= 1;
  }catch(e){
    show("connection", "Dashboard/API error");
    el("callbutton").disabled = true;
  }
}

async function requestCall(){
  el("callbutton").disabled = true;
  try{
    const r = await fetch("/api/call", {method:"POST"});
    const data = await r.json();
    show("callstatus", data.message || "Request finished");
  }catch(e){
    show("callstatus", "Request failed");
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
    app.run(host="0.0.0.0", port=5000)
