"""Static checks of tuner/web/index.html and tuner/start_tuner.bat with regular expressions only (no browser, no node).

The page is cut once into markup, <style> and <script>; the tests compare the three with each other (DOM ids, CSS classes, functions) and with tools/tuner_server.py (routes, header names, answer fields). The JS helpers are plain regexes: strings, comments and braces are only handled as far as this one file needs.
"""
import inspect
import re
import unittest

from support import ROOT

import tuner_server as ts

HTML = (ROOT / "tuner" / "web" / "index.html").read_text(encoding="utf-8")
BAT = (ROOT / "tuner" / "start_tuner.bat").read_text(encoding="ascii")
README = (ROOT / "README.md").read_text(encoding="utf-8")
STYLE = re.search(r"<style>(.*?)</style>", HTML, re.S).group(1)
SCRIPT = re.search(r"<script>(.*?)</script>", HTML, re.S).group(1)
MARKUP = re.sub(r"<style>.*?</style>|<script>.*?</script>", "", HTML, flags=re.S)
CODE = re.sub(r"(?m)^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", SCRIPT, flags=re.S))
TITLE = "ACE - Simple Car Tuner"
# classes the script sets through a variable (addStat(.., "bad"), setMsg(.., "err")), not as a literal next to el() / classList
DYNAMIC_CLASSES = {"ok", "bad", "warn", "err"}


def function_body(name):
    """The text between the braces of a top-level function of the script (braces inside strings are not handled)."""
    m = re.search(r"(?:async )?function %s\([^)]*\) \{" % name, CODE)
    assert m, "no function %s in the script" % name
    depth, i = 1, m.end()
    while depth:
        depth += (CODE[i] == "{") - (CODE[i] == "}")
        i += 1
    return CODE[m.end():i - 1]


def dom_ids():
    return re.findall(r'\bid="([^"]+)"', MARKUP)


def referenced_ids():
    ids = set(re.findall(r"""\$\(\s*["']([^"']+)["']\s*\)""", CODE))
    ids |= set(re.findall(r"""getElementById\(\s*["']([^"']+)["']\s*\)""", CODE))
    ids |= set(re.findall(r"""querySelector(?:All)?\(\s*["']#([\w-]+)""", CODE))
    for array in re.findall(r"for \(const id of \[([^\]]*)\]", CODE):
        ids |= set(re.findall(r'"([^"]+)"', array))
    return ids


def css_classes():
    rules = STYLE
    while re.search(r"\{[^{}]*\}", rules):
        rules = re.sub(r"\{[^{}]*\}", " ", rules)
    return set(re.findall(r"\.([A-Za-z][\w-]*)", rules))


def used_classes():
    used = set()
    for m in re.finditer(r'\bclass="([^"]+)"', MARKUP):
        used |= set(m.group(1).split())
    for m in re.finditer(r'\bel\("[a-z0-9]+",\s*"([^"]*)"', CODE):
        used |= set(m.group(1).split())
    for m in re.finditer(r'classList\.(?:add|remove|toggle)\("([^"]+)"', CODE):
        used.add(m.group(1))
    for m in re.finditer(r'className = "([^"]+)"', CODE):
        used |= set(m.group(1).split())
    return used


def quoted_words(*objects):
    return {w for o in objects for w in re.findall(r'"(\w+)"', inspect.getsource(o))}


class TestStructure(unittest.TestCase):
    def test_the_file_is_cut_into_one_style_and_one_script(self):
        self.assertEqual(HTML.count("<style>"), 1)
        self.assertEqual(HTML.count("<script>"), 1)
        self.assertTrue(len(STYLE) > 1000 and len(SCRIPT) > 5000)
        self.assertNotIn("<script", MARKUP)

    def test_it_is_a_html5_page_in_english_with_a_viewport(self):
        self.assertTrue(HTML.startswith("<!DOCTYPE html>\n<html lang=\"en\">"))
        self.assertIn('<meta charset="utf-8">', HTML)
        self.assertIn('<meta name="viewport" content="width=device-width, initial-scale=1">', HTML)

    def test_the_page_is_ascii_only(self):
        HTML.encode("ascii")

    def test_the_page_loads_nothing_from_outside(self):
        self.assertEqual(re.findall(r"https?://", HTML), [])
        self.assertEqual(re.findall(r"\b(?:src|href)=", MARKUP), [])
        self.assertEqual(re.findall(r"<link|@import|url\(", HTML), [])

    def test_brackets_of_the_script_balance(self):
        code = re.sub(r'"(?:[^"\\\n]|\\.)*"', '""', CODE)
        for opening, closing in ("()", "[]", "{}"):
            self.assertEqual(code.count(opening), code.count(closing), opening + closing)

    def test_all_dom_ids_are_unique(self):
        ids = dom_ids()
        self.assertEqual(len(ids), len(set(ids)))


class TestDomIds(unittest.TestCase):
    def test_every_id_the_script_looks_up_exists_in_the_markup(self):
        self.assertEqual(sorted(referenced_ids() - set(dom_ids())), [])

    def test_the_script_looks_up_a_known_set_of_ids(self):
        self.assertTrue({"status", "progress", "init-panel", "tuner", "rows", "car-select", "btn-apply", "btn-copy", "btn-init",
                         "btn-reset-all", "search", "changed-only", "name-host", "untested", "caption", "empty", "init-text"}
                        <= referenced_ids(), sorted(referenced_ids()))

    # R4-026 found the h1 id "title" unused; it may go away, but no other id may be left without a reader
    def test_ids_nobody_references_are_only_the_known_ones(self):
        self.assertLessEqual(set(dom_ids()) - referenced_ids(), {"title"})


class TestFunctions(unittest.TestCase):
    def test_the_script_defines_the_functions_the_page_needs(self):
        names = set(re.findall(r"^(?:async )?function (\w+)", CODE, re.M))
        self.assertTrue({"api", "refresh", "renderStatus", "renderCars", "renderButtons", "renderProgress", "buildTable", "buildRow",
                         "loadSettings", "startJob", "resetAll", "switchCar", "applyFilter"} <= names, sorted(names))

    def test_every_function_is_referenced_at_least_once_besides_its_definition(self):
        for name in re.findall(r"^(?:async )?function (\w+)", CODE, re.M):
            with self.subTest(name):
                self.assertGreaterEqual(len(re.findall(r"\b%s\b" % name, CODE)), 2)

    def test_every_top_level_variable_is_used(self):
        for name in re.findall(r"^(?:let|const) (\w+)", CODE, re.M):
            with self.subTest(name):
                self.assertGreaterEqual(len(re.findall(r"(?<![\w$])%s(?![\w$])" % re.escape(name), CODE)), 2)

    def test_the_script_runs_in_strict_mode(self):
        self.assertTrue(CODE.lstrip().startswith('"use strict";'))


class TestNoInjectionSinks(unittest.TestCase):
    def test_no_html_is_ever_built_from_text(self):
        for sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval(", "new Function", "setTimeout(\"",
                     "setInterval(\"", "createContextualFragment", "srcdoc"):
            with self.subTest(sink):
                self.assertNotIn(sink, HTML)

    def test_no_inline_event_handlers_or_javascript_urls(self):
        self.assertEqual(re.findall(r"\son[a-z]+\s*=", MARKUP), [])
        self.assertNotIn("javascript:", HTML)

    def test_server_text_enters_the_page_as_text_only(self):
        self.assertIn("textContent", CODE)
        self.assertIn("createTextNode", CODE)


class TestApiContract(unittest.TestCase):
    ROUTES = list(ts.GET_ROUTES) + list(ts.POST_ROUTES)

    def test_the_script_has_one_fetch_call(self):
        self.assertEqual(len(re.findall(r"\bfetch\(", CODE)), 1)
        self.assertEqual(len(re.findall(r"XMLHttpRequest|WebSocket|sendBeacon", CODE)), 0)

    def test_every_api_path_in_the_script_is_a_route_of_the_server(self):
        paths = set(re.findall(r'"(/api/[^"?]*)"', CODE))
        self.assertTrue(paths)
        self.assertEqual(sorted(paths - set(self.ROUTES)), [])

    def test_every_route_of_the_server_is_called_by_the_page(self):
        paths = set(re.findall(r'"(/api/[^"?]*)"', CODE))
        self.assertEqual(sorted(set(self.ROUTES) - paths), [])

    def test_get_routes_are_called_without_a_body_and_post_routes_with_one(self):
        for route in ts.GET_ROUTES:
            with self.subTest(route):
                self.assertRegex(CODE, r'api\("%s", undefined' % route)
                self.assertNotRegex(CODE, r'(?:api|startJob)\("%s", \{' % route)
        for route in ts.POST_ROUTES:
            with self.subTest(route):
                self.assertRegex(CODE, r'(?:api|startJob)\("%s", \{' % route)
                self.assertNotRegex(CODE, r'api\("%s", undefined' % route)

    def test_the_page_sends_the_headers_the_server_demands(self):
        body = function_body("api")
        self.assertIn('"Content-Type": "application/json"', body)
        self.assertIn('"X-Tuner": "1"', body)
        self.assertIn('method: "POST"', body)

    def test_the_car_goes_in_the_query_of_a_get_and_in_the_body_of_a_post(self):
        body = function_body("api")
        self.assertIn('"?car=" + encodeURIComponent(car)', body)
        self.assertIn("{ car: car }", body)

    def test_the_apply_bodies_use_the_modes_of_the_server(self):
        modes = set(re.findall(r'mode: "(\w+)"', CODE))
        self.assertEqual(modes, set(ts.MODES))
        self.assertIn("new_id:", CODE)

    def test_the_state_fields_the_page_reads_are_sent_by_the_server(self):
        sent = quoted_words(ts.api_state, ts.installed_info) | set(ts.JOB)
        read = set(re.findall(r"\binfo\.(\w+)", CODE)) | set(re.findall(r"\binst\.(\w+)", CODE)) | set(re.findall(r"\bjob\.(\w+)", CODE))
        self.assertTrue({"base_present", "game_running", "job", "installed", "cars", "car", "work"} <= read, sorted(read))
        self.assertEqual(sorted(read - sent), [])

    def test_the_row_fields_the_page_reads_are_sent_by_the_server(self):
        sent = quoted_words(ts.row_json)
        read = set(re.findall(r"\b(?:data|d)\.(\w+)", CODE)) - {"error"}
        self.assertTrue({"id", "label", "type", "value", "default", "changed", "choices", "ui", "copy_values"} <= read, sorted(read))
        self.assertEqual(sorted(read - sent), [])

    def test_the_page_polls_in_the_documented_rhythm(self):
        consts = dict(re.findall(r"^const (\w+_MS) = (\d+);", CODE, re.M))
        poll_idle, poll_busy, debounce = (int(consts[k]) for k in ("POLL_IDLE_MS", "POLL_BUSY_MS", "DEBOUNCE_MS"))
        self.assertTrue(1000 <= poll_idle <= 60000, poll_idle)
        self.assertTrue(500 <= poll_busy < poll_idle, poll_busy)
        self.assertTrue(100 <= debounce <= 2000, debounce)
        self.assertIn("setTimeout(refresh, busy ? POLL_BUSY_MS : POLL_IDLE_MS)", CODE)

    def test_the_page_polls_faster_while_a_job_runs(self):
        self.assertIn('const busy = info && info.job.state === "running";', CODE)


class TestCssClasses(unittest.TestCase):
    def test_every_class_the_markup_and_script_use_has_a_css_rule(self):
        self.assertEqual(sorted((used_classes() | DYNAMIC_CLASSES) - css_classes()), [])

    def test_every_css_class_is_used_by_the_markup_or_the_script(self):
        self.assertEqual(sorted(css_classes() - used_classes() - DYNAMIC_CLASSES), [])

    def test_the_dynamic_classes_are_in_the_script_as_literals(self):
        for cls in DYNAMIC_CLASSES:
            with self.subTest(cls):
                self.assertIn('"%s"' % cls, CODE)

    def test_the_class_collectors_see_the_main_classes(self):
        self.assertTrue({"panel", "strip", "namerow", "mono", "badge", "amber", "reset", "changed", "valuewrap", "page", "sr-only"}
                        <= used_classes(), sorted(used_classes()))

    def test_every_css_custom_property_that_is_defined_is_used(self):
        defined = set(re.findall(r"(--[\w-]+):", STYLE))
        for name in sorted(defined):
            with self.subTest(name):
                self.assertIn("var(%s)" % name, STYLE)

    def test_every_custom_property_that_is_used_is_defined(self):
        self.assertEqual(sorted(set(re.findall(r"var\((--[\w-]+)\)", STYLE)) - set(re.findall(r"(--[\w-]+):", STYLE))), [])

    def test_the_dark_theme_only_redefines_properties_of_the_light_one(self):
        light_css, dark_css = STYLE.split("@media (prefers-color-scheme: dark)")[:2]
        light = set(re.findall(r"(--[\w-]+):", light_css))
        dark = set(re.findall(r"(--[\w-]+):", dark_css.split("* { box-sizing")[0]))
        self.assertTrue(dark and dark <= light, sorted(dark - light))


class TestTexts(unittest.TestCase):
    def test_the_title_and_the_heading_are_the_product_name(self):
        self.assertEqual(re.search(r"<title>(.*?)</title>", HTML).group(1), TITLE)
        self.assertEqual(re.search(r"<h1[^>]*>(.*?)</h1>", MARKUP).group(1), TITLE)

    def test_the_readme_uses_the_same_name(self):
        self.assertTrue(README.startswith("# " + TITLE), README[:60])

    def test_the_buttons_carry_the_labels_the_readme_names(self):
        for label in ("Apply (update my car)", "Save as new copy&hellip;", "Extract stock car (one time, ~20 s)", "Reset all"):
            with self.subTest(label):
                self.assertIn(">%s</button>" % label, MARKUP)
        self.assertIn("changed only", MARKUP)
        self.assertIn('el("button", "reset", "reset")', CODE)
        for label in ("Apply (update my car)", "Save as new copy", "Extract stock car", "changed only", "reset", "Reset all"):
            self.assertIn(label, README)

    def test_the_table_has_the_four_documented_columns_in_order(self):
        heads = re.findall(r'<th scope="col">(.*?)</th>', MARKUP)
        self.assertEqual(heads, ["Variable name", "Value", "Default (for the selected car)", "Description"])

    def test_the_prompt_tells_the_id_rules_of_the_server(self):
        self.assertIn("only lowercase a-z, 0-9 and _", CODE)
        self.assertIn("info.stock_id_length", CODE)


class TestAccessibility(unittest.TestCase):
    def test_the_controls_have_accessible_names(self):
        self.assertIn('<select id="car-select" aria-label="Car"', MARKUP)
        self.assertIn('aria-label="Search settings"', MARKUP)
        self.assertIn('setAttribute("aria-label", "Value of " + d.label)', CODE)
        self.assertIn('<caption id="caption" class="sr-only">', MARKUP)

    def test_status_and_row_messages_are_live_regions(self):
        self.assertIn('id="status" class="strip" role="status" aria-live="polite"', MARKUP)
        self.assertIn('id="progress"', MARKUP)
        self.assertEqual(CODE.count('setAttribute("role", "alert")'), 2)

    def test_keyboard_focus_is_visible_and_the_hidden_attribute_wins(self):
        self.assertIn("button:focus-visible, input:focus-visible, select:focus-visible", STYLE)
        self.assertIn("[hidden] { display: none !important; }", STYLE)

    def test_the_page_follows_the_system_colour_scheme(self):
        self.assertIn("color-scheme: light dark;", STYLE)
        self.assertIn("@media (prefers-color-scheme: dark)", STYLE)

    # R4-021: renderStatus rebuilds the aria-live strip at every poll; it should return early when nothing changed like renderCars / renderProgress
    @unittest.expectedFailure
    def test_render_status_skips_the_rebuild_when_nothing_changed(self):
        body = function_body("renderStatus")
        guard = re.search(r"if \(sig === \w+\) return;", body)
        self.assertIsNotNone(guard, "renderStatus has no signature guard")
        self.assertLess(guard.start(), body.index("replaceChildren"))

    def test_render_cars_and_render_progress_have_the_signature_guard(self):
        self.assertIn("if (sig === carsSig) return;", function_body("renderCars"))
        self.assertIn("if (sig === jobSig) return;", function_body("renderProgress"))

    # R4-024: the "unverified" and "copies differ" badges explain themselves in a title only, a screen reader and touch users never get it
    @unittest.expectedFailure
    def test_the_badges_have_text_for_screen_readers(self):
        body = function_body("buildRow")
        self.assertEqual(body.count('"badge'), 2)
        self.assertGreaterEqual(body.count('"sr-only"'), 2)

    # R4-024: the suggested range of a value field is a title only
    @unittest.expectedFailure
    def test_the_suggested_range_is_available_to_screen_readers(self):
        self.assertIn('setAttribute("aria-description"', function_body("buildField"))


class TestErrorHandling(unittest.TestCase):
    def test_a_failed_job_start_or_reset_shows_the_error(self):
        self.assertIn("localError = e.message;", function_body("startJob"))
        self.assertIn("localError = e.message;", function_body("resetAll"))
        self.assertIn("localError = e.message;", function_body("loadSettings"))

    def test_a_new_job_and_a_car_switch_clear_the_old_error(self):
        self.assertIn('localError = "";', function_body("startJob"))
        self.assertIn('localError = "";', function_body("switchCar"))

    # R4-020: a failed settings load shows the red panel; the next poll loads the table but the error stays on screen
    @unittest.expectedFailure
    def test_a_successful_settings_load_clears_the_old_error(self):
        body = function_body("loadSettings")
        success = body.index("tableLoaded = true;")
        self.assertIn('localError = "";', body[success:])

    def test_a_failing_api_call_becomes_an_error_with_the_server_text(self):
        body = function_body("api")
        self.assertIn('throw new Error("server not reachable")', body)
        self.assertIn("data.error", body)
        self.assertIn('"HTTP " + res.status', body)


class TestStartBat(unittest.TestCase):
    def test_it_starts_the_server_script_of_the_repo_from_the_repo_root(self):
        self.assertIn(r'tools\tuner_server.py', BAT)
        self.assertTrue((ROOT / "tools" / "tuner_server.py").is_file())
        self.assertIn(r'cd /d "%~dp0.."', BAT)
        self.assertEqual((ROOT / "tuner" / "start_tuner.bat").parent.parent, ROOT)

    def test_paths_are_relative_to_the_batch_file(self):
        self.assertIn("%~dp0", BAT)
        self.assertNotRegex(BAT, r"(?i)\b[a-z]:\\users\\")

    def test_python_runs_isolated_with_the_documented_port_flag(self):
        self.assertRegex(BAT, r'"%PY%" -I tools\\tuner_server\.py --port \d+')
        self.assertIn("--port", ts.__doc__)

    def test_the_port_is_the_default_port_of_the_server_and_the_readme(self):
        self.assertEqual(set(re.findall(r"(?:--port |127\.0\.0\.1:|PORT=)(\d+)", BAT)), {str(ts.DEFAULT_PORT)})
        self.assertIn("http://127.0.0.1:%d/" % ts.DEFAULT_PORT, README)

    def test_it_looks_for_the_python_the_readme_documents(self):
        path = re.search(r'set "PY=(.*?python\.exe)"', BAT).group(1)
        self.assertEqual(path, r"%LOCALAPPDATA%\Programs\Python\Python312\python.exe")
        self.assertIn(path.rsplit("\\", 1)[0] + "\\", README)

    def test_a_missing_python_stops_with_a_message_and_exit_code_1(self):
        self.assertIn('if not exist "%PY%" (', BAT)
        self.assertIn("exit /b 1", BAT)
        self.assertIn("pause", BAT)

    # R4-006: the browser is opened after a fixed delay (ping -n 3 is about 2 s), not when the server listens
    def test_the_browser_is_opened_after_a_fixed_two_second_delay(self):
        self.assertRegex(BAT, r'start "" /min cmd /c "ping -n 3 127\.0\.0\.1 >nul & start http://127\.0\.0\.1:\d+/"')

    def test_the_file_is_plain_ascii_without_a_byte_order_mark(self):
        raw = (ROOT / "tuner" / "start_tuner.bat").read_bytes()
        raw.decode("ascii")
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
