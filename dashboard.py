import sys, sqlite3
from pathlib import Path
from flask import Flask, jsonify

DB_NAME = sys.argv[1] if len(sys.argv) > 1 else "gate_log.db"
DB_PATH = Path(__file__).resolve().parent / DB_NAME
HOST, PORT = "127.0.0.1", 5000     # "0.0.0.0" lets a phone on the same Wi-Fi connect

CLASSES = ["authorized", "unknown", "visitor", "delivery-person",
           "facecovered", "photo-spoof", "loitering"]

app = Flask(__name__)

def query(sql, args=()):
    """Read-only query. Returns [] if the file or table does not exist yet."""
    try:
        conn = sqlite3.connect(f"{DB_PATH.as_uri()}?mode=ro", uri=True)
        try:
            return conn.execute(sql, args).fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return []

def scalar(sql, args=()):
    rows = query(sql, args)
    return rows[0][0] if rows else 0

@app.route("/api/data")
def api_data():
    recent = query("SELECT timestamp, label, confidence, decision "
                   "FROM events ORDER BY id DESC LIMIT 15")
    counts = dict(query("SELECT decision, COUNT(*) FROM events GROUP BY decision"))
    live = []
    for c in CLASSES:
        rows = query("SELECT COUNT(*), COALESCE(SUM(correct), 0) "
                     "FROM live_trials WHERE actual = ?", (c,))
        n, ok = rows[0] if rows else (0, 0)
        live.append({"cls": c, "trials": n, "correct": ok})
    return jsonify(
        recent=[{"time": t, "label": l, "conf": cf, "decision": d} for t, l, cf, d in recent],
        counts=counts,
        total=sum(counts.values()),
        live=live,
        fa=scalar("SELECT COUNT(*) FROM live_trials "
                  "WHERE actual != 'authorized' AND decision = 'ACCESS GRANTED'"),
        fa_total=scalar("SELECT COUNT(*) FROM live_trials WHERE actual != 'authorized'"),
        fr=scalar("SELECT COUNT(*) FROM live_trials "
                  "WHERE actual = 'authorized' AND decision != 'ACCESS GRANTED'"),
        fr_total=scalar("SELECT COUNT(*) FROM live_trials WHERE actual = 'authorized'"),
        db=DB_NAME,
    )

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Gate Dashboard</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #f2f4f7; color: #1b1f24; }
  header { background: #1b2a41; color: #fff; padding: 14px 20px; }
  header h1 { margin: 0; font-size: 1.2rem; }
  header small { opacity: .7; }
  main { max-width: 960px; margin: 0 auto; padding: 16px; }
  #status { border-radius: 10px; padding: 22px; color: #fff; background: #777; margin-bottom: 16px; }
  #status .big { font-size: 2rem; font-weight: 700; }
  #status .sub { opacity: .9; margin-top: 4px; }
  .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; margin-bottom: 16px; }
  .card { background: #fff; border-radius: 10px; padding: 12px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .card .n { font-size: 1.6rem; font-weight: 700; }
  .card .t { font-size: .8rem; color: #555; }
  section { background: #fff; border-radius: 10px; padding: 14px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,.08); overflow-x: auto; }
  h2 { margin: 0 0 10px; font-size: 1rem; }
  table { width: 100%; border-collapse: collapse; font-size: .9rem; }
  th, td { text-align: left; padding: 6px 8px; border-bottom: 1px solid #e6e8eb; }
  th { color: #555; font-weight: 600; }
  .pill { color: #fff; border-radius: 12px; padding: 2px 10px; font-size: .8rem; white-space: nowrap; }
  .note { font-size: .85rem; color: #555; margin-top: 8px; }
</style>
</head>
<body>
<header><h1>Smart Gate Dashboard</h1><small id="src"></small></header>
<main>
  <div id="status"><div class="big">Loading...</div></div>
  <div class="cards" id="cards"></div>
  <section><h2>Recent events</h2><table id="events"></table></section>
  <section><h2>Live test results</h2><table id="live"></table><div class="note" id="risk"></div></section>
</main>
<script>
const COLORS = {"ACCESS GRANTED": "#1e9e4a", "ACCESS DENIED": "#d33232",
                "NOTIFY OWNER": "#e8890c", "LOITERING ALERT": "#9b1c1c"};
const color = d => COLORS[d] || "#777";
function esc(s) { const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }

async function refresh() {
  try {
    const d = await (await fetch("/api/data")).json();
    document.getElementById("src").textContent = "Database: " + d.db + " | updates every 3 s";

    const st = document.getElementById("status");
    if (d.recent.length) {
      const e = d.recent[0];
      st.style.background = color(e.decision);
      st.innerHTML = '<div class="big">' + esc(e.decision) + '</div>' +
        '<div class="sub">Last logged: ' + esc(e.label) + ' (' + Math.round(e.conf * 100) +
        '%) at ' + esc(e.time) + '</div>';
    } else {
      st.style.background = "#777";
      st.innerHTML = '<div class="big">No events yet</div><div class="sub">Run smart_gate.py to start logging.</div>';
    }

    const c = d.counts;
    const cards = [["Total events", d.total], ["Granted", c["ACCESS GRANTED"] || 0],
                   ["Notify owner", c["NOTIFY OWNER"] || 0], ["Denied", c["ACCESS DENIED"] || 0],
                   ["Loitering", c["LOITERING ALERT"] || 0]];
    document.getElementById("cards").innerHTML = cards.map(x =>
      '<div class="card"><div class="n">' + x[1] + '</div><div class="t">' + x[0] + '</div></div>').join("");

    document.getElementById("events").innerHTML =
      "<tr><th>Time</th><th>Detected</th><th>Confidence</th><th>Decision</th></tr>" +
      d.recent.map(e => "<tr><td>" + esc(e.time) + "</td><td>" + esc(e.label) + "</td><td>" +
        Math.round(e.conf * 100) + '%</td><td><span class="pill" style="background:' + color(e.decision) +
        '">' + esc(e.decision) + "</span></td></tr>").join("");

    document.getElementById("live").innerHTML =
      "<tr><th>Class</th><th>Trials</th><th>Correct</th><th>Accuracy</th></tr>" +
      d.live.map(r => "<tr><td>" + esc(r.cls) + "</td><td>" + r.trials + "</td><td>" + r.correct +
        "</td><td>" + (r.trials ? Math.round(100 * r.correct / r.trials) + "%" : "n/a") + "</td></tr>").join("");
    document.getElementById("risk").textContent =
      "False accepts: " + d.fa + "/" + d.fa_total + "   |   False rejects: " + d.fr + "/" + d.fr_total;
  } catch (err) {
    const st = document.getElementById("status");
    st.style.background = "#777";
    st.innerHTML = '<div class="big">Connection lost</div>';
  }
}
refresh();
setInterval(refresh, 3000);
</script>
</body>
</html>"""

@app.route("/")
def index():
    return PAGE

if __name__ == "__main__":
    print(f"Dashboard on http://{HOST}:{PORT}  (database: {DB_PATH})")
    app.run(host=HOST, port=PORT)