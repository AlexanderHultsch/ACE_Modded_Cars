"""Tests for tools/tuner_server.py: the real Handler on a ThreadingHTTPServer in this process (127.0.0.1, port 0, one thread), main() with a stub server, the pure helpers and the CLI conventions.

Work and mods folders are temp dirs. Everything that needs the game or the schemas is stubbed (support.FakeCar replaces tune.load_msg / save_msg, tune.init / tune.apply are recorders, game_running is a switch, subprocess.run fails the test if called); only the committed tuner/web/index.html is read. Server and job threads are stopped in addCleanup.
"""
import email.message
import http.client
import http.server
import io
import json
import ntpath
import os
import re
import shutil
import sys
import threading
import time
import unittest
from unittest import mock

from support import ROOT, FakeCar, mini_catalogue, mini_setting, run_tool, tmp

import clone_car
import tune
import tuner_server as ts

USAGE = ts.__doc__.split("\n\n")[1]
REAL_GAME_RUNNING = ts.game_running
GAME_ARGV = ["tasklist", "/FI", "IMAGENAME eq AssettoCorsaEVO.exe", "/NH", "/FO", "CSV"]
STATE_KEYS = {"work", "car", "tune", "default_car", "cars", "base_present", "game_running", "installed", "stock_id_length",
              "default_new_id", "settings_applicable", "settings_hidden", "job", "modded", "default_tune_taken",
              "proposed_new_id", "proposed_suffix"}
MODDED_KEYS = {"id", "stock", "label", "name_suffix", "default", "installed", "built"}
CAR_KEYS = {"id", "label", "display_name", "extracted", "tested", "new_id", "installed"}
JOB_KEYS = {"kind", "state", "log", "result", "error"}
ROW_KEYS = {"id", "group", "label", "kind", "type", "unit", "description", "verified", "default", "value", "changed",
            "absent", "copies_differ"}
INIT_RESULT = {"present": False, "dir": "/w/ks_x/base/content/cars/ks_x", "files": 3, "dirs": 1, "bytes": 10}
APPLY_RESULT = {"new_id": "ax_x", "tune": "ax_x", "name_suffix": "_MY", "build_dir": "/w/ks_x/build/ax_x", "package": "/w/ks_x/build/ax_x/ax_x.kspkg", "size": 7,
                "applied": [{"id": "limiter", "old": 7000, "new": 8000, "files": ["data/engine.carengine", "data/x.car"]}],
                "notes": ["note: from build"], "installed": "/m/ax_x.kspkg", "backup": None}
GS = "content\\cars\\common_phsx\\"
ROAD_A, ROAD_B, SLICK_S = GS + "tyres\\road\\a.tyre", GS + "tyres\\road\\b.tyre", GS + "tyres\\slick\\s.tyre"
KEY_AB, KEY_SS = ROAD_A + "|" + ROAD_B, SLICK_S + "|" + SLICK_S
ST_AB, ST_SS = "stock:" + KEY_AB, "stock:" + KEY_SS
TYRE_KEYS = {"id", "name", "source", "changed"}
TYRE_ROW_KEYS = {"id", "label", "group", "unit", "type", "kind", "description", "verified", "min", "max", "axle", "default", "value",
                 "changed", "applicable", "reason"}
GARAGE_KEYS = {"choices", "custom", "missing", "car", "tune"}
TURBO_KEYS = {"donor", "available", "reason", "donors", "picked", "car", "tune", "has_turbo"}
TWIN = {"car": "ks_b", "label": "Twin B", "count": 2, "kind": "twin turbo", "boost": [0.7, 0.7]}
OWN = {"car": "ks_t", "label": "Car T", "count": 1, "kind": "single turbo", "boost": [1.0]}
SINGLE = {"car": "ks_a", "label": "Single A", "count": 1, "kind": "single turbo", "boost": [0.9]}
JOB_RUNNING = {"error": "a job is running, wait until it has finished"}


def limiter():
    return mini_setting("limiter", type="int", min=3000, max=12000, targets=[("@engine", "limiter"), ("@car", "engine.limiter", True)])


def aids_off():
    return mini_setting("aids_off", kind="flag", type="bool", value=0, targets=[("@setup", "electronics.tc1")])


def suffix():
    return mini_setting("name_suffix", kind="meta", type="string", default="_MY", handler="name_suffix", ui="header")


def boost():
    return mini_setting("boost", type="float", targets=[("@turbo[0]", "max_boost")])


def tyre_dy(axle):
    return mini_setting("tyre_dy_" + axle, group="Tyres", unit="mu", min=0.5, max=2.5, targets=[("@tyre_" + axle, "modelData.Dy0")])


def gated(test, fn):
    """A job body for tune.init / tune.apply: records the call, waits for test.gate when one is set, then returns or raises."""
    def stub(*args, **kw):
        test.calls.append((fn, args, kw))
        test.entered.set()
        if test.gate is not None:
            test.gate.wait(10)
        if test.errors.get(fn):
            raise test.errors[fn]
        return dict(INIT_RESULT) if fn == "init" else dict(APPLY_RESULT, new_id=args[2], tune=args[2])
    return stub


class Env(unittest.TestCase):
    """CONFIG and JOB patched, stdout / stderr captured, game_running / tune.init / tune.apply stubbed, no subprocess."""

    def setUp(self):
        cm = tmp()
        self.d = cm.__enter__()
        self.addCleanup(cm.__exit__, None, None, None)
        self.work, self.mods = str(self.d / "work"), str(self.d / "mods")
        self.out, self.err = io.StringIO(), io.StringIO()
        self.patch(sys, "stdout", self.out)
        self.patch(sys, "stderr", self.err)
        self.patch_dict(ts.CONFIG, {"port": 0, "work": self.work, "mods": self.mods})
        self.patch_dict(ts.JOB, {"kind": None, "state": "idle", "log": [], "result": None, "error": None})
        self.addCleanup(self.drain)
        self.game_up, self.gate, self.calls, self.errors = False, None, [], {}
        self.entered = threading.Event()
        self.patch(ts, "game_running", lambda: self.game_up)
        self.patch_list(ts.GAME_CHECK, [float("-inf"), False])
        self.patch(tune.subprocess, "run", mock.Mock(side_effect=AssertionError("a subprocess was started")))
        self.patch(tune, "init", gated(self, "init"))
        self.patch(tune, "apply", gated(self, "apply"))
        self.data = {"default": "ks_x", "cars": [{"id": "ks_x", "label": "Car X"}]}
        self.cat = mini_catalogue(limiter(), aids_off(), suffix(), boost())
        self.patch(tune, "load_cars", lambda path=None: self.data)
        self.patch(tune, "load_catalogue", lambda path=None: self.cat)

    def patch(self, target, name, value):
        p = mock.patch.object(target, name, value)
        p.start()
        self.addCleanup(p.stop)
        return value

    def patch_list(self, target, values):
        saved = list(target)
        target[:] = values
        self.addCleanup(target.__setitem__, slice(None), saved)

    def patch_dict(self, target, values):
        p = mock.patch.dict(target, values)
        p.start()
        self.addCleanup(p.stop)

    def drain(self):
        if self.gate is None:
            return
        self.gate.set()
        end = time.monotonic() + 5
        while ts.job_snapshot()["state"] == "running" and time.monotonic() < end:
            time.sleep(0.01)

    def hold_jobs(self):
        self.gate = threading.Event()

    def wait_job(self, timeout=5):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            snap = ts.job_snapshot()
            if snap["state"] != "running":
                return snap
            time.sleep(0.01)
        self.fail("the job did not finish: %r" % ts.job_snapshot())

    def finish_held_job(self):
        self.gate.set()
        return self.wait_job()


class ServerCase(Env):
    """Env plus a running server and request helpers; make_car() builds the stubbed extracted car ks_x."""
    handler = ts.Handler

    def setUp(self):
        super().setUp()
        self.fc = FakeCar(self.work, "ks_x").install(self)
        index = [{"id": "ks_x", "display_name": "Car X", "brand": "B", "year": 1999},
                 {"id": "ks_y", "display_name": "Car Y", "brand": "B", "year": 2000}]
        self.write(os.path.join(self.work, "cars_index.json"), index)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), self.handler)
        self.port = self.server.server_address[1]
        ts.CONFIG["port"] = self.port
        self.host = "127.0.0.1:%d" % self.port
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(self.stop_server, thread)

    def stop_server(self, thread):
        self.server.shutdown()
        self.server.server_close()
        thread.join(5)

    def write(self, path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def make_car(self):
        gp = self.fc.game_path
        self.car = {"engine_path": gp("data/engine.carengine"), "stock_setup": gp("data/setup.carsetup"), "engine": {"limiter": 7000}}
        self.engine = {"limiter": 7000, "turbos_to_load": []}
        self.setup = {"electronics": {"tc1": 2}}
        self.fc.add("data/x.car", self.car)
        self.fc.add("data/engine.carengine", self.engine)
        self.fc.add("data/setup.carsetup", self.setup)
        self.write(tune.stock_info_path(self.work, "ks_x"), {"car_id": "ks_x", "display_name": "Car X", "brand": "Brand", "year": 1999})

    def state_file(self, car="ks_x"):
        return tune.state_path(self.work, car)

    def saved_state(self):
        with open(self.state_file(), encoding="utf-8") as f:
            return json.load(f)

    def request(self, method, path, body=None, host=None, headers=None, post_headers=True, prefix=True):
        """One request on a new connection; the path gets the base path /ACESCT unless it starts with it or prefix=False;
        host=False sends no Host header, a headers value of None drops that header."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            if prefix and not path.startswith(ts.BASE_PATH):
                path = ts.BASE_PATH + path
            conn.putrequest(method, path, skip_host=True, skip_accept_encoding=True)
            send = {}
            if host is not False:
                send["Host"] = self.host if host is None else host
            if method == "POST" and post_headers:
                send.update({"X-Tuner": "1", "Content-Type": "application/json"})
            data = None
            if body is not None:
                data = body if isinstance(body, bytes) else json.dumps(body).encode("utf-8")
                send["Content-Length"] = str(len(data))
            send.update(headers or {})
            for key, value in send.items():
                if value is not None:
                    conn.putheader(key, value)
            conn.endheaders(data)
            resp = conn.getresponse()
            return Reply(resp.status, resp.msg, resp.read())
        finally:
            conn.close()

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, {} if body is None else body, **kw)


class Reply:
    def __init__(self, status, headers, data):
        self.status, self.headers, self.data = status, headers, data

    @property
    def json(self):
        return json.loads(self.data.decode("utf-8"))


# -------------------------------------------------------------------------------------------------- routes and status codes
class TestRoutes(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_route_tables(self):
        self.assertEqual(sorted(ts.GET_ROUTES), ["/api/garage", "/api/groups", "/api/settings", "/api/state", "/api/turbo", "/api/tyre",
                                                 "/api/tyres"])
        self.assertEqual(sorted(ts.POST_ROUTES), ["/api/apply", "/api/duplicate", "/api/garage_reset", "/api/garage_set", "/api/init",
                                                  "/api/reset_all", "/api/set", "/api/turbo_reset", "/api/turbo_set", "/api/tyre_delete",
                                                  "/api/tyre_new", "/api/tyre_rename", "/api/tyre_reset", "/api/tyre_set",
                                                  "/api/tyre_source", "/api/tyre_unset", "/api/unset"])
        self.assertEqual(ts.ACCEPTED, ("/api/init", "/api/apply"))
        self.assertEqual(ts.QUERY_ROUTES, ("/api/tyre",))
        self.assertTrue(set(ts.QUERY_ROUTES) <= set(ts.GET_ROUTES))

    def test_the_index_page_is_served_from_the_repo_file(self):
        r = self.get("/")
        with open(ts.INDEX, "rb") as f:
            self.assertEqual((r.status, r.data), (200, f.read()))
        self.assertEqual(r.headers.get("Content-Type"), "text/html; charset=utf-8")
        self.assertEqual(r.headers.get("Cache-Control"), "no-store")
        self.assertEqual(r.headers.get("Content-Length"), str(len(r.data)))

    def test_the_page_ignores_a_query(self):
        self.assertEqual(self.get("/?car=ks_x").status, 200)

    def test_state_is_json_with_the_documented_keys(self):
        r = self.get("/api/state")
        self.assertEqual((r.status, r.headers.get("Content-Type"), r.headers.get("Cache-Control")),
                         (200, "application/json; charset=utf-8", "no-store"))
        self.assertEqual(set(r.json), STATE_KEYS)
        self.assertEqual(r.json["job"], {"kind": None, "state": "idle", "log": [], "result": None, "error": None})

    def test_settings_is_a_json_list_of_rows(self):
        r = self.get("/api/settings")
        self.assertEqual((r.status, r.headers.get("Content-Type")), (200, "application/json; charset=utf-8"))
        self.assertIsInstance(r.json, list)
        self.assertEqual([row["id"] for row in r.json], ["limiter", "aids_off", "name_suffix"])

    def test_post_routes_answer_json_with_their_documented_shape(self):
        s = self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.assertEqual((s.status, set(s.json)), (200, {"row", "warnings"}))
        u = self.post("/api/unset", {"id": "limiter"})
        self.assertEqual((u.status, set(u.json)), (200, {"row"}))
        r = self.post("/api/reset_all")
        self.assertEqual((r.status, r.json), (200, {"ok": True}))

    def test_job_routes_answer_202_started(self):
        i = self.post("/api/init")
        self.assertEqual((i.status, i.json), (202, {"job": "started"}))
        self.wait_job()
        a = self.post("/api/apply", {"tune": "draft"})
        self.assertEqual((a.status, a.json), (202, {"job": "started"}))

    def test_unknown_paths_are_404_json(self):
        for path in ("/api/nothing", "/index.html", "/api/state/", "/favicon.svg", "/api/set", "/api"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual((r.status, r.json), (404, {"error": "not found"}))

    def test_a_get_route_is_not_a_post_route_and_back(self):
        self.assertEqual(self.post("/api/state").status, 404)
        self.assertEqual(self.post("/").status, 404)
        self.assertEqual(self.get("/api/reset_all").status, 404)

    def test_the_route_of_the_removed_install_all_tested_cars_button_is_404(self):
        r = self.post("/api/install_tested")
        self.assertEqual((r.status, r.json), (404, {"error": "not found"}))
        self.assertEqual(ts.job_snapshot()["state"], "idle")

    def test_traversal_attempts_are_404_and_never_read_a_file(self):
        for path in ("/../../etc/passwd", "/%2e%2e/%2e%2e/etc/passwd", "/..%2f..%2fetc%2fpasswd", "/api/../../etc/passwd",
                     "/static/../tools/tuner_server.py", "/tools/tuner_server.py", "/tuner/web/index.html", "/%00",
                     "/....//....//etc/passwd", "/%252e%252e/etc/passwd"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual((r.status, r.json), (404, {"error": "not found"}))
                self.assertNotIn(b"root:", r.data)

    def test_other_methods_are_405_with_a_json_error_and_the_allow_header(self):
        for method in ("PUT", "DELETE", "PATCH"):
            with self.subTest(method):
                r = self.request(method, "/api/set")
                self.assertEqual((r.status, r.json), (405, {"error": "method not allowed"}))
                self.assertEqual((r.headers.get("Allow"), r.headers.get("Content-Type")), ("GET, POST", "application/json; charset=utf-8"))
        self.assertEqual(self.request("PUT", "/api/set").headers.get("Access-Control-Allow-Origin"), None)

    def test_head_and_options_are_405_with_the_allow_header_and_the_framing_headers(self):
        for method in ("HEAD", "OPTIONS"):
            with self.subTest(method):
                r = self.request(method, "/")
                self.assertEqual(r.status, 405)
                self.assertEqual((r.headers.get("Allow"), r.headers.get("X-Frame-Options")), ("GET, POST", "DENY"))
                self.assertIn("frame-ancestors", r.headers.get("Content-Security-Policy", ""))
                self.assertEqual(r.headers.get("Access-Control-Allow-Origin"), None)
        self.assertEqual(self.request("HEAD", "/").data, b"")

    def test_an_unexpected_exception_is_a_500_with_only_the_class_name(self):
        def boom(car, tune_id):
            raise RuntimeError("secret detail")
        with mock.patch.dict(ts.GET_ROUTES, {"/api/state": boom}):
            r = self.get("/api/state")
        self.assertEqual((r.status, r.json), (500, {"error": "internal error: RuntimeError"}))
        self.assertIn("RuntimeError: secret detail", self.err.getvalue())

    def test_value_and_os_errors_are_a_500_with_their_text(self):
        for exc in (ValueError("bad stock info"), OSError("disk gone")):
            def boom(car, tune_id, exc=exc):
                raise exc
            with self.subTest(type(exc).__name__), mock.patch.dict(ts.GET_ROUTES, {"/api/state": boom}):
                r = self.get("/api/state")
                self.assertEqual((r.status, r.json), (500, {"error": str(exc)}))


class TestBasePath(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def raw(self, path, **kw):
        return self.get(path, prefix=False, **kw)

    def test_the_base_path_is_fixed(self):
        self.assertEqual(ts.BASE_PATH, "/ACESCT")

    def test_the_page_is_served_at_the_base_path_with_a_slash(self):
        r = self.raw("/ACESCT/")
        with open(ts.INDEX, "rb") as f:
            self.assertEqual((r.status, r.data), (200, f.read()))
        self.assertEqual(r.headers.get("Content-Type"), "text/html; charset=utf-8")
        self.assertEqual(self.raw("/ACESCT/?car=ks_x").status, 200)

    def test_the_base_path_without_a_slash_is_a_301_to_the_page(self):
        for path in ("/ACESCT", "/ACESCT?car=ks_x"):
            with self.subTest(path):
                r = self.raw(path)
                self.assertEqual((r.status, r.headers.get("Location"), r.data), (301, "/ACESCT/", b""))

    def test_the_root_is_a_302_to_the_page(self):
        for path in ("/", "/?car=ks_x"):
            with self.subTest(path):
                r = self.raw(path)
                self.assertEqual((r.status, r.headers.get("Location"), r.data), (302, "/ACESCT/", b""))

    def test_the_redirects_carry_the_framing_headers_and_no_cors_headers(self):
        for path in ("/", "/ACESCT"):
            with self.subTest(path):
                r = self.raw(path)
                self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
                self.assertIn("frame-ancestors 'none'", r.headers.get("Content-Security-Policy", ""))
                self.assertEqual(r.headers.get("Cache-Control"), "no-store")
                self.assertEqual([h for h in r.headers if h.lower().startswith("access-control")], [])

    def test_the_redirects_check_the_host_first(self):
        for path in ("/", "/ACESCT"):
            with self.subTest(path):
                r = self.raw(path, host="evil.example")
                self.assertEqual((r.status, r.json, r.headers.get("Location")), (403, {"error": "forbidden host"}, None))

    def test_the_api_lives_below_the_base_path_only(self):
        r = self.raw("/ACESCT/api/state")
        self.assertEqual((r.status, set(r.json)), (200, STATE_KEYS))
        r = self.raw("/api/state")
        self.assertEqual((r.status, r.json), (404, {"error": "not found"}))
        r = self.request("POST", "/api/set", {"id": "limiter", "value": "8000"}, prefix=False)
        self.assertEqual((r.status, r.json), (404, {"error": "not found"}))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_every_other_path_is_404_json(self):
        for path in ("/ACESCT2", "/ACESCT2/", "/ACESCTx/api/state", "/ACESCT/x/api/state", "/acesct/", "/acesct/api/state", "/ACESCT//api/state",
                     "/ACESCT/api", "/ACESCT/api/state/", "/ACESCT/index.html", "/ACESCT/ACESCT/", "/index.html", "/api/groups"):
            with self.subTest(path):
                r = self.raw(path)
                self.assertEqual((r.status, r.json), (404, {"error": "not found"}))

    def test_a_post_to_the_page_or_a_redirect_is_404(self):
        for path in ("/", "/ACESCT", "/ACESCT/"):
            with self.subTest(path):
                self.assertEqual(self.request("POST", path, {}, prefix=False).status, 404)

    def test_the_quiet_poll_filter_matches_the_prefixed_state_path(self):
        self.assertEqual(self.raw("/ACESCT/api/state").status, 200)
        self.assertEqual(self.raw("/ACESCT/api/state?car=ks_x").status, 200)
        self.assertNotIn("/api/state", self.err.getvalue())
        self.assertEqual(self.raw("/api/state").status, 404)
        self.assertIn('"GET /api/state HTTP/1.1" 404 -', self.err.getvalue())


STATIC = {"apple-touch-icon.png": "image/png", "icon-192.png": "image/png", "icon-512.png": "image/png", "favicon.png": "image/png",
          "favicon.ico": "image/x-icon", "manifest.webmanifest": "application/manifest+json"}


class TestStaticFiles(ServerCase):
    def file(self, name):
        return (ROOT / "tuner" / "web" / name).read_bytes()

    def test_the_table_holds_exactly_the_six_files_of_the_web_folder(self):
        self.assertEqual({k: v[1] for k, v in ts.STATIC_FILES.items()}, {"/" + k: v for k, v in STATIC.items()})
        self.assertEqual({k: v[0].name for k, v in ts.STATIC_FILES.items()}, {"/" + k: k for k in STATIC})
        for path, _ in ts.STATIC_FILES.values():
            self.assertEqual(path.parent, ts.INDEX.parent)
            self.assertTrue(path.is_file(), path)

    def test_each_file_is_served_below_the_base_path_with_its_content_type_and_bytes(self):
        for name, ctype in STATIC.items():
            with self.subTest(name):
                r = self.get("/" + name)
                self.assertEqual((r.status, r.headers.get("Content-Type"), r.data), (200, ctype, self.file(name)))
                self.assertEqual(r.headers.get("Content-Length"), str(len(r.data)))
                self.assertEqual(r.headers.get_all("Cache-Control"), ["no-store"])
                self.assertGreater(len(r.data), 100)

    def test_the_answers_carry_the_framing_headers_and_no_cors_headers(self):
        for name in STATIC:
            with self.subTest(name):
                r = self.get("/" + name)
                self.assertEqual(r.headers.get("X-Frame-Options"), "DENY")
                self.assertIn("frame-ancestors 'none'", r.headers.get("Content-Security-Policy", ""))
                self.assertEqual([h for h in r.headers if h.lower().startswith("access-control")], [])

    def test_a_query_is_ignored(self):
        self.assertEqual(self.get("/icon-192.png?v=2").data, self.file("icon-192.png"))

    def test_every_other_file_name_is_404_json(self):
        for path in ("/ACESCT/secret.txt", "/ACESCT/../x", "/ACESCT/icon-192.png/extra", "/ACESCT/ICON-192.PNG", "/ACESCT/icon-192.png/",
                     "/ACESCT//icon-192.png", "/ACESCT/%69con-192.png", "/ACESCT/icon-192.png%00", "/ACESCT/..%2ficon-192.png",
                     "/ACESCT/../tuner/web/icon-192.png", "/ACESCT/icons/icon-192.png", "/ACESCT/manifest.json", "/ACESCT/favicon.svg",
                     "/ACESCT/icon-180.png", "/ACESCT/web/icon-192.png", "/ACESCT/icon-192.png.bak", "/ACESCT/index.html",
                     "/ACESCT/make_icons.py", "/icon-192.png", "/favicon.ico", "/manifest.webmanifest", "/apple-touch-icon.png"):
            with self.subTest(path):
                r = self.get(path, prefix=False)
                self.assertEqual((r.status, r.json), (404, {"error": "not found"}))

    def test_the_host_is_checked(self):
        for name in STATIC:
            with self.subTest(name):
                r = self.get("/" + name, host="evil.example")
                self.assertEqual((r.status, r.json), (403, {"error": "forbidden host"}))
                self.assertEqual(self.get("/" + name, host=False).status, 403)
        self.assertEqual(self.get("/icon-192.png", host="localhost:%d" % self.port).status, 200)

    def test_a_post_is_404(self):
        for name in STATIC:
            with self.subTest(name):
                r = self.post("/" + name)
                self.assertEqual((r.status, r.json), (404, {"error": "not found"}))

    def test_head_is_405_as_for_the_page(self):
        r = self.request("HEAD", "/icon-192.png")
        self.assertEqual((r.status, r.headers.get("Allow"), r.data), (405, "GET, POST", b""))

    def test_a_missing_file_is_a_500_json_error(self):
        with mock.patch.dict(ts.STATIC_FILES, {"/icon-192.png": (self.d / "gone.png", "image/png")}):
            r = self.get("/icon-192.png")
        self.assertEqual(r.status, 500)
        self.assertEqual(set(r.json), {"error"})

    def test_the_page_is_still_html_and_json_is_still_json(self):
        self.assertEqual(self.get("/").headers.get("Content-Type"), "text/html; charset=utf-8")
        self.assertEqual(self.get("/api/nothing").headers.get("Content-Type"), "application/json; charset=utf-8")


class ForeignHandler(ts.Handler):
    """A Handler whose client always comes from a public address."""
    @property
    def client_address(self):
        return ("8.8.8.8", 4711)

    @client_address.setter
    def client_address(self, value):
        pass


class TestForeignClient(ServerCase):
    handler = ForeignHandler

    def setUp(self):
        super().setUp()
        self.make_car()

    def test_a_public_client_is_403_for_every_route_and_changes_nothing(self):
        for r in (self.get("/"), self.get("/api/state"), self.get("/nothing"), self.get("/", prefix=False), self.get("/ACESCT", prefix=False),
                  self.post("/api/set", {"id": "limiter", "value": "8000"}), self.post("/api/init")):
            self.assertEqual((r.status, r.json), (403, {"error": "forbidden client address"}))
            self.assertEqual([h for h in r.headers if h.lower().startswith("access-control")], [])
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertEqual(ts.job_snapshot()["state"], "idle")

    def test_the_client_address_is_checked_before_the_host(self):
        r = self.get("/api/state", host="evil.example")
        self.assertEqual((r.status, r.json), (403, {"error": "forbidden client address"}))
        self.assertEqual(self.get("/api/state", host=False).json, {"error": "forbidden client address"})

    def test_a_public_client_gets_no_static_file(self):
        for name in STATIC:
            with self.subTest(name):
                r = self.get("/" + name)
                self.assertEqual((r.status, r.json), (403, {"error": "forbidden client address"}))
                self.assertNotEqual(r.data, (ROOT / "tuner" / "web" / name).read_bytes())


# -------------------------------------------------------------------------------------------------- request checks
class TestHostAndHeaders(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_the_two_allowed_hosts_are_accepted(self):
        for host in ("127.0.0.1:%d", "localhost:%d", "LOCALHOST:%d"):
            with self.subTest(host):
                self.assertEqual(self.get("/api/state", host=host % self.port).status, 200)

    def test_every_other_host_is_403(self):
        for host in ("evil.example", "evil.example:%d" % self.port, "127.0.0.1", "localhost", "[::1]:%d" % self.port,
                     "127.0.0.1:%d.evil.example" % self.port, "127.0.0.1:%d" % (self.port + 1), "0.0.0.0:%d" % self.port,
                     ""):
            with self.subTest(host):
                r = self.get("/api/state", host=host)
                self.assertEqual((r.status, r.json), (403, {"error": "forbidden host"}))

    def test_private_hosts_with_the_port_and_the_machine_name_are_accepted(self):
        with mock.patch.object(ts.socket, "gethostname", return_value="Alex-PC"):
            for host in ("localhost:%d", "127.0.0.1:%d", "127.1.2.3:%d", "192.168.1.20:%d", "10.0.0.5:%d", "172.16.0.1:%d", "172.31.255.1:%d",
                         "Alex-PC:%d", "ALEX-PC:%d", "alex-pc:%d"):
                with self.subTest(host):
                    self.assertEqual(self.get("/api/state", host=host % self.port).status, 200)

    def test_other_hosts_are_403_with_the_machine_name_set(self):
        with mock.patch.object(ts.socket, "gethostname", return_value="Alex-PC"):
            for host in ("localhost:%d" % (self.port + 1), "192.168.1.20:%d" % (self.port + 1), "192.168.1.20", "Alex-PC", "Alex-PC:%d" % (self.port + 1),
                         "evil.example:%d" % self.port, "8.8.8.8:%d" % self.port, "172.32.0.1:%d" % self.port, "100.64.0.1:%d" % self.port,
                         "[::1]:%d" % self.port, "192.168.1.20.evil.example:%d" % self.port, "Alex-PC.evil.example:%d" % self.port,
                         "Alex-PC.local:%d" % self.port, "other-pc:%d" % self.port, "0.0.0.0:%d" % self.port, ":%d" % self.port):
                with self.subTest(host):
                    r = self.get("/api/state", host=host)
                    self.assertEqual((r.status, r.json), (403, {"error": "forbidden host"}))

    def test_a_missing_host_header_is_403(self):
        self.assertEqual(self.get("/api/state", host=False).status, 403)

    def test_the_host_is_checked_for_the_page_posts_and_unknown_paths_too(self):
        self.assertEqual(self.get("/", host="evil.example").status, 403)
        self.assertEqual(self.get("/nothing", host="evil.example").status, 403)
        self.assertEqual(self.post("/api/reset_all", host="evil.example").status, 403)
        self.assertFalse(os.path.exists(self.state_file()))

    def test_a_post_without_x_tuner_is_403_and_changes_nothing(self):
        r = self.post("/api/set", {"id": "limiter", "value": "8000"}, headers={"X-Tuner": None})
        self.assertEqual((r.status, r.json), (403, {"error": "missing header X-Tuner: 1"}))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_x_tuner_must_be_exactly_1(self):
        for value in ("0", "true", "", "1 "):
            with self.subTest(repr(value)):
                self.assertEqual(self.post("/api/reset_all", headers={"X-Tuner": value}).status, 403)

    def test_a_post_with_another_content_type_is_415(self):
        for ctype in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data", "application/jsonx", None):
            with self.subTest(ctype):
                r = self.post("/api/set", {"id": "limiter", "value": "8000"}, headers={"Content-Type": ctype})
                self.assertEqual((r.status, r.json), (415, {"error": "Content-Type must be application/json"}))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_content_type_parameters_and_case_are_accepted(self):
        for ctype in ("application/json; charset=utf-8", "Application/JSON", "application/json ;charset=utf-8"):
            with self.subTest(ctype):
                self.assertEqual(self.post("/api/reset_all", headers={"Content-Type": ctype}).status, 200)

    def test_the_post_headers_are_checked_before_the_route(self):
        self.assertEqual(self.post("/api/nothing", headers={"X-Tuner": None}).status, 403)
        self.assertEqual(self.post("/api/nothing").status, 404)

    def test_a_get_needs_no_x_tuner_and_no_content_type(self):
        self.assertEqual(self.get("/api/state").status, 200)

    def test_no_cors_headers_are_ever_sent(self):
        for r in (self.get("/api/state"), self.get("/api/state", host="evil.example"), self.get("/nothing")):
            self.assertEqual([h for h in r.headers if h.lower().startswith("access-control")], [])


class TestBodies(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def set_raw(self, raw, **kw):
        return self.request("POST", "/api/set", raw, **kw)

    def test_malformed_json_is_400(self):
        for raw in (b"{bad", b'{"id": "limiter", "value": }', b"\xff\xfe{}", b"'x'", b"{} {}"):
            with self.subTest(raw):
                r = self.set_raw(raw)
                self.assertEqual((r.status, r.json), (400, {"error": "body is not valid JSON"}))

    def test_json_that_is_not_an_object_is_400(self):
        for raw in (b"[1, 2]", b"5", b'"x"', b"null", b"true"):
            with self.subTest(raw):
                r = self.set_raw(raw)
                self.assertEqual((r.status, r.json), (400, {"error": "body must be a JSON object"}))

    def test_an_empty_or_blank_body_is_an_empty_object(self):
        for raw in (b"", b"  \n"):
            with self.subTest(raw):
                r = self.set_raw(raw)
                self.assertEqual((r.status, r.json["error"]), (400, "need id (text) and value (text, number or true/false)"))
        self.assertEqual(self.request("POST", "/api/reset_all", None).status, 200)

    def test_wrong_field_types_are_400(self):
        for body in ({"id": 5, "value": "1"}, {"id": None, "value": "1"}, {"value": "1"}, {"id": "limiter"},
                     {"id": "limiter", "value": None}, {"id": "limiter", "value": [1]}, {"id": "limiter", "value": {"a": 1}},
                     {"id": ["limiter"], "value": 1}):
            with self.subTest(body):
                r = self.post("/api/set", body)
                self.assertEqual((r.status, r.json), (400, {"error": "need id (text) and value (text, number or true/false)"}))
        for body in ({"id": 5}, {}, {"id": None}):
            with self.subTest(body):
                self.assertEqual(self.post("/api/unset", body).json, {"error": "need id (text)"})
        self.assertFalse(os.path.exists(self.state_file()))

    def test_value_types_text_number_and_bool_are_accepted(self):
        for value in ("8000", 8000):
            with self.subTest(repr(value)):
                self.assertEqual(self.post("/api/set", {"id": "limiter", "value": value}).status, 200)
        self.assertEqual(self.post("/api/set", {"id": "aids_off", "value": True}).status, 200)

    def test_the_body_limit_is_65536_bytes(self):
        self.assertEqual(ts.MAX_BODY, 65536)
        pad = b" " * (ts.MAX_BODY - len(b'{"id": "limiter", "value": 8000}'))
        raw = b'{"id": "limiter", "value": 8000}' + pad
        self.assertEqual(len(raw), 65536)
        r = self.set_raw(raw)
        self.assertEqual((r.status, r.json["row"]["value"]), (200, 8000))

    def test_a_longer_body_is_413_before_it_is_read(self):
        r = self.request("POST", "/api/set", None, headers={"Content-Length": str(ts.MAX_BODY + 1)})
        self.assertEqual((r.status, r.json), (413, {"error": "request body too large"}))
        big = self.request("POST", "/api/set", None, headers={"Content-Length": "100000000"})
        self.assertEqual(big.status, 413)
        self.assertFalse(os.path.exists(self.state_file()))

    def test_a_bad_content_length_is_400(self):
        r = self.request("POST", "/api/set", None, headers={"Content-Length": "abc"})
        self.assertEqual((r.status, r.json), (400, {"error": "bad Content-Length"}))
        r = self.request("POST", "/api/set", None, headers={"Content-Length": "-5"})
        self.assertEqual(r.status, 400)

    def test_a_non_ascii_value_survives_the_json_round_trip(self):
        r = self.post("/api/set", {"id": "name_suffix", "value": "_M\u00dcNCHEN"})
        self.assertEqual(r.json["row"]["value"], "_M\u00dcNCHEN")
        self.assertEqual(self.saved_state(), {"name_suffix": "_M\u00dcNCHEN"})


class TestCarIds(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_an_unknown_car_in_the_query_is_400_for_both_get_routes(self):
        for path in ("/api/state?car=../x", "/api/state?car=nope", "/api/settings?car=nope", "/api/state?car=%2e%2e%2fx",
                     "/api/settings?car=ks_x/../ks_y"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith("unknown car"), r.json)

    def test_an_unknown_car_in_the_body_is_400_for_every_post_route(self):
        for path in ("/api/set", "/api/unset", "/api/reset_all", "/api/init", "/api/apply"):
            with self.subTest(path):
                r = self.post(path, {"car": "../x", "id": "limiter", "value": "1", "mode": "update"})
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith("unknown car"), r.json)
        self.assertFalse(os.path.exists(os.path.join(self.work, "..", "x")))
        self.assertEqual(self.calls, [])
        self.assertEqual(ts.job_snapshot()["state"], "idle")

    def test_a_close_match_is_suggested(self):
        r = self.get("/api/state?car=ks_xx")
        self.assertIn("close matches: ks_x", r.json["error"])

    def test_the_car_must_be_text(self):
        for value in (5, ["ks_x"], {"id": "ks_x"}, True):
            with self.subTest(repr(value)):
                r = self.post("/api/reset_all", {"car": value})
                self.assertEqual((r.status, r.json), (400, {"error": "car must be text"}))

    def test_a_null_car_means_the_default_car(self):
        self.assertEqual(self.post("/api/reset_all", {"car": None}).status, 200)
        self.assertTrue(os.path.exists(self.state_file()))

    def test_a_game_car_that_is_not_in_cars_json_is_accepted(self):
        r = self.get("/api/state?car=ks_y")
        self.assertEqual((r.status, r.json["car"], r.json["base_present"], r.json["default_new_id"]), (200, "ks_y", False, "ax_y"))

    def test_without_a_car_the_default_car_is_used(self):
        self.assertEqual(self.get("/api/state").json["car"], "ks_x")

    def test_a_blank_car_query_means_the_default_car(self):
        self.assertEqual(self.get("/api/state?car=").json["car"], "ks_x")

    def test_the_body_car_wins_over_the_query_car(self):
        self.assertEqual(self.post("/api/reset_all?car=ks_y", {"car": "ks_x"}).status, 200)
        self.assertTrue(os.path.exists(self.state_file("ks_x")))
        self.assertFalse(os.path.exists(self.state_file("ks_y")))

    def test_the_query_car_is_used_when_the_body_has_none(self):
        r = self.post("/api/set?car=ks_y", {"id": "limiter", "value": "8000"})
        self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))

    def test_without_the_game_car_list_only_the_tested_cars_are_known(self):
        os.remove(os.path.join(self.work, "cars_index.json"))
        self.patch(tune, "DEFAULT_GAME", os.path.join(self.work, "no_game.kspkg"))
        self.assertEqual([c["id"] for c in self.get("/api/state").json["cars"]], ["ks_x"])
        r = self.get("/api/state?car=ks_y")
        self.assertEqual(r.status, 400)
        self.assertIn("car list of the game is not available", r.json["error"])


# -------------------------------------------------------------------------------------------------- state and settings
class TestStateAndSettings(ServerCase):
    def test_state_without_a_base_car(self):
        r = self.get("/api/state").json
        self.assertEqual((r["work"], r["car"], r["default_car"], r["base_present"], r["game_running"]), (self.work, "ks_x", "ks_x", False, False))
        self.assertEqual((r["stock_id_length"], r["default_new_id"], r["settings_applicable"], r["settings_hidden"]), (4, "ax_x", None, None))
        self.assertEqual(r["installed"], {"path": os.path.join(os.path.abspath(self.mods), "ax_x.kspkg"), "exists": False, "bytes": None, "modified": None})

    def test_state_lists_every_game_car_with_its_flags(self):
        cars = self.get("/api/state").json["cars"]
        self.assertEqual([set(c) for c in cars], [CAR_KEYS, CAR_KEYS])
        self.assertEqual([(c["id"], c["display_name"], c["tested"], c["extracted"], c["new_id"], c["installed"]) for c in cars],
                         [("ks_x", "Car X", True, False, "ax_x", False), ("ks_y", "Car Y", False, False, "ax_y", False)])

    def test_state_with_a_base_car_counts_applicable_and_hidden_settings(self):
        self.make_car()
        r = self.get("/api/state").json
        self.assertEqual((r["base_present"], r["settings_applicable"], r["settings_hidden"]), (True, 3, 1))
        self.assertTrue(r["cars"][0]["extracted"])

    def test_an_empty_car_folder_is_no_base(self):
        os.makedirs(self.fc.car_root)
        self.assertFalse(self.get("/api/state").json["base_present"])

    def test_the_counts_are_null_while_the_car_is_being_extracted(self):
        self.make_car()
        self.hold_jobs()
        self.assertEqual(self.post("/api/init").status, 202)
        r = self.get("/api/state").json
        self.assertEqual((r["base_present"], r["settings_applicable"], r["settings_hidden"]), (True, None, None))
        self.finish_held_job()
        self.assertEqual(self.get("/api/state").json["settings_applicable"], 3)

    def test_state_reports_the_game_and_the_installed_package(self):
        self.make_car()
        self.game_up = True
        os.makedirs(self.mods)
        with open(os.path.join(self.mods, "ax_x.kspkg"), "wb") as f:
            f.write(b"12345")
        r = self.get("/api/state").json
        self.assertTrue(r["game_running"])
        self.assertEqual((r["installed"]["exists"], r["installed"]["bytes"]), (True, 5))
        self.assertTrue(r["cars"][0]["installed"])
        self.assertFalse(r["cars"][1]["installed"])

    def test_settings_rows_carry_the_documented_fields(self):
        self.make_car()
        rows = {r["id"]: r for r in self.get("/api/settings").json}
        self.assertEqual(set(rows["limiter"]), ROW_KEYS | {"min", "max"})
        self.assertEqual((rows["limiter"]["default"], rows["limiter"]["value"], rows["limiter"]["changed"], rows["limiter"]["copies_differ"]),
                         (7000, 7000, False, False))
        self.assertEqual(set(rows["name_suffix"]), ROW_KEYS | {"ui"})
        self.assertEqual((rows["name_suffix"]["ui"], rows["name_suffix"]["default"]), ("header", "_MY"))
        self.assertEqual((rows["aids_off"]["type"], rows["aids_off"]["default"], rows["aids_off"]["value"]), ("bool", False, False))

    def write_ranges(self, ranges):
        return self.write(os.path.join(self.work, tune.RANGES_FILE), ranges)

    def test_settings_rows_carry_the_base_range_of_the_settings_that_have_an_entry(self):
        self.make_car()
        self.write_ranges({"limiter": {"low": 5000, "high": 9000.5}, "boost": {"low": 1, "high": 2}, "gone": {"low": 0, "high": 1}})
        r = self.get("/api/settings")
        rows = {x["id"]: x for x in r.json}
        self.assertEqual(r.status, 200)
        self.assertEqual(rows["limiter"]["base_range"], {"low": 5000, "high": 9000.5})
        self.assertEqual(set(rows["limiter"]), ROW_KEYS | {"min", "max", "base_range"})
        self.assertEqual((rows["limiter"]["min"], rows["limiter"]["max"]), (3000, 12000))
        self.assertNotIn("base_range", rows["aids_off"])
        self.assertNotIn("base_range", rows["name_suffix"])
        self.assertEqual(set(rows), {"limiter", "aids_off", "name_suffix"})

    def test_settings_rows_have_no_base_range_without_a_ranges_file(self):
        self.make_car()
        self.assertFalse(os.path.exists(os.path.join(self.work, tune.RANGES_FILE)))
        r = self.get("/api/settings")
        self.assertEqual((r.status, [x["id"] for x in r.json]), (200, ["limiter", "aids_off", "name_suffix"]))
        self.assertEqual([x["id"] for x in r.json if "base_range" in x], [])

    def test_settings_rows_have_no_base_range_from_a_damaged_ranges_file(self):
        self.make_car()
        self.write(os.path.join(self.work, tune.RANGES_FILE), "{not json")
        r = self.get("/api/settings")
        self.assertEqual(r.status, 200)
        self.assertEqual([x["id"] for x in r.json if "base_range" in x], [])

    def test_settings_not_applicable_to_the_car_are_left_out(self):
        self.make_car()
        self.assertNotIn("boost", [r["id"] for r in self.get("/api/settings").json])

    def test_copies_that_differ_are_listed_with_their_values(self):
        self.make_car()
        self.car["engine"]["limiter"] = 6500
        row = self.get("/api/settings").json[0]
        self.assertTrue(row["copies_differ"])
        self.assertEqual(row["copy_values"], [{"target": "@engine limiter", "value": 7000}, {"target": "@car engine.limiter", "value": 6500}])

    def test_settings_show_the_saved_state(self):
        self.make_car()
        self.write(self.state_file(), {"limiter": 8000})
        row = self.get("/api/settings").json[0]
        self.assertEqual((row["value"], row["default"], row["changed"]), (8000, 7000, True))


class TestMissingBase(ServerCase):
    def assertNoBase(self, r):
        self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))

    def test_settings_set_unset_and_apply_are_409_without_a_base(self):
        self.assertNoBase(self.get("/api/settings"))
        self.assertNoBase(self.post("/api/set", {"id": "limiter", "value": "8000"}))
        self.assertNoBase(self.post("/api/unset", {"id": "limiter"}))
        self.assertNoBase(self.post("/api/apply", {"mode": "update"}))
        self.assertEqual(self.calls, [])
        self.assertEqual(ts.job_snapshot()["state"], "idle")

    def test_set_and_unset_create_no_state_file_without_a_base(self):
        self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.post("/api/unset", {"id": "limiter"})
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x")))

    def test_the_input_checks_come_before_the_base_check(self):
        self.assertEqual(self.post("/api/set", {"id": 5, "value": 1}).status, 400)
        self.assertEqual(self.post("/api/apply", {"tune": "draft", "new_id": 5}).status, 400)
        self.assertEqual(self.post("/api/apply", {"tune": "draft", "suffix": ["_X"]}).status, 400)
        self.assertEqual(self.post("/api/duplicate", {"new_id": 5}).status, 400)

    def test_init_needs_no_base(self):
        self.assertEqual(self.post("/api/init").status, 202)

    def test_reset_all_without_a_base_is_409(self):
        self.assertNoBase(self.post("/api/reset_all"))

    def test_reset_all_without_a_base_creates_no_state_file(self):
        self.post("/api/reset_all")
        self.assertFalse(os.path.exists(self.state_file()), "tune_state.json was created for a car that was never extracted")


# -------------------------------------------------------------------------------------------------- set / unset / reset_all and the state file
class TestStateRoutes(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_set_answers_with_the_new_row(self):
        r = self.post("/api/set", {"id": "limiter", "value": "8000"})
        row = r.json["row"]
        self.assertEqual((r.json["warnings"], row["id"], row["value"], row["default"], row["changed"]), ([], "limiter", 8000, 7000, True))
        self.assertEqual(set(row), ROW_KEYS | {"min", "max"})

    def test_set_and_unset_answer_a_row_with_the_base_range(self):
        self.write(os.path.join(self.work, tune.RANGES_FILE), {"limiter": {"low": 5000, "high": 9000}})
        for path, body in (("/api/set", {"id": "limiter", "value": "8000"}), ("/api/unset", {"id": "limiter"})):
            with self.subTest(path):
                row = self.post(path, body).json["row"]
                self.assertEqual(row["base_range"], {"low": 5000, "high": 9000})
                self.assertEqual(set(row), ROW_KEYS | {"min", "max", "base_range"})

    def test_set_answers_a_row_without_base_range_when_the_setting_has_no_entry_or_there_is_no_file(self):
        self.assertNotIn("base_range", self.post("/api/set", {"id": "limiter", "value": "8000"}).json["row"])
        self.write(os.path.join(self.work, tune.RANGES_FILE), {"boost": {"low": 1, "high": 2}})
        self.assertNotIn("base_range", self.post("/api/set", {"id": "limiter", "value": "8100"}).json["row"])
        self.assertNotIn("base_range", self.post("/api/set", {"id": "aids_off", "value": True}).json["row"])

    def test_set_persists_the_coerced_value_in_the_state_file(self):
        self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.post("/api/set", {"id": "aids_off", "value": True})
        self.assertEqual(self.saved_state(), {"limiter": 8000, "aids_off": True})
        self.assertEqual(os.path.dirname(self.state_file()), os.path.join(self.work, "ks_x"))

    def test_set_outside_the_suggested_range_warns_but_stores(self):
        r = self.post("/api/set", {"id": "limiter", "value": "20000"})
        self.assertEqual((r.status, r.json["warnings"]), (200, ["limiter=20000 is outside the suggested range 3000..12000"]))
        self.assertEqual(self.saved_state(), {"limiter": 20000})

    def test_set_with_a_bad_value_is_400_and_changes_nothing(self):
        self.write(self.state_file(), {"limiter": 7500})
        r = self.post("/api/set", {"id": "limiter", "value": "fast"})
        self.assertEqual(r.status, 400)
        self.assertIn("limiter expects an integer", r.json["error"])
        self.assertEqual(self.saved_state(), {"limiter": 7500})

    def test_set_of_an_unknown_setting_is_400(self):
        r = self.post("/api/set", {"id": "nope", "value": "1"})
        self.assertEqual((r.status, r.json), (400, {"error": "unknown setting 'nope'"}))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_set_of_a_setting_the_car_does_not_have_is_400(self):
        r = self.post("/api/set", {"id": "boost", "value": "1.5"})
        self.assertEqual(r.status, 400)
        self.assertIn("boost is not applicable to ks_x", r.json["error"])
        self.assertFalse(os.path.exists(self.state_file()))

    def test_unset_removes_the_entry_and_answers_with_the_default_row(self):
        self.write(self.state_file(), {"limiter": 8000, "aids_off": True})
        r = self.post("/api/unset", {"id": "limiter"})
        self.assertEqual((r.status, r.json["row"]["value"], r.json["row"]["changed"]), (200, 7000, False))
        self.assertEqual(self.saved_state(), {"aids_off": True})

    def test_unset_of_a_value_that_was_never_set_is_a_noop(self):
        r = self.post("/api/unset", {"id": "limiter"})
        self.assertEqual((r.status, r.json["row"]["changed"]), (200, False))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_unset_of_an_unknown_setting_is_400(self):
        self.assertEqual(self.post("/api/unset", {"id": "nope"}).json, {"error": "unknown setting 'nope'"})

    def test_reset_all_writes_an_empty_state(self):
        self.write(self.state_file(), {"limiter": 8000, "aids_off": True})
        r = self.post("/api/reset_all")
        self.assertEqual((r.status, r.json), (200, {"ok": True}))
        self.assertEqual(self.saved_state(), {})
        self.assertFalse(any(row["changed"] for row in self.get("/api/settings").json))

    def test_the_state_is_kept_per_car(self):
        self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.assertFalse(os.path.exists(self.state_file("ks_y")))

    def test_a_saved_value_shows_up_in_the_settings_list(self):
        self.post("/api/set", {"id": "limiter", "value": "8000"})
        row = self.get("/api/settings").json[0]
        self.assertEqual((row["value"], row["changed"]), (8000, True))

    def test_every_state_write_happens_under_state_lock(self):
        held = []
        real = tune.save_state

        def spy(*args, **kw):
            held.append(ts.STATE_LOCK.locked())
            return real(*args, **kw)
        self.patch(tune, "save_state", spy)
        self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.post("/api/unset", {"id": "limiter"})
        self.post("/api/reset_all")
        self.assertEqual(held, [True, True, True])

    def test_the_settings_list_is_built_under_state_lock(self):
        held = []
        real = tune.effective_rows

        def spy(*args, **kw):
            held.append(ts.STATE_LOCK.locked())
            return real(*args, **kw)
        self.patch(tune, "effective_rows", spy)
        self.get("/api/settings")
        self.assertEqual(held, [True])

    def test_two_edits_at_the_same_time_are_both_kept(self):
        real = tune.load_state

        def slow(*args, **kw):
            state = real(*args, **kw)
            time.sleep(0.05)
            return state
        self.patch(tune, "load_state", slow)
        start, results = threading.Barrier(2), []

        def send(body):
            start.wait(5)
            results.append(self.post("/api/set", body).status)
        threads = [threading.Thread(target=send, args=(b,)) for b in ({"id": "limiter", "value": "8000"}, {"id": "aids_off", "value": True})]
        for t in threads:
            t.start()
        for t in threads:
            t.join(10)
        self.assertEqual(results, [200, 200])
        self.assertEqual(self.saved_state(), {"limiter": 8000, "aids_off": True})


# -------------------------------------------------------------------------------------------------- apply and init
class TuneCase(ServerCase):
    """ServerCase with the stub car ks_x extracted and helpers for modded cars (tunes) of it."""

    def setUp(self):
        super().setUp()
        self.make_car()

    def make_tune(self, tune_id=None, state=None):
        """A modded car of ks_x with the given saved values (tune_id None = the default tune ax_x)."""
        tune.save_state(self.work, "ks_x", dict(state or {}), tune_id)

    def tune_state(self, tune_id=None):
        return tune.load_state(self.work, "ks_x", tune_id)

    def tune_ids(self):
        return [t["id"] for t in tune.list_tunes(self.work, "ks_x")]

    def put_package(self, name, data=b"12345"):
        os.makedirs(self.mods, exist_ok=True)
        with open(os.path.join(self.mods, name + ".kspkg"), "wb") as f:
            f.write(data)

    def game_arg(self):
        return os.path.expandvars(tune.DEFAULT_GAME)


class TestApplyRoute(TuneCase):
    def test_a_new_id_or_suffix_that_is_not_text_is_400_for_the_draft(self):
        for body, text in (({"new_id": 5}, "new_id must be text"), ({"new_id": ["ax_y"]}, "new_id must be text"),
                           ({"suffix": 5}, "suffix must be text"), ({"suffix": {"a": 1}}, "suffix must be text")):
            with self.subTest(body):
                r = self.post("/api/apply", dict(body, tune="draft"))
                self.assertEqual((r.status, r.json), (400, {"error": text}))
        self.assertEqual((self.calls, self.tune_ids(), ts.job_snapshot()["state"]), ([], [], "idle"))

    def test_an_explicit_new_id_that_is_not_a_plain_same_length_id_is_400_and_creates_nothing(self):
        for new_id in ("../../x", "../x", "AX_Y", "ax y", "ax_yy", "ax", "ax-y", "ax_\u00e9", "ax/y", "a\x00b_", ""):
            with self.subTest(new_id):
                r = self.post("/api/apply", {"tune": "draft", "new_id": new_id})
                self.assertEqual(r.status, 400, r.json)
        self.assertEqual((self.calls, self.tune_ids(), ts.job_snapshot()["state"]), ([], [], "idle"))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "tunes")))

    def test_the_stock_id_and_the_id_of_an_existing_default_car_are_refused_as_new_ids(self):
        stock = self.post("/api/apply", {"tune": "draft", "new_id": "ks_x"})
        self.assertEqual((stock.status, stock.json["error"]), (400, "new id equals the old id 'ks_x'"))
        self.make_tune()
        default = self.post("/api/apply", {"tune": "draft", "new_id": "ax_x"})
        self.assertEqual((default.status, default.json["error"]), (400, "ax_x is already a tune of ks_x"))
        self.assertEqual((self.calls, self.tune_ids()), ([], ["ax_x"]))

    def test_a_new_id_that_another_modded_car_or_a_package_uses_is_400(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        self.put_package("ax02")
        for new_id in ("ax01", "ax02"):
            with self.subTest(new_id):
                r = self.post("/api/apply", {"tune": "draft", "new_id": new_id})
                self.assertEqual((r.status, r.json["error"]), (400, "tuned car id %s is already used or reserved" % new_id))
        self.assertEqual((self.calls, self.tune_ids()), ([], ["ax01"]))

    def test_an_explicit_suffix_that_another_modded_car_uses_is_400_and_creates_nothing(self):
        self.make_tune(None, {"name_suffix": "_A"})
        r = self.post("/api/apply", {"tune": "draft", "suffix": "_A"})
        self.assertEqual((r.status, r.json), (400, {"error": "name suffix already used by ax_x"}))
        self.assertEqual((self.calls, self.tune_ids()), ([], ["ax_x"]))
        bad = self.post("/api/apply", {"tune": "draft", "suffix": ""})
        self.assertEqual(bad.status, 400)
        self.assertEqual(self.tune_ids(), ["ax_x"])

    def test_the_draft_creates_the_first_modded_car_under_the_default_id_and_builds_it(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        r = self.post("/api/apply", {"tune": "draft"})
        self.assertEqual((r.status, r.json), (202, {"job": "started"}))
        snap = self.wait_job()
        self.assertEqual(self.calls, [("apply", (self.work, "ks_x", "ax_x", True, self.mods), {"game": self.game_arg()})])
        self.assertEqual((snap["kind"], snap["state"], snap["error"]), ("apply", "done", None))
        self.assertEqual(snap["result"], dict(APPLY_RESULT, created=True))
        self.assertEqual(self.tune_ids(), ["ax_x"])
        self.assertEqual(self.tune_state(), {"limiter": 8000, "name_suffix": "_MY"})

    def test_the_second_modded_car_of_the_draft_gets_a_counter_id_and_the_next_suffix(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        self.post("/api/apply", {"tune": "draft"})
        self.wait_job()
        self.make_tune(tune.DRAFT, {"limiter": 9000})
        self.post("/api/apply", {"tune": "draft"})
        snap = self.wait_job()
        self.assertEqual([c[1][2] for c in self.calls], ["ax_x", "ax01"])
        self.assertEqual((snap["result"]["new_id"], snap["result"]["tune"], snap["result"]["created"]), ("ax01", "ax01", True))
        self.assertEqual(self.tune_ids(), ["ax_x", "ax01"])
        self.assertEqual(self.tune_state("ax01"), {"limiter": 9000, "name_suffix": "_MY2"})
        self.assertEqual(self.tune_state(), {"limiter": 8000, "name_suffix": "_MY"})

    def test_an_explicit_new_id_and_suffix_are_used_for_the_draft(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        self.post("/api/apply", {"tune": "draft", "new_id": "ax_z", "suffix": "_Z"})
        snap = self.wait_job()
        self.assertEqual(self.calls[0][1][2], "ax_z")
        self.assertEqual((snap["result"]["new_id"], snap["result"]["created"]), ("ax_z", True))
        self.assertEqual(self.tune_state("ax_z"), {"limiter": 8000, "name_suffix": "_Z"})
        self.assertEqual(self.tune_ids(), ["ax_z"])

    def test_the_draft_is_cleared_after_a_successful_build(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000, "aids_off": True})
        self.post("/api/apply", {"tune": "draft"})
        self.wait_job()
        self.assertEqual(self.tune_state(tune.DRAFT), {})
        self.assertFalse(any(r["changed"] for r in self.get("/api/settings?tune=draft").json))

    def test_the_draft_is_cleared_under_state_lock(self):
        held = []
        real = tune.save_state

        def spy(work, car, state, tune_id=None):
            held.append((tune_id, ts.STATE_LOCK.locked()))
            return real(work, car, state, tune_id)
        self.patch(tune, "save_state", spy)
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        self.post("/api/apply", {"tune": "draft"})
        self.wait_job()
        self.assertEqual(held[-1], (tune.DRAFT, True))

    def test_a_failed_build_keeps_the_draft_and_leaves_the_created_modded_car_listed(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        self.errors["apply"] = ValueError("clone self-check failed")
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)
        snap = self.wait_job()
        self.assertEqual((snap["state"], snap["error"], snap["result"]), ("error", "clone self-check failed", None))
        self.assertEqual(self.tune_state(tune.DRAFT), {"limiter": 8000})
        self.assertEqual(self.tune_ids(), ["ax_x"])
        self.assertEqual([m["id"] for m in self.get("/api/state").json["modded"]], ["ax_x"])

    def test_a_retry_after_a_failed_build_creates_one_more_modded_car(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        self.errors["apply"] = ValueError("boom")
        self.post("/api/apply", {"tune": "draft"})
        self.wait_job()
        self.errors.clear()
        self.post("/api/apply", {"tune": "draft"})
        self.wait_job()
        self.assertEqual(self.tune_ids(), ["ax_x", "ax01"])
        self.assertEqual(self.tune_state(tune.DRAFT), {})

    def test_an_empty_draft_creates_a_modded_car_with_the_stock_values(self):
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)
        self.wait_job()
        self.assertEqual(self.tune_state(), {"name_suffix": "_MY"})

    def test_a_modded_car_is_updated_under_its_own_id(self):
        self.make_tune("ax01", {"limiter": 8000, "name_suffix": "_A"})
        self.make_tune(tune.DRAFT, {"limiter": 9000})
        r = self.post("/api/apply", {"tune": "ax01"})
        self.assertEqual((r.status, r.json), (202, {"job": "started"}))
        snap = self.wait_job()
        self.assertEqual(self.calls, [("apply", (self.work, "ks_x", "ax01", True, self.mods), {"game": self.game_arg()})])
        self.assertEqual((snap["state"], snap["error"]), ("done", None))
        self.assertEqual(snap["result"], dict(APPLY_RESULT, new_id="ax01", tune="ax01", created=False))
        self.assertEqual(self.tune_ids(), ["ax01"])
        self.assertEqual(self.tune_state(tune.DRAFT), {"limiter": 9000})

    def test_without_a_tune_the_default_modded_car_is_updated(self):
        self.make_tune()
        self.assertEqual(self.post("/api/apply", {}).status, 202)
        snap = self.wait_job()
        self.assertEqual(self.calls, [("apply", (self.work, "ks_x", "ax_x", True, self.mods), {"game": self.game_arg()})])
        self.assertEqual((snap["state"], snap["result"]["created"]), ("done", False))
        self.assertEqual(self.post("/api/apply", {"tune": None}).status, 202)

    def test_without_a_tune_and_without_a_default_modded_car_apply_is_400(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        r = self.post("/api/apply", {})
        self.assertEqual((r.status, r.json), (400, {"error": "no modded car selected, pick one or use the draft of the car to create it"}))
        self.assertEqual((self.calls, self.tune_ids(), ts.job_snapshot()["state"]), ([], ["ax01"], "idle"))

    def test_an_update_ignores_new_id_and_suffix_in_the_body(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        self.post("/api/apply", {"tune": "ax01", "new_id": "../../x", "suffix": 5})
        self.wait_job()
        self.assertEqual(self.calls[0][1][2], "ax01")
        self.assertEqual((self.tune_ids(), self.tune_state("ax01")), (["ax01"], {"name_suffix": "_A"}))

    def test_an_update_whose_suffix_another_modded_car_uses_is_400_with_the_message(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.make_tune("ax01", {"name_suffix": "_A"})
        r = self.post("/api/apply", {"tune": "ax01"})
        self.assertEqual((r.status, r.json), (400, {"error": "name suffix _A is already used by ax_x"}))
        self.assertEqual(self.post("/api/apply", {}).json, {"error": "name suffix _A is already used by ax01"})
        self.assertEqual((self.calls, ts.job_snapshot()["state"]), ([], "idle"))

    def test_a_suffix_conflict_found_by_tune_apply_ends_the_job_in_the_error_state(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        self.errors["apply"] = ValueError("name suffix _A is already used by ax_x")
        self.assertEqual(self.post("/api/apply", {"tune": "ax01"}).status, 202)
        snap = self.wait_job()
        self.assertEqual((snap["state"], snap["error"]), ("error", "name suffix _A is already used by ax_x"))

    def test_an_unknown_modded_car_is_400_and_starts_no_job(self):
        r = self.post("/api/apply", {"tune": "ax01"})
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car ax01 of ks_x"}))
        self.assertEqual((self.calls, ts.job_snapshot()["state"]), ([], "idle"))

    def test_the_apply_log_has_the_build_line_and_the_result_lines(self):
        self.make_tune()
        self.post("/api/apply", {})
        self.assertEqual(self.wait_job()["log"], [
            "building ax_x, this takes a while ...", "applied 1 setting(s)",
            "  limiter: 7000 -> 8000  [data/engine.carengine, data/x.car]", "note: from build",
            "package: /w/ks_x/build/ax_x/ax_x.kspkg (7 bytes)", "installed: /m/ax_x.kspkg", "backup: no previous install"])

    def test_apply_is_refused_while_the_game_runs_and_creates_no_modded_car(self):
        self.game_up = True
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        r = self.post("/api/apply", {"tune": "draft"})
        self.assertEqual((r.status, r.json), (409, {"error": "close the game first, AssettoCorsaEVO.exe is running"}))
        self.assertEqual((self.calls, self.tune_ids(), ts.job_snapshot()["state"]), ([], [], "idle"))
        self.make_tune()
        self.assertEqual(self.post("/api/apply", {}).status, 409)
        self.assertEqual(self.tune_state(tune.DRAFT), {"limiter": 8000})

    def test_apply_is_allowed_again_once_the_game_is_closed(self):
        self.game_up = True
        self.post("/api/apply", {"tune": "draft"})
        self.game_up = False
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)

    def test_the_configured_game_package_reaches_tune_apply(self):
        ts.CONFIG["game"] = "other.kspkg"
        self.post("/api/apply", {"tune": "draft"})
        self.wait_job()
        args, kw = self.calls[0][1:]
        self.assertIn("other.kspkg", list(args) + list(kw.values()))

    def test_an_unexpandable_mods_folder_is_a_409_and_starts_no_job_and_creates_no_modded_car(self):
        ts.CONFIG["mods"] = "%ACE_TEST_NO_SUCH_VAR%/m"
        r = self.post("/api/apply", {"tune": "draft"})
        self.assertEqual((r.status, r.json), (409, {"error": "cannot expand the mods folder '%ACE_TEST_NO_SUCH_VAR%/m'"}))
        self.assertEqual((self.calls, ts.job_snapshot()["state"], self.tune_ids()), ([], "idle", []))

    def test_a_running_job_refuses_the_draft_before_a_modded_car_is_created(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/init").status, 202)
        self.entered.wait(5)
        r = self.post("/api/apply", {"tune": "draft"})
        self.assertEqual(r.status, 409, r.json)
        self.assertEqual(self.tune_ids(), [])
        self.finish_held_job()

    def test_a_failing_apply_ends_in_the_error_state(self):
        self.errors["apply"] = ValueError("no base car in x, run init first")
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)
        snap = self.wait_job()
        self.assertEqual((snap["state"], snap["error"], snap["result"]), ("error", "no base car in x, run init first", None))
        self.assertEqual(snap["log"][-1], "error: no base car in x, run init first")

    def test_the_proposed_ids_of_the_state_are_what_apply_from_the_draft_creates(self):
        for _ in range(3):
            state = self.get("/api/state").json
            self.post("/api/apply", {"tune": "draft"})
            new_id = self.wait_job()["result"]["new_id"]
            self.assertEqual(new_id, state["proposed_new_id"])
            self.assertEqual(self.tune_state(new_id)["name_suffix"], state["proposed_suffix"])


class TestInitRoute(ServerCase):
    def test_init_runs_tune_init_as_a_job_with_the_default_game_path(self):
        r = self.post("/api/init")
        self.assertEqual((r.status, r.json), (202, {"job": "started"}))
        snap = self.wait_job()
        self.assertEqual(self.calls, [("init", (self.work, "ks_x", os.path.expandvars(tune.DEFAULT_GAME)), {})])
        self.assertEqual((snap["kind"], snap["state"], snap["result"], snap["error"]), ("init", "done", INIT_RESULT, None))
        self.assertEqual(snap["log"], ["extracting the stock car from the game package (about 20 s) ...", "extracted the stock car",
                                       "/w/ks_x/base/content/cars/ks_x: 3 files, 1 folders, 10 bytes"])

    def test_the_configured_game_package_reaches_tune_init(self):
        ts.CONFIG["game"] = "other.kspkg"
        self.post("/api/init")
        self.wait_job()
        args, kw = self.calls[0][1:]
        self.assertIn("other.kspkg", list(args) + list(kw.values()))

    def test_init_of_a_present_base_says_so(self):
        self.patch(tune, "init", lambda *a, **k: dict(INIT_RESULT, present=True))
        self.post("/api/init")
        self.assertEqual(self.wait_job()["log"][1], "base already present")

    def test_init_for_another_game_car(self):
        self.post("/api/init", {"car": "ks_y"})
        self.wait_job()
        self.assertEqual(self.calls[0][1][1], "ks_y")

    def test_a_failing_init_ends_in_the_error_state(self):
        self.errors["init"] = ValueError("game package not found: x")
        self.post("/api/init")
        snap = self.wait_job()
        self.assertEqual((snap["state"], snap["error"], snap["log"][-1]), ("error", "game package not found: x", "error: game package not found: x"))


# -------------------------------------------------------------------------------------------------- tunes: resolution, state, edits, duplicate
class TestTuneResolution(TuneCase):
    def setUp(self):
        super().setUp()
        self.make_tune("ax01", {"name_suffix": "_A"})

    def test_without_a_tune_the_state_echoes_null(self):
        for path in ("/api/state", "/api/state?car=ks_x", "/api/state?tune=", "/api/state?tune"):
            with self.subTest(path):
                self.assertEqual(self.get(path).json["tune"], None)

    def test_the_draft_and_a_modded_car_are_echoed(self):
        self.assertEqual(self.get("/api/state?tune=draft").json["tune"], "draft")
        self.assertEqual(self.get("/api/state?car=ks_x&tune=ax01").json["tune"], "ax01")

    def test_the_draft_needs_no_modded_car(self):
        os.remove(tune.state_path(self.work, "ks_x", "ax01"))
        self.assertEqual(self.tune_ids(), [])
        self.assertEqual(self.get("/api/state?tune=draft").status, 200)
        self.assertEqual(self.get("/api/settings?tune=draft").status, 200)

    def test_the_default_modded_car_can_be_selected_only_when_it_exists(self):
        r = self.get("/api/state?tune=ax_x")
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car ax_x of ks_x"}))
        self.make_tune()
        self.assertEqual(self.get("/api/state?tune=ax_x").json["tune"], "ax_x")

    def test_an_unknown_modded_car_is_400_on_both_get_routes(self):
        for path in ("/api/state?tune=nope", "/api/settings?tune=nope", "/api/state?tune=../x", "/api/state?tune=%2e%2e%2fx",
                     "/api/state?tune=DRAFT", "/api/state?tune=ax02", "/api/state?tune=ks_x"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith("unknown modded car "), r.json)
                self.assertTrue(r.json["error"].endswith(" of ks_x"), r.json)

    def test_a_modded_car_of_another_stock_car_is_unknown(self):
        tune.save_state(self.work, "ks_y", {}, "ax02")
        r = self.get("/api/state?tune=ax02")
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car ax02 of ks_x"}))
        self.assertEqual(self.get("/api/state?car=ks_y&tune=ax02").json["tune"], "ax02")
        self.assertEqual(self.get("/api/state?car=ks_y&tune=ax01").status, 400)

    def test_an_unknown_modded_car_is_400_on_every_post_route(self):
        for path in ("/api/set", "/api/unset", "/api/reset_all", "/api/init", "/api/duplicate", "/api/apply"):
            with self.subTest(path):
                r = self.post(path, {"tune": "nope", "id": "limiter", "value": "1"})
                self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car nope of ks_x"}))
        self.assertEqual((self.calls, ts.job_snapshot()["state"], self.tune_ids()), ([], "idle", ["ax01"]))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x", "draft")))

    def test_the_tune_must_be_text(self):
        for value in (5, ["draft"], {"id": "ax01"}, True, 0, 1.5):
            for path in ("/api/set", "/api/reset_all", "/api/duplicate", "/api/apply"):
                with self.subTest(repr(value), path=path):
                    r = self.post(path, {"tune": value, "id": "limiter", "value": "1"})
                    self.assertEqual((r.status, r.json), (400, {"error": "tune must be text"}))

    def test_a_null_tune_is_the_default_tune(self):
        self.assertEqual(self.post("/api/set", {"id": "limiter", "value": "8000", "tune": None}).status, 200)
        self.assertEqual(self.saved_state(), {"limiter": 8000})

    def test_an_empty_text_tune_in_the_body_is_unknown(self):
        r = self.post("/api/reset_all", {"tune": ""})
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car  of ks_x"}))

    def test_a_post_takes_the_tune_from_the_query_when_the_body_has_none_and_the_body_wins(self):
        self.post("/api/set?tune=ax01", {"id": "limiter", "value": "8000"})
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A", "limiter": 8000})
        self.post("/api/set?tune=ax01", {"id": "limiter", "value": "9000", "tune": "draft"})
        self.assertEqual((self.tune_state("ax01")["limiter"], self.tune_state("draft")), (8000, {"limiter": 9000}))

    def test_an_unknown_car_is_reported_before_an_unknown_tune(self):
        r = self.get("/api/state?car=nope&tune=nope")
        self.assertTrue(r.json["error"].startswith("unknown car"), r.json)

    def test_request_tune(self):
        self.assertIsNone(ts.request_tune(None, "", "ks_x"))
        self.assertIsNone(ts.request_tune(None, "car=ks_x", "ks_x"))
        self.assertEqual(ts.request_tune(None, "tune=ax01", "ks_x"), "ax01")
        self.assertEqual(ts.request_tune("draft", "tune=ax01", "ks_x"), "draft")
        self.assertEqual(ts.request_tune("ax01", "tune=nope", "ks_x"), "ax01")
        self.assertEqual(ts.request_tune(None, "a=1&tune=draft&b=2", "ks_x"), "draft")
        for value, query, text in (("nope", "", "unknown modded car nope of ks_x"), (None, "tune=nope", "unknown modded car nope of ks_x"),
                                   (5, "", "tune must be text"), (["ax01"], "", "tune must be text")):
            with self.subTest(value, query=query), self.assertRaises(ts.ApiError) as cm:
                ts.request_tune(value, query, "ks_x")
            self.assertEqual((cm.exception.status, cm.exception.message), (400, text))


class TestStateOfTunes(TuneCase):
    def test_a_car_without_modded_cars_proposes_the_default_id_and_suffix(self):
        r = self.get("/api/state").json
        self.assertEqual((r["modded"], r["default_tune_taken"], r["proposed_new_id"], r["proposed_suffix"]), ([], False, "ax_x", "_MY"))
        self.assertNotIn("modded_error", r)
        self.assertEqual(r["default_new_id"], "ax_x")

    def test_the_modded_cars_are_listed_with_their_flags(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.make_tune("ax01", {"name_suffix": "_B"})
        self.put_package("ax01")
        build = os.path.join(tune.build_dir(self.work, "ks_x"), "ax_x")
        os.makedirs(build)
        with open(os.path.join(build, "ax_x.kspkg"), "wb"):
            pass
        r = self.get("/api/state").json
        self.assertEqual([set(m) for m in r["modded"]], [MODDED_KEYS, MODDED_KEYS])
        self.assertEqual(r["modded"], [
            {"id": "ax_x", "stock": "ks_x", "label": "Car X_A", "name_suffix": "_A", "default": True, "installed": False, "built": True},
            {"id": "ax01", "stock": "ks_x", "label": "Car X_B", "name_suffix": "_B", "default": False, "installed": True, "built": False}])

    def test_the_list_is_the_one_of_tune_list_modded_for_the_configured_mods_folder(self):
        self.make_tune("ax01", {"name_suffix": "_B"})
        seen = []

        def spy(work, mods_dir=None):
            seen.append((work, mods_dir))
            return [{"id": "ax01"}]
        self.patch(tune, "list_modded", spy)
        self.assertEqual(self.get("/api/state").json["modded"], [{"id": "ax01"}])
        self.assertEqual(seen, [(self.work, os.path.abspath(self.mods))])

    def test_the_modded_cars_of_every_stock_car_are_listed(self):
        self.make_tune("ax01", {"name_suffix": "_B"})
        tune.save_state(self.work, "ks_y", {"name_suffix": "_C"}, "ax02")
        self.assertEqual(sorted(m["id"] for m in self.get("/api/state").json["modded"]), ["ax01", "ax02"])
        self.assertEqual(sorted(m["id"] for m in self.get("/api/state?car=ks_y").json["modded"]), ["ax01", "ax02"])

    def test_a_list_that_cannot_be_read_gives_an_empty_list_and_the_error_text(self):
        def broken(work, mods_dir=None):
            raise ValueError("tune_state.json: expected an object")
        self.patch(tune, "list_modded", broken)
        r = self.get("/api/state")
        self.assertEqual(r.status, 200)
        self.assertEqual((r.json["modded"], r.json["modded_error"]), ([], "tune_state.json: expected an object"))
        self.assertEqual((r.json["proposed_new_id"], r.json["default_tune_taken"]), ("ax_x", False))

    def test_a_damaged_state_file_does_not_make_the_state_a_500(self):
        self.write(self.state_file(), "[1, 2]")
        r = self.get("/api/state")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json["modded"], [])
        self.assertIn("expected an object", r.json["modded_error"])
        self.assertEqual((r.json["default_tune_taken"], r.json["proposed_new_id"], r.json["proposed_suffix"]), (False, None, None))

    def test_an_existing_default_modded_car_is_taken_and_the_next_id_and_suffix_are_proposed(self):
        self.make_tune()
        r = self.get("/api/state").json
        self.assertEqual((r["default_tune_taken"], r["proposed_new_id"], r["proposed_suffix"]), (True, "ax01", "_MY2"))
        self.make_tune("ax01", {"name_suffix": "_MY2"})
        r = self.get("/api/state").json
        self.assertEqual((r["proposed_new_id"], r["proposed_suffix"]), ("ax02", "_MY3"))

    def test_a_build_folder_alone_takes_the_default_modded_car(self):
        os.makedirs(os.path.join(tune.build_dir(self.work, "ks_x"), "ax_x"))
        r = self.get("/api/state").json
        self.assertEqual((r["default_tune_taken"], r["proposed_new_id"], [m["id"] for m in r["modded"]]), (True, "ax01", ["ax_x"]))

    def test_installed_packages_take_their_ids_out_of_the_proposals(self):
        self.make_tune()
        self.put_package("ax01")
        self.assertEqual(self.get("/api/state").json["proposed_new_id"], "ax02")

    def test_the_proposals_are_per_stock_car(self):
        self.make_tune()
        r = self.get("/api/state?car=ks_y").json
        self.assertEqual((r["default_tune_taken"], r["proposed_new_id"], r["proposed_suffix"]), (False, "ax_y", "_MY"))

    def test_no_free_id_proposes_null(self):
        self.make_tune()

        def full(*args, **kw):
            raise ValueError("no free tuned car id left for ks_x")
        self.patch(tune, "free_tune_id", full)
        r = self.get("/api/state")
        self.assertEqual((r.status, r.json["proposed_new_id"], r.json["default_tune_taken"]), (200, None, True))

    def test_installed_is_the_package_of_the_selected_modded_car(self):
        self.make_tune("ax01", {"name_suffix": "_B"})
        self.put_package("ax01", b"123456")
        sel = self.get("/api/state?tune=ax01").json["installed"]
        self.assertEqual((sel["path"], sel["exists"], sel["bytes"]), (os.path.join(os.path.abspath(self.mods), "ax01.kspkg"), True, 6))
        self.assertRegex(sel["modified"], r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d$")

    def test_installed_of_the_draft_and_of_no_tune_is_the_package_of_the_default_id(self):
        self.put_package("ax01")
        self.put_package("ax_x", b"12")
        for path in ("/api/state", "/api/state?tune=draft"):
            with self.subTest(path):
                inst = self.get(path).json["installed"]
                self.assertEqual((os.path.basename(inst["path"]), inst["exists"], inst["bytes"]), ("ax_x.kspkg", True, 2))
        os.remove(os.path.join(self.mods, "ax_x.kspkg"))
        self.make_tune("ax01", {"name_suffix": "_B"})
        self.assertFalse(self.get("/api/state?tune=draft").json["installed"]["exists"])
        self.assertTrue(self.get("/api/state?tune=ax01").json["installed"]["exists"])

    def test_installed_info_for_a_tune(self):
        self.assertTrue(ts.installed_info("ks_x", "ax01")["path"].endswith("ax01.kspkg"))
        for tune_id in (None, "draft"):
            self.assertTrue(ts.installed_info("ks_x", tune_id)["path"].endswith("ax_x.kspkg"))

    def test_the_cars_list_keeps_the_default_package_flag(self):
        self.make_tune("ax01", {"name_suffix": "_B"})
        self.put_package("ax01")
        self.assertFalse(self.get("/api/state?tune=ax01").json["cars"][0]["installed"])

    def test_an_unexpandable_mods_folder_is_409_with_a_tune_too(self):
        ts.CONFIG["mods"] = "%ACE_TEST_NO_SUCH_VAR%/m"
        self.assertEqual(self.get("/api/state?tune=draft").status, 409)


class TestSettingsOfTunes(TuneCase):
    def row(self, rows, setting_id="limiter"):
        return next(r for r in rows if r["id"] == setting_id)

    def test_settings_show_the_values_of_the_selected_modded_car(self):
        self.make_tune("ax01", {"limiter": 8000, "name_suffix": "_A"})
        rows = self.get("/api/settings?tune=ax01").json
        self.assertEqual([r["id"] for r in rows], ["limiter", "aids_off", "name_suffix"])
        self.assertEqual((self.row(rows)["value"], self.row(rows)["default"], self.row(rows)["changed"]), (8000, 7000, True))
        self.assertEqual((self.row(rows, "name_suffix")["value"], self.row(rows, "name_suffix")["changed"]), ("_A", True))

    def test_settings_of_the_draft_start_from_the_stock_defaults(self):
        self.make_tune(None, {"limiter": 8000})
        rows = self.get("/api/settings?tune=draft").json
        self.assertEqual((self.row(rows)["value"], self.row(rows)["changed"]), (7000, False))
        self.assertEqual(self.row(rows, "name_suffix")["value"], "_MY")

    def test_settings_without_a_tune_are_those_of_the_default_modded_car(self):
        self.make_tune("ax01", {"limiter": 9000, "name_suffix": "_A"})
        self.make_tune(tune.DRAFT, {"limiter": 6000})
        self.assertEqual(self.row(self.get("/api/settings").json)["value"], 7000)
        self.make_tune(None, {"limiter": 8000})
        self.assertEqual(self.row(self.get("/api/settings").json)["value"], 8000)
        self.assertEqual(self.row(self.get("/api/settings?tune=ax_x").json)["value"], 8000)

    def test_settings_of_a_tune_are_409_without_a_base(self):
        tune.save_state(self.work, "ks_y", {"name_suffix": "_C"}, "ax02")
        for tune_id in ("draft", "ax02"):
            with self.subTest(tune_id):
                r = self.get("/api/settings?car=ks_y&tune=" + tune_id)
                self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))

    def test_set_on_a_modded_car_changes_only_its_state(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        r = self.post("/api/set", {"id": "limiter", "value": "8000", "tune": "ax01"})
        self.assertEqual((r.status, r.json["row"]["value"], r.json["row"]["changed"], r.json["warnings"]), (200, 8000, True, []))
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A", "limiter": 8000})
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x", "draft")))

    def test_set_on_the_draft_needs_only_the_base_car(self):
        r = self.post("/api/set", {"id": "limiter", "value": "8000", "tune": "draft"})
        self.assertEqual((r.status, r.json["row"]["value"]), (200, 8000))
        self.assertEqual(self.tune_state("draft"), {"limiter": 8000})
        self.assertEqual(os.path.basename(tune.state_path(self.work, "ks_x", "draft")), "draft_state.json")
        self.assertEqual(self.tune_ids(), [])
        self.assertFalse(os.path.exists(self.state_file()))

    def test_set_on_a_tune_without_a_base_is_409_and_writes_nothing(self):
        tune.save_state(self.work, "ks_y", {"name_suffix": "_C"}, "ax02")
        for tune_id in ("draft", "ax02"):
            with self.subTest(tune_id):
                r = self.post("/api/set", {"car": "ks_y", "tune": tune_id, "id": "limiter", "value": "8000"})
                self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))
        self.assertEqual(tune.load_state(self.work, "ks_y", "ax02"), {"name_suffix": "_C"})
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_y", "draft")))

    def test_the_default_the_draft_and_a_modded_car_keep_separate_values(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.post("/api/set", {"id": "limiter", "value": "9000", "tune": "ax01"})
        self.post("/api/set", {"id": "limiter", "value": "6000", "tune": "draft"})
        self.assertEqual(self.saved_state(), {"limiter": 8000})
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A", "limiter": 9000})
        self.assertEqual(self.tune_state("draft"), {"limiter": 6000})
        for query, value in (("", 8000), ("?tune=ax_x", 8000), ("?tune=ax01", 9000), ("?tune=draft", 6000)):
            with self.subTest(query):
                self.assertEqual(self.row(self.get("/api/settings" + query).json)["value"], value)

    def test_set_with_a_bad_value_on_a_tune_changes_nothing(self):
        self.make_tune("ax01", {"limiter": 7500, "name_suffix": "_A"})
        r = self.post("/api/set", {"id": "limiter", "value": "fast", "tune": "ax01"})
        self.assertEqual(r.status, 400)
        self.assertEqual(self.tune_state("ax01"), {"limiter": 7500, "name_suffix": "_A"})

    def test_unset_on_a_modded_car_and_on_the_draft(self):
        self.make_tune("ax01", {"limiter": 8000, "aids_off": True, "name_suffix": "_A"})
        self.make_tune(tune.DRAFT, {"limiter": 6000})
        self.make_tune(None, {"limiter": 5000})
        r = self.post("/api/unset", {"id": "limiter", "tune": "ax01"})
        self.assertEqual((r.status, r.json["row"]["value"], r.json["row"]["changed"]), (200, 7000, False))
        self.assertEqual(self.tune_state("ax01"), {"aids_off": True, "name_suffix": "_A"})
        r = self.post("/api/unset", {"id": "limiter", "tune": "draft"})
        self.assertEqual((r.status, self.tune_state("draft")), (200, {}))
        self.assertEqual(self.saved_state(), {"limiter": 5000})

    def test_edits_on_a_tune_are_refused_while_a_job_runs(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        self.hold_jobs()
        self.assertEqual(self.post("/api/apply", {"tune": "ax01"}).status, 202)
        for path, body in (("/api/set", {"id": "limiter", "value": "8000"}), ("/api/unset", {"id": "limiter"}), ("/api/reset_all", {}),
                           ("/api/duplicate", {})):
            for tune_id in ("ax01", "draft"):
                with self.subTest(path, tune=tune_id):
                    self.assertEqual(self.post(path, dict(body, tune=tune_id)).status, 409)
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A"})

    def test_every_state_write_for_a_tune_happens_under_state_lock(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        held = []
        real = tune.save_state

        def spy(*args, **kw):
            held.append(ts.STATE_LOCK.locked())
            return real(*args, **kw)
        self.patch(tune, "save_state", spy)
        self.post("/api/set", {"id": "limiter", "value": "8000", "tune": "ax01"})
        self.post("/api/unset", {"id": "limiter", "tune": "ax01"})
        self.post("/api/reset_all", {"tune": "ax01"})
        self.post("/api/reset_all", {"tune": "draft"})
        self.post("/api/duplicate", {"tune": "ax01"})
        self.assertEqual(held, [True] * 5)

    def test_the_settings_of_a_tune_are_built_under_state_lock(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        held = []
        real = tune.effective_rows

        def spy(*args, **kw):
            held.append((kw.get("tune"), ts.STATE_LOCK.locked()))
            return real(*args, **kw)
        self.patch(tune, "effective_rows", spy)
        self.get("/api/settings?tune=ax01")
        self.assertEqual(held, [("ax01", True)])


class TestResetAllOfTunes(TuneCase):
    def test_the_default_modded_car_is_cleared_completely(self):
        self.make_tune(None, {"limiter": 8000, "name_suffix": "_A"})
        self.assertEqual(self.post("/api/reset_all").json, {"ok": True})
        self.assertEqual(self.saved_state(), {})
        self.assertEqual(self.post("/api/reset_all", {"tune": "ax_x"}).status, 200)
        self.assertEqual(self.saved_state(), {})

    def test_the_draft_is_cleared_completely(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000, "name_suffix": "_A"})
        self.make_tune("ax01", {"limiter": 9000, "name_suffix": "_B"})
        r = self.post("/api/reset_all", {"tune": "draft"})
        self.assertEqual((r.status, r.json), (200, {"ok": True}))
        self.assertEqual(self.tune_state("draft"), {})
        self.assertEqual(self.tune_state("ax01"), {"limiter": 9000, "name_suffix": "_B"})

    def test_another_modded_car_keeps_its_name_suffix(self):
        self.make_tune(None, {"limiter": 8000, "name_suffix": "_A"})
        self.make_tune("ax01", {"limiter": 9000, "aids_off": True, "name_suffix": "_B"})
        r = self.post("/api/reset_all", {"tune": "ax01"})
        self.assertEqual((r.status, r.json), (200, {"ok": True}))
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_B"})
        self.assertEqual(self.saved_state(), {"limiter": 8000, "name_suffix": "_A"})
        self.assertEqual([t["name_suffix"] for t in tune.list_tunes(self.work, "ks_x")], ["_A", "_B"])
        rows = self.get("/api/settings?tune=ax01").json
        self.assertEqual([r["changed"] for r in rows], [False, False, True])

    def test_a_modded_car_without_a_saved_suffix_is_reset_to_an_empty_state(self):
        self.make_tune("ax01", {"limiter": 9000})
        self.post("/api/reset_all", {"tune": "ax01"})
        self.assertEqual(self.tune_state("ax01"), {})
        self.assertEqual(self.tune_ids(), ["ax01"])

    def test_reset_all_of_a_tune_without_a_base_is_409_and_writes_nothing(self):
        tune.save_state(self.work, "ks_y", {"name_suffix": "_C", "limiter": 1}, "ax02")
        for tune_id in ("draft", "ax02"):
            with self.subTest(tune_id):
                r = self.post("/api/reset_all", {"car": "ks_y", "tune": tune_id})
                self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))
        self.assertEqual(tune.load_state(self.work, "ks_y", "ax02"), {"name_suffix": "_C", "limiter": 1})
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_y", "draft")))


class TestDuplicateRoute(TuneCase):
    def test_the_default_modded_car_is_copied_with_an_automatic_id_and_suffix(self):
        self.make_tune(None, {"limiter": 8000, "name_suffix": "_A"})
        r = self.post("/api/duplicate", {})
        self.assertEqual((r.status, r.json), (200, {"id": "ax01", "stock": "ks_x", "name_suffix": "_A2"}))
        self.assertEqual(self.tune_state("ax01"), {"limiter": 8000, "name_suffix": "_A2"})
        self.assertEqual(self.saved_state(), {"limiter": 8000, "name_suffix": "_A"})
        self.assertEqual(self.tune_ids(), ["ax_x", "ax01"])

    def test_a_modded_car_is_copied_and_the_counter_goes_on(self):
        self.make_tune("ax01", {"limiter": 8000, "name_suffix": "_A"})
        self.make_tune("ax02", {"limiter": 9000, "name_suffix": "_B"})
        r = self.post("/api/duplicate", {"tune": "ax01"})
        self.assertEqual((r.status, r.json), (200, {"id": "ax03", "stock": "ks_x", "name_suffix": "_A2"}))
        self.assertEqual(self.tune_state("ax03"), {"limiter": 8000, "name_suffix": "_A2"})
        self.assertEqual(self.tune_state("ax01"), {"limiter": 8000, "name_suffix": "_A"})

    def test_the_draft_is_copied_and_stays_as_it_is(self):
        self.make_tune(tune.DRAFT, {"limiter": 8000})
        r = self.post("/api/duplicate", {"tune": "draft"})
        self.assertEqual((r.status, r.json), (200, {"id": "ax01", "stock": "ks_x", "name_suffix": "_MY"}))
        self.assertEqual(self.tune_state("ax01"), {"limiter": 8000, "name_suffix": "_MY"})
        self.assertEqual(self.tune_state("draft"), {"limiter": 8000})

    def test_an_explicit_id_and_suffix_are_used(self):
        self.make_tune(None, {"name_suffix": "_A"})
        r = self.post("/api/duplicate", {"new_id": "ax_z", "suffix": "_Z"})
        self.assertEqual((r.status, r.json), (200, {"id": "ax_z", "stock": "ks_x", "name_suffix": "_Z"}))
        self.assertEqual(self.tune_state("ax_z"), {"name_suffix": "_Z"})

    def test_null_id_and_suffix_mean_automatic(self):
        self.make_tune(None, {"name_suffix": "_A"})
        r = self.post("/api/duplicate", {"new_id": None, "suffix": None})
        self.assertEqual((r.json["id"], r.json["name_suffix"]), ("ax01", "_A2"))

    def test_an_id_that_is_used_is_400_with_the_message_and_changes_nothing(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.make_tune("ax01", {"name_suffix": "_B"})
        self.put_package("ax02")
        for new_id, text in (("ax01", "tuned car id ax01 is already used or reserved"), ("ax02", "tuned car id ax02 is already used or reserved"),
                             ("ax_x", "ax_x is already a tune of ks_x"), ("ax_y", "tuned car id ax_y is already used or reserved"),
                             ("ks_x", "new id equals the old id 'ks_x'")):
            with self.subTest(new_id):
                r = self.post("/api/duplicate", {"new_id": new_id})
                self.assertEqual((r.status, r.json), (400, {"error": text}))
        self.assertEqual(self.tune_ids(), ["ax_x", "ax01"])

    def test_an_id_that_is_not_a_plain_same_length_id_is_400(self):
        for new_id in ("../../x", "../x", "AX_Y", "ax y", "ax_yy", "ax", "ax-y", "ax_\u00e9", "ax/y", "a\x00b_", ""):
            with self.subTest(new_id):
                self.assertEqual(self.post("/api/duplicate", {"new_id": new_id}).status, 400)
        self.assertEqual(self.tune_ids(), [])
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_x", "tunes")))

    def test_a_suffix_that_another_modded_car_uses_is_400_with_the_message(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.make_tune("ax01", {"name_suffix": "_B"})
        r = self.post("/api/duplicate", {"suffix": "_B"})
        self.assertEqual((r.status, r.json), (400, {"error": "name suffix already used by ax01"}))
        self.assertEqual(self.post("/api/duplicate", {"suffix": ""}).status, 400)
        self.assertEqual(self.post("/api/duplicate", {"suffix": "x" * 31}).status, 400)
        self.assertEqual(self.tune_ids(), ["ax_x", "ax01"])

    def test_an_id_or_suffix_that_is_not_text_is_400(self):
        for body, text in (({"new_id": 5}, "new_id must be text"), ({"new_id": ["ax01"]}, "new_id must be text"),
                           ({"suffix": 5}, "suffix must be text"), ({"suffix": True}, "suffix must be text")):
            with self.subTest(body):
                self.assertEqual(self.post("/api/duplicate", body).json, {"error": text})
        self.assertEqual(self.tune_ids(), [])

    def test_duplicate_is_409_while_a_job_runs_and_writes_nothing(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.hold_jobs()
        self.assertEqual(self.post("/api/init").status, 202)
        self.entered.wait(5)
        r = self.post("/api/duplicate", {})
        self.assertEqual(r.status, 409, r.json)
        self.assertEqual(self.tune_ids(), ["ax_x"])
        self.finish_held_job()
        self.assertEqual(self.post("/api/duplicate", {}).status, 200)

    def test_duplicate_needs_the_base_car(self):
        tune.save_state(self.work, "ks_y", {"name_suffix": "_C"}, "ax02")
        for tune_id in (None, "draft", "ax02"):
            with self.subTest(tune_id):
                r = self.post("/api/duplicate", {"car": "ks_y", "tune": tune_id})
                self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))
        self.assertEqual([t["id"] for t in tune.list_tunes(self.work, "ks_y")], ["ax02"])

    def test_an_unexpandable_mods_folder_is_409(self):
        ts.CONFIG["mods"] = "%ACE_TEST_NO_SUCH_VAR%/m"
        r = self.post("/api/duplicate", {})
        self.assertEqual((r.status, r.json), (409, {"error": "cannot expand the mods folder '%ACE_TEST_NO_SUCH_VAR%/m'"}))
        self.assertEqual(self.tune_ids(), [])

    def test_a_duplicate_shows_up_in_the_state_and_starts_no_job(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.post("/api/duplicate", {})
        state = self.get("/api/state").json
        self.assertEqual([(m["id"], m["label"]) for m in state["modded"]], [("ax_x", "Car X_A"), ("ax01", "Car X_A2")])
        self.assertEqual((state["job"]["state"], self.calls), ("idle", []))

    def test_the_duplicate_is_not_built_or_installed(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.post("/api/duplicate", {})
        self.assertFalse(os.path.exists(os.path.join(tune.build_dir(self.work, "ks_x"), "ax01")))
        self.assertFalse(os.path.exists(os.path.join(self.mods, "ax01.kspkg")))
        modded = {m["id"]: m for m in self.get("/api/state").json["modded"]}
        self.assertEqual((modded["ax01"]["built"], modded["ax01"]["installed"]), (False, False))

    def test_the_automatic_id_takes_the_installed_packages_into_account(self):
        self.make_tune(None, {"name_suffix": "_A"})
        self.put_package("ax01")
        self.assertEqual(self.post("/api/duplicate", {}).json["id"], "ax02")

    def test_the_default_modded_car_is_the_source_when_no_tune_is_given_even_if_it_does_not_exist(self):
        r = self.post("/api/duplicate", {})
        self.assertEqual((r.status, r.json), (200, {"id": "ax01", "stock": "ks_x", "name_suffix": "_MY"}))
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_MY"})


# -------------------------------------------------------------------------------------------------- setting groups
class TestGroupsRoute(TuneCase):
    """GET /api/groups: the group list of the catalogue, static, independent of the car, the tune and the base car."""

    def setUp(self):
        super().setUp()
        self.cat = mini_catalogue(limiter(), suffix(), tyre_dy("front"))
        self.cat["groups"] = [{"name": "Tyres", "description": "Grip and türkis"}, {"name": "G", "description": "General"}]

    def expected(self):
        return {"groups": [{"name": "Tyres", "description": "Grip and türkis"}, {"name": "G", "description": "General"}]}

    def test_it_answers_the_groups_with_name_and_description_in_catalogue_order(self):
        r = self.get("/api/groups")
        self.assertEqual((r.status, r.headers.get("Content-Type"), r.headers.get("Cache-Control")),
                         (200, "application/json; charset=utf-8", "no-store"))
        self.assertEqual(r.json, self.expected())
        self.assertEqual(r.json, {"groups": tune.group_list()})
        self.assertEqual([g["name"] for g in r.json["groups"]], ["Tyres", "G"])
        self.assertEqual([set(g) for g in r.json["groups"]], [{"name", "description"}] * 2)

    def test_the_groups_of_the_real_catalogue_are_answered_in_the_order_of_the_file(self):
        real = tune.read_json(tune.CATALOGUE)
        self.patch(tune, "load_catalogue", lambda path=None: real)
        r = self.get("/api/groups")
        self.assertEqual(r.status, 200)
        self.assertEqual(r.json, {"groups": [{"name": g["name"], "description": g["description"]} for g in real["groups"]]})
        self.assertGreater(len(r.json["groups"]), 1)

    def test_it_needs_no_base_car(self):
        self.assertFalse(ts.base_present(self.work, "ks_y"))
        self.assertEqual(self.get("/api/settings?car=ks_y").status, 409)
        r = self.get("/api/groups?car=ks_y")
        self.assertEqual((r.status, r.json), (200, self.expected()))

    def test_it_is_the_same_for_the_draft_the_default_tune_and_a_modded_car(self):
        self.make_tune("ax01", {"limiter": 9000})
        self.make_tune(None, {"limiter": 8000})
        for query in ("", "?tune=draft", "?tune=ax01", "?tune=ax_x", "?car=ks_x&tune=ax01"):
            with self.subTest(query):
                r = self.get("/api/groups" + query)
                self.assertEqual((r.status, r.json), (200, self.expected()))

    def test_the_dispatcher_still_resolves_the_car_and_the_tune(self):
        r = self.get("/api/groups?car=nope")
        self.assertEqual(r.status, 400)
        self.assertTrue(r.json["error"].startswith("unknown car"), r.json)
        r = self.get("/api/groups?tune=nope")
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car nope of ks_x"}))

    def test_it_needs_neither_the_state_lock_nor_an_idle_job_and_writes_nothing(self):
        with ts.STATE_LOCK:
            self.assertEqual(self.get("/api/groups").status, 200)
        ts.JOB["state"] = "running"
        self.assertEqual(self.get("/api/groups").status, 200)
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertEqual(self.tune_ids(), [])

    def test_it_checks_the_host_and_is_405_for_other_methods_and_404_for_a_post(self):
        r = self.get("/api/groups", host="evil.example")
        self.assertEqual((r.status, r.json), (403, {"error": "forbidden host"}))
        for method in ("PUT", "DELETE", "PATCH"):
            with self.subTest(method):
                r = self.request(method, "/api/groups")
                self.assertEqual((r.status, r.json, r.headers.get("Allow")), (405, {"error": "method not allowed"}, "GET, POST"))
        self.assertEqual(self.post("/api/groups").status, 404)

    def test_the_handler_gets_the_resolved_car_and_tune_and_no_query(self):
        seen = []
        with mock.patch.dict(ts.GET_ROUTES, {"/api/groups": lambda car, tune_id: seen.append((car, tune_id)) or {"groups": []}}):
            r = self.get("/api/groups?id=soft&tune=draft")
        self.assertEqual((r.status, r.json, seen), (200, {"groups": []}, [("ks_x", "draft")]))
        self.assertNotIn("/api/groups", ts.QUERY_ROUTES)


# -------------------------------------------------------------------------------------------------- tyre library and garage
class TyreCase(TuneCase):
    """TuneCase with the tyre settings in the catalogue, three shared tyre files and one preset (stock pairs a+b and s+s) in ks_x."""

    def setUp(self):
        super().setUp()
        self.cat = mini_catalogue(limiter(), aids_off(), suffix(), boost(), tyre_dy("front"), tyre_dy("rear"))
        self.fc.add_shared("tyres/road/a.tyre", {"modelData": {"Dy0": 1.25}})
        self.fc.add_shared("tyres/road/b.tyre", {"modelData": {"Dy0": 1.0}})
        self.fc.add_shared("tyres/slick/s.tyre", {"modelData": {"Dy0": 1.5}})
        self.fc.add("presets/p.compatibletyres", {"physic_compounds": [
            {"front_tyre_data_path": ROAD_A, "rear_tyre_data_paths": ROAD_B},
            {"front_tyre_data_path": SLICK_S, "rear_tyre_data_paths": [SLICK_S]}]})

    def make_tyre(self, name="Soft", key=KEY_AB):
        return tune.create_tyre(self.work, name, key)["id"]

    def library_bytes(self):
        folder, out = os.path.join(self.work, "tyres"), {}
        for n in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            with open(os.path.join(folder, n), "rb") as f:
                out[n] = f.read()
        return out

    def rows_of(self, tyre_id):
        return json.loads(json.dumps(tune.tyre_rows(self.work, tyre_id, self.cat)))

    def row(self, rows, setting_id="tyre_dy_front"):
        return next(r for r in rows if r["id"] == setting_id)


class TestTyreReadRoutes(TyreCase):
    def test_tyres_lists_the_library_and_the_sources_of_the_extracted_cars(self):
        r = self.get("/api/tyres")
        self.assertEqual((r.status, r.headers.get("Content-Type")), (200, "application/json; charset=utf-8"))
        self.assertEqual(r.json, {"tyres": [], "sources": tune.list_source_tyres(self.work)})
        self.assertEqual([(s["key"], s["cars"]) for s in r.json["sources"]], [(KEY_AB, ["ks_x"]), (KEY_SS, ["ks_x"])])
        self.assertEqual(set(r.json["sources"][0]), {"key", "front", "rear", "label", "cars"})
        self.make_tyre("Soft")
        self.write(os.path.join(self.work, "tyres", "broken.json"), "not json")
        r = self.get("/api/tyres")
        self.assertEqual(r.json["tyres"][0], {"id": "soft", "name": "Soft", "source": {"front": ROAD_A, "rear": ROAD_B}, "changed": 0})
        self.assertEqual([t["id"] for t in r.json["tyres"]], ["soft", "broken"])
        self.assertIn("error", r.json["tyres"][1])
        self.assertEqual(r.json, json.loads(json.dumps({"tyres": tune.list_tyres(self.work), "sources": tune.list_source_tyres(self.work)})))

    def test_tyres_of_an_empty_work_folder_are_two_empty_lists(self):
        self.fc.store.clear()
        self.assertEqual(self.get("/api/tyres?car=ks_y").json, {"tyres": [], "sources": []})

    def test_the_library_routes_need_no_base_car(self):
        self.assertFalse(ts.base_present(self.work, "ks_y"))
        self.assertEqual(self.get("/api/tyres?car=ks_y").status, 200)
        r = self.post("/api/tyre_new", {"car": "ks_y", "name": "Soft", "source": KEY_AB})
        self.assertEqual(r.status, 200)
        self.assertEqual(self.get("/api/tyre?car=ks_y&id=soft").status, 200)

    def test_tyre_answers_with_the_tyre_and_its_rows(self):
        self.make_tyre("Soft")
        tune.set_tyre_value(self.work, "soft", "tyre_dy_rear", "1.5", self.cat)
        r = self.get("/api/tyre?id=soft")
        self.assertEqual((r.status, set(r.json)), (200, {"tyre", "rows"}))
        self.assertEqual(r.json["tyre"], {"id": "soft", "name": "Soft", "source": {"front": ROAD_A, "rear": ROAD_B}, "changed": 1})
        rows = r.json["rows"]
        self.assertEqual([x["id"] for x in rows], ["tyre_dy_front", "tyre_dy_rear"])
        self.assertEqual([set(x) for x in rows], [TYRE_ROW_KEYS, TYRE_ROW_KEYS])
        self.assertEqual(rows, self.rows_of("soft"))
        front, rear = rows
        self.assertEqual((front["axle"], front["default"], front["value"], front["changed"], front["applicable"], front["reason"]),
                         ("front", 1.25, 1.25, False, True, None))
        self.assertEqual((rear["axle"], rear["default"], rear["value"], rear["changed"]), ("rear", 1.0, 1.5, True))
        self.assertEqual((front["min"], front["max"], front["unit"], front["group"]), (0.5, 2.5, "mu", "Tyres"))

    def test_tyre_reads_the_id_from_the_query_among_other_parameters(self):
        self.make_tyre("Soft")
        self.make_tyre("Slicky", KEY_SS)
        for path, tyre_id in (("/api/tyre?id=soft", "soft"), ("/api/tyre?car=ks_x&id=slicky&tune=draft", "slicky"),
                              ("/api/tyre?id=slicky&car=ks_x", "slicky"), ("/api/tyre?id=soft&id=slicky", "soft")):
            with self.subTest(path):
                self.assertEqual(self.get(path).json["tyre"]["id"], tyre_id)

    def test_tyre_without_an_id_is_400(self):
        self.make_tyre("Soft")
        for path in ("/api/tyre", "/api/tyre?id=", "/api/tyre?car=ks_x", "/api/tyre?tune=draft&id"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual((r.status, r.json), (400, {"error": "need id (text)"}))

    def test_tyre_with_an_unknown_or_bad_id_is_400_with_the_tune_message(self):
        r = self.get("/api/tyre?id=nope")
        self.assertEqual((r.status, r.json), (400, {"error": "no tyre 'nope' in the library"}))
        for path in ("/api/tyre?id=..%2fx", "/api/tyre?id=A", "/api/tyre?id=" + "x" * 25, "/api/tyre?id=a%5Cb"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith("bad tyre id "), r.json)

    def test_tyre_whose_source_no_extracted_car_offers_is_400(self):
        self.write(os.path.join(self.work, "tyres", "gone.json"), {"version": 1, "name": "Gone", "values": {},
                                                                   "source": {"front": GS + "tyres\\x\\f.tyre", "rear": GS + "tyres\\x\\r.tyre"}})
        r = self.get("/api/tyre?id=gone")
        self.assertEqual(r.status, 400)
        self.assertIn("no extracted car offers its source", r.json["error"])

    def test_tyre_with_a_damaged_file_is_400_and_not_a_500(self):
        self.write(os.path.join(self.work, "tyres", "bad.json"), "{")
        self.assertEqual(self.get("/api/tyre?id=bad").status, 400)

    def test_the_raw_query_is_the_third_argument_of_a_query_route_only(self):
        seen, two = [], []

        def spy(car, tune_id, query):
            seen.append((car, tune_id, query))
            return {}
        with mock.patch.dict(ts.GET_ROUTES, {"/api/tyre": spy}):
            self.assertEqual(self.get("/api/tyre?id=soft&car=ks_x&tune=draft").status, 200)
        self.assertEqual(seen, [("ks_x", "draft", "id=soft&car=ks_x&tune=draft")])
        with mock.patch.dict(ts.GET_ROUTES, {"/api/state": lambda car, tune_id: two.append((car, tune_id)) or {}}):
            self.assertEqual(self.get("/api/state?id=soft&tune=draft").status, 200)
        self.assertEqual(two, [("ks_x", "draft")])

    def test_the_existing_get_routes_ignore_an_id_parameter(self):
        self.make_tyre("Soft")
        self.assertEqual(self.get("/api/state?id=soft").json["car"], "ks_x")
        self.assertEqual(self.get("/api/settings?id=nope").json, self.get("/api/settings").json)

    def test_tyre_rows_are_built_under_state_lock(self):
        self.make_tyre("Soft")
        held, real = [], tune.tyre_rows

        def spy(*args, **kw):
            held.append(ts.STATE_LOCK.locked())
            return real(*args, **kw)
        self.patch(tune, "tyre_rows", spy)
        self.get("/api/tyre?id=soft")
        self.assertEqual(held, [True])

    def test_an_unknown_car_or_modded_car_is_400_for_the_tyre_routes_too(self):
        self.make_tyre("Soft")
        for path in ("/api/tyres?car=nope", "/api/tyre?id=soft&car=nope", "/api/garage?car=nope"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith("unknown car"), r.json)
        r = self.get("/api/tyres?tune=nope")
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car nope of ks_x"}))
        r = self.post("/api/tyre_new", {"car": "../x", "name": "Other", "source": KEY_SS})
        self.assertEqual(r.status, 400)
        self.assertTrue(r.json["error"].startswith("unknown car"), r.json)
        r = self.post("/api/tyre_new", {"tune": "nope", "name": "Other", "source": KEY_SS})
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car nope of ks_x"}))
        self.assertEqual([t["id"] for t in tune.list_tyres(self.work)], ["soft"])


class TestTyreWriteRoutes(TyreCase):
    def test_tyre_new_creates_a_library_tyre(self):
        r = self.post("/api/tyre_new", {"name": "  Soft Slick ", "source": KEY_AB})
        self.assertEqual((r.status, r.json), (200, {"tyre": {"id": "soft_slick", "name": "Soft Slick",
                                                              "source": {"front": ROAD_A, "rear": ROAD_B}}}))
        self.assertEqual(tune.load_tyre(self.work, "soft_slick"),
                         {"version": 1, "name": "Soft Slick", "source": {"front": ROAD_A, "rear": ROAD_B}, "values": {}})
        again = self.post("/api/tyre_new", {"name": "Soft Slick 2", "source": KEY_SS})
        self.assertEqual(again.json["tyre"]["id"], "soft_slick_2")

    def test_a_non_ascii_name_survives_the_round_trip(self):
        r = self.post("/api/tyre_new", {"name": "Reifen Größe", "source": KEY_AB})
        self.assertEqual((r.status, r.json["tyre"]["name"]), (200, "Reifen Größe"))
        self.assertEqual(self.get("/api/tyres").json["tyres"][0]["name"], "Reifen Größe")

    def test_tyre_new_with_wrong_fields_is_400_and_creates_nothing(self):
        for body in ({}, {"name": "Soft"}, {"source": KEY_AB}, {"name": 5, "source": KEY_AB}, {"name": "Soft", "source": None},
                     {"name": ["Soft"], "source": KEY_AB}, {"name": "Soft", "source": 5}, {"name": None, "source": None}):
            with self.subTest(body):
                r = self.post("/api/tyre_new", body)
                self.assertEqual((r.status, r.json), (400, {"error": "need name (text) and source (text)"}))
        self.assertFalse(os.path.exists(os.path.join(self.work, "tyres")))

    def test_tyre_new_with_a_bad_name_or_source_is_400_with_the_tune_message(self):
        self.make_tyre("Soft")
        before = self.library_bytes()
        for body, text in (({"name": "Other", "source": "nope"}, "unknown tyre source 'nope'"),
                           ({"name": "Other", "source": ""}, "unknown tyre source ''"),
                           ({"name": "SOFT", "source": KEY_SS}, "a tyre named 'Soft' exists already"),
                           ({"name": "", "source": KEY_SS}, "a tyre name needs 1 to 40 characters"),
                           ({"name": "x" * 41, "source": KEY_SS}, "a tyre name needs 1 to 40 characters"),
                           ({"name": "a\nb", "source": KEY_SS}, "a tyre name needs 1 to 40 characters")):
            with self.subTest(body):
                r = self.post("/api/tyre_new", body)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith(text), r.json)
        self.assertEqual(self.library_bytes(), before)

    def test_tyre_rename_answers_with_the_tyre(self):
        self.make_tyre("Soft")
        tune.set_tyre_value(self.work, "soft", "tyre_dy_front", "1.5", self.cat)
        r = self.post("/api/tyre_rename", {"id": "soft", "name": "Hard"})
        self.assertEqual((r.status, r.json), (200, {"tyre": {"id": "soft", "name": "Hard", "source": {"front": ROAD_A, "rear": ROAD_B},
                                                             "changed": 1}}))
        self.assertEqual(tune.load_tyre(self.work, "soft")["values"], {"tyre_dy_front": 1.5})
        self.assertEqual(self.post("/api/tyre_rename", {"id": "soft", "name": "HARD"}).status, 200)

    def test_tyre_rename_errors(self):
        self.make_tyre("Soft")
        self.make_tyre("Hard", KEY_SS)
        before = self.library_bytes()
        for body, status, text in (({"id": "soft", "name": "hard"}, 400, "a tyre named 'Hard' exists already"),
                                   ({"id": "soft", "name": ""}, 400, "a tyre name needs"),
                                   ({"id": "nope", "name": "X"}, 400, "no tyre 'nope' in the library"),
                                   ({"id": "../x", "name": "X"}, 400, "bad tyre id"),
                                   ({"id": "soft"}, 400, "need id (text) and name (text)"),
                                   ({"name": "X"}, 400, "need id (text) and name (text)"),
                                   ({"id": 5, "name": "X"}, 400, "need id (text) and name (text)"),
                                   ({"id": "soft", "name": 5}, 400, "need id (text) and name (text)")):
            with self.subTest(body):
                r = self.post("/api/tyre_rename", body)
                self.assertEqual(r.status, status)
                self.assertTrue(r.json["error"].startswith(text), r.json)
        self.assertEqual(self.library_bytes(), before)

    def test_tyre_source_points_the_tyre_at_another_source_and_keeps_the_values(self):
        self.make_tyre("Soft")
        tune.set_tyre_value(self.work, "soft", "tyre_dy_front", "1.5", self.cat)
        r = self.post("/api/tyre_source", {"id": "soft", "source": KEY_SS})
        self.assertEqual((r.status, r.json), (200, {"tyre": {"id": "soft", "name": "Soft", "source": {"front": SLICK_S, "rear": SLICK_S},
                                                              "changed": 1}}))
        t = tune.load_tyre(self.work, "soft")
        self.assertEqual((t["source"], t["values"]), ({"front": SLICK_S, "rear": SLICK_S}, {"tyre_dy_front": 1.5}))
        self.assertEqual(self.row(self.get("/api/tyre?id=soft").json["rows"])["default"], 1.5)

    def test_tyre_source_errors(self):
        self.make_tyre("Soft")
        before = self.library_bytes()
        for body, text in (({"id": "soft", "source": "nope"}, "unknown tyre source 'nope'"), ({"id": "nope", "source": KEY_SS}, "no tyre 'nope'"),
                           ({"id": "../x", "source": KEY_SS}, "bad tyre id"), ({"id": "soft"}, "need id (text) and source (text)"),
                           ({"source": KEY_SS}, "need id (text) and source (text)"), ({"id": "soft", "source": 5}, "need id (text) and source (text)"),
                           ({"id": ["soft"], "source": KEY_SS}, "need id (text) and source (text)")):
            with self.subTest(body):
                r = self.post("/api/tyre_source", body)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith(text), r.json)
        self.assertEqual(self.library_bytes(), before)

    def test_tyre_set_answers_with_the_new_row(self):
        self.make_tyre("Soft")
        r = self.post("/api/tyre_set", {"id": "soft", "setting": "tyre_dy_front", "value": "1.5"})
        self.assertEqual((r.status, set(r.json)), (200, {"row", "warnings"}))
        row = r.json["row"]
        self.assertEqual(set(row), TYRE_ROW_KEYS)
        self.assertEqual((r.json["warnings"], row["id"], row["value"], row["default"], row["changed"]), ([], "tyre_dy_front", 1.5, 1.25, True))
        self.assertEqual(row, self.row(self.rows_of("soft")))
        self.assertEqual(tune.load_tyre(self.work, "soft")["values"], {"tyre_dy_front": 1.5})

    def test_tyre_set_takes_text_numbers_and_the_rear_axle(self):
        self.make_tyre("Soft")
        for value in ("1.5", 1.5, 2, " 2 "):
            with self.subTest(repr(value)):
                r = self.post("/api/tyre_set", {"id": "soft", "setting": "tyre_dy_rear", "value": value})
                self.assertEqual((r.status, r.json["row"]["axle"], r.json["row"]["value"]), (200, "rear", float(str(value).strip())))
        self.assertEqual(tune.load_tyre(self.work, "soft")["values"], {"tyre_dy_rear": 2.0})

    def test_tyre_set_outside_the_suggested_range_warns_but_stores(self):
        self.make_tyre("Soft")
        r = self.post("/api/tyre_set", {"id": "soft", "setting": "tyre_dy_front", "value": 3})
        self.assertEqual((r.status, r.json["warnings"]), (200, ["tyre_dy_front=3.0 is outside the suggested range 0.5..2.5"]))
        self.assertEqual(tune.load_tyre(self.work, "soft")["values"], {"tyre_dy_front": 3.0})

    def test_tyre_set_with_a_value_equal_to_the_default_is_not_changed(self):
        self.make_tyre("Soft")
        r = self.post("/api/tyre_set", {"id": "soft", "setting": "tyre_dy_front", "value": "1.25"})
        self.assertEqual((r.json["row"]["value"], r.json["row"]["changed"]), (1.25, False))

    def test_tyre_set_errors_change_nothing(self):
        self.make_tyre("Soft")
        tune.set_tyre_value(self.work, "soft", "tyre_dy_front", "1.5", self.cat)
        before = self.library_bytes()
        good = {"id": "soft", "setting": "tyre_dy_front", "value": "1.75"}
        for body, text in ((dict(good, value="fast"), "tyre_dy_front expects a number"), (dict(good, value=True), "tyre_dy_front expects a number"),
                           (dict(good, setting="nope"), "unknown setting 'nope'"), (dict(good, setting="limiter"), "limiter is not a tyre setting"),
                           (dict(good, id="nope"), "no tyre 'nope' in the library"), (dict(good, id="../x"), "bad tyre id"),
                           (dict(good, value=None), "need id (text), setting (text) and value (text, number or true/false)"),
                           (dict(good, value=[1]), "need id (text), setting (text) and value (text, number or true/false)"),
                           (dict(good, value={"a": 1}), "need id (text), setting (text) and value (text, number or true/false)"),
                           ({"id": "soft", "value": "1"}, "need id (text), setting (text) and value (text, number or true/false)"),
                           ({"setting": "tyre_dy_front", "value": "1"}, "need id (text), setting (text) and value (text, number or true/false)"),
                           (dict(good, id=5), "need id (text), setting (text) and value (text, number or true/false)"),
                           (dict(good, setting=["tyre_dy_front"]), "need id (text), setting (text) and value (text, number or true/false)")):
            with self.subTest(body):
                r = self.post("/api/tyre_set", body)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith(text), r.json)
        self.assertEqual(self.library_bytes(), before)

    def test_tyre_unset_removes_the_value_and_answers_with_the_default_row(self):
        self.make_tyre("Soft")
        tune.set_tyre_value(self.work, "soft", "tyre_dy_front", "1.5", self.cat)
        tune.set_tyre_value(self.work, "soft", "tyre_dy_rear", "1.75", self.cat)
        r = self.post("/api/tyre_unset", {"id": "soft", "setting": "tyre_dy_front"})
        self.assertEqual((r.status, set(r.json), set(r.json["row"])), (200, {"row"}, TYRE_ROW_KEYS))
        self.assertEqual((r.json["row"]["value"], r.json["row"]["default"], r.json["row"]["changed"]), (1.25, 1.25, False))
        self.assertEqual(tune.load_tyre(self.work, "soft")["values"], {"tyre_dy_rear": 1.75})

    def test_tyre_unset_of_a_value_that_was_never_set_is_a_noop(self):
        self.make_tyre("Soft")
        before = self.library_bytes()
        r = self.post("/api/tyre_unset", {"id": "soft", "setting": "tyre_dy_rear"})
        self.assertEqual((r.status, r.json["row"]["changed"]), (200, False))
        self.assertEqual(self.library_bytes(), before)

    def test_tyre_unset_errors(self):
        self.make_tyre("Soft")
        before = self.library_bytes()
        for body, text in (({"id": "soft", "setting": "nope"}, "unknown setting 'nope'"), ({"id": "soft", "setting": "limiter"}, "limiter is not a tyre setting"),
                           ({"id": "nope", "setting": "tyre_dy_front"}, "no tyre 'nope' in the library"),
                           ({"id": "soft"}, "need id (text) and setting (text)"), ({"setting": "tyre_dy_front"}, "need id (text) and setting (text)"),
                           ({"id": 5, "setting": "tyre_dy_front"}, "need id (text) and setting (text)"),
                           ({"id": "soft", "setting": None}, "need id (text) and setting (text)")):
            with self.subTest(body):
                r = self.post("/api/tyre_unset", body)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith(text), r.json)
        self.assertEqual(self.library_bytes(), before)

    def test_tyre_reset_drops_every_changed_value(self):
        self.make_tyre("Soft")
        tune.set_tyre_value(self.work, "soft", "tyre_dy_front", "1.5", self.cat)
        tune.set_tyre_value(self.work, "soft", "tyre_dy_rear", "1.75", self.cat)
        r = self.post("/api/tyre_reset", {"id": "soft"})
        self.assertEqual((r.status, r.json), (200, {"ok": True}))
        self.assertEqual(tune.load_tyre(self.work, "soft")["values"], {})
        self.assertFalse(any(x["changed"] for x in self.get("/api/tyre?id=soft").json["rows"]))
        self.assertEqual(self.post("/api/tyre_reset", {"id": "soft"}).json, {"ok": True})

    def test_tyre_reset_and_delete_errors(self):
        self.make_tyre("Soft")
        before = self.library_bytes()
        for path in ("/api/tyre_reset", "/api/tyre_delete"):
            for body, text in (({"id": "nope"}, "no tyre 'nope' in the library"), ({"id": "../x"}, "bad tyre id"),
                               ({"id": "A"}, "bad tyre id"), ({}, "need id (text)"), ({"id": 5}, "need id (text)"),
                               ({"id": None}, "need id (text)"), ({"id": ["soft"]}, "need id (text)")):
                with self.subTest(path, body=body):
                    r = self.post(path, body)
                    self.assertEqual(r.status, 400)
                    self.assertTrue(r.json["error"].startswith(text), r.json)
        self.assertEqual(self.library_bytes(), before)

    def test_tyre_delete_removes_the_file(self):
        self.make_tyre("Soft")
        self.make_tyre("Slicky", KEY_SS)
        r = self.post("/api/tyre_delete", {"id": "soft"})
        self.assertEqual((r.status, r.json), (200, {"ok": True}))
        self.assertEqual([t["id"] for t in tune.list_tyres(self.work)], ["slicky"])
        self.assertEqual(self.post("/api/tyre_delete", {"id": "soft"}).status, 400)

    def test_a_tyre_a_modded_car_selects_is_409_until_the_selection_is_gone(self):
        self.make_tyre("Soft")
        self.make_tune("ax01", {"name_suffix": "_A"})
        self.assertEqual(self.post("/api/garage_set", {"keys": ["own:soft", ST_AB], "tune": "ax01"}).status, 200)
        r = self.post("/api/tyre_delete", {"id": "soft"})
        self.assertEqual((r.status, r.json), (409, {"error": "tyre soft is used by ks_x / ax01"}))
        self.assertTrue(tune.tyre_exists(self.work, "soft"))
        self.assertEqual(self.post("/api/garage_set", {"keys": ["own:soft", ST_AB], "tune": "draft"}).status, 200)
        r = self.post("/api/tyre_delete", {"id": "soft"})
        self.assertEqual((r.status, r.json), (409, {"error": "tyre soft is used by ks_x / ax01, ks_x (draft)"}))
        self.assertEqual(self.post("/api/garage_reset", {"tune": "ax01"}).status, 200)
        r = self.post("/api/tyre_delete", {"id": "soft"})
        self.assertEqual((r.status, r.json), (409, {"error": "tyre soft is used by ks_x (draft)"}))
        self.assertEqual(self.post("/api/garage_reset", {"tune": "draft"}).status, 200)
        r = self.post("/api/tyre_delete", {"id": "soft"})
        self.assertEqual((r.status, r.json), (200, {"ok": True}))
        self.assertFalse(tune.tyre_exists(self.work, "soft"))

    def test_a_tyre_the_default_modded_car_selects_is_409(self):
        self.make_tyre("Soft")
        self.make_tune()
        self.post("/api/garage_set", {"keys": ["own:soft"]})
        r = self.post("/api/tyre_delete", {"id": "soft"})
        self.assertEqual((r.status, r.json), (409, {"error": "tyre soft is used by ks_x / ax_x"}))

    def test_a_missing_tyre_is_400_not_409_even_when_a_state_names_it(self):
        self.make_tune("ax01", {"name_suffix": "_A", tune.TYRE_KEY: ["own:ghost"]})
        r = self.post("/api/tyre_delete", {"id": "ghost"})
        self.assertEqual((r.status, r.json), (400, {"error": "no tyre 'ghost' in the library"}))

    def test_every_library_and_garage_write_happens_under_state_lock(self):
        held = []
        for name in ("save_tyre", "delete_tyre", "set_garage", "reset_garage"):
            def spy(*args, _name=name, _real=getattr(tune, name), **kw):
                held.append((_name, ts.STATE_LOCK.locked()))
                return _real(*args, **kw)
            self.patch(tune, name, spy)
        steps = (("/api/tyre_new", {"name": "Soft", "source": KEY_AB}), ("/api/tyre_rename", {"id": "soft", "name": "Hard"}),
                 ("/api/tyre_source", {"id": "soft", "source": KEY_SS}), ("/api/tyre_set", {"id": "soft", "setting": "tyre_dy_front", "value": 1.5}),
                 ("/api/tyre_unset", {"id": "soft", "setting": "tyre_dy_front"}),
                 ("/api/tyre_set", {"id": "soft", "setting": "tyre_dy_rear", "value": 1.5}), ("/api/tyre_reset", {"id": "soft"}),
                 ("/api/garage_set", {"keys": ["own:soft", ST_AB]}), ("/api/garage_reset", {}), ("/api/tyre_delete", {"id": "soft"}))
        for path, body in steps:
            self.assertEqual(self.post(path, body).status, 200, path)
        self.assertEqual(held, [("save_tyre", True)] * 7 + [("set_garage", True), ("reset_garage", True), ("delete_tyre", True)])

    def test_every_write_route_is_409_while_a_job_runs_and_changes_nothing(self):
        self.make_tyre("Soft")
        self.make_tune("ax01", {"name_suffix": "_A"})
        before = self.library_bytes()
        self.hold_jobs()
        self.assertEqual(self.post("/api/init").status, 202)
        self.entered.wait(5)
        writes = (("/api/tyre_new", {"name": "Other", "source": KEY_SS}), ("/api/tyre_rename", {"id": "soft", "name": "X"}),
                  ("/api/tyre_source", {"id": "soft", "source": KEY_SS}),
                  ("/api/tyre_set", {"id": "soft", "setting": "tyre_dy_front", "value": "1.5"}),
                  ("/api/tyre_unset", {"id": "soft", "setting": "tyre_dy_front"}), ("/api/tyre_reset", {"id": "soft"}),
                  ("/api/tyre_delete", {"id": "soft"}))
        for path, body in writes:
            with self.subTest(path):
                r = self.post(path, body)
                self.assertEqual((r.status, r.json), (409, JOB_RUNNING))
        for path, body in (("/api/garage_set", {"keys": ["own:soft"]}), ("/api/garage_reset", {})):
            for tune_id in (None, "ax01", "draft"):
                with self.subTest(path, tune=tune_id):
                    r = self.post(path, dict(body, tune=tune_id))
                    self.assertEqual((r.status, r.json), (409, JOB_RUNNING))
        self.assertEqual(self.library_bytes(), before)
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A"})
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x", "draft")))
        for path in ("/api/tyres", "/api/tyre?id=soft", "/api/garage"):
            self.assertEqual(self.get(path).status, 200, path)
        self.finish_held_job()
        self.assertEqual(self.post("/api/tyre_reset", {"id": "soft"}).status, 200)
        self.assertEqual(self.post("/api/tyre_new", {"name": "Other", "source": KEY_SS}).status, 200)

    def test_a_new_post_route_checks_the_host_and_the_post_headers_before_it_writes(self):
        body = {"name": "Soft", "source": KEY_AB}
        r = self.post("/api/tyre_new", body, headers={"X-Tuner": None})
        self.assertEqual((r.status, r.json), (403, {"error": "missing header X-Tuner: 1"}))
        r = self.post("/api/tyre_new", body, headers={"Content-Type": "text/plain"})
        self.assertEqual((r.status, r.json), (415, {"error": "Content-Type must be application/json"}))
        r = self.post("/api/tyre_new", body, host="evil.example")
        self.assertEqual((r.status, r.json), (403, {"error": "forbidden host"}))
        r = self.post("/api/garage_set", {"keys": [ST_AB]}, headers={"X-Tuner": None})
        self.assertEqual(r.status, 403)
        self.assertEqual(tune.list_tyres(self.work), [])
        self.assertFalse(os.path.exists(self.state_file()))

    def test_a_new_post_route_is_405_for_other_methods_and_404_for_a_get(self):
        for method in ("PUT", "DELETE", "PATCH"):
            with self.subTest(method):
                r = self.request(method, "/api/tyre_new")
                self.assertEqual((r.status, r.json, r.headers.get("Allow")), (405, {"error": "method not allowed"}, "GET, POST"))
        self.assertEqual(self.get("/api/tyre_new").status, 404)
        self.assertEqual(self.get("/api/garage_set").status, 404)
        self.assertEqual(tune.list_tyres(self.work), [])

    def test_a_new_get_route_checks_the_host_and_is_405_for_other_methods_and_404_for_a_post(self):
        self.make_tyre("Soft")
        for path in ("/api/tyre?id=soft", "/api/tyres", "/api/garage"):
            with self.subTest(path):
                r = self.get(path, host="evil.example")
                self.assertEqual((r.status, r.json), (403, {"error": "forbidden host"}))
        for method in ("PUT", "DELETE", "PATCH"):
            with self.subTest(method):
                r = self.request(method, "/api/tyre?id=soft")
                self.assertEqual((r.status, r.json, r.headers.get("Allow")), (405, {"error": "method not allowed"}, "GET, POST"))
        for path in ("/api/tyre", "/api/tyres", "/api/garage"):
            self.assertEqual(self.post(path, {"id": "soft"}).status, 404, path)
        self.assertEqual(self.get("/api/tyre?id=soft").status, 200)


class TestGarageRoutes(TyreCase):
    def setUp(self):
        super().setUp()
        self.make_tyre("Soft")
        self.make_tyre("Slicky", KEY_SS)

    def garage(self, query=""):
        return self.get("/api/garage" + query)

    def test_garage_of_the_default_car_ticks_the_stock_tyres(self):
        r = self.garage()
        self.assertEqual((r.status, set(r.json)), (200, GARAGE_KEYS))
        self.assertEqual((r.json["car"], r.json["tune"], r.json["custom"], r.json["missing"]), ("ks_x", None, False, []))
        self.assertEqual([(c["key"], c["kind"], c["ticked"], c["start"]) for c in r.json["choices"]],
                         [("own:slicky", "own", False, False), ("own:soft", "own", False, False), (ST_AB, "stock", True, True),
                          (ST_SS, "stock", True, False)])
        self.assertEqual(r.json, dict(tune.garage_choices(self.work, "ks_x"), car="ks_x", tune=None))

    def test_garage_echoes_the_tune_and_reads_its_own_state(self):
        self.make_tune("ax01", {"name_suffix": "_A", tune.TYRE_KEY: ["own:soft"]})
        r = self.garage("?tune=ax01")
        self.assertEqual((r.json["tune"], r.json["custom"], [c["key"] for c in r.json["choices"] if c["ticked"]]), ("ax01", True, ["own:soft"]))
        self.assertEqual([c["key"] for c in r.json["choices"] if c["start"]], ["own:soft"])
        self.assertEqual(self.garage("?tune=draft").json["tune"], "draft")
        self.assertFalse(self.garage("?tune=draft").json["custom"])
        self.assertFalse(self.garage().json["custom"])

    def test_garage_lists_the_saved_keys_that_are_no_choice_any_more(self):
        self.make_tune(None, {tune.TYRE_KEY: ["own:ghost", ST_AB]})
        r = self.garage()
        self.assertEqual((r.json["custom"], r.json["missing"]), (True, ["own:ghost"]))

    def test_garage_needs_the_base_car(self):
        r = self.garage("?car=ks_y")
        self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))
        r = self.garage("?car=ks_y&tune=draft")
        self.assertEqual(r.status, 409)

    def test_garage_with_a_damaged_selection_is_400(self):
        self.make_tune(None, {tune.TYRE_KEY: "own:soft"})
        r = self.garage()
        self.assertEqual(r.status, 400)
        self.assertIn("must be a list of tyre keys", r.json["error"])

    def test_garage_is_read_under_state_lock(self):
        held, real = [], tune.garage_choices

        def spy(*args, **kw):
            held.append(ts.STATE_LOCK.locked())
            return real(*args, **kw)
        self.patch(tune, "garage_choices", spy)
        self.garage()
        self.assertEqual(held, [True])

    def test_garage_set_ticks_the_tyres_of_the_default_tune_in_the_fixed_order(self):
        r = self.post("/api/garage_set", {"keys": [ST_AB, "own:soft"]})
        self.assertEqual((r.status, set(r.json)), (200, {"result", "garage"}))
        self.assertEqual(r.json["result"], {"keys": ["own:soft", ST_AB], "start": "own:soft"})
        self.assertEqual(r.json["garage"], self.garage().json)
        self.assertEqual((r.json["garage"]["custom"], [c["key"] for c in r.json["garage"]["choices"] if c["ticked"]]),
                         (True, ["own:soft", ST_AB]))
        self.assertEqual(self.saved_state(), {tune.TYRE_KEY: ["own:soft", ST_AB]})

    def test_garage_set_keeps_the_other_values_of_the_state(self):
        self.write(self.state_file(), {"limiter": 8000})
        self.post("/api/garage_set", {"keys": [ST_SS]})
        self.assertEqual(self.saved_state(), {"limiter": 8000, tune.TYRE_KEY: [ST_SS]})

    def test_garage_set_to_all_stock_tyres_is_the_default_and_removes_the_entry(self):
        self.write(self.state_file(), {"limiter": 8000, tune.TYRE_KEY: ["own:soft"]})
        r = self.post("/api/garage_set", {"keys": [ST_SS, ST_AB]})
        self.assertEqual((r.status, r.json["result"]), (200, {"keys": [ST_AB, ST_SS], "start": ST_AB, "default": True}))
        self.assertFalse(r.json["garage"]["custom"])
        self.assertEqual(self.saved_state(), {"limiter": 8000})

    def test_garage_set_of_a_modded_car_changes_only_its_state(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        r = self.post("/api/garage_set", {"keys": ["own:slicky"], "tune": "ax01"})
        self.assertEqual((r.status, r.json["result"], r.json["garage"]["tune"]), (200, {"keys": ["own:slicky"], "start": "own:slicky"}, "ax01"))
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A", tune.TYRE_KEY: ["own:slicky"]})
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x", "draft")))
        self.assertEqual(self.garage("?tune=ax01").json, r.json["garage"])

    def test_garage_set_of_the_draft_needs_no_modded_car(self):
        r = self.post("/api/garage_set", {"keys": ["own:soft"], "tune": "draft"})
        self.assertEqual((r.status, r.json["garage"]["tune"]), (200, "draft"))
        self.assertEqual(self.tune_state("draft"), {tune.TYRE_KEY: ["own:soft"]})
        self.assertEqual(self.tune_ids(), [])
        self.assertFalse(os.path.exists(self.state_file()))

    def test_garage_set_errors_change_nothing(self):
        self.write(self.state_file(), {"limiter": 8000, tune.TYRE_KEY: [ST_SS]})
        for body, text in (({}, "need keys (a list of text)"), ({"keys": "own:soft"}, "need keys (a list of text)"),
                           ({"keys": None}, "need keys (a list of text)"), ({"keys": {"own:soft": 1}}, "need keys (a list of text)"),
                           ({"keys": ["own:soft", 5]}, "need keys (a list of text)"), ({"keys": [None]}, "need keys (a list of text)"),
                           ({"keys": []}, "tick at least one tyre"), ({"keys": ["own:ghost"]}, "no tyre 'ghost' in the library"),
                           ({"keys": ["own:../x"]}, "bad tyre id"), ({"keys": ["stock:nope|nope"]}, "unknown stock tyre nope|nope of ks_x"),
                           ({"keys": ["soft"]}, "bad tyre key 'soft'"), ({"keys": ["own:soft", "own:soft"]}, "tyre key own:soft is listed twice")):
            with self.subTest(body):
                r = self.post("/api/garage_set", body)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].startswith(text), r.json)
        self.assertEqual(self.saved_state(), {"limiter": 8000, tune.TYRE_KEY: [ST_SS]})

    def test_garage_set_without_a_base_is_409_and_writes_nothing(self):
        for tune_id in (None, "draft"):
            with self.subTest(tune_id):
                r = self.post("/api/garage_set", {"car": "ks_y", "keys": ["own:soft"], "tune": tune_id})
                self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_y")))

    def test_garage_set_with_an_unknown_modded_car_is_400(self):
        r = self.post("/api/garage_set", {"keys": ["own:soft"], "tune": "nope"})
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car nope of ks_x"}))

    def test_garage_reset_removes_the_selection(self):
        self.write(self.state_file(), {"limiter": 8000, tune.TYRE_KEY: ["own:soft"]})
        r = self.post("/api/garage_reset", {})
        self.assertEqual((r.status, set(r.json), r.json["removed"]), (200, {"removed", "garage"}, True))
        self.assertEqual((r.json["garage"]["custom"], set(r.json["garage"])), (False, GARAGE_KEYS))
        self.assertEqual(r.json["garage"], self.garage().json)
        self.assertEqual(self.saved_state(), {"limiter": 8000})

    def test_garage_reset_without_a_selection_changes_nothing(self):
        r = self.post("/api/garage_reset")
        self.assertEqual((r.status, r.json["removed"], r.json["garage"]["custom"]), (200, False, False))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_garage_reset_of_a_modded_car_and_of_the_draft(self):
        self.make_tune("ax01", {"name_suffix": "_A", tune.TYRE_KEY: ["own:soft"]})
        self.make_tune(tune.DRAFT, {tune.TYRE_KEY: ["own:slicky"], "limiter": 8000})
        self.make_tune(None, {tune.TYRE_KEY: [ST_SS]})
        r = self.post("/api/garage_reset", {"tune": "ax01"})
        self.assertEqual((r.status, r.json["removed"], r.json["garage"]["tune"]), (200, True, "ax01"))
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A"})
        self.assertEqual(self.post("/api/garage_reset", {"tune": "draft"}).json["removed"], True)
        self.assertEqual(self.tune_state("draft"), {"limiter": 8000})
        self.assertEqual(self.saved_state(), {tune.TYRE_KEY: [ST_SS]})

    def test_garage_reset_without_a_base_is_409(self):
        r = self.post("/api/garage_reset", {"car": "ks_y"})
        self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))

    def test_garage_reset_with_a_damaged_selection_still_removes_it(self):
        self.write(self.state_file(), {tune.TYRE_KEY: "own:soft"})
        r = self.post("/api/garage_reset", {})
        self.assertEqual((r.status, r.json["removed"], r.json["garage"]["custom"]), (200, True, False))
        self.assertEqual(self.saved_state(), {})


# -------------------------------------------------------------------------------------------------- turbo kit
class TurboCase(TuneCase):
    """TuneCase with two donor cars next to ks_x (no turbo): ks_a has one turbo (boost 0.9, name from the car index) and ks_b two
    (boost 0.7 and 0.7, name from its stock info), ks_t one (boost 1.0): all three are donors of ks_x, and each is the car under test
    where the car itself has a turbo."""

    def setUp(self):
        super().setUp()
        self.write(os.path.join(self.work, "cars_index.json"),
                   [{"id": "ks_x", "display_name": "Car X", "brand": "B", "year": 1999}, {"id": "ks_y", "display_name": "Car Y", "brand": "B", "year": 2000},
                    {"id": "ks_a", "display_name": "Single A", "brand": "B", "year": 2001}, {"id": "ks_b", "display_name": "Twin B", "brand": "B", "year": 2002},
                    {"id": "ks_t", "display_name": "Car T", "brand": "B", "year": 2003}])
        self.add_car("ks_a", ["t0.turbo"], [0.9])
        self.add_car("ks_b", ["t0.turbo", "t1.turbo"], [0.7, 0.7])
        self.add_car("ks_t", ["t0.turbo"], [1.0])
        self.write(tune.stock_info_path(self.work, "ks_b"), {"car_id": "ks_b", "display_name": "Twin B", "brand": "Brand", "year": 1999})

    def add_car(self, car_id, turbos, boost):
        fc = FakeCar(self.work, car_id)
        fc.store = self.fc.store
        gp = fc.game_path
        fc.add("data/%s.car" % car_id, {"engine_path": gp("data/engine.carengine")})
        fc.add("data/engine.carengine", {"limiter": 7000, "turbos_to_load": [gp("data/" + t) for t in turbos],
                                         "turbos": [{"max_boost": b} for b in boost]})
        for t in turbos:
            fc.add("data/" + t, {"max_boost": 1.0})
        return fc

    def turbo(self, query=""):
        return self.get("/api/turbo" + query)

    def kit(self, donor):
        return {tune.TURBO_KEY: {"donor": donor}}


class TestTurboRoutes(TurboCase):
    def test_turbo_of_the_default_car_offers_the_donors_and_has_no_kit(self):
        r = self.turbo()
        self.assertEqual((r.status, r.headers.get("Content-Type"), set(r.json)), (200, "application/json; charset=utf-8", TURBO_KEYS))
        self.assertEqual((r.json["car"], r.json["tune"], r.json["donor"], r.json["picked"]), ("ks_x", None, None, None))
        self.assertEqual((r.json["available"], r.json["reason"], r.json["has_turbo"]), (True, "", False))
        self.assertEqual(r.json["donors"], [OWN, SINGLE, TWIN])
        self.assertEqual(r.json, dict(tune.turbo_choice(self.work, "ks_x"), car="ks_x", tune=None, has_turbo=False))

    def test_a_car_with_a_turbo_of_its_own_has_turbo_and_no_choice_and_is_not_its_own_donor(self):
        r = self.turbo("?car=ks_t")
        self.assertEqual((r.status, r.json["has_turbo"], r.json["available"], r.json["reason"]), (200, True, False, "the car has a turbo already"))
        self.assertEqual(r.json["donors"], [SINGLE, TWIN])
        r = self.turbo("?car=ks_a")
        self.assertEqual((r.json["has_turbo"], [d["car"] for d in r.json["donors"]]), (True, ["ks_t", "ks_b"]))

    def test_without_any_donor_the_choice_is_not_available_and_the_car_has_no_turbo(self):
        for car_id in ("ks_a", "ks_b", "ks_t"):
            shutil.rmtree(tune.base_dir(self.work, car_id))
        r = self.turbo()
        self.assertEqual((r.status, r.json["donors"], r.json["available"], r.json["reason"], r.json["has_turbo"]),
                         (200, [], False, "no installed car has a turbo", False))

    def test_turbo_echoes_the_tune_and_reads_its_own_state(self):
        self.make_tune("ax01", dict({"name_suffix": "_A"}, **self.kit("ks_b")))
        r = self.turbo("?tune=ax01")
        self.assertEqual((r.json["tune"], r.json["donor"], r.json["picked"]), ("ax01", "ks_b", TWIN))
        self.assertEqual(self.turbo("?tune=draft").json["tune"], "draft")
        self.assertIsNone(self.turbo("?tune=draft").json["donor"])
        self.assertIsNone(self.turbo().json["donor"])

    def test_turbo_names_a_saved_donor_that_is_not_offered_any_more(self):
        self.make_tune(None, self.kit("ks_gone"))
        r = self.turbo()
        self.assertEqual((r.status, r.json["donor"], r.json["picked"], r.json["available"]), (200, "ks_gone", None, True))

    def test_turbo_needs_the_base_car(self):
        r = self.turbo("?car=ks_y")
        self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))
        self.assertEqual(self.turbo("?car=ks_y&tune=draft").status, 409)

    def test_turbo_with_a_damaged_kit_is_400(self):
        self.make_tune(None, {tune.TURBO_KEY: "ks_b"})
        r = self.turbo()
        self.assertEqual((r.status, r.json), (400, {"error": "damaged turbo kit in the saved state"}))

    def test_turbo_is_read_under_state_lock(self):
        held, real = [], tune.turbo_choice

        def spy(*args, **kw):
            held.append(ts.STATE_LOCK.locked())
            return real(*args, **kw)
        self.patch(tune, "turbo_choice", spy)
        self.turbo()
        self.assertEqual(held, [True])

    def test_turbo_set_chooses_the_donor_of_the_default_tune(self):
        r = self.post("/api/turbo_set", {"donor": "ks_b"})
        self.assertEqual((r.status, set(r.json)), (200, {"result", "turbo"}))
        self.assertEqual(r.json["result"], {"donor": "ks_b", "count": 2, "kind": "twin turbo", "boost": [0.7, 0.7]})
        self.assertEqual(r.json["turbo"], self.turbo().json)
        self.assertEqual((r.json["turbo"]["donor"], r.json["turbo"]["picked"], r.json["turbo"]["has_turbo"]), ("ks_b", TWIN, False))
        self.assertEqual(self.saved_state(), self.kit("ks_b"))

    def test_turbo_set_names_the_kind_and_the_boost_of_each_donor(self):
        r = self.post("/api/turbo_set", {"donor": "ks_a"})
        self.assertEqual((r.json["result"]["kind"], r.json["result"]["boost"], r.json["turbo"]["picked"]["kind"], r.json["turbo"]["picked"]["boost"]),
                         ("single turbo", [0.9], "single turbo", [0.9]))

    def test_turbo_set_replaces_the_donor_and_keeps_the_other_values_of_the_state(self):
        self.write(self.state_file(), {"limiter": 8000})
        self.post("/api/turbo_set", {"donor": "ks_b"})
        r = self.post("/api/turbo_set", {"donor": "ks_a"})
        self.assertEqual((r.status, r.json["turbo"]["donor"]), (200, "ks_a"))
        self.assertEqual(self.saved_state(), {"limiter": 8000, tune.TURBO_KEY: {"donor": "ks_a"}})

    def test_turbo_set_of_a_modded_car_changes_only_its_state(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        r = self.post("/api/turbo_set", {"donor": "ks_b", "tune": "ax01"})
        self.assertEqual((r.status, r.json["turbo"]["tune"], r.json["turbo"]["donor"]), (200, "ax01", "ks_b"))
        self.assertEqual(self.tune_state("ax01"), dict({"name_suffix": "_A"}, **self.kit("ks_b")))
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x", "draft")))
        self.assertEqual(self.turbo("?tune=ax01").json, r.json["turbo"])

    def test_turbo_set_of_the_draft_needs_no_modded_car(self):
        r = self.post("/api/turbo_set", {"donor": "ks_a", "tune": "draft"})
        self.assertEqual((r.status, r.json["turbo"]["tune"]), (200, "draft"))
        self.assertEqual(self.tune_state("draft"), self.kit("ks_a"))
        self.assertEqual(self.tune_ids(), [])
        self.assertFalse(os.path.exists(self.state_file()))

    def test_turbo_set_with_a_donor_that_is_not_text_is_400_and_writes_nothing(self):
        for body in ({}, {"donor": None}, {"donor": 5}, {"donor": ["ks_b"]}, {"donor": {"car": "ks_b"}}, {"donor": True}):
            with self.subTest(body):
                r = self.post("/api/turbo_set", body)
                self.assertEqual((r.status, r.json), (400, {"error": "need donor (text)"}))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_turbo_set_with_a_refused_donor_is_400_with_the_message_and_changes_nothing(self):
        self.write(self.state_file(), {"limiter": 8000, tune.TURBO_KEY: {"donor": "ks_a"}})
        for body, text in (({"donor": "ks_zz"}, "ks_zz is not an installed car with a turbo"),
                           ({"donor": "ks_y"}, "ks_y is not an installed car with a turbo"),
                           ({"donor": "ks_x"}, "ks_x cannot be its own turbo donor"),
                           ({"donor": ""}, " is not an installed car with a turbo"),
                           ({"donor": "ks_b", "car": "ks_t"}, "ks_t has a turbo already")):
            with self.subTest(body):
                r = self.post("/api/turbo_set", body)
                self.assertEqual(r.status, 400)
                self.assertTrue(r.json["error"].endswith(text), r.json)
        self.assertEqual(self.saved_state(), {"limiter": 8000, tune.TURBO_KEY: {"donor": "ks_a"}})
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_t")))

    def test_turbo_set_without_a_base_is_409_and_writes_nothing(self):
        for tune_id in (None, "draft"):
            with self.subTest(tune_id):
                r = self.post("/api/turbo_set", {"car": "ks_y", "donor": "ks_b", "tune": tune_id})
                self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))
        self.assertFalse(os.path.exists(os.path.join(self.work, "ks_y")))

    def test_turbo_set_with_an_unknown_modded_car_is_400(self):
        r = self.post("/api/turbo_set", {"donor": "ks_b", "tune": "nope"})
        self.assertEqual((r.status, r.json), (400, {"error": "unknown modded car nope of ks_x"}))

    def test_turbo_reset_removes_the_kit_and_keeps_the_other_values(self):
        self.write(self.state_file(), {"limiter": 8000, tune.TURBO_KEY: {"donor": "ks_b"}})
        r = self.post("/api/turbo_reset", {})
        self.assertEqual((r.status, set(r.json), r.json["removed"]), (200, {"removed", "turbo"}, True))
        self.assertEqual((r.json["turbo"]["donor"], r.json["turbo"]["picked"], set(r.json["turbo"])), (None, None, TURBO_KEYS))
        self.assertEqual(r.json["turbo"], self.turbo().json)
        self.assertEqual(self.saved_state(), {"limiter": 8000})

    def test_turbo_reset_without_a_kit_changes_nothing(self):
        r = self.post("/api/turbo_reset")
        self.assertEqual((r.status, r.json["removed"], r.json["turbo"]["donor"]), (200, False, None))
        self.assertFalse(os.path.exists(self.state_file()))

    def test_turbo_reset_of_a_modded_car_and_of_the_draft(self):
        self.make_tune("ax01", dict({"name_suffix": "_A"}, **self.kit("ks_b")))
        self.make_tune(tune.DRAFT, dict({"limiter": 8000}, **self.kit("ks_a")))
        self.make_tune(None, self.kit("ks_a"))
        r = self.post("/api/turbo_reset", {"tune": "ax01"})
        self.assertEqual((r.status, r.json["removed"], r.json["turbo"]["tune"]), (200, True, "ax01"))
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A"})
        self.assertEqual(self.post("/api/turbo_reset", {"tune": "draft"}).json["removed"], True)
        self.assertEqual(self.tune_state("draft"), {"limiter": 8000})
        self.assertEqual(self.saved_state(), self.kit("ks_a"))

    def test_turbo_reset_without_a_base_is_409(self):
        r = self.post("/api/turbo_reset", {"car": "ks_y"})
        self.assertEqual((r.status, r.json), (409, {"error": "base car missing, run init"}))

    def test_turbo_reset_with_a_damaged_kit_still_removes_it(self):
        self.write(self.state_file(), {tune.TURBO_KEY: "ks_b"})
        r = self.post("/api/turbo_reset", {})
        self.assertEqual((r.status, r.json["removed"], r.json["turbo"]["donor"]), (200, True, None))
        self.assertEqual(self.saved_state(), {})

    def test_the_kit_writes_happen_under_state_lock(self):
        held = []
        for name in ("set_turbo", "reset_turbo"):
            def spy(*args, _name=name, _real=getattr(tune, name), **kw):
                held.append((_name, ts.STATE_LOCK.locked()))
                return _real(*args, **kw)
            self.patch(tune, name, spy)
        self.assertEqual(self.post("/api/turbo_set", {"donor": "ks_b"}).status, 200)
        self.assertEqual(self.post("/api/turbo_reset", {}).status, 200)
        self.assertEqual(held, [("set_turbo", True), ("reset_turbo", True)])

    def test_both_writes_are_409_while_a_job_runs_and_change_nothing(self):
        self.make_tune("ax01", {"name_suffix": "_A"})
        self.hold_jobs()
        self.assertEqual(self.post("/api/init").status, 202)
        self.entered.wait(5)
        for path, body in (("/api/turbo_set", {"donor": "ks_b"}), ("/api/turbo_reset", {})):
            for tune_id in (None, "ax01", "draft"):
                with self.subTest(path, tune=tune_id):
                    r = self.post(path, dict(body, tune=tune_id))
                    self.assertEqual((r.status, r.json), (409, JOB_RUNNING))
        r = self.post("/api/turbo_set", {"donor": 5})
        self.assertEqual((r.status, r.json), (409, JOB_RUNNING))
        self.assertEqual(self.tune_state("ax01"), {"name_suffix": "_A"})
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertFalse(os.path.exists(tune.state_path(self.work, "ks_x", "draft")))
        self.assertEqual(self.turbo().status, 200)
        self.finish_held_job()
        self.assertEqual(self.post("/api/turbo_set", {"donor": "ks_b"}).status, 200)

    def test_the_routes_check_the_host_the_post_headers_and_the_method(self):
        self.assertEqual(self.post("/api/turbo_set", {"donor": "ks_b"}, headers={"X-Tuner": None}).status, 403)
        r = self.post("/api/turbo_reset", {}, headers={"Content-Type": "text/plain"})
        self.assertEqual((r.status, r.json), (415, {"error": "Content-Type must be application/json"}))
        self.assertEqual(self.get("/api/turbo", host="evil.example").status, 403)
        self.assertEqual(self.post("/api/turbo_set", {"donor": "ks_b"}, host="evil.example").status, 403)
        self.assertFalse(os.path.exists(self.state_file()))
        self.assertEqual(self.get("/api/turbo_set").status, 404)
        self.assertEqual(self.get("/api/turbo_reset").status, 404)
        self.assertEqual(self.post("/api/turbo", {}).status, 404)
        for method in ("PUT", "DELETE", "PATCH"):
            with self.subTest(method):
                r = self.request(method, "/api/turbo")
                self.assertEqual((r.status, r.headers.get("Allow")), (405, "GET, POST"))

    def test_the_statuses_of_the_turbo_routes_are_200_not_202(self):
        self.assertTrue({"/api/turbo", "/api/turbo_set", "/api/turbo_reset"}.isdisjoint(ts.ACCEPTED))
        self.assertTrue({"/api/turbo"}.isdisjoint(ts.QUERY_ROUTES))


class TestSettingsWithATurboKit(TurboCase):
    def test_the_settings_of_a_tune_with_a_kit_are_read_from_the_kit_root(self):
        asked = []

        def kit_root(work, car_id, donor):
            asked.append((work, car_id, donor))
            return tune.base_dir(work, car_id)
        self.patch(tune, "kit_root", kit_root)
        self.make_tune("ax01", dict({"limiter": 8000, "name_suffix": "_A"}, **self.kit("ks_b")))
        r = self.get("/api/settings?tune=ax01")
        self.assertEqual(r.status, 200)
        self.assertEqual(next(row["value"] for row in r.json if row["id"] == "limiter"), 8000)
        self.assertEqual(set(asked), {(self.work, "ks_x", "ks_b")})
        self.assertEqual(self.get("/api/settings?tune=draft").status, 200)
        self.assertEqual(set(asked), {(self.work, "ks_x", "ks_b")})

    def test_the_settings_of_the_draft_and_the_default_tune_with_a_kit_use_it_too(self):
        asked = []
        self.patch(tune, "kit_root", lambda work, car_id, donor: asked.append(donor) or tune.base_dir(work, car_id))
        self.make_tune(tune.DRAFT, self.kit("ks_a"))
        self.make_tune(None, dict({"name_suffix": "_D"}, **self.kit("ks_b")))
        self.assertEqual(self.get("/api/settings?tune=draft").status, 200)
        self.assertEqual(self.get("/api/settings").status, 200)
        self.assertEqual(asked, ["ks_a", "ks_b"])

    def test_the_settings_of_a_tune_whose_donor_is_gone_are_400_with_the_turbo_kit_message(self):
        for tune_id, state in (("ax01", {"name_suffix": "_A", tune.TURBO_KEY: {"donor": "ks_gone"}}), (tune.DRAFT, self.kit("ks_gone")),
                               (None, self.kit("ks_gone"))):
            with self.subTest(tune_id):
                self.make_tune(tune_id, state)
                r = self.get("/api/settings" + ("" if tune_id is None else "?tune=" + tune_id))
                self.assertEqual((r.status, r.json), (400, {"error": "turbo kit: ks_gone is not an installed car with a turbo"}))

    def test_the_settings_of_a_car_that_has_a_turbo_but_a_saved_kit_are_400(self):
        tune.save_state(self.work, "ks_t", self.kit("ks_b"), tune.DRAFT)
        r = self.get("/api/settings?car=ks_t&tune=draft")
        self.assertEqual((r.status, r.json), (400, {"error": "turbo kit: ks_t has a turbo already"}))

    def test_removing_the_kit_makes_the_settings_readable_again(self):
        self.make_tune(None, self.kit("ks_gone"))
        self.assertEqual(self.get("/api/settings").status, 400)
        self.assertEqual(self.post("/api/turbo_reset", {}).json["removed"], True)
        self.assertEqual(self.get("/api/settings").status, 200)


# -------------------------------------------------------------------------------------------------- job lifecycle
class TestJobs(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_a_second_job_while_one_runs_is_409_for_init_and_apply(self):
        tune.save_state(self.work, "ks_x", {})
        self.hold_jobs()
        self.assertEqual(self.post("/api/init").status, 202)
        self.entered.wait(5)
        for path, body, text in (("/api/init", {}, "another job is running, wait until it has finished"),
                                 ("/api/apply", {}, "another job is running, wait until it has finished"),
                                 ("/api/apply", {"tune": "draft"}, "a job is running, wait until it has finished")):
            with self.subTest(path, body=body):
                r = self.post(path, body)
                self.assertEqual((r.status, r.json), (409, {"error": text}))
        self.assertEqual([c[0] for c in self.calls], ["init"])
        self.assertEqual([t["id"] for t in tune.list_tunes(self.work, "ks_x")], ["ax_x"])
        self.finish_held_job()

    def test_a_job_that_is_running_shows_in_the_state(self):
        self.hold_jobs()
        self.post("/api/apply", {"tune": "draft"})
        self.entered.wait(5)
        job = self.get("/api/state").json["job"]
        self.assertEqual(set(job), JOB_KEYS)
        self.assertEqual((job["kind"], job["state"], job["result"], job["error"]), ("apply", "running", None, None))
        self.assertEqual(job["log"], ["building ax_x, this takes a while ..."])
        self.finish_held_job()
        self.assertEqual(self.get("/api/state").json["job"]["state"], "done")

    def test_the_state_of_a_finished_job_is_kept_until_the_next_job(self):
        self.post("/api/init")
        done = self.wait_job()
        self.assertEqual(self.get("/api/state").json["job"], done)
        self.assertEqual(self.get("/api/state").json["job"], done)
        self.assertEqual(self.get("/api/state?car=ks_y").json["job"], done)

    def test_a_new_job_starts_with_an_empty_result_and_log(self):
        self.post("/api/init")
        self.wait_job()
        self.hold_jobs()
        self.entered.clear()
        self.post("/api/apply", {"tune": "draft"})
        job = ts.job_snapshot()
        self.assertEqual((job["kind"], job["state"], job["result"], job["error"]), ("apply", "running", None, None))
        self.assertNotIn("extracted the stock car", job["log"])
        self.finish_held_job()

    def test_a_failed_job_does_not_block_the_next_one(self):
        self.errors["init"] = ValueError("x")
        self.post("/api/init")
        self.assertEqual(self.wait_job()["state"], "error")
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)

    def test_the_game_check_is_not_used_by_init(self):
        self.game_up = True
        self.assertEqual(self.post("/api/init").status, 202)

    def test_set_is_refused_while_a_job_runs(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)
        r = self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.assertEqual(r.status, 409, r.json)

    def test_unset_is_refused_while_a_job_runs(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)
        r = self.post("/api/unset", {"id": "limiter"})
        self.assertEqual(r.status, 409, r.json)

    def test_reset_all_is_refused_while_a_job_runs(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)
        r = self.post("/api/reset_all")
        self.assertEqual(r.status, 409, r.json)


class TestJobFunctions(Env):
    def test_the_job_starts_idle(self):
        self.assertEqual(ts.job_snapshot(), {"kind": None, "state": "idle", "log": [], "result": None, "error": None})

    def test_claim_job_marks_the_job_running_and_clears_the_old_one(self):
        ts.JOB.update(kind="init", state="done", log=["old"], result={"x": 1}, error="old error")
        ts.claim_job("apply")
        self.assertEqual(ts.job_snapshot(), {"kind": "apply", "state": "running", "log": [], "result": None, "error": None})

    def test_a_second_claim_while_running_is_refused_and_keeps_the_first(self):
        ts.claim_job("init")
        ts.log_line("one")
        with self.assertRaises(ts.ApiError) as cm:
            ts.claim_job("apply")
        self.assertEqual((cm.exception.status, cm.exception.message), (409, "another job is running, wait until it has finished"))
        self.assertEqual((ts.job_snapshot()["kind"], ts.job_snapshot()["log"]), ("init", ["one"]))

    def test_a_claim_is_possible_after_done_and_after_error(self):
        for state in ("done", "error"):
            with self.subTest(state):
                ts.JOB.update(state=state)
                ts.claim_job("apply")
                self.assertEqual(ts.job_snapshot()["state"], "running")

    def test_finish_job_sets_state_result_and_error(self):
        ts.claim_job("init")
        ts.finish_job("done", {"files": 3})
        self.assertEqual(ts.job_snapshot(), {"kind": "init", "state": "done", "log": [], "result": {"files": 3}, "error": None})
        ts.finish_job("error", error="boom")
        self.assertEqual(ts.job_snapshot(), {"kind": "init", "state": "error", "log": [], "result": None, "error": "boom"})

    def test_log_line_appends_in_order(self):
        ts.log_line("a")
        ts.log_line("b")
        self.assertEqual(ts.job_snapshot()["log"], ["a", "b"])

    def test_the_snapshot_is_a_copy_of_the_log(self):
        ts.log_line("a")
        snap = ts.job_snapshot()
        snap["log"].append("b")
        self.assertEqual(ts.JOB["log"], ["a"])

    def test_job_thread_success_is_done_with_the_result(self):
        ts.claim_job("init")
        ts.job_thread(lambda: {"ok": 1})
        self.assertEqual((ts.job_snapshot()["state"], ts.job_snapshot()["result"], ts.job_snapshot()["error"]), ("done", {"ok": 1}, None))

    def test_job_thread_value_and_os_errors_end_in_error_with_a_log_line(self):
        for exc in (ValueError("bad value"), OSError("disk full")):
            with self.subTest(type(exc).__name__):
                ts.claim_job("apply")

                def task(exc=exc):
                    raise exc
                ts.job_thread(task)
                snap = ts.job_snapshot()
                self.assertEqual((snap["state"], snap["error"], snap["log"]), ("error", str(exc), ["error: %s" % exc]))

    def test_job_thread_system_exit_ends_in_error_with_its_text(self):
        ts.claim_job("apply")

        def task():
            raise SystemExit("clone self-check failed")
        ts.job_thread(task)
        snap = ts.job_snapshot()
        self.assertEqual((snap["state"], snap["error"], snap["log"]), ("error", "clone self-check failed", ["error: clone self-check failed"]))

    def test_job_thread_unexpected_error_is_internal_and_prints_a_traceback(self):
        ts.claim_job("apply")

        def task():
            raise RuntimeError("boom")
        ts.job_thread(task)
        snap = ts.job_snapshot()
        self.assertEqual((snap["state"], snap["error"], snap["log"]), ("error", "internal error: boom", ["error: internal error: boom"]))
        self.assertIn("RuntimeError: boom", self.err.getvalue())

    def test_run_job_claims_first_and_runs_the_task_in_a_daemon_thread(self):
        self.hold_jobs()
        seen = []
        ts.run_job("init", lambda: (seen.append(threading.current_thread()), self.gate.wait(5), "r")[2])
        self.assertEqual(ts.job_snapshot()["state"], "running")
        with self.assertRaises(ts.ApiError):
            ts.run_job("apply", lambda: None)
        self.gate.set()
        self.assertEqual((self.wait_job()["state"], ts.job_snapshot()["result"]), ("done", "r"))
        self.assertTrue(seen[0].daemon)
        self.assertIsNot(seen[0], threading.current_thread())


# -------------------------------------------------------------------------------------------------- logging, headers, game check
class TestLogging(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_an_idle_poll_is_not_logged(self):
        self.assertEqual(self.get("/api/state").status, 200)
        self.assertEqual(self.get("/api/state?car=ks_x").status, 200)
        self.assertNotIn("/api/state", self.err.getvalue())

    def test_other_requests_are_logged_with_their_status(self):
        self.get("/api/settings")
        self.get("/nothing")
        log = self.err.getvalue()
        self.assertIn('"GET /ACESCT/api/settings HTTP/1.1" 200 -', log)
        self.assertIn('"GET /ACESCT/nothing HTTP/1.1" 404 -', log)

    def test_a_failing_state_request_is_logged(self):
        self.assertEqual(self.get("/api/state?car=nope").status, 400)
        self.assertIn("/api/state?car=nope", self.err.getvalue())

    def test_a_forbidden_state_request_is_logged(self):
        self.assertEqual(self.get("/api/state", host="evil.example").status, 403)
        self.assertIn("/api/state", self.err.getvalue())


class TestFramingHeaders(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_every_response_forbids_framing(self):
        replies = {"page": self.get("/"), "state": self.get("/api/state"), "404": self.get("/nothing"),
                   "403": self.get("/api/state", host="evil.example"), "400": self.post("/api/set", b"{bad"),
                   "202": self.post("/api/init")}
        missing = []
        for label, r in replies.items():
            if r.headers.get("X-Frame-Options") not in ("DENY", "SAMEORIGIN"):
                missing.append(label + ": X-Frame-Options")
            if not re.search(r"frame-ancestors\s+('none'|'self')", r.headers.get("Content-Security-Policy", "")):
                missing.append(label + ": Content-Security-Policy frame-ancestors")
        self.assertEqual(missing, [])


class TestGameRunning(unittest.TestCase):
    def run_with(self, result=None, error=None):
        run = mock.Mock(return_value=result, side_effect=error)
        with mock.patch.object(tune.subprocess, "run", run):
            return REAL_GAME_RUNNING(), run

    def done(self, code, out):
        return tune.subprocess.CompletedProcess(GAME_ARGV, code, stdout=out, stderr=b"")

    def test_it_asks_tasklist_with_a_fixed_argument_list(self):
        _, run = self.run_with(self.done(0, b""))
        run.assert_called_once_with(GAME_ARGV, capture_output=True, timeout=5)

    def test_the_game_is_running_when_tasklist_lists_the_exe(self):
        self.assertTrue(self.run_with(self.done(0, b'"AssettoCorsaEVO.exe","1234","Console","1","1,000 K"\r\n'))[0])
        self.assertTrue(self.run_with(self.done(0, b'"assettocorsaevo.EXE","1234"\r\n'))[0])

    def test_the_game_is_not_running_when_tasklist_finds_nothing(self):
        self.assertFalse(self.run_with(self.done(0, b"INFO: No tasks are running which match the specified criteria.\r\n"))[0])
        self.assertFalse(self.run_with(self.done(0, b""))[0])

    def test_a_failing_tasklist_means_not_running(self):
        self.assertFalse(self.run_with(self.done(1, b'"AssettoCorsaEVO.exe","1"'))[0])

    def test_a_missing_or_slow_tasklist_means_not_running(self):
        self.assertFalse(self.run_with(error=FileNotFoundError("tasklist"))[0])
        self.assertFalse(self.run_with(error=tune.subprocess.TimeoutExpired("tasklist", 5))[0])

    def test_non_ascii_output_does_not_raise(self):
        self.assertFalse(self.run_with(self.done(0, b"\xff\xfe\x00 nothing"))[0])


class TestStatePollCost(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_three_quick_polls_start_at_most_one_tasklist(self):
        run = mock.Mock(return_value=tune.subprocess.CompletedProcess(GAME_ARGV, 0, stdout=b"INFO: No tasks", stderr=b""))
        self.patch(ts, "game_running", REAL_GAME_RUNNING)
        self.patch(tune.subprocess, "run", run)
        statuses = [self.get("/api/state").status for _ in range(3)]
        self.assertEqual(statuses, [200, 200, 200])
        self.assertLessEqual(run.call_count, 1, "tasklist was started %d times for 3 polls" % run.call_count)

    def test_the_poll_check_asks_again_after_the_cache_time(self):
        calls = []
        self.patch(ts, "game_running", lambda: calls.append(1) or True)
        ts.GAME_CHECK[:] = [time.monotonic() - 10, False]
        self.assertTrue(ts.game_running_cached())
        self.assertTrue(ts.game_running_cached())
        self.assertEqual(len(calls), 1)
        ts.GAME_CHECK[0] -= 10
        self.assertTrue(ts.game_running_cached())
        self.assertEqual(len(calls), 2)

    def test_an_unexpandable_mods_folder_is_a_409_for_the_state(self):
        ts.CONFIG["mods"] = "%ACE_TEST_NO_SUCH_VAR%/m"
        r = self.get("/api/state")
        self.assertEqual((r.status, r.json), (409, {"error": "cannot expand the mods folder '%ACE_TEST_NO_SUCH_VAR%/m'"}))

    def test_apply_always_checks_the_game_itself(self):
        run = mock.Mock(return_value=tune.subprocess.CompletedProcess(GAME_ARGV, 0, stdout=b"INFO: No tasks", stderr=b""))
        self.patch(ts, "game_running", REAL_GAME_RUNNING)
        self.patch(tune.subprocess, "run", run)
        self.get("/api/state")
        before = run.call_count
        self.assertEqual(self.post("/api/apply", {"tune": "draft"}).status, 202)
        self.assertEqual(run.call_count, before + 1)


# -------------------------------------------------------------------------------------------------- pure helpers
class TestHelpers(Env):
    def test_api_error_carries_status_and_message(self):
        e = ts.ApiError(409, "nope")
        self.assertIsInstance(e, Exception)
        self.assertEqual((e.status, e.message, str(e), e.args), (409, "nope", "nope", ("nope",)))

    def test_check_host(self):
        ts.CONFIG["port"] = 8765
        for host in ("127.0.0.1:8765", "localhost:8765", "LocalHost:8765"):
            ts.check_host(host)
        for host in (None, "", "127.0.0.1", "localhost", "127.0.0.1:80", "127.0.0.1:8765x", "evil:8765", "[::1]:8765", "x127.0.0.1:8765"):
            with self.subTest(host), self.assertRaises(ts.ApiError) as cm:
                ts.check_host(host)
            self.assertEqual((cm.exception.status, cm.exception.message), (403, "forbidden host"))

    def test_check_host_follows_the_configured_port(self):
        ts.CONFIG["port"] = 9000
        ts.check_host("127.0.0.1:9000")
        with self.assertRaises(ts.ApiError):
            ts.check_host("127.0.0.1:8765")

    def test_check_host_accepts_localhost_private_addresses_and_the_machine_name(self):
        ts.CONFIG["port"] = 8080
        with mock.patch.object(ts.socket, "gethostname", return_value="Alex-PC"):
            for host in ("localhost:8080", "127.0.0.1:8080", "192.168.1.20:8080", "10.0.0.5:8080", "172.16.0.1:8080", "Alex-PC:8080", "alex-pc:8080"):
                with self.subTest(host):
                    ts.check_host(host)

    def test_check_host_refuses_everything_else(self):
        ts.CONFIG["port"] = 8080
        with mock.patch.object(ts.socket, "gethostname", return_value="Alex-PC"):
            for host in (None, "", "192.168.1.20", "Alex-PC", "192.168.1.20:8081", "192.168.1.20:80800", "192.168.1.20:", "evil.example:8080",
                         "8.8.8.8:8080", "[::1]:8080", "192.168.1.20.evil.example:8080", "Alex-PC.local:8080", "172.32.0.1:8080",
                         "100.64.0.1:8080", "0.0.0.0:8080", ":8080", "1:8080"):
                with self.subTest(host), self.assertRaises(ts.ApiError) as cm:
                    ts.check_host(host)
                self.assertEqual((cm.exception.status, cm.exception.message), (403, "forbidden host"))

    def test_check_host_needs_no_dns_lookup(self):
        ts.CONFIG["port"] = 8080
        with mock.patch.object(ts.socket, "getaddrinfo", side_effect=AssertionError("a DNS lookup")), \
                mock.patch.object(ts.socket, "gethostbyname", side_effect=AssertionError("a DNS lookup")):
            ts.check_host("192.168.1.20:8080")
            with self.assertRaises(ts.ApiError):
                ts.check_host("evil.example:8080")

    def test_private_ip(self):
        for address in ("127.0.0.1", "127.1.2.3", "192.168.1.5", "10.1.2.3", "172.16.0.1", "172.31.255.255"):
            with self.subTest(address):
                self.assertTrue(ts.private_ip(address))
        for address in ("8.8.8.8", "100.64.0.1", "172.32.0.1", "0.0.0.0", "::1", "fe80::1", "", "garbage", "192.168.1", "192.168.1.5.6", "192.168.1.5:80",
                        "[::1]", None, "1"):
            with self.subTest(address):
                self.assertFalse(ts.private_ip(address))

    def test_check_client_accepts_loopback_and_private_addresses(self):
        for address in ("192.168.1.5", "10.1.2.3", "127.0.0.1"):
            with self.subTest(address):
                ts.check_client(address)

    def test_check_client_refuses_public_shared_and_unparsable_addresses(self):
        for address in ("8.8.8.8", "100.64.0.1", "172.32.0.1", "garbage", "", None):
            with self.subTest(address), self.assertRaises(ts.ApiError) as cm:
                ts.check_client(address)
            self.assertEqual((cm.exception.status, cm.exception.message), (403, "forbidden client address"))

    def probe_socket(self, address=("192.168.1.20", 5555), error=None):
        probe = mock.MagicMock()
        probe.__enter__.return_value = probe
        probe.getsockname.return_value = address
        if error:
            probe.connect.side_effect = error
        return probe

    def lan(self, infos, probe):
        with mock.patch.object(ts.socket, "gethostname", return_value="Alex-PC"), \
                mock.patch.object(ts.socket, "getaddrinfo", **infos) as lookup, \
                mock.patch.object(ts.socket, "socket", return_value=probe) as make:
            found = ts.lan_addresses()
        return found, lookup, make

    def infos(self, *addresses):
        return {"return_value": [(ts.socket.AF_INET, ts.socket.SOCK_STREAM, 6, "", (a, 0)) for a in addresses]}

    def test_lan_addresses_keeps_private_non_loopback_addresses_without_duplicates(self):
        probe = self.probe_socket(("10.0.0.7", 5555))
        found, lookup, make = self.lan(self.infos("192.168.1.20", "127.0.0.1", "8.8.8.8", "192.168.1.20", "169.254.3.4", "100.64.0.1", "10.0.0.7",
                                                  "0.0.0.0"), probe)
        self.assertEqual(found, ["192.168.1.20", "169.254.3.4", "10.0.0.7"])
        lookup.assert_called_once_with("Alex-PC", None, ts.socket.AF_INET)

    def test_lan_addresses_asks_the_routing_table_with_a_udp_connect_and_sends_nothing(self):
        probe = self.probe_socket(("192.168.1.20", 5555))
        found, _, make = self.lan(self.infos(), probe)
        self.assertEqual(found, ["192.168.1.20"])
        make.assert_called_once_with(ts.socket.AF_INET, ts.socket.SOCK_DGRAM)
        probe.connect.assert_called_once_with(("10.255.255.255", 1))
        for name in ("send", "sendto", "sendall"):
            getattr(probe, name).assert_not_called()

    def test_lan_addresses_drops_a_loopback_or_public_probe_result(self):
        for address in ("127.0.0.1", "8.8.8.8", "0.0.0.0"):
            with self.subTest(address):
                self.assertEqual(self.lan(self.infos(), self.probe_socket((address, 1)))[0], [])

    def test_lan_addresses_ignores_failing_lookups(self):
        probe = self.probe_socket(("192.168.1.20", 5555))
        found, _, _ = self.lan({"side_effect": ts.socket.gaierror(11001, "getaddrinfo failed")}, probe)
        self.assertEqual(found, ["192.168.1.20"])
        failing = self.probe_socket(error=OSError(101, "Network is unreachable"))
        found, _, _ = self.lan(self.infos("10.0.0.7"), failing)
        self.assertEqual(found, ["10.0.0.7"])
        found, _, _ = self.lan({"side_effect": OSError("no network")}, failing)
        self.assertEqual(found, [])

    def headers(self, **kw):
        msg = email.message.Message()
        for key, value in kw.items():
            msg[key.replace("_", "-")] = value
        return msg

    def test_check_post_headers_accepts_the_page_headers(self):
        ts.check_post_headers(self.headers(X_Tuner="1", Content_Type="application/json"))
        ts.check_post_headers(self.headers(x_tuner="1", content_type="Application/JSON; charset=utf-8"))

    def test_check_post_headers_refuses_a_missing_or_wrong_x_tuner(self):
        for h in (self.headers(Content_Type="application/json"), self.headers(X_Tuner="2", Content_Type="application/json")):
            with self.assertRaises(ts.ApiError) as cm:
                ts.check_post_headers(h)
            self.assertEqual((cm.exception.status, cm.exception.message), (403, "missing header X-Tuner: 1"))

    def test_check_post_headers_refuses_another_content_type(self):
        for h in (self.headers(X_Tuner="1"), self.headers(X_Tuner="1", Content_Type="text/plain"),
                  self.headers(X_Tuner="1", Content_Type="json")):
            with self.assertRaises(ts.ApiError) as cm:
                ts.check_post_headers(h)
            self.assertEqual((cm.exception.status, cm.exception.message), (415, "Content-Type must be application/json"))

    def test_parse_port_accepts_ports_of_a_user_server(self):
        for text, port in (("8765", 8765), ("1024", 1024), ("5000", 5000), ("65535", 65535)):
            self.assertEqual(ts.parse_port(text), port)

    def test_parse_port_rejects_everything_else(self):
        for text in ("0", "65536", "99999999999", "-1", "abc", "", "1.5", "80x", "0x50", "8 0", "+80"):
            with self.subTest(text), self.assertRaisesRegex(ValueError, r"^--port must be a number from \d+ to 65535$"):
                ts.parse_port(text)

    def test_parse_port_rejects_port_80(self):
        with self.assertRaisesRegex(ValueError, "--port"):
            ts.parse_port("80")

    def test_mods_dir_expands_variables_and_makes_the_path_absolute(self):
        with mock.patch.dict(os.environ, {"ACE_TEST_MODS": str(self.d)}):
            ts.CONFIG["mods"] = "$ACE_TEST_MODS/m"
            self.assertEqual(ts.mods_dir(), os.path.join(str(self.d), "m"))
        ts.CONFIG["mods"] = "rel/mods"
        self.assertEqual(ts.mods_dir(), os.path.abspath("rel/mods"))

    def test_mods_dir_refuses_a_variable_that_cannot_be_expanded(self):
        ts.CONFIG["mods"] = "%ACE_TEST_NO_SUCH_VAR%/m"
        with self.assertRaises(ValueError):
            ts.mods_dir()

    def test_mods_dir_defaults_to_the_game_mods_folder(self):
        ts.CONFIG["mods"] = None
        with mock.patch.dict(os.environ, {"USERPROFILE": str(self.d)}), mock.patch.object(os.path, "expandvars", ntpath.expandvars):
            self.assertEqual(ts.mods_dir(), os.path.abspath(os.path.expandvars(clone_car.DEFAULT_MODS)))

    def test_installed_info_without_a_package(self):
        self.assertEqual(ts.installed_info("ks_x"), {"path": os.path.join(self.mods, "ax_x.kspkg"), "exists": False, "bytes": None, "modified": None})

    def test_installed_info_with_a_package(self):
        os.makedirs(self.mods)
        path = os.path.join(self.mods, "ax_x.kspkg")
        with open(path, "wb") as f:
            f.write(b"123456")
        os.utime(path, (1700000000, 1700000000))
        info = ts.installed_info("ks_x")
        self.assertEqual((info["path"], info["exists"], info["bytes"]), (path, True, 6))
        self.assertRegex(info["modified"], r"^20\d\d-\d\d-\d\dT\d\d:\d\d:\d\d$")

    def test_installed_info_names_the_package_after_the_new_id(self):
        self.assertTrue(ts.installed_info("ks_bmw_m3")["path"].endswith("ax_bmw_m3.kspkg"))

    def test_apply_lines_with_an_install_and_a_backup(self):
        res = dict(APPLY_RESULT, applied=[{"id": "a", "old": 1.5, "new": 2.0, "files": ["f1", "f2"]}, {"id": "b", "old": None, "new": True, "files": []}],
                   notes=["n1", "n2"], backup="/b/old.kspkg")
        self.assertEqual(ts.apply_lines(res), [
            "applied 2 setting(s)", "  a: 1.5 -> 2.0  [f1, f2]", "  b: - -> true  []", "n1", "n2",
            "package: /w/ks_x/build/ax_x/ax_x.kspkg (7 bytes)", "installed: /m/ax_x.kspkg", "backup: /b/old.kspkg"])

    def test_apply_lines_without_an_install(self):
        res = dict(APPLY_RESULT, applied=[], notes=[], installed=None)
        self.assertEqual(ts.apply_lines(res), ["applied 0 setting(s)", "package: /w/ks_x/build/ax_x/ax_x.kspkg (7 bytes)"])

    def test_request_car(self):
        self.write_index([{"id": "ks_x", "display_name": "Car X"}, {"id": "ks_y", "display_name": "Car Y"}])
        self.assertEqual(ts.request_car(None, ""), "ks_x")
        self.assertEqual(ts.request_car(None, "car=ks_y"), "ks_y")
        self.assertEqual(ts.request_car(None, "a=1&car=ks_y&b=2"), "ks_y")
        self.assertEqual(ts.request_car(None, "car=ks%5Fy"), "ks_y")
        self.assertEqual(ts.request_car("ks_x", "car=ks_y"), "ks_x")
        self.assertEqual(ts.request_car(None, "car="), "ks_x")
        self.assertEqual(ts.request_car("", "car=ks_y"), "ks_x")

    def test_request_car_refuses_unknown_and_non_text_cars(self):
        self.write_index([{"id": "ks_x", "display_name": "Car X"}])
        for value, query, text in (("../x", "", "unknown car"), (None, "car=../x", "unknown car"), (5, "", "car must be text"),
                                   (["ks_x"], "", "car must be text")):
            with self.subTest(value, query=query), self.assertRaises(ts.ApiError) as cm:
                ts.request_car(value, query)
            self.assertEqual(cm.exception.status, 400)
            self.assertTrue(cm.exception.message.startswith(text), cm.exception.message)

    def test_request_car_without_a_car_list_knows_only_the_tested_cars(self):
        self.patch(tune, "load_cars_index", lambda work, game=None: None)
        self.assertEqual(ts.request_car("ks_x", ""), "ks_x")
        with self.assertRaises(ts.ApiError) as cm:
            ts.request_car("ks_y", "")
        self.assertEqual(cm.exception.status, 400)

    def write_index(self, index):
        os.makedirs(self.work, exist_ok=True)
        with open(os.path.join(self.work, "cars_index.json"), "w", encoding="utf-8") as f:
            json.dump(index, f)

    def test_row_json_keeps_the_documented_fields_only(self):
        row = {k: k for k in ROW_KEYS}
        row.update(copies_differ=False, targets=["secret"], reason=None, applicable=True, ok=True)
        s = {"min": 1, "max": 5, "choices": ["a"], "ui": "header", "targets": ["x"], "handler": "h"}
        out = ts.row_json(row, s)
        self.assertEqual(set(out), ROW_KEYS | {"min", "max", "choices", "ui"})
        self.assertEqual((out["min"], out["max"], out["choices"], out["ui"]), (1, 5, ["a"], "header"))
        self.assertNotIn("copy_values", out)

    def test_row_json_passes_advanced_only_when_the_setting_has_it(self):
        row = {k: k for k in ROW_KEYS}
        row.update(copies_differ=False)
        self.assertNotIn("advanced", ts.row_json(row, {"min": 1}))
        out = ts.row_json(row, {"advanced": True})
        self.assertEqual((set(out), out["advanced"]), (ROW_KEYS | {"advanced"}, True))

    def test_row_json_adds_the_copy_values_only_when_the_copies_differ(self):
        row = {k: k for k in ROW_KEYS}
        row.update(copies_differ=True, copy_values=[{"target": "t", "value": 1}])
        out = ts.row_json(row, {})
        self.assertEqual((set(out), out["copy_values"]), (ROW_KEYS | {"copy_values"}, [{"target": "t", "value": 1}]))

    def test_row_json_adds_the_base_range_only_when_one_is_given(self):
        row = {k: k for k in ROW_KEYS}
        row.update(copies_differ=False)
        self.assertNotIn("base_range", ts.row_json(row, {"min": 1}))
        self.assertNotIn("base_range", ts.row_json(row, {"min": 1}, None))
        out = ts.row_json(row, {"min": 1}, {"low": 2, "high": 3, "extra": 4})
        self.assertEqual((set(out), out["base_range"], out["min"]), (ROW_KEYS | {"min", "base_range"}, {"low": 2, "high": 3}, 1))

    def test_rows_json_needs_a_base_car(self):
        with self.assertRaises(ts.ApiError) as cm:
            ts.rows_json(self.work, "ks_x", self.cat)
        self.assertEqual((cm.exception.status, cm.exception.message), (409, "base car missing, run init"))

    def test_rows_json_of_a_stub_car(self):
        fc = FakeCar(self.work, "ks_x").install(self)
        gp = fc.game_path
        fc.add("data/x.car", {"engine_path": gp("data/e.carengine"), "stock_setup": gp("data/s.carsetup"), "engine": {"limiter": 7000}})
        fc.add("data/e.carengine", {"limiter": 7000, "turbos_to_load": []})
        fc.add("data/s.carsetup", {"electronics": {"tc1": 2}})
        write_state = {"limiter": 8000}
        tune.save_state(self.work, "ks_x", write_state)
        rows = ts.rows_json(self.work, "ks_x", self.cat)
        self.assertEqual([r["id"] for r in rows], ["limiter", "aids_off", "name_suffix"])
        self.assertEqual((rows[0]["value"], rows[0]["default"], rows[0]["changed"]), (8000, 7000, True))
        self.assertEqual(ts.row_of(self.work, "ks_x", self.cat, "aids_off")["id"], "aids_off")

    def test_base_present_needs_a_non_empty_car_folder(self):
        fc = FakeCar(self.work, "ks_x")
        self.assertFalse(ts.base_present(self.work, "ks_x"))
        os.makedirs(fc.car_root)
        self.assertFalse(ts.base_present(self.work, "ks_x"))
        fc.add("data/x.car")
        self.assertTrue(ts.base_present(self.work, "ks_x"))


# -------------------------------------------------------------------------------------------------- main()
class StubServer:
    """Stands for ThreadingHTTPServer in main(): records its construction order and raises what the test says in serve_forever."""
    log = []
    serve_error = KeyboardInterrupt
    bind_error = None

    def __init__(self, address, handler):
        StubServer.log.append("server")
        if StubServer.bind_error:
            raise StubServer.bind_error
        self.address, self.handler, self.closed = address, handler, False
        StubServer.last = self

    def serve_forever(self):
        StubServer.log.append("serve")
        if StubServer.serve_error:
            raise StubServer.serve_error

    def server_close(self):
        self.closed = True
        StubServer.log.append("close")


class TestServerClass(unittest.TestCase):
    def test_the_port_is_not_shared(self):
        self.assertFalse(ts.Server.allow_reuse_address)
        self.assertTrue(issubclass(ts.Server, http.server.ThreadingHTTPServer))

    def bind(self, name):
        server = ts.Server.__new__(ts.Server)
        server.socket = mock.Mock()
        with mock.patch.object(http.server.HTTPServer, "server_bind") as base, \
                mock.patch.object(ts.os, "name", name), \
                mock.patch.object(ts.socket, "SO_EXCLUSIVEADDRUSE", -5, create=True):
            ts.Server.server_bind(server)
        base.assert_called_once_with(server)
        return server.socket.setsockopt

    def test_windows_binds_exclusively_before_the_bind(self):
        self.bind("nt").assert_called_once_with(ts.socket.SOL_SOCKET, -5, 1)

    def test_other_systems_set_no_socket_option(self):
        self.bind("posix").assert_not_called()


class TestRealServer(Env):
    def test_the_server_class_answers_below_the_base_path_on_a_real_socket(self):
        server = ts.Server(("127.0.0.1", 0), ts.Handler)
        port = ts.CONFIG["port"] = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        for path, status in (("/ACESCT/", 200), ("/ACESCT", 301), ("/", 302), ("/api/state", 404)):
            with self.subTest(path):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                try:
                    conn.request("GET", path)
                    self.assertEqual(conn.getresponse().status, status)
                finally:
                    conn.close()


class TestMain(Env):
    def setUp(self):
        super().setUp()
        StubServer.log, StubServer.serve_error, StubServer.bind_error = [], KeyboardInterrupt, None
        self.patch(ts, "Server", StubServer)
        self.patch(tune, "load_cars_index", lambda work, *a, **k: StubServer.log.append("index"))
        self.lan = ["192.168.1.20"]
        self.patch(ts, "lan_addresses", lambda: self.lan)
        self.argv = ["--port", "8765", "--work", self.work, "--mods", self.mods]

    def run_main(self, *argv):
        """main() with the given arguments; returns what it exits with (None when it returns)."""
        with mock.patch.object(sys, "argv", ["tuner_server.py", *argv]):
            try:
                ts.main()
            except SystemExit as e:
                return e.code
        return None

    def test_start_binds_every_address_with_the_handler_and_prints_the_urls(self):
        self.lan = ["192.168.1.20", "10.0.0.7"]
        self.assertIsNone(self.run_main(*self.argv))
        self.assertEqual((StubServer.last.address, StubServer.last.handler), (("0.0.0.0", 8765), ts.Handler))
        self.assertEqual(self.out.getvalue(), "tuner running on http://127.0.0.1:8765/ACESCT/\n"
                         "reachable in the home network: http://192.168.1.20:8765/ACESCT/\n"
                         "reachable in the home network: http://10.0.0.7:8765/ACESCT/\nstopped\n")

    def test_start_prints_only_the_local_url_when_the_pc_has_no_private_address(self):
        self.lan = []
        self.run_main(*self.argv)
        self.assertEqual(self.out.getvalue(), "tuner running on http://127.0.0.1:8765/ACESCT/\nstopped\n")

    def test_bind_127_0_0_1_serves_this_pc_only_and_prints_one_url(self):
        self.assertIsNone(self.run_main(*self.argv, "--bind", "127.0.0.1"))
        self.assertEqual(StubServer.last.address, ("127.0.0.1", 8765))
        self.assertEqual(self.out.getvalue(), "tuner running on http://127.0.0.1:8765/ACESCT/\nstopped\n")

    def test_bind_takes_any_address_of_the_option(self):
        self.run_main(*self.argv, "--bind", "192.168.1.20")
        self.assertEqual(StubServer.last.address, ("192.168.1.20", 8765))

    def test_the_default_bind_is_every_ipv4_address(self):
        self.assertEqual(ts.DEFAULT_BIND, "0.0.0.0")
        self.run_main("--work", self.work)
        self.assertEqual(StubServer.last.address[0], "0.0.0.0")

    def test_a_bind_address_that_cannot_be_used_is_an_error_line(self):
        StubServer.bind_error = OSError(10049, "address not valid in its context")
        self.assertEqual(self.run_main(*self.argv, "--bind", "203.0.113.9"), "error: [Errno 10049] address not valid in its context")
        self.assertEqual(self.out.getvalue(), "")

    def test_start_sets_config_from_the_options(self):
        self.run_main(*self.argv)
        self.assertEqual((ts.CONFIG["port"], ts.CONFIG["work"], ts.CONFIG["mods"]), (8765, os.path.abspath(self.work), self.mods))

    def test_the_default_port_is_8080(self):
        self.run_main("--work", self.work)
        self.assertEqual((ts.DEFAULT_PORT, StubServer.last.address), (8080, ("0.0.0.0", 8080)))
        self.assertIn("http://127.0.0.1:8080/ACESCT/\n", self.out.getvalue())

    def test_ctrl_c_closes_the_server_and_returns(self):
        self.assertIsNone(self.run_main(*self.argv))
        self.assertEqual(StubServer.log[-2:], ["serve", "close"])
        self.assertTrue(StubServer.last.closed)

    def test_the_server_is_closed_after_an_unexpected_error_too(self):
        StubServer.serve_error = RuntimeError("boom")
        with self.assertRaises(RuntimeError):
            self.run_main(*self.argv)
        self.assertTrue(StubServer.last.closed)

    def test_a_bad_port_is_an_error_line(self):
        exit_text = self.run_main("--port", "abc", "--work", self.work)
        self.assertTrue(exit_text.startswith("error: --port must be a number from"), exit_text)
        self.assertEqual(StubServer.log, [])

    def test_an_unexpandable_work_folder_is_an_error_line(self):
        exit_text = self.run_main("--work", "%ACE_TEST_NO_SUCH_VAR%/w")
        self.assertTrue(exit_text.startswith("error: cannot expand the work directory"), exit_text)

    def test_a_port_that_cannot_be_bound_is_an_error_line(self):
        StubServer.bind_error = OSError(98, "Address already in use")
        self.assertEqual(self.run_main(*self.argv), "error: [Errno 98] Address already in use")
        self.assertEqual(self.out.getvalue(), "")

    def test_the_old_single_car_layout_is_moved_into_the_default_car_folder(self):
        os.makedirs(os.path.join(self.work, "base"))
        with open(os.path.join(self.work, "base", "x.bin"), "wb"):
            pass
        with open(os.path.join(self.work, "tune_state.json"), "w") as f:
            f.write("{}")
        self.run_main(*self.argv)
        self.assertTrue(os.path.isfile(os.path.join(self.work, "ks_x", "base", "x.bin")))
        self.assertTrue(os.path.isfile(os.path.join(self.work, "ks_x", "tune_state.json")))
        self.assertIn("moved the old single-car layout of", self.out.getvalue())
        self.assertIn("base, tune_state.json", self.out.getvalue())

    def test_every_option_of_the_usage_block_is_accepted(self):
        values = {"port": "8765", "bind": "127.0.0.1", "work": self.work, "mods": self.mods, "game": "game.kspkg"}
        flags = re.findall(r"\[--(\w+) ", USAGE)
        self.assertTrue({"port", "bind", "work", "mods"} <= set(flags), flags)
        self.assertIsNone(self.run_main(*[w for flag in flags for w in ("--" + flag, values[flag])]))

    def test_the_game_option_is_accepted_and_kept_in_the_config(self):
        self.assertIsNone(self.run_main(*self.argv, "--game", "game.kspkg"))
        self.assertEqual(ts.CONFIG.get("game"), os.path.expandvars("game.kspkg"))

    def test_the_listening_server_is_created_before_the_car_index_is_loaded(self):
        self.run_main(*self.argv)
        self.assertIn("server", StubServer.log)
        self.assertIn("index", StubServer.log)
        self.assertLess(StubServer.log.index("server"), StubServer.log.index("index"), StubServer.log)

    def test_the_game_option_reaches_the_car_index(self):
        seen = []
        self.patch(tune, "load_cars_index", lambda work, *a, **k: seen.append(a))
        self.run_main(*self.argv, "--game", "game.kspkg")
        self.assertEqual(seen, [("game.kspkg",)])

    def test_the_game_defaults_to_the_steam_package(self):
        self.run_main(*self.argv)
        self.assertEqual(ts.CONFIG["game"], os.path.expandvars(tune.DEFAULT_GAME))

    def test_a_job_that_runs_at_ctrl_c_is_announced(self):
        self.hold_jobs()
        ts.run_job("apply", lambda: self.gate.wait(10))
        self.addCleanup(self.gate.set)
        main = threading.Thread(target=lambda: self.run_main(*self.argv), daemon=True)
        main.start()
        main.join(0.3)
        self.assertIn("a job is still running", self.out.getvalue())
        self.gate.set()
        main.join(5)
        self.assertTrue(self.out.getvalue().endswith("stopped\n"))

    def test_the_car_index_is_loaded_once_per_start(self):
        self.run_main(*self.argv)
        self.assertEqual(StubServer.log.count("index"), 1)

    def test_ctrl_c_waits_for_a_running_job(self):
        self.hold_jobs()
        ts.run_job("apply", lambda: self.gate.wait(10))
        exits = []
        main = threading.Thread(target=lambda: exits.append(self.run_main(*self.argv)), daemon=True)
        self.addCleanup(main.join, 5)
        self.addCleanup(self.gate.set)
        main.start()
        main.join(0.3)
        self.assertTrue(main.is_alive(), "main() returned while the job was still running")
        self.gate.set()
        main.join(5)
        self.assertFalse(main.is_alive())
        self.assertEqual(exits, [None])

    def test_ctrl_c_without_a_job_returns_at_once(self):
        main = threading.Thread(target=lambda: self.run_main(*self.argv), daemon=True)
        main.start()
        main.join(5)
        self.assertFalse(main.is_alive())


# -------------------------------------------------------------------------------------------------- CLI conventions
def usage_case(name, argv):
    def test(self):
        with tmp() as d:
            r = run_tool("tuner_server.py", *argv, cwd=d)
        self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (2, USAGE.strip(), ""))
    test.__name__ = "test_usage_" + name
    return test


class TestCli(unittest.TestCase):
    pass


for _name, _argv in (("positional", ["foo"]), ("positional_after_options", ["--port", "8765", "foo"]),
                     ("unknown_option", ["--bogus", "1"]), ("help", ["--help"]), ("port_without_value", ["--port"]),
                     ("work_without_value", ["--work"]), ("mods_without_value", ["--mods"]), ("bind_without_value", ["--bind"])):
    setattr(TestCli, "test_usage_" + _name, usage_case(_name, _argv))


class TestCliRuntimeErrors(unittest.TestCase):
    def run_server(self, *argv):
        with tmp() as d:
            return run_tool("tuner_server.py", *argv, cwd=d)

    def test_a_port_below_1024_is_an_error_line_on_stderr_with_exit_1(self):
        r = self.run_server("--port", "80")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (1, "", "error: --port must be a number from 1024 to 65535\n"))

    def test_a_bad_port_is_an_error_line_on_stderr_with_exit_1(self):
        for port in ("abc", "0", "70000", "-1"):
            with self.subTest(port):
                r = self.run_server("--port", port)
                self.assertEqual((r.returncode, r.stdout), (1, ""))
                self.assertRegex(r.stderr, r"^error: --port must be a number from \d+ to 65535\n$")

    def test_an_unexpandable_work_folder_is_an_error_line_on_stderr_with_exit_1(self):
        r = self.run_server("--work", "%ACE_TEST_NO_SUCH_VAR%/w")
        self.assertEqual((r.returncode, r.stdout), (1, ""))
        self.assertTrue(r.stderr.startswith("error: cannot expand the work directory"), r.stderr)


class TestUsageText(unittest.TestCase):
    def test_usage_block_is_the_first_paragraph_after_the_title(self):
        self.assertEqual(len(ts.__doc__.split("\n\n")[0].splitlines()), 1)
        self.assertTrue(USAGE.startswith("usage:\n  python tools/tuner_server.py [--port N]"), USAGE)
        self.assertIn("[--bind <address>]", USAGE)

    def test_the_documented_defaults_match_the_code(self):
        self.assertIn("default port 8080", ts.__doc__)
        self.assertEqual(ts.DEFAULT_PORT, 8080)
        self.assertIn("--bind <address> (default 0.0.0.0", ts.__doc__)
        self.assertIn("http://127.0.0.1:<port>/ACESCT/", ts.__doc__)
        self.assertIn("http://<address of the PC>:<port>/ACESCT/", ts.__doc__)
        self.assertIn("fixed base path " + ts.BASE_PATH, ts.__doc__)

    def test_the_documented_checks_are_the_ones_of_the_code(self):
        doc = " ".join(ts.__doc__.split())
        for text in ("client is not loopback or private", "or the host name of this PC", "(301)", "(302)"):
            self.assertIn(text, doc)

    def test_every_documented_route_exists(self):
        for route in re.findall(r"^  (?:GET|POST) +(/api/\w+)", ts.__doc__, re.M):
            self.assertIn(route, list(ts.GET_ROUTES) + list(ts.POST_ROUTES))
        for route in re.findall(r"POST (/api/\w+)", ts.__doc__):
            self.assertIn(route, ts.POST_ROUTES)
        for route in list(ts.GET_ROUTES) + list(ts.POST_ROUTES):
            self.assertIn(route, ts.__doc__)


if __name__ == "__main__":
    unittest.main()
