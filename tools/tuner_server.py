"""Local web server of the E46 tuner: serves the settings table and runs Apply through tools/tune.py.

usage:
  python tools/tuner_server.py [--port N] [--work <dir>] [--mods <dir>]

Serves tuner/web/index.html at http://127.0.0.1:<port>/ (default port 8765) and a small JSON API:
  GET  /api/state       work folder, base car, game running, installed package, background job
  GET  /api/settings    every setting with default, current value and changed flag
  POST /api/set         {"id": ..., "value": ...}          POST /api/unset  {"id": ...}
  POST /api/reset_all   clears every changed value         POST /api/init   extracts the stock car (background job)
  POST /api/apply       {"mode": "update" | "new_copy", "new_id": ...}   builds and installs (background job)
Binds to 127.0.0.1 only and accepts only the Host headers 127.0.0.1:<port> and localhost:<port>. Every POST needs
the header X-Tuner: 1 and Content-Type application/json. One background job at a time; its state is kept until the
next job starts. Apply refuses to run while AssettoCorsaEVO.exe is running.
<work> defaults to %USERPROFILE%\\ace_modded_cars_work, <mods> to %USERPROFILE%\\Saved Games\\ACE\\mods (see tune.py).

Stdlib only.
"""
import datetime
import http.server
import json
import os
import pathlib
import subprocess
import sys
import threading
import traceback

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import clone_car  # noqa: E402
import tune  # noqa: E402

INDEX = tune.REPO / "tuner" / "web" / "index.html"
DEFAULT_PORT = 8765
GAME_EXE = "AssettoCorsaEVO.exe"
MAX_BODY = 65536
MODES = ("update", "new_copy")
ACCEPTED = ("/api/init", "/api/apply")

CONFIG = {"port": DEFAULT_PORT, "work": None, "mods": None}
JOB = {"kind": None, "state": "idle", "log": [], "result": None, "error": None}
JOB_LOCK = threading.Lock()
STATE_LOCK = threading.Lock()


class ApiError(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status = status
        self.message = message


def mods_dir():
    return os.path.abspath(os.path.expandvars(CONFIG["mods"] or clone_car.DEFAULT_MODS))


def base_present(work, cat):
    car_root = tune.car_root_of(os.path.join(work, "base"), cat["car_id"])
    return os.path.isdir(car_root) and bool(os.listdir(car_root))


def require_base(work, cat):
    if not base_present(work, cat):
        raise ApiError(409, "base car missing, run init")


def game_running():
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq " + GAME_EXE, "/NH", "/FO", "CSV"],
                             capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return False
    return out.returncode == 0 and GAME_EXE.lower() in out.stdout.decode("ascii", "replace").lower()


def installed_info():
    path = os.path.join(mods_dir(), tune.DEFAULT_NEW_ID + ".kspkg")
    info = {"path": path, "exists": os.path.isfile(path), "bytes": None, "modified": None}
    if info["exists"]:
        st = os.stat(path)
        info["bytes"] = st.st_size
        info["modified"] = datetime.datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds")
    return info


def job_snapshot():
    with JOB_LOCK:
        return {"kind": JOB["kind"], "state": JOB["state"], "log": list(JOB["log"]),
                "result": JOB["result"], "error": JOB["error"]}


def claim_job(kind):
    with JOB_LOCK:
        if JOB["state"] == "running":
            raise ApiError(409, "another job is running, wait until it has finished")
        JOB.update(kind=kind, state="running", log=[], result=None, error=None)


def log_line(text):
    with JOB_LOCK:
        JOB["log"].append(text)


def finish_job(state, result=None, error=None):
    with JOB_LOCK:
        JOB.update(state=state, result=result, error=error)


def job_thread(task):
    try:
        result = task()
    except (ValueError, OSError) as e:
        log_line("error: %s" % e)
        finish_job("error", error=str(e))
    except SystemExit as e:
        log_line("error: %s" % e.code)
        finish_job("error", error=str(e.code))
    except Exception as e:
        traceback.print_exc()
        log_line("error: internal error: %s" % e)
        finish_job("error", error="internal error: %s" % e)
    else:
        finish_job("done", result)


def run_job(kind, task):
    claim_job(kind)
    threading.Thread(target=job_thread, args=(task,), daemon=True).start()


def init_task():
    log_line("extracting the stock car from the game package (about 20 s) ...")
    res = tune.init(CONFIG["work"], os.path.expandvars(tune.DEFAULT_GAME))
    log_line("base already present" if res["present"] else "extracted the stock car")
    log_line("%s: %d files, %d folders, %d bytes" % (res["dir"], res["files"], res["dirs"], res["bytes"]))
    return res


def apply_lines(res):
    lines = ["applied %d setting(s)" % len(res["applied"])]
    for a in res["applied"]:
        lines.append("  %s: %s -> %s  [%s]" % (a["id"], tune.fmt(a["old"]), tune.fmt(a["new"]), ", ".join(a["files"])))
    lines.append("package: %s (%d bytes)" % (res["package"], res["size"]))
    if res["installed"]:
        lines.append("installed: %s" % res["installed"])
        lines.append("backup: %s" % (res["backup"] or "no previous install"))
    return lines


def apply_task(mode, new_id):
    def task():
        log_line("building %s (%s), this takes a while ..." % (new_id, mode))
        res = tune.apply(CONFIG["work"], new_id, True, CONFIG["mods"])
        for line in apply_lines(res):
            log_line(line)
        return dict(res, mode=mode)
    return task


def row_json(row, s):
    out = {k: row[k] for k in ("id", "group", "label", "kind", "type", "unit", "description", "verified",
                               "default", "value", "changed", "absent")}
    out.update({k: s[k] for k in ("min", "max", "choices") if k in s})
    return out


def rows_json(work, cat):
    require_base(work, cat)
    return [row_json(r, s) for r, s in zip(tune.effective_rows(work, cat), cat["settings"])]


def row_of(work, cat, setting_id):
    return next(r for r in rows_json(work, cat) if r["id"] == setting_id)


def api_state():
    work, cat = CONFIG["work"], tune.load_catalogue()
    return {"work": work, "base_present": base_present(work, cat), "game_running": game_running(),
            "installed": installed_info(), "stock_id_length": len(cat["car_id"]),
            "default_new_id": tune.DEFAULT_NEW_ID, "job": job_snapshot()}


def api_settings():
    with STATE_LOCK:
        return rows_json(CONFIG["work"], tune.load_catalogue())


def api_set(body):
    work, cat = CONFIG["work"], tune.load_catalogue()
    setting_id, value = body.get("id"), body.get("value")
    if not isinstance(setting_id, str) or type(value) not in (str, int, float):
        raise ApiError(400, "need id (text) and value (text or number)")
    require_base(work, cat)
    with STATE_LOCK:
        try:
            res = tune.set_value(work, setting_id, value, cat)
        except ValueError as e:
            raise ApiError(400, str(e))
        return {"row": row_of(work, cat, setting_id), "warnings": res["warnings"]}


def api_unset(body):
    work, cat = CONFIG["work"], tune.load_catalogue()
    setting_id = body.get("id")
    if not isinstance(setting_id, str):
        raise ApiError(400, "need id (text)")
    require_base(work, cat)
    with STATE_LOCK:
        try:
            tune.unset_value(work, setting_id, cat)
        except ValueError as e:
            raise ApiError(400, str(e))
        return {"row": row_of(work, cat, setting_id)}


def api_reset_all(body):
    with STATE_LOCK:
        tune.save_state(CONFIG["work"], {})
    return {"ok": True}


def api_init(body):
    run_job("init", init_task)
    return {"job": "started"}


def check_new_id(new_id, car_id, work):
    if not isinstance(new_id, str) or not new_id:
        raise ApiError(400, "new_id is required for mode new_copy")
    if new_id == tune.DEFAULT_NEW_ID:
        raise ApiError(400, "new id equals %s, the id used by Apply (update), pick another one" % tune.DEFAULT_NEW_ID)
    try:
        clone_car.validate(car_id, new_id, os.path.join(work, "build", "unused"))
    except ValueError as e:
        raise ApiError(400, str(e))
    return new_id


def api_apply(body):
    work, cat = CONFIG["work"], tune.load_catalogue()
    mode = body.get("mode")
    if mode not in MODES:
        raise ApiError(400, 'mode must be "update" or "new_copy"')
    new_id = tune.DEFAULT_NEW_ID if mode == "update" else check_new_id(body.get("new_id"), cat["car_id"], work)
    require_base(work, cat)
    if game_running():
        raise ApiError(409, "close the game first, %s is running" % GAME_EXE)
    run_job("apply", apply_task(mode, new_id))
    return {"job": "started"}


GET_ROUTES = {"/api/state": api_state, "/api/settings": api_settings}
POST_ROUTES = {"/api/set": api_set, "/api/unset": api_unset, "/api/reset_all": api_reset_all,
               "/api/init": api_init, "/api/apply": api_apply}


def check_host(host):
    port = CONFIG["port"]
    if (host or "").lower() not in ("127.0.0.1:%d" % port, "localhost:%d" % port):
        raise ApiError(403, "forbidden host")


def check_post_headers(headers):
    if headers.get("X-Tuner") != "1":
        raise ApiError(403, "missing header X-Tuner: 1")
    if headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
        raise ApiError(403, "Content-Type must be application/json")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "TunerServer"

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "bad Content-Length")
        if length < 0 or length > MAX_BODY:
            raise ApiError(400, "request body too large")
        raw = self.rfile.read(length)
        if not raw.strip():
            return {}
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(400, "body is not valid JSON")
        if not isinstance(body, dict):
            raise ApiError(400, "body must be a JSON object")
        return body

    def dispatch(self, method):
        check_host(self.headers.get("Host"))
        path = self.path.split("?", 1)[0]
        if method == "POST":
            check_post_headers(self.headers)
        if method == "GET" and path == "/":
            with open(INDEX, "rb") as f:
                return 200, f.read()
        route = (GET_ROUTES if method == "GET" else POST_ROUTES).get(path)
        if route is None:
            raise ApiError(404, "not found")
        payload = route(self.read_body()) if method == "POST" else route()
        return (202 if path in ACCEPTED else 200), payload

    def handle_request(self, method):
        try:
            status, payload = self.dispatch(method)
        except ApiError as e:
            status, payload = e.status, {"error": e.message}
        except (ValueError, OSError) as e:
            status, payload = 500, {"error": str(e)}
        except Exception as e:
            traceback.print_exc()
            status, payload = 500, {"error": "internal error: %s" % type(e).__name__}
        self.send_payload(status, payload)

    def send_payload(self, status, payload):
        if isinstance(payload, bytes):
            data, ctype = payload, "text/html; charset=utf-8"
        else:
            data, ctype = json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        if "/api/state" not in getattr(self, "path", ""):
            http.server.BaseHTTPRequestHandler.log_message(self, fmt, *args)


def parse_port(text):
    if not text.isdigit() or not 1 <= int(text) <= 65535:
        raise ValueError("--port must be a number from 1 to 65535")
    return int(text)


def main():
    try:
        pos, opts = tune.parse_args(sys.argv[1:], ("port", "work", "mods"))
        if pos:
            sys.exit(__doc__.split("\n\n")[1])
        tune.load_catalogue()
        port = parse_port(opts.get("port", str(DEFAULT_PORT)))
        CONFIG.update(port=port, work=tune.work_dir(opts.get("work")), mods=opts.get("mods"))
        server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)
    print("tuner running on http://127.0.0.1:%d/" % port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
