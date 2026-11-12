"""Local web server of the tuner: serves the settings table and runs Apply through tools/tune.py.

usage:
  python tools/tuner_server.py [--port N] [--work <dir>] [--mods <dir>] [--game <content.kspkg>]

Serves tuner/web/index.html at http://127.0.0.1:<port>/ (default port 8765, allowed 1024 to 65535) and a small JSON API:
  GET  /api/state       work folder, base car, game running, installed package, background job; every car of the game
                        (id, label, display_name, extracted, tested, new_id, installed) and the number of applicable and
                        hidden settings of the car (null while the base is missing or being extracted)
  GET  /api/settings    every setting applicable to the car, with default, current value and changed flag
                        (copies_differ, plus copy_values when the copies of the value differ in the stock data;
                        "ui": "header" on name_suffix: the page shows it under its title, not in the table)
  POST /api/set         {"id": ..., "value": ...}          POST /api/unset  {"id": ...}
                        (value: text, number, or true/false for the settings of type bool, which are on/off switches
                        and appear in the rows with type "bool" and true/false as default and value)
  POST /api/reset_all   clears every changed value         POST /api/init   extracts the stock car (background job)
  POST /api/apply       {"mode": "update" | "new_copy", "new_id": ...}   builds and installs (background job)
Every route takes an optional car id of the game (the list is cached in <work>/cars_index.json, see tune.py; without it
and without the game package only the tested cars of tuner/cars.json): the query parameter ?car=<id> on GET, the field
"car" in the JSON body on POST (any other id is a 400 error). Without it the default car of tuner/cars.json is used.

Answers: JSON {"error": text} with 400 (bad input, unknown car), 403 (wrong Host, missing X-Tuner or Content-Type), 404 (unknown path), 409 (base car missing, another job running, edit while a job runs, game running, mods folder not expandable), 500 (internal error); /api/init and /api/apply answer 202 {"job": "started"} and the page polls GET /api/state; every other route answers 200. Other HTTP methods get the standard 501 page.

The job state (GET /api/state "job") is global, there is one background job at a time for all cars. The state answer
also lists the car ("car", "cars") and the installed package of that car; the old single-car layout of the work folder
is moved into the default car's folder when the server starts.
Binds to 127.0.0.1 only and accepts only the Host headers 127.0.0.1:<port> and localhost:<port>. Every POST needs
the header X-Tuner: 1 and Content-Type application/json. One background job at a time; its state is kept until the
next job starts. Apply refuses to run while AssettoCorsaEVO.exe is running.
<work> defaults to %USERPROFILE%\\ace_modded_cars_work, <mods> to %USERPROFILE%\\Saved Games\\ACE\\mods, <game> to the
Steam default content.kspkg (see tune.py). Wrong arguments print the usage block and exit 2.
Ctrl+C while a job runs waits for it; a second Ctrl+C aborts it.

Stdlib only.
"""
import datetime
import http.server
import json
import os
import pathlib
import socket
import sys
import threading
import time
import traceback
import urllib.parse

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import clone_car  # noqa: E402
import kspkg  # noqa: E402
import tune  # noqa: E402

INDEX = tune.REPO / "tuner" / "web" / "index.html"
DEFAULT_PORT = 8765
GAME_CHECK_SECONDS = 4.0
MAX_BODY = 65536
MODES = ("update", "new_copy")
# routes that start a background job answer 202 instead of 200
ACCEPTED = ("/api/init", "/api/apply")

CONFIG = {"port": DEFAULT_PORT, "work": None, "mods": None, "game": tune.DEFAULT_GAME}
JOB = {"kind": None, "state": "idle", "log": [], "result": None, "error": None, "thread": None}
JOB_LOCK = threading.Lock()
# STATE_LOCK serializes tune_state.json edits and row builds; JOB_LOCK guards the JOB dict (the job thread does not take STATE_LOCK)
STATE_LOCK = threading.Lock()
# the poll path asks for the game at most every GAME_CHECK_SECONDS: [time of the last check, its result]
GAME_CHECK = [float("-inf"), False]


class ApiError(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status = status
        self.message = message


def mods_dir():
    return clone_car.expand(CONFIG["mods"] or clone_car.DEFAULT_MODS)


def require_mods():
    try:
        return mods_dir()
    except ValueError:
        raise ApiError(409, "cannot expand the mods folder %r" % (CONFIG["mods"] or clone_car.DEFAULT_MODS)) from None


def base_present(work, car):
    car_root = kspkg.long_path(tune.car_root_of(tune.base_dir(work, car), car))
    return os.path.isdir(car_root) and bool(os.listdir(car_root))


def require_base(work, car):
    if not base_present(work, car):
        raise ApiError(409, "base car missing, run init")


game_running = tune.game_running


def game_running_cached():
    now = time.monotonic()
    if now - GAME_CHECK[0] > GAME_CHECK_SECONDS:
        GAME_CHECK[:] = [now, game_running()]
    return GAME_CHECK[1]


def installed_info(car):
    path = os.path.join(mods_dir(), tune.new_id_for(car) + ".kspkg")
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
    thread = threading.Thread(target=job_thread, args=(task,), daemon=True)
    with JOB_LOCK:
        JOB["thread"] = thread
    thread.start()


def refuse_while_job_runs():
    if job_snapshot()["state"] == "running":
        raise ApiError(409, "a job is running, wait until it has finished")


def init_task(car):
    def task():
        log_line("extracting the stock car from the game package (about 20 s) ...")
        res = tune.init(CONFIG["work"], car, CONFIG["game"])
        log_line("base already present" if res["present"] else "extracted the stock car")
        log_line("%s: %d files, %d folders, %d bytes" % (res["dir"], res["files"], res["dirs"], res["bytes"]))
        return res
    return task


def apply_lines(res):
    lines = ["applied %d setting(s)" % len(res["applied"])]
    for a in res["applied"]:
        lines.append("  %s: %s -> %s  [%s]" % (a["id"], tune.fmt(a["old"]), tune.fmt(a["new"]), ", ".join(a["files"])))
    lines += res["notes"]
    lines.append("package: %s (%d bytes)" % (res["package"], res["size"]))
    if res["installed"]:
        lines.append("installed: %s" % res["installed"])
        lines.append("backup: %s" % (res["backup"] or "no previous install"))
    return lines


def apply_task(car, mode, new_id):
    def task():
        log_line("building %s (%s), this takes a while ..." % (new_id, mode))
        res = tune.apply(CONFIG["work"], car, new_id, True, CONFIG["mods"], game=CONFIG["game"])
        for line in apply_lines(res):
            log_line(line)
        return dict(res, mode=mode)
    return task


def row_json(row, s):
    out = {k: row[k] for k in ("id", "group", "label", "kind", "type", "unit", "description", "verified",
                               "default", "value", "changed", "absent", "copies_differ")}
    out.update({k: s[k] for k in ("min", "max", "choices", "ui") if k in s})
    if row["copies_differ"]:
        out["copy_values"] = row["copy_values"]
    return out


def rows_json(work, car, cat):
    require_base(work, car)
    return [row_json(r, tune.find_setting(cat, r["id"])) for r in tune.effective_rows(work, car, cat)]


def row_of(work, car, cat, setting_id):
    require_base(work, car)
    return row_json(tune.effective_row(work, car, setting_id, cat), tune.find_setting(cat, setting_id))


def settings_counts(work, car):
    job = job_snapshot()
    if not base_present(work, car) or (job["kind"] == "init" and job["state"] == "running"):
        return None, None
    rows = tune.resolve_defaults(work, car, hidden=True)
    applicable = sum(1 for r in rows if r["applicable"])
    return applicable, len(rows) - applicable


def api_state(car):
    require_mods()
    work, cars = CONFIG["work"], tune.load_cars()
    applicable, hidden = settings_counts(work, car)
    return {"work": work, "car": car, "default_car": cars["default"],
            "cars": [{k: c[k] for k in ("id", "label", "display_name", "extracted", "tested", "new_id", "installed")}
                     for c in tune.list_cars(work, CONFIG["mods"], game=CONFIG["game"], sizes=False)],
            "base_present": base_present(work, car), "game_running": game_running_cached(),
            "installed": installed_info(car), "stock_id_length": len(car),
            "default_new_id": tune.new_id_for(car), "settings_applicable": applicable, "settings_hidden": hidden,
            "job": job_snapshot()}


def api_settings(car):
    with STATE_LOCK:
        return rows_json(CONFIG["work"], car, tune.load_catalogue())


def api_set(car, body):
    work, cat = CONFIG["work"], tune.load_catalogue()
    setting_id, value = body.get("id"), body.get("value")
    if not isinstance(setting_id, str) or type(value) not in (str, int, float, bool):
        raise ApiError(400, "need id (text) and value (text, number or true/false)")
    refuse_while_job_runs()
    require_base(work, car)
    with STATE_LOCK:
        try:
            res = tune.set_value(work, car, setting_id, value, cat)
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        return {"row": row_of(work, car, cat, setting_id), "warnings": res["warnings"]}


def api_unset(car, body):
    work, cat = CONFIG["work"], tune.load_catalogue()
    setting_id = body.get("id")
    if not isinstance(setting_id, str):
        raise ApiError(400, "need id (text)")
    refuse_while_job_runs()
    require_base(work, car)
    with STATE_LOCK:
        try:
            tune.unset_value(work, car, setting_id, cat)
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        return {"row": row_of(work, car, cat, setting_id)}


def api_reset_all(car, body):
    refuse_while_job_runs()
    require_base(CONFIG["work"], car)
    with STATE_LOCK:
        tune.save_state(CONFIG["work"], car, {})
    return {"ok": True}


def api_init(car, body):
    run_job("init", init_task(car))
    return {"job": "started"}


def check_new_id(new_id, car_id, work):
    if not isinstance(new_id, str) or not new_id:
        raise ApiError(400, "new_id is required for mode new_copy")
    if new_id == tune.new_id_for(car_id):
        raise ApiError(400, "new id equals %s, the id used by Apply (update), pick another one" % new_id)
    try:
        clone_car.validate(car_id, new_id, os.path.join(tune.build_dir(work, car_id), "unused"))
    except ValueError as e:
        raise ApiError(400, str(e)) from None
    return new_id


def api_apply(car, body):
    work = CONFIG["work"]
    mode = body.get("mode")
    if mode not in MODES:
        raise ApiError(400, 'mode must be "update" or "new_copy"')
    new_id = tune.new_id_for(car) if mode == "update" else check_new_id(body.get("new_id"), car, work)
    require_base(work, car)
    require_mods()
    if game_running():
        raise ApiError(409, "close the game first, %s is running" % tune.GAME_EXE)
    run_job("apply", apply_task(car, mode, new_id))
    return {"job": "started"}


def request_car(value, query):
    if value is None:
        value = (urllib.parse.parse_qs(query).get("car") or [None])[0]
    if value is not None and not isinstance(value, str):
        raise ApiError(400, "car must be text")
    try:
        return tune.pick_car(tune.load_cars(), value, tune.load_cars_index(CONFIG["work"], CONFIG["game"]))
    except ValueError as e:
        raise ApiError(400, str(e)) from None


GET_ROUTES = {"/api/state": api_state, "/api/settings": api_settings}
POST_ROUTES = {"/api/set": api_set, "/api/unset": api_unset, "/api/reset_all": api_reset_all,
               "/api/init": api_init, "/api/apply": api_apply}


# DNS rebinding: a hostile site resolving to 127.0.0.1 sends its own Host header
def check_host(host):
    port = CONFIG["port"]
    if (host or "").lower() not in ("127.0.0.1:%d" % port, "localhost:%d" % port):
        raise ApiError(403, "forbidden host")


# a cross-site form or no-cors fetch cannot send X-Tuner or application/json without a preflight, and no CORS is answered
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
            raise ApiError(400, "bad Content-Length") from None
        if length < 0 or length > MAX_BODY:
            raise ApiError(400, "request body too large")
        raw = self.rfile.read(length)
        if not raw.strip():
            return {}
        try:
            body = json.loads(raw.decode("utf-8"))
        except ValueError:
            raise ApiError(400, "body is not valid JSON") from None
        if not isinstance(body, dict):
            raise ApiError(400, "body must be a JSON object")
        return body

    def dispatch(self, method):
        check_host(self.headers.get("Host"))
        path, _, query = self.path.partition("?")
        if method == "POST":
            check_post_headers(self.headers)
        if method == "GET" and path == "/":
            with open(INDEX, "rb") as f:
                return 200, f.read()
        route = (GET_ROUTES if method == "GET" else POST_ROUTES).get(path)
        if route is None:
            raise ApiError(404, "not found")
        if method == "POST":
            body = self.read_body()
            payload = route(request_car(body.get("car"), query), body)
        else:
            payload = route(request_car(None, query))
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

    def end_headers(self):
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        http.server.BaseHTTPRequestHandler.end_headers(self)

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

    # the page polls /api/state every few seconds; keep that out of the console
    def log_request(self, code="-", size="-"):
        if getattr(self, "path", "").partition("?")[0] == "/api/state" and str(code) == "200":
            return
        http.server.BaseHTTPRequestHandler.log_request(self, code, size)


class Server(http.server.ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if os.name == "nt":
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        http.server.ThreadingHTTPServer.server_bind(self)


def parse_port(text):
    if not text.isdigit() or not 1024 <= int(text) <= 65535:
        raise ValueError("--port must be a number from 1024 to 65535")
    return int(text)


def usage():
    print(__doc__.split("\n\n")[1])
    sys.exit(2)


def wait_for_job():
    thread = JOB["thread"]
    if job_snapshot()["state"] != "running" or thread is None:
        return
    print("a job is still running, wait for it or press Ctrl+C again to abort it ...", flush=True)
    try:
        while thread.is_alive():
            thread.join(0.5)
    except KeyboardInterrupt:
        pass


def main():
    try:
        pos, opts = kspkg.parse_args(sys.argv[1:], ("port", "work", "mods", "game"))
    except ValueError:
        usage()
    if pos:
        usage()
    try:
        tune.load_catalogue()
        port = parse_port(opts.get("port", str(DEFAULT_PORT)))
        CONFIG.update(port=port, work=tune.work_dir(opts.get("work")), mods=opts.get("mods"),
                      game=os.path.expandvars(opts.get("game", tune.DEFAULT_GAME)))
        default_car = tune.load_cars()["default"]
        moved = tune.migrate_old_layout(CONFIG["work"], default_car)
        if moved:
            print("moved the old single-car layout of %s into %s: %s" % (
                CONFIG["work"], tune.car_work(CONFIG["work"], default_car), ", ".join(moved)))
        server = Server(("127.0.0.1", port), Handler)
        tune.load_cars_index(CONFIG["work"], CONFIG["game"])
    except (ValueError, OSError) as e:
        sys.exit("error: %s" % e)
    print("tuner running on http://127.0.0.1:%d/" % port, flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        wait_for_job()
        print("stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
