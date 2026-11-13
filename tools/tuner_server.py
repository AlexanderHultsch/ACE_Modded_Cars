"""Local web server of the tuner: serves the settings table and runs Apply through tools/tune.py.

usage:
  python tools/tuner_server.py [--port N] [--work <dir>] [--mods <dir>] [--game <content.kspkg>]

Serves tuner/web/index.html at http://127.0.0.1:<port>/ (default port 8765, allowed 1024 to 65535) and a small JSON API:
  GET  /api/state       work folder, base car, game running, installed package, background job; every car of the game
                        (id, label, display_name, extracted, tested, new_id, installed) and the number of applicable and
                        hidden settings of the car (null while the base is missing or being extracted); the selected
                        tune ("tune"); the modded cars of all stock cars ("modded": id, stock, label, name_suffix,
                        default, installed, built; "modded_error" and an empty list when they cannot be read);
                        "default_tune_taken" (the default tune of this car exists), "proposed_new_id" (the id the next
                        modded car made from the draft gets, null when none is free) and "proposed_suffix" (its name
                        suffix); "installed" is the package of the selected modded car
  GET  /api/settings    every setting applicable to the car, with default, current value and changed flag
                        (copies_differ, plus copy_values when the copies of the value differ in the stock data;
                        "ui": "header" on name_suffix: the page shows it under its title, not in the table)
  POST /api/set         {"id": ..., "value": ...}          POST /api/unset  {"id": ...}
                        (value: text, number, or true/false for the settings of type bool, which are on/off switches
                        and appear in the rows with type "bool" and true/false as default and value)
  POST /api/reset_all   clears every changed value         POST /api/init   extracts the stock car (background job)
  POST /api/duplicate   {"tune": source, "new_id": ..., "suffix": ...}   copies a modded car or the draft to a new modded
                        car (new_id and suffix are optional, automatic when left out); answers {"id", "stock", "name_suffix"}
  POST /api/apply       {"tune": ..., "new_id": ..., "suffix": ...}   builds and installs (background job): a modded car
                        (without "tune": the default one, which must exist) is updated, the draft ("tune": "draft") creates a new modded car (new_id and suffix are optional,
                        automatic when left out; ignored when a modded car is updated) and builds it, the draft is
                        cleared after a successful build; the job result has new_id, tune, name_suffix and created
Every route takes an optional car id of the game (the list is cached in <work>/cars_index.json, see tune.py; without it
and without the game package only the tested cars of tuner/cars.json): the query parameter ?car=<id> on GET, the field
"car" in the JSON body on POST (any other id is a 400 error). Without it the default car of tuner/cars.json is used.
Every route also takes an optional tune next to the car (?tune=<x> on GET, the field "tune" on POST): absent or null is
the default tune of the car (the modded car <new_id>), "draft" the draft of the base car (the values of the base car
that are not saved as a modded car yet), any other value the id of a modded car of that car (400 otherwise).

Answers: JSON {"error": text} with 400 (bad input, unknown car or modded car, malformed JSON, new id or name suffix refused), 403 (wrong Host, missing X-Tuner), 404 (unknown path), 405 (any method but GET and POST, with the header Allow: GET, POST), 413 (body over 65536 bytes), 415 (Content-Type is not application/json), 409 (base car missing, another job running, edit or duplicate while a job runs, game running, mods folder not expandable), 500 (internal error); /api/init and /api/apply answer 202 {"job": "started"} and the page polls GET /api/state; every other route answers 200.

The job state (GET /api/state "job") is global, there is one background job at a time for all cars. The state answer
also lists the car ("car", "cars") and the installed package of the selected modded car; the old single-car layout of the work folder
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
# routes that start a background job answer 202 instead of 200
ACCEPTED = ("/api/init", "/api/apply")

CONFIG = {"port": DEFAULT_PORT, "work": None, "mods": None, "game": tune.DEFAULT_GAME}
JOB = {"kind": None, "state": "idle", "log": [], "result": None, "error": None, "thread": None}
JOB_LOCK = threading.Lock()
# STATE_LOCK serializes tune_state.json edits and row builds; JOB_LOCK guards the JOB dict (the job thread takes STATE_LOCK only to clear the draft)
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


def installed_info(car, tune_id=None):
    path = os.path.join(mods_dir(), (tune.new_id_for(car) if tune_id in (None, tune.DRAFT) else tune_id) + ".kspkg")
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


def apply_task(car, new_id, created):
    def task():
        log_line("building %s, this takes a while ..." % new_id)
        res = tune.apply(CONFIG["work"], car, new_id, True, CONFIG["mods"], game=CONFIG["game"])
        for line in apply_lines(res):
            log_line(line)
        if created:
            with STATE_LOCK:
                tune.save_state(CONFIG["work"], car, {}, tune.DRAFT)
        return dict(res, created=created)
    return task


def row_json(row, s):
    out = {k: row[k] for k in ("id", "group", "label", "kind", "type", "unit", "description", "verified",
                               "default", "value", "changed", "absent", "copies_differ")}
    out.update({k: s[k] for k in ("min", "max", "choices", "ui") if k in s})
    if row["copies_differ"]:
        out["copy_values"] = row["copy_values"]
    return out


def rows_json(work, car, cat, tune_id=None):
    require_base(work, car)
    return [row_json(r, tune.find_setting(cat, r["id"])) for r in tune.effective_rows(work, car, cat, tune=tune_id)]


def row_of(work, car, cat, setting_id, tune_id=None):
    require_base(work, car)
    return row_json(tune.effective_row(work, car, setting_id, cat, tune=tune_id), tune.find_setting(cat, setting_id))


def settings_counts(work, car):
    job = job_snapshot()
    if not base_present(work, car) or (job["kind"] == "init" and job["state"] == "running"):
        return None, None
    rows = tune.resolve_defaults(work, car, hidden=True)
    applicable = sum(1 for r in rows if r["applicable"])
    return applicable, len(rows) - applicable


def or_none(fn, *args):
    try:
        return fn(*args)
    except ValueError:
        return None


def tune_proposals(work, car):
    try:
        taken = any(t["default"] for t in tune.list_tunes(work, car))
    except ValueError:
        return {"default_tune_taken": False, "proposed_new_id": None, "proposed_suffix": None}
    new_id = or_none(tune.free_tune_id, work, car, mods_dir()) if taken else tune.new_id_for(car)
    return {"default_tune_taken": taken, "proposed_new_id": new_id,
            "proposed_suffix": or_none(tune.free_suffix, work, car, tune.name_suffix_setting()["default"])}


def modded_cars(work):
    try:
        return {"modded": tune.list_modded(work, mods_dir())}
    except ValueError as e:
        return {"modded": [], "modded_error": str(e)}


def api_state(car, tune_id):
    require_mods()
    work, cars = CONFIG["work"], tune.load_cars()
    applicable, hidden = settings_counts(work, car)
    return dict({"work": work, "car": car, "tune": tune_id, "default_car": cars["default"],
                 "cars": [{k: c[k] for k in ("id", "label", "display_name", "extracted", "tested", "new_id", "installed")}
                          for c in tune.list_cars(work, CONFIG["mods"], game=CONFIG["game"], sizes=False)],
                 "base_present": base_present(work, car), "game_running": game_running_cached(),
                 "installed": installed_info(car, tune_id), "stock_id_length": len(car),
                 "default_new_id": tune.new_id_for(car), "settings_applicable": applicable, "settings_hidden": hidden,
                 "job": job_snapshot()}, **modded_cars(work), **tune_proposals(work, car))


def api_settings(car, tune_id):
    with STATE_LOCK:
        return rows_json(CONFIG["work"], car, tune.load_catalogue(), tune_id)


def api_set(car, body):
    work, cat, tune_id = CONFIG["work"], tune.load_catalogue(), body.get("tune")
    setting_id, value = body.get("id"), body.get("value")
    if not isinstance(setting_id, str) or type(value) not in (str, int, float, bool):
        raise ApiError(400, "need id (text) and value (text, number or true/false)")
    refuse_while_job_runs()
    require_base(work, car)
    with STATE_LOCK:
        try:
            res = tune.set_value(work, car, setting_id, value, cat, tune=tune_id)
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        return {"row": row_of(work, car, cat, setting_id, tune_id), "warnings": res["warnings"]}


def api_unset(car, body):
    work, cat, tune_id = CONFIG["work"], tune.load_catalogue(), body.get("tune")
    setting_id = body.get("id")
    if not isinstance(setting_id, str):
        raise ApiError(400, "need id (text)")
    refuse_while_job_runs()
    require_base(work, car)
    with STATE_LOCK:
        try:
            tune.unset_value(work, car, setting_id, cat, tune=tune_id)
        except ValueError as e:
            raise ApiError(400, str(e)) from None
        return {"row": row_of(work, car, cat, setting_id, tune_id)}


def api_reset_all(car, body):
    work, tune_id = CONFIG["work"], body.get("tune")
    refuse_while_job_runs()
    require_base(work, car)
    with STATE_LOCK:
        state = {}
        if not (tune.is_default_tune(car, tune_id) or tune_id == tune.DRAFT):
            suffix_id = tune.name_suffix_setting()["id"]
            kept = tune.load_state(work, car, tune_id)
            if suffix_id in kept:
                state[suffix_id] = kept[suffix_id]
        tune.save_state(work, car, state, tune_id)
    return {"ok": True}


def api_init(car, body):
    run_job("init", init_task(car))
    return {"job": "started"}


def optional_text(body, field):
    value = body.get(field)
    if value is not None and not isinstance(value, str):
        raise ApiError(400, "%s must be text" % field)
    return value


def api_duplicate(car, body):
    work, tune_id = CONFIG["work"], body.get("tune")
    new_id, suffix = optional_text(body, "new_id"), optional_text(body, "suffix")
    refuse_while_job_runs()
    require_base(work, car)
    mods = require_mods()
    with STATE_LOCK:
        try:
            return tune.duplicate_tune(work, car, tune_id, new_id, suffix, mods)
        except ValueError as e:
            raise ApiError(400, str(e)) from None


def update_target(work, car, tune_id):
    if tune_id is None:
        tune_id = tune.new_id_for(car)
        if not any(t["default"] for t in tune.list_tunes(work, car)):
            raise ApiError(400, "no modded car selected, pick one or use the draft of the car to create it")
    with STATE_LOCK:
        suffix = tune.state_suffix(tune.load_state(work, car, tune_id), tune.name_suffix_setting())
        owner = tune.suffix_owner(work, car, suffix, exclude=tune_id)
    if owner:
        raise ApiError(400, "name suffix %s is already used by %s" % (suffix, owner))
    return tune_id


def new_target(work, car, new_id, suffix):
    with STATE_LOCK:
        try:
            return tune.new_tune_from_draft(work, car, suffix, new_id, mods_dir())["id"]
        except ValueError as e:
            raise ApiError(400, str(e)) from None


def api_apply(car, body):
    work, tune_id = CONFIG["work"], body.get("tune")
    draft = tune_id == tune.DRAFT
    new_id, suffix = (optional_text(body, "new_id"), optional_text(body, "suffix")) if draft else (None, None)
    require_base(work, car)
    require_mods()
    if game_running():
        raise ApiError(409, "close the game first, %s is running" % tune.GAME_EXE)
    if draft:
        refuse_while_job_runs()
        target = new_target(work, car, new_id, suffix)
    else:
        target = update_target(work, car, tune_id)
    run_job("apply", apply_task(car, target, draft))
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


def request_tune(value, query, car):
    if value is None:
        value = (urllib.parse.parse_qs(query).get("tune") or [None])[0]
    if value is not None and not isinstance(value, str):
        raise ApiError(400, "tune must be text")
    if value is not None and value != tune.DRAFT and value not in [t["id"] for t in tune.list_tunes(CONFIG["work"], car)]:
        raise ApiError(400, "unknown modded car %s of %s" % (value, car))
    return value


GET_ROUTES = {"/api/state": api_state, "/api/settings": api_settings}
POST_ROUTES = {"/api/set": api_set, "/api/unset": api_unset, "/api/reset_all": api_reset_all,
               "/api/init": api_init, "/api/duplicate": api_duplicate, "/api/apply": api_apply}


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
        raise ApiError(415, "Content-Type must be application/json")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "TunerServer"

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def method_not_allowed(self):
        self.send_payload(405, {"error": "method not allowed"}, {"Allow": "GET, POST"})

    do_PUT = do_DELETE = do_PATCH = do_OPTIONS = do_HEAD = method_not_allowed

    def read_body(self):
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise ApiError(400, "bad Content-Length") from None
        if length < 0:
            raise ApiError(400, "bad Content-Length")
        if length > MAX_BODY:
            raise ApiError(413, "request body too large")
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
            car = request_car(body.get("car"), query)
            body["tune"] = request_tune(body.get("tune"), query, car)
            payload = route(car, body)
        else:
            car = request_car(None, query)
            payload = route(car, request_tune(None, query, car))
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

    def send_payload(self, status, payload, headers=None):
        if isinstance(payload, bytes):
            data, ctype = payload, "text/html; charset=utf-8"
        else:
            data, ctype = json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        if self.command != "HEAD":
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
