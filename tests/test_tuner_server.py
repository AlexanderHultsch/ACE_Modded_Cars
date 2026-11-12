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
import sys
import threading
import time
import unittest
from unittest import mock

from support import FakeCar, mini_catalogue, mini_setting, run_tool, tmp

import clone_car
import tune
import tuner_server as ts

USAGE = ts.__doc__.split("\n\n")[1]
REAL_GAME_RUNNING = ts.game_running
GAME_ARGV = ["tasklist", "/FI", "IMAGENAME eq AssettoCorsaEVO.exe", "/NH", "/FO", "CSV"]
STATE_KEYS = {"work", "car", "default_car", "cars", "base_present", "game_running", "installed", "stock_id_length",
              "default_new_id", "settings_applicable", "settings_hidden", "job"}
CAR_KEYS = {"id", "label", "display_name", "extracted", "tested", "new_id", "installed"}
JOB_KEYS = {"kind", "state", "log", "result", "error"}
ROW_KEYS = {"id", "group", "label", "kind", "type", "unit", "description", "verified", "default", "value", "changed",
            "absent", "copies_differ"}
INIT_RESULT = {"present": False, "dir": "/w/ks_x/base/content/cars/ks_x", "files": 3, "dirs": 1, "bytes": 10}
APPLY_RESULT = {"new_id": "ax_x", "build_dir": "/w/ks_x/build/ax_x", "package": "/w/ks_x/build/ax_x/ax_x.kspkg", "size": 7,
                "applied": [{"id": "limiter", "old": 7000, "new": 8000, "files": ["data/engine.carengine", "data/x.car"]}],
                "notes": ["note: from build"], "installed": "/m/ax_x.kspkg", "backup": None}


def limiter():
    return mini_setting("limiter", type="int", min=3000, max=12000, targets=[("@engine", "limiter"), ("@car", "engine.limiter", True)])


def aids_off():
    return mini_setting("aids_off", kind="flag", type="bool", value=0, targets=[("@setup", "electronics.tc1")])


def suffix():
    return mini_setting("name_suffix", kind="meta", type="string", default="_MY", handler="name_suffix", ui="header")


def boost():
    return mini_setting("boost", type="float", targets=[("@turbo[0]", "max_boost")])


def gated(test, fn):
    """A job body for tune.init / tune.apply: records the call, waits for test.gate when one is set, then returns or raises."""
    def stub(*args, **kw):
        test.calls.append((fn, args, kw))
        test.entered.set()
        if test.gate is not None:
            test.gate.wait(10)
        if test.errors.get(fn):
            raise test.errors[fn]
        return dict(INIT_RESULT if fn == "init" else APPLY_RESULT)
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

    def setUp(self):
        super().setUp()
        self.fc = FakeCar(self.work, "ks_x").install(self)
        index = [{"id": "ks_x", "display_name": "Car X", "brand": "B", "year": 1999},
                 {"id": "ks_y", "display_name": "Car Y", "brand": "B", "year": 2000}]
        self.write(os.path.join(self.work, "cars_index.json"), index)
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), ts.Handler)
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

    def request(self, method, path, body=None, host=None, headers=None, post_headers=True):
        """One request on a new connection; host=False sends no Host header, a headers value of None drops that header."""
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
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
        self.assertEqual(sorted(ts.GET_ROUTES), ["/api/settings", "/api/state"])
        self.assertEqual(sorted(ts.POST_ROUTES), ["/api/apply", "/api/init", "/api/reset_all", "/api/set", "/api/unset"])
        self.assertEqual(ts.ACCEPTED, ("/api/init", "/api/apply"))

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
        a = self.post("/api/apply", {"mode": "update"})
        self.assertEqual((a.status, a.json), (202, {"job": "started"}))

    def test_unknown_paths_are_404_json(self):
        for path in ("/api/nothing", "/index.html", "/api/state/", "/favicon.ico", "/api/set", "/api"):
            with self.subTest(path):
                r = self.get(path)
                self.assertEqual((r.status, r.json), (404, {"error": "not found"}))

    def test_a_get_route_is_not_a_post_route_and_back(self):
        self.assertEqual(self.post("/api/state").status, 404)
        self.assertEqual(self.post("/").status, 404)
        self.assertEqual(self.get("/api/reset_all").status, 404)

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
        def boom(car):
            raise RuntimeError("secret detail")
        with mock.patch.dict(ts.GET_ROUTES, {"/api/state": boom}):
            r = self.get("/api/state")
        self.assertEqual((r.status, r.json), (500, {"error": "internal error: RuntimeError"}))
        self.assertIn("RuntimeError: secret detail", self.err.getvalue())

    def test_value_and_os_errors_are_a_500_with_their_text(self):
        for exc in (ValueError("bad stock info"), OSError("disk gone")):
            def boom(car, exc=exc):
                raise exc
            with self.subTest(type(exc).__name__), mock.patch.dict(ts.GET_ROUTES, {"/api/state": boom}):
                r = self.get("/api/state")
                self.assertEqual((r.status, r.json), (500, {"error": str(exc)}))


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
        self.assertEqual(self.post("/api/apply", {"mode": "bad"}).status, 400)
        self.assertEqual(self.post("/api/apply", {"mode": "new_copy", "new_id": "../../x"}).status, 400)

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
class TestApplyRoute(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_the_mode_must_be_update_or_new_copy(self):
        for body in ({}, {"mode": "bad"}, {"mode": None}, {"mode": 5}, {"mode": ["update"]}, {"mode": "UPDATE"}, {"mode": ""}):
            with self.subTest(body):
                r = self.post("/api/apply", body)
                self.assertEqual((r.status, r.json), (400, {"error": 'mode must be "update" or "new_copy"'}))
        self.assertEqual(self.calls, [])

    def test_new_copy_needs_a_new_id(self):
        for body in ({"mode": "new_copy"}, {"mode": "new_copy", "new_id": ""}, {"mode": "new_copy", "new_id": None},
                     {"mode": "new_copy", "new_id": 5}, {"mode": "new_copy", "new_id": ["ax_y"]}):
            with self.subTest(body):
                r = self.post("/api/apply", body)
                self.assertEqual((r.status, r.json), (400, {"error": "new_id is required for mode new_copy"}))

    def test_a_new_id_that_is_not_a_plain_same_length_id_is_400(self):
        for new_id in ("../../x", "../x", "AX_Y", "ax y", "ax_yy", "ax", "ax-y", "ax_\u00e9", "ax/y", "a\x00b_"):
            with self.subTest(new_id):
                r = self.post("/api/apply", {"mode": "new_copy", "new_id": new_id})
                self.assertEqual(r.status, 400, r.json)
        self.assertEqual(self.calls, [])
        self.assertEqual(ts.job_snapshot()["state"], "idle")

    def test_the_stock_id_and_the_update_id_are_refused_as_new_ids(self):
        stock = self.post("/api/apply", {"mode": "new_copy", "new_id": "ks_x"})
        self.assertEqual((stock.status, stock.json["error"]), (400, "new id equals the old id 'ks_x'"))
        update = self.post("/api/apply", {"mode": "new_copy", "new_id": "ax_x"})
        self.assertEqual((update.status, update.json["error"]),
                         (400, "new id equals ax_x, the id used by Apply (update), pick another one"))

    def test_update_builds_the_default_new_id_and_installs(self):
        r = self.post("/api/apply", {"mode": "update"})
        self.assertEqual((r.status, r.json), (202, {"job": "started"}))
        snap = self.wait_job()
        self.assertEqual(self.calls, [("apply", (self.work, "ks_x", "ax_x", True, self.mods), {"game": os.path.expandvars(tune.DEFAULT_GAME)})])
        self.assertEqual((snap["kind"], snap["state"], snap["error"]), ("apply", "done", None))
        self.assertEqual(snap["result"], dict(APPLY_RESULT, mode="update"))

    def test_new_copy_builds_the_given_id(self):
        r = self.post("/api/apply", {"mode": "new_copy", "new_id": "ax_y"})
        self.assertEqual(r.status, 202)
        snap = self.wait_job()
        self.assertEqual(self.calls, [("apply", (self.work, "ks_x", "ax_y", True, self.mods), {"game": os.path.expandvars(tune.DEFAULT_GAME)})])
        self.assertEqual(snap["result"]["mode"], "new_copy")

    def test_update_ignores_a_new_id_in_the_body(self):
        self.post("/api/apply", {"mode": "update", "new_id": "../../x"})
        self.wait_job()
        self.assertEqual(self.calls[0][1][2], "ax_x")

    def test_the_apply_log_has_the_build_line_and_the_result_lines(self):
        self.post("/api/apply", {"mode": "update"})
        self.assertEqual(self.wait_job()["log"], [
            "building ax_x (update), this takes a while ...", "applied 1 setting(s)",
            "  limiter: 7000 -> 8000  [data/engine.carengine, data/x.car]", "note: from build",
            "package: /w/ks_x/build/ax_x/ax_x.kspkg (7 bytes)", "installed: /m/ax_x.kspkg", "backup: no previous install"])

    def test_apply_is_refused_while_the_game_runs(self):
        self.game_up = True
        r = self.post("/api/apply", {"mode": "update"})
        self.assertEqual((r.status, r.json), (409, {"error": "close the game first, AssettoCorsaEVO.exe is running"}))
        self.assertEqual((self.calls, ts.job_snapshot()["state"]), ([], "idle"))
        self.assertEqual(self.post("/api/apply", {"mode": "new_copy", "new_id": "ax_y"}).status, 409)

    def test_apply_is_allowed_again_once_the_game_is_closed(self):
        self.game_up = True
        self.post("/api/apply", {"mode": "update"})
        self.game_up = False
        self.assertEqual(self.post("/api/apply", {"mode": "update"}).status, 202)

    def test_the_configured_game_package_reaches_tune_apply(self):
        ts.CONFIG["game"] = "other.kspkg"
        self.post("/api/apply", {"mode": "update"})
        self.wait_job()
        args, kw = self.calls[0][1:]
        self.assertIn("other.kspkg", list(args) + list(kw.values()))

    def test_an_unexpandable_mods_folder_is_a_409_and_starts_no_job(self):
        ts.CONFIG["mods"] = "%ACE_TEST_NO_SUCH_VAR%/m"
        r = self.post("/api/apply", {"mode": "update"})
        self.assertEqual((r.status, r.json), (409, {"error": "cannot expand the mods folder '%ACE_TEST_NO_SUCH_VAR%/m'"}))
        self.assertEqual((self.calls, ts.job_snapshot()["state"]), ([], "idle"))

    def test_a_failing_apply_ends_in_the_error_state(self):
        self.errors["apply"] = ValueError("no base car in x, run init first")
        self.assertEqual(self.post("/api/apply", {"mode": "update"}).status, 202)
        snap = self.wait_job()
        self.assertEqual((snap["state"], snap["error"], snap["result"]), ("error", "no base car in x, run init first", None))
        self.assertEqual(snap["log"][-1], "error: no base car in x, run init first")


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


# -------------------------------------------------------------------------------------------------- job lifecycle
class TestJobs(ServerCase):
    def setUp(self):
        super().setUp()
        self.make_car()

    def test_a_second_job_while_one_runs_is_409_for_init_and_apply(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/init").status, 202)
        self.entered.wait(5)
        for path, body in (("/api/init", {}), ("/api/apply", {"mode": "update"}), ("/api/apply", {"mode": "new_copy", "new_id": "ax_y"})):
            with self.subTest(path, body=body):
                r = self.post(path, body)
                self.assertEqual((r.status, r.json), (409, {"error": "another job is running, wait until it has finished"}))
        self.assertEqual([c[0] for c in self.calls], ["init"])
        self.finish_held_job()

    def test_a_job_that_is_running_shows_in_the_state(self):
        self.hold_jobs()
        self.post("/api/apply", {"mode": "update"})
        self.entered.wait(5)
        job = self.get("/api/state").json["job"]
        self.assertEqual(set(job), JOB_KEYS)
        self.assertEqual((job["kind"], job["state"], job["result"], job["error"]), ("apply", "running", None, None))
        self.assertEqual(job["log"], ["building ax_x (update), this takes a while ..."])
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
        self.post("/api/apply", {"mode": "update"})
        job = ts.job_snapshot()
        self.assertEqual((job["kind"], job["state"], job["result"], job["error"]), ("apply", "running", None, None))
        self.assertNotIn("extracted the stock car", job["log"])
        self.finish_held_job()

    def test_a_failed_job_does_not_block_the_next_one(self):
        self.errors["init"] = ValueError("x")
        self.post("/api/init")
        self.assertEqual(self.wait_job()["state"], "error")
        self.assertEqual(self.post("/api/apply", {"mode": "update"}).status, 202)

    def test_the_game_check_is_not_used_by_init(self):
        self.game_up = True
        self.assertEqual(self.post("/api/init").status, 202)

    def test_set_is_refused_while_a_job_runs(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/apply", {"mode": "update"}).status, 202)
        r = self.post("/api/set", {"id": "limiter", "value": "8000"})
        self.assertEqual(r.status, 409, r.json)

    def test_unset_is_refused_while_a_job_runs(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/apply", {"mode": "update"}).status, 202)
        r = self.post("/api/unset", {"id": "limiter"})
        self.assertEqual(r.status, 409, r.json)

    def test_reset_all_is_refused_while_a_job_runs(self):
        self.hold_jobs()
        self.assertEqual(self.post("/api/apply", {"mode": "update"}).status, 202)
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
        self.assertIn('"GET /api/settings HTTP/1.1" 200 -', log)
        self.assertIn('"GET /nothing HTTP/1.1" 404 -', log)

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
        self.assertEqual(self.post("/api/apply", {"mode": "update"}).status, 202)
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

    def test_check_new_id(self):
        self.assertEqual(ts.check_new_id("ax_y", "ks_x", self.work), "ax_y")
        for bad, text in ((None, "new_id is required"), ("", "new_id is required"), (7, "new_id is required"),
                          ("ax_x", "new id equals ax_x"), ("ks_x", "new id equals the old id"), ("ax_yy", "must have exactly 4"),
                          ("AX_Y", "may only contain lowercase"), ("../x", "may only contain lowercase")):
            with self.subTest(bad), self.assertRaises(ts.ApiError) as cm:
                ts.check_new_id(bad, "ks_x", self.work)
            self.assertEqual(cm.exception.status, 400)
            self.assertIn(text.replace("must have exactly 4", "it must have exactly 4"), cm.exception.message)

    def test_check_new_id_touches_no_file(self):
        ts.check_new_id("ax_y", "ks_x", self.work)
        self.assertFalse(os.path.exists(self.work))

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

    def test_row_json_adds_the_copy_values_only_when_the_copies_differ(self):
        row = {k: k for k in ROW_KEYS}
        row.update(copies_differ=True, copy_values=[{"target": "t", "value": 1}])
        out = ts.row_json(row, {})
        self.assertEqual((set(out), out["copy_values"]), (ROW_KEYS | {"copy_values"}, [{"target": "t", "value": 1}]))

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


class TestMain(Env):
    def setUp(self):
        super().setUp()
        StubServer.log, StubServer.serve_error, StubServer.bind_error = [], KeyboardInterrupt, None
        self.patch(ts, "Server", StubServer)
        self.patch(tune, "load_cars_index", lambda work, *a, **k: StubServer.log.append("index"))
        self.argv = ["--port", "8765", "--work", self.work, "--mods", self.mods]

    def run_main(self, *argv):
        """main() with the given arguments; returns what it exits with (None when it returns)."""
        with mock.patch.object(sys, "argv", ["tuner_server.py", *argv]):
            try:
                ts.main()
            except SystemExit as e:
                return e.code
        return None

    def test_start_binds_localhost_only_with_the_handler_and_prints_the_url(self):
        self.assertIsNone(self.run_main(*self.argv))
        self.assertEqual((StubServer.last.address, StubServer.last.handler), (("127.0.0.1", 8765), ts.Handler))
        self.assertEqual(self.out.getvalue(), "tuner running on http://127.0.0.1:8765/\nstopped\n")

    def test_start_sets_config_from_the_options(self):
        self.run_main(*self.argv)
        self.assertEqual((ts.CONFIG["port"], ts.CONFIG["work"], ts.CONFIG["mods"]), (8765, os.path.abspath(self.work), self.mods))

    def test_the_default_port_is_8765(self):
        self.run_main("--work", self.work)
        self.assertEqual((ts.DEFAULT_PORT, StubServer.last.address), (8765, ("127.0.0.1", 8765)))

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
        values = {"port": "8765", "work": self.work, "mods": self.mods, "game": "game.kspkg"}
        flags = re.findall(r"\[--(\w+) ", USAGE)
        self.assertTrue({"port", "work", "mods"} <= set(flags), flags)
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
                     ("work_without_value", ["--work"]), ("mods_without_value", ["--mods"])):
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

    def test_the_documented_defaults_match_the_code(self):
        self.assertIn("default port 8765", ts.__doc__)
        self.assertEqual(ts.DEFAULT_PORT, 8765)

    def test_every_documented_route_exists(self):
        for route in re.findall(r"^  (?:GET|POST) +(/api/\w+)", ts.__doc__, re.M):
            self.assertIn(route, list(ts.GET_ROUTES) + list(ts.POST_ROUTES))
        for route in re.findall(r"POST (/api/\w+)", ts.__doc__):
            self.assertIn(route, ts.POST_ROUTES)
        for route in list(ts.GET_ROUTES) + list(ts.POST_ROUTES):
            self.assertIn(route, ts.__doc__)


if __name__ == "__main__":
    unittest.main()
