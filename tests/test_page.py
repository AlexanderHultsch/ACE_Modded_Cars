"""Static checks of tuner/web/index.html and start_tuner.bat with regular expressions only (no browser, no node).

The page is cut once into markup, <style> and <script>; the tests compare the three with each other (DOM ids, CSS classes, functions) and with tools/tuner_server.py (routes, header names, answer fields). The JS helpers are plain regexes: strings, comments and braces are only handled as far as this one file needs.
"""
import inspect
import re
import unittest

from support import ROOT

import tuner_server as ts

HTML = (ROOT / "tuner" / "web" / "index.html").read_text(encoding="utf-8")
BAT = (ROOT / "start_tuner.bat").read_text(encoding="ascii")
README = (ROOT / "docs" / "README.md").read_text(encoding="utf-8")
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
        self.assertTrue({"status", "progress", "init-panel", "tuner", "rows", "car-select", "btn-apply", "btn-duplicate", "btn-init",
                         "btn-reset-all", "search", "changed-only", "name-host", "untested", "caption", "empty", "init-text",
                         "dialog", "dialog-title", "dialog-id", "dialog-suffix", "dialog-hint", "dialog-error", "dialog-ok",
                         "dialog-cancel"}
                        <= referenced_ids(), sorted(referenced_ids()))

    # R4-026: no id may be left without a reader
    def test_ids_nobody_references_are_only_the_known_ones(self):
        self.assertLessEqual(set(dom_ids()) - referenced_ids(), set())


class TestFunctions(unittest.TestCase):
    def test_the_script_defines_the_functions_the_page_needs(self):
        names = set(re.findall(r"^(?:async )?function (\w+)", CODE, re.M))
        self.assertTrue({"api", "refresh", "renderStatus", "renderCars", "renderButtons", "renderProgress", "buildTable", "buildRow",
                         "loadSettings", "startJob", "resetAll", "switchCar", "applyFilter", "openDialog", "closeDialog", "submitDialog",
                         "dialogKey"} <= names, sorted(names))

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


def called_paths():
    """The route paths the script writes as plain strings, plus the routes of ts.QUERY_ROUTES, which the script writes with their
    query string: "/api/tyre?id=" + encodeURIComponent(id). No other route may carry a query string."""
    paths = set(re.findall(r'"(/api/[^"?]*)"', CODE))
    return paths | {p for p in re.findall(r'"(/api/[^"?]*)\?id=" \+ encodeURIComponent\(', CODE) if p in ts.QUERY_ROUTES}


class TestApiContract(unittest.TestCase):
    ROUTES = list(ts.GET_ROUTES) + list(ts.POST_ROUTES)

    def test_the_script_has_one_fetch_call(self):
        self.assertEqual(len(re.findall(r"\bfetch\(", CODE)), 1)
        self.assertEqual(len(re.findall(r"XMLHttpRequest|WebSocket|sendBeacon", CODE)), 0)

    def test_every_api_path_in_the_script_is_a_route_of_the_server(self):
        paths = called_paths()
        self.assertTrue(paths)
        self.assertEqual(sorted(paths - set(self.ROUTES)), [])

    def test_every_route_of_the_server_is_called_by_the_page(self):
        self.assertEqual(sorted(set(self.ROUTES) - called_paths()), [])

    def test_get_routes_are_called_without_a_body_and_post_routes_with_one(self):
        for route in (r for r in ts.GET_ROUTES if r in self.ROUTES and r not in ts.QUERY_ROUTES):
            with self.subTest(route):
                self.assertRegex(CODE, r'api\("%s", undefined' % route)
                self.assertNotRegex(CODE, r'(?:api|startJob)\("%s", \{' % route)
        # a GET route with a query string carries the id of the tyre there and still has no body
        for route in ts.QUERY_ROUTES:
            with self.subTest(route):
                self.assertRegex(CODE, r'api\("%s\?id=" \+ encodeURIComponent\(\w+\), undefined, selection\)' % route)
                self.assertNotRegex(CODE, r'(?:api|startJob)\("%s"' % route)
                self.assertNotRegex(CODE, r'(?:api|startJob)\("%s\?id=[^)]*, \{' % route)
        for route in (r for r in ts.POST_ROUTES if r in self.ROUTES):
            with self.subTest(route):
                self.assertRegex(CODE, r'(?:api|startJob)\("%s", \{' % route)
                self.assertNotRegex(CODE, r'api\("%s", undefined' % route)

    def test_api_requests_are_relative_to_the_page_below_the_base_path(self):
        self.assertIn('res = await fetch(path.replace(/^\//, ""), opts);', function_body("api"))
        self.assertEqual(re.findall(r"\bfetch\((\w+)", CODE), ["path"])
        self.assertEqual(re.findall(r"\b(?:href|src|action)\s*=|EventSource|location\.|window\.open|<(?:a|link|img|form|iframe)\b", HTML), [])

    def test_the_page_sends_the_headers_the_server_demands(self):
        body = function_body("api")
        self.assertIn('"Content-Type": "application/json"', body)
        self.assertIn('"X-Tuner": "1"', body)
        self.assertIn('method: "POST"', body)

    def test_the_car_and_the_tune_go_in_the_query_of_a_get_and_in_the_body_of_a_post(self):
        body = function_body("api")
        self.assertIn('"car=" + encodeURIComponent(target.car)', body)
        self.assertIn('"tune=" + encodeURIComponent(target.tune)', body)
        self.assertIn("{ car: target.car, tune: target.tune }", body)

    def test_every_api_call_of_the_page_passes_the_selection_which_carries_the_tune(self):
        calls = re.findall(r"await api\((.*)\);$", CODE, re.M)
        self.assertEqual(len(calls), 21, calls)
        for call in calls:
            with self.subTest(call):
                self.assertRegex(call, r", (?:want|target|r\.target|selection)$")
        plain = set(re.findall(r'\b(?:api|startJob)\("(/api/[a-z_]+)"', CODE))
        queried = {r for r in ts.QUERY_ROUTES if re.search(r'\bapi\("%s\?id=" \+ encodeURIComponent\(\w+\), undefined, selection\)' % r, CODE)}
        self.assertEqual(sorted(plain | queried), sorted(self.ROUTES))
        self.assertEqual(re.findall(r"async function api\((.*?)\) \{", CODE), ["path, body, target"])

    def test_the_bodies_of_apply_and_duplicate_use_the_fields_of_the_server(self):
        self.assertNotRegex(CODE, r"\bmode\b")
        self.assertEqual(re.findall(r'api\("/api/apply", (\{[^}]*\}), \w+\)', CODE), ["{ new_id: newId, suffix: suffix }"])
        self.assertEqual(re.findall(r'api\("/api/duplicate", (\{[^}]*\}), \w+\)', CODE), ["{ new_id: newId, suffix: suffix }"])
        self.assertIn('startJob("/api/apply", {})', CODE)
        sent = set(re.findall(r'"(\w+)"', inspect.getsource(ts.api_apply) + inspect.getsource(ts.api_duplicate)))
        self.assertTrue({"new_id", "suffix", "tune"} <= sent, sorted(sent))
        # an empty field sends nothing: undefined is dropped by JSON.stringify
        body = function_body("submitDialog")
        self.assertIn('const newId = $("dialog-id").value.trim() || undefined;', body)
        self.assertIn('const suffix = $("dialog-suffix").value || undefined;', body)

    def test_the_routes_of_the_page_are_the_routes_of_the_server(self):
        self.assertEqual(called_paths(), set(self.ROUTES))

    def test_the_state_fields_the_page_reads_are_sent_by_the_server(self):
        sent = quoted_words(ts.api_state, ts.installed_info, ts.modded_cars, ts.tune_proposals) | set(ts.JOB)
        read = set(re.findall(r"\binfo\.(\w+)", CODE)) | set(re.findall(r"\binst\.(\w+)", CODE)) | set(re.findall(r"\bjob\.(\w+)", CODE))
        self.assertTrue({"base_present", "game_running", "job", "installed", "cars", "car", "work", "tune", "modded", "modded_error",
                         "proposed_new_id", "proposed_suffix", "stock_id_length"} <= read, sorted(read))
        self.assertEqual(sorted(read - sent), [])

    def test_the_row_fields_the_page_reads_are_sent_by_the_server(self):
        # the rows of the tyre editor come from tune.tyre_rows: its quoted keys and its keyword arguments
        sent = quoted_words(ts.row_json, ts.tune.tyre_rows) | set(re.findall(r"\b(\w+)=", inspect.getsource(ts.tune.tyre_rows)))
        read = set(re.findall(r"\b(?:data|d)\.(\w+)", CODE)) - {"error"}
        self.assertTrue({"id", "label", "type", "value", "default", "changed", "choices", "ui", "copy_values", "axle", "applicable",
                         "reason"} <= read, sorted(read))
        self.assertEqual(sorted(read - sent), [])

    def test_the_page_polls_in_the_documented_rhythm(self):
        consts = dict(re.findall(r"^const (\w+_MS) = (\d+);", CODE, re.M))
        poll_idle, poll_busy, debounce = (int(consts[k]) for k in ("POLL_IDLE_MS", "POLL_BUSY_MS", "DEBOUNCE_MS"))
        self.assertTrue(1000 <= poll_idle <= 60000, poll_idle)
        self.assertTrue(500 <= poll_busy < poll_idle, poll_busy)
        self.assertTrue(100 <= debounce <= 2000, debounce)
        self.assertIn("setTimeout(refresh, document.hidden ? POLL_HIDDEN_MS : (busy ? POLL_BUSY_MS : POLL_IDLE_MS))", CODE)

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


class TestDarkTheme(unittest.TestCase):
    TOKENS = {"--color-bg": "#0e1013", "--color-bg-alt": "#16191f", "--color-bg-elevated": "#1c2028", "--color-text": "#e8eaed",
              "--color-text-muted": "#9aa1ac", "--color-border": "#2a2f38", "--color-accent": "#4f8cff",
              "--color-accent-contrast": "#0e1013"}
    ROOT_RULE = re.search(r":root \{(.*?)\n\}", STYLE, re.S).group(1)
    OUTSIDE_ROOT = STYLE.replace(ROOT_RULE, "")
    ALLOWED = {"transparent", "inherit", "currentColor", "none"}

    def test_the_tokens_of_the_site_are_defined_on_root_with_their_exact_values(self):
        for name, value in self.TOKENS.items():
            with self.subTest(name):
                self.assertRegex(self.ROOT_RULE, r"%s: %s;" % (re.escape(name), re.escape(value)))
        self.assertRegex(self.ROOT_RULE, r'--font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;')
        self.assertRegex(self.ROOT_RULE, r'--font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, "Liberation Mono", monospace;')

    def test_the_page_is_dark_only(self):
        self.assertIn("color-scheme: dark;", self.ROOT_RULE)
        self.assertNotIn("light", re.sub(r"color-scheme: dark;", "", STYLE))
        self.assertNotIn("prefers-color-scheme", STYLE)

    def test_colours_are_written_only_in_the_root_rule(self):
        self.assertEqual(re.findall(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?)\(", self.OUTSIDE_ROOT), [])

    def test_every_colour_and_background_value_is_a_token_or_on_the_allowed_list(self):
        found = re.findall(r"(?:^|[;{\s])((?:background|color|border(?:-[a-z]+)*-color|outline-color|accent-color))\s*:\s*([^;}]+)", self.OUTSIDE_ROOT)
        self.assertTrue(len(found) > 40, len(found))
        for prop, value in found:
            with self.subTest(prop + ": " + value):
                self.assertTrue(re.fullmatch(r"var\(--[\w-]+\)", value.strip()) or value.strip() in self.ALLOWED, value)

    def test_borders_and_outlines_use_tokens_for_their_colour(self):
        for prop, value in re.findall(r"(?:^|[;{\s])((?:border(?:-(?:top|right|bottom|left))?|outline)):\s*([^;}]+)", self.OUTSIDE_ROOT):
            with self.subTest(prop + ": " + value):
                self.assertRegex(value, r"^(?:0|none|\S+ solid (?:var\(--[\w-]+\)|currentColor))$")

    def test_the_font_stacks_come_from_the_tokens(self):
        self.assertIn("font: 15px/1.45 var(--font-sans);", STYLE)
        self.assertIn(".mono { font-family: var(--font-mono); }", STYLE)

    def test_the_primary_button_is_accent_filled_with_the_contrast_text(self):
        self.assertIn("button.primary { background: var(--color-accent); border-color: var(--color-accent); color: var(--color-accent-contrast); }", STYLE)

    def test_the_focus_ring_is_two_pixels_of_the_accent(self):
        self.assertIn("outline: 2px solid var(--color-accent); outline-offset: 1px;", STYLE)


class TestTexts(unittest.TestCase):
    def test_the_title_and_the_heading_are_the_product_name(self):
        self.assertEqual(re.search(r"<title>(.*?)</title>", HTML).group(1), TITLE)
        self.assertEqual(re.search(r"<h1[^>]*>(.*?)</h1>", MARKUP).group(1), TITLE)

    def test_the_readme_uses_the_same_name(self):
        self.assertTrue(README.startswith("# " + TITLE), README[:60])

    def test_the_buttons_carry_the_labels_the_readme_names(self):
        for label in ("Create modded car&hellip;", "Duplicate&hellip;", "Install car (pull game files)", "Reset all"):
            with self.subTest(label):
                self.assertIn(">%s</button>" % label, MARKUP)
        self.assertIn("changed only", MARKUP)
        self.assertIn('el("button", "reset", "reset")', CODE)
        for label in ("Install car (pull game files)", "Tyre Creator", "Garage tyres", "Expand all", "changed only",
                      "show advanced settings", "reset", "Reset all", "Create modded car", "Duplicate"):
            self.assertIn(label, README)

    def test_the_tables_have_the_documented_columns_in_order(self):
        heads = [h.replace("<br>", " ") for h in re.findall(r'<th scope="col">(.*?)</th>', MARKUP)]
        self.assertEqual(heads, ["Variable name", "Value", "Default (for the selected car)", "Range for base cars", "Description",
                                 "Variable name", "Value", "Default (source tyre)", "Description"])

    def test_both_default_headers_break_the_line_directly_before_the_opening_bracket(self):
        heads = re.findall(r'<th scope="col">(Default.*?)</th>', MARKUP)
        self.assertEqual(heads, ["Default<br>(for the selected car)", "Default<br>(source tyre)"])

    def test_the_dialog_tells_the_id_rules_of_the_server(self):
        body = function_body("openDialog")
        self.assertIn('"The id has exactly " + info.stock_id_length +', body)
        self.assertIn('" characters: lower case letters, digits, underscore"', body)


class TestAccessibility(unittest.TestCase):
    def test_the_controls_have_accessible_names(self):
        self.assertIn('<select id="car-select" aria-label="Car"', MARKUP)
        self.assertIn('aria-label="Search settings"', MARKUP)
        self.assertIn('setAttribute("aria-label", "Value of " + d.label)', CODE)
        self.assertIn('<caption id="caption" class="sr-only">', MARKUP)

    def test_status_and_row_messages_are_live_regions(self):
        self.assertIn('id="status" class="strip" role="status" aria-live="polite"', MARKUP)
        self.assertIn('id="progress"', MARKUP)
        self.assertEqual(CODE.count('setAttribute("role", "alert")'), 1)

    def test_keyboard_focus_is_visible_and_the_hidden_attribute_wins(self):
        self.assertIn("button:focus-visible, input:focus-visible, select:focus-visible", STYLE)
        self.assertIn("[hidden] { display: none !important; }", STYLE)

    def test_the_native_controls_follow_the_dark_theme(self):
        self.assertIn("color-scheme: dark;", STYLE)

    def test_render_status_skips_the_rebuild_when_nothing_changed(self):
        body = function_body("renderStatus")
        guard = re.search(r"if \(sig === \w+\) return;", body)
        self.assertIsNotNone(guard, "renderStatus has no signature guard")
        self.assertLess(guard.start(), body.index("replaceChildren"))

    def test_render_cars_and_render_progress_have_the_signature_guard(self):
        self.assertIn("if (sig === carsSig) return;", function_body("renderCars"))
        self.assertIn("if (sig === jobSig) return;", function_body("renderProgress"))

    def test_the_badges_have_text_for_screen_readers(self):
        body = function_body("buildRow")
        self.assertEqual(body.count('"badge'), 2)
        self.assertGreaterEqual(body.count('"sr-only"'), 2)

    def test_the_suggested_range_is_available_to_screen_readers(self):
        self.assertIn('setAttribute("aria-description"', function_body("buildField"))


class TestCollapsibleGroups(unittest.TestCase):
    def test_a_group_header_is_a_toggle_button_inside_the_rowgroup_cell(self):
        body = function_body("buildGroup")
        self.assertIn('th.scope = "rowgroup";', body)
        self.assertIn('el("button", "grouptoggle")', body)
        self.assertIn('g.btn.type = "button";', body)
        self.assertIn('g.btn.setAttribute("aria-expanded", "false");', body)
        self.assertIn('th.appendChild(g.btn);', body)
        self.assertIn('el("span", "gname", name)', body)
        self.assertIn('chev.setAttribute("aria-hidden", "true");', body)
        self.assertIn('g.btn.addEventListener("click", () => toggleGroup(g));', body)
        self.assertIn("buildGroup(data.group)", function_body("buildTable"))

    def test_the_toggle_controls_the_rows_of_its_group(self):
        body = function_body("buildTable")
        self.assertIn('r.tr.id = "row-" + rows.length;', body)
        self.assertIn('g.btn.setAttribute("aria-controls", g.rows.map((r) => r.tr.id).join(" "));', body)

    def test_the_chevron_is_css_only_and_rotates_with_aria_expanded(self):
        self.assertRegex(STYLE, r"\.chev \{[^}]*border-right: 2px solid currentColor; border-bottom: 2px solid currentColor;[^}]*transform: rotate\(-45deg\);")
        self.assertIn('.grouptoggle[aria-expanded="true"] .chev { transform: rotate(45deg); }', STYLE)
        self.assertIn("@media (prefers-reduced-motion: reduce)", STYLE)
        self.assertNotRegex(CODE, r"\\u25|&#x?2[0-9a-f]+;")

    def test_every_group_starts_collapsed(self):
        self.assertRegex(CODE, r"(?m)^const expanded = new Set\(\);")
        self.assertIn("expanded.has(g.name)", function_body("applyFilter"))
        self.assertNotRegex(CODE, r"expanded = new Set\([^)]")

    def test_toggling_flips_the_remembered_state_and_applies_it(self):
        body = function_body("toggleGroup")
        self.assertIn("if (!expanded.delete(g.name)) expanded.add(g.name);", body)
        self.assertIn("applyFilter();", body)

    def test_the_rows_of_a_collapsed_group_are_hidden_not_removed(self):
        body = function_body("applyFilter")
        self.assertIn("r.tr.hidden = !(open && r.match);", body)
        self.assertNotIn("remove(", body)

    def test_the_count_names_the_settings_and_the_changed_ones_and_follows_the_rows(self):
        body = function_body("applyFilter")
        self.assertIn('"(" + listed + (listed === 1 ? " setting, " : " settings, ") + changed + " changed)"', body)
        self.assertIn("if (r.data.changed && !unlisted) changed += 1;", body)
        self.assertIn("if (refilter) applyFilter();", function_body("showRow"))

    def test_the_expanded_state_is_kept_by_edits_polls_and_a_table_rebuild_and_cleared_by_a_switch(self):
        self.assertIn("expanded.clear();", function_body("switchCar"))
        for name in ("buildTable", "clearTable", "showRow", "refresh", "loadSettings", "resetAll", "sendSet"):
            with self.subTest(name):
                self.assertNotIn("expanded.clear()", function_body(name))
                self.assertNotIn("new Set", function_body(name))
        self.assertEqual(len(re.findall(r"expanded\.clear\(\)", CODE)), 2)

    def test_a_filter_opens_the_groups_with_matches_without_changing_the_remembered_state(self):
        body = function_body("applyFilter")
        self.assertIn('const filtering = q !== "" || changedOnly;', body)
        self.assertIn("const open = filtering ? any : expanded.has(g.name);", body)
        self.assertIn("g.tr.hidden = !any;", body)
        self.assertNotIn("expanded.add", body)
        self.assertNotIn("expanded.delete", body)
        self.assertIn('$("search").addEventListener("input", applyFilter);', CODE)
        self.assertIn('$("changed-only").addEventListener("change", applyFilter);', CODE)

    def test_the_filter_message_logic_is_unchanged(self):
        self.assertIn('$("empty").hidden = visible > 0 || rows.length === 0;', function_body("applyFilter"))
        self.assertIn("if (any) visible += 1;", function_body("applyFilter"))

    def test_expand_all_and_collapse_all_are_buttons_next_to_the_filters_and_wired(self):
        bar = re.search(r'<div class="toolbar">.*?</div>', MARKUP, re.S).group(0)
        self.assertRegex(bar, r'(?s)id="changed-only".*<button id="btn-expand-all" type="button">Expand all</button>\s*'
                              r'<button id="btn-collapse-all" type="button">Collapse all</button>\s*<span class="spacer">')
        self.assertIn('$("btn-expand-all").addEventListener("click", () => setAllGroups(true));', CODE)
        self.assertIn('$("btn-collapse-all").addEventListener("click", () => setAllGroups(false));', CODE)
        body = function_body("setAllGroups")
        self.assertIn("for (const g of groups) expanded.add(g.name);", body)
        self.assertIn("expanded.clear();", body)
        self.assertIn("applyFilter();", body)

    def test_a_message_in_a_row_opens_its_group(self):
        self.assertIn("if (text) revealGroup(r);", function_body("setMsg"))
        body = function_body("revealGroup")
        self.assertIn("groups.includes(r.group)", body)
        self.assertIn("expanded.add(r.group.name);", body)
        self.assertIn("applyFilter();", body)
        self.assertIn("r.group = current;", function_body("buildTable"))
        self.assertIn("group: null", function_body("newRow"))

    def test_the_toggles_announce_nothing_through_a_live_region(self):
        for name in ("buildGroup", "toggleGroup", "setAllGroups", "revealGroup", "applyFilter"):
            with self.subTest(name):
                self.assertNotIn("aria-live", function_body(name))
                self.assertNotIn("role", function_body(name))
        self.assertEqual(CODE.count('setAttribute("role", "alert")'), 1)

    def test_the_group_toggle_has_a_visible_focus_ring_inside_its_cell(self):
        self.assertIn("button.grouptoggle:focus-visible { outline-offset: -2px; }", STYLE)


class TestAdvancedSettings(unittest.TestCase):
    TOOLBAR = re.search(r'<div class="toolbar">.*?</div>', MARKUP, re.S).group(0)

    def test_the_box_sits_next_to_changed_only_with_its_label_and_is_unchecked(self):
        self.assertIn('<label><input id="show-advanced" type="checkbox"> <span id="show-advanced-text">show advanced settings</span></label>',
                      self.TOOLBAR)
        self.assertRegex(self.TOOLBAR, r'(?s)id="changed-only".*?id="show-advanced".*?id="btn-expand-all"')
        self.assertNotRegex(re.search(r'<input id="show-advanced"[^>]*>', MARKUP).group(0), r"\bchecked\b")

    def test_the_choice_is_a_boolean_for_the_life_of_the_page(self):
        self.assertRegex(CODE, r"(?m)^let showAdvanced = false;")
        self.assertIn('showAdvanced = $("show-advanced").checked;', CODE)
        for name in ("switchCar", "buildTable", "clearTable", "loadSettings", "refresh"):
            with self.subTest(name):
                self.assertNotIn("showAdvanced", function_body(name))
                self.assertNotIn("show-advanced", function_body(name))

    def test_ticking_the_box_runs_the_filter_and_touches_no_group(self):
        m = re.search(r'\$\("show-advanced"\)\.addEventListener\("change", \(\) => \{(.*?)\}\);', CODE, re.S)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).split(), ['showAdvanced', '=', '$("show-advanced").checked;', 'applyFilter();'])
        self.assertNotIn("expanded", m.group(1))

    def test_an_advanced_row_is_unlisted_unless_the_box_is_ticked_or_the_row_is_changed(self):
        body = function_body("applyFilter")
        self.assertIn("const unlisted = !!r.data.advanced && !showAdvanced && !r.data.changed;", body)
        self.assertIn("r.match = !unlisted && (!q || r.hay.includes(q)) && (!changedOnly || r.data.changed);", body)
        self.assertIn("r.tr.hidden = !(open && r.match);", body)
        self.assertIn("g.tr.hidden = !any;", body)

    def test_the_group_counts_leave_out_the_unlisted_rows_and_the_toggle_keeps_all_rows(self):
        body = function_body("applyFilter")
        self.assertIn("if (!unlisted) listed += 1;", body)
        self.assertNotIn("g.rows.length", body)
        self.assertIn('g.btn.setAttribute("aria-controls", g.rows.map((r) => r.tr.id).join(" "));', function_body("buildTable"))

    def test_the_label_carries_the_number_of_hidden_advanced_rows(self):
        body = function_body("applyFilter")
        self.assertIn("if (unlisted) advancedHidden += 1;", body)
        self.assertIn('"show advanced settings" + (advancedHidden > 0 ? " (" + advancedHidden + " hidden)" : "")', body)
        self.assertIn('$("show-advanced-text").textContent', body)

    def test_the_filter_does_not_open_or_close_groups_for_the_box(self):
        body = function_body("applyFilter")
        self.assertNotIn("expanded.add", body)
        self.assertNotIn("expanded.delete", body)
        self.assertNotIn("expanded.clear", body)

    def test_the_tyre_creator_warns_below_the_intro_with_the_warning_class(self):
        text = ("Kunos advises against editing the tyre model values: the code that connects them is not user-controlled, and a changed "
                "calibration can make a tyre behave unpredictably (tyres may need too much slip to grip or react nervously). "
                "Change little and test in the game.")
        section = TestTabs.TYRES_PANEL.split("<section", 1)[1].split("</section>", 1)[0]
        paragraphs = re.findall(r"<p\b([^>]*)>(.*?)</p>", section)
        self.assertEqual([p[1] for p in paragraphs][1], text)
        self.assertEqual(paragraphs[1][0].strip(), 'class="msg warn"')
        self.assertTrue(paragraphs[0][1].startswith("Tyres you create here"))
        self.assertIn(".msg.warn { color: var(--color-warning); }", STYLE)

    def test_the_warning_text_reads_on_the_panel_background(self):
        tokens = dict(re.findall(r"--([\w-]+): (#[0-9a-fA-F]{6});", STYLE))
        self.assertGreaterEqual(contrast(tokens["color-warning"], tokens["color-bg-alt"]), 4.5)


def luminance(hex_colour):
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    r, g, b = (c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(foreground, background):
    light, dark = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (light + 0.05) / (dark + 0.05)


class TestGroupList(unittest.TestCase):
    def test_the_group_list_is_read_once_with_the_selection_and_without_a_body(self):
        body = function_body("loadGroupInfo")
        self.assertIn('const res = await api("/api/groups", undefined, target);', body)
        self.assertIn("groupInfo = res.groups;", body)
        self.assertIn("if (groupInfo) return;", body)
        self.assertRegex(CODE, r"(?m)^let groupInfo = null;")
        self.assertEqual(len(re.findall(r'"/api/groups"', CODE)), 1)

    def test_it_is_read_before_the_table_is_built_and_read_again_only_after_a_failed_read(self):
        body = function_body("loadSettings")
        self.assertIn("await loadGroupInfo(target);", body)
        self.assertLess(body.index("await loadGroupInfo(target);"), body.index('api("/api/settings"'))
        self.assertLess(body.index("await loadGroupInfo(target);"), body.index("buildTable(list, target);"))
        self.assertEqual(CODE.count("loadGroupInfo("), 2)
        self.assertEqual(len(re.findall(r"groupInfo = ", CODE)), 3)
        self.assertIn("groupInfo = null;", function_body("loadGroupInfo")[function_body("loadGroupInfo").index("catch"):])
        self.assertNotIn("groupInfo", function_body("switchCar"))
        self.assertNotIn("groupInfo", function_body("clearTable"))

    def test_a_failed_read_is_no_error_of_the_table(self):
        body = function_body("loadGroupInfo")
        self.assertIn("} catch (e) {", body)
        self.assertNotIn("localError", body)
        self.assertNotIn("throw", body)
        self.assertEqual(function_body("loadSettings").count("localError = e.message;"), 1)
        self.assertLess(function_body("loadSettings").index("await loadGroupInfo(target);"),
                        function_body("loadSettings").index("} catch (e) {"))

    def test_the_groups_follow_the_list_of_the_server_and_unknown_groups_come_last_in_the_order_they_appeared(self):
        body = function_body("buildTable")
        self.assertIn("const listed = (groupInfo || []).map((x) => x.name);", body)
        self.assertIn("const rank = (g) => (listed.includes(g.name) ? listed.indexOf(g.name) : listed.length);", body)
        self.assertIn("groups.sort((a, b) => rank(a) - rank(b));", body)

    def test_each_header_is_followed_by_the_rows_of_its_group_even_when_the_settings_of_a_group_are_spread(self):
        body = function_body("buildTable")
        self.assertIn("body.append(g.tr, ...g.rows.map((r) => r.tr));", body)
        self.assertNotIn("insertBefore", body)
        self.assertNotIn("body.appendChild", body)
        self.assertIn("groups.find((g) => g.name === data.group)", body)
        self.assertLess(body.index("groups.sort("), body.index("body.append("))
        self.assertLess(body.index("body.append("), body.index("applyFilter();"))
        self.assertIn('r.tr.id = "row-" + rows.length;', body)
        self.assertIn('g.btn.setAttribute("aria-controls", g.rows.map((r) => r.tr.id).join(" "));', body)
        self.assertIn('if (data.ui === "header") {', body)

    def test_the_description_is_a_text_element_in_the_header_cell_below_the_toggle(self):
        body = function_body("buildGroup")
        self.assertIn("const known = (groupInfo || []).find((x) => x.name === name);", body)
        self.assertIn("if (known && known.description) {", body)
        self.assertIn('g.desc = el("div", "gdesc", known.description);', body)
        self.assertIn('g.desc.id = "gdesc-" + groups.length;', body)
        self.assertIn("g.desc.hidden = true;", body)
        self.assertIn('g.btn.setAttribute("aria-describedby", g.desc.id);', body)
        self.assertLess(body.index("th.appendChild(g.btn);"), body.index("th.appendChild(g.desc);"))
        self.assertLess(body.index("th.appendChild(g.desc);"), body.index("g.tr.appendChild(th);"))
        self.assertIn("desc: null", body)
        self.assertNotIn("innerHTML", body)
        self.assertIn('"aria-controls"', function_body("buildTable"))
        self.assertNotIn("aria-controls", body)

    def test_the_description_is_hidden_with_the_rows_by_the_open_state_of_the_group(self):
        body = function_body("applyFilter")
        self.assertIn("if (g.desc) g.desc.hidden = !open;", body)
        self.assertLess(body.index("const open = filtering ? any : expanded.has(g.name);"), body.index("g.desc.hidden = !open;"))
        for name in ("toggleGroup", "setAllGroups", "revealGroup"):
            with self.subTest(name):
                self.assertNotIn("desc", function_body(name))

    def test_the_description_style_is_muted_normal_weight_and_not_uppercase_with_a_readable_width(self):
        rule = re.search(r"\n\.gdesc \{([^}]*)\}", STYLE).group(1)
        self.assertIn("color: var(--color-text-muted);", rule)
        self.assertIn("font-weight: normal;", rule)
        self.assertIn("text-transform: none;", rule)
        self.assertIn("letter-spacing: normal;", rule)
        self.assertRegex(rule, r"max-width: \d+ch;")
        self.assertIn("gdesc", used_classes())
        self.assertIn("gdesc", css_classes())

    def test_the_muted_text_reads_on_the_group_header_background(self):
        tokens = dict(re.findall(r"(--[\w-]+): (#[0-9a-fA-F]{6});", TestDarkTheme.ROOT_RULE))
        self.assertIn("background: var(--color-bg-elevated);", re.search(r"tr\.group th \{([^}]*)\}", STYLE).group(1))
        self.assertGreaterEqual(contrast(tokens["--color-text-muted"], tokens["--color-bg-elevated"]), 4.5)


class TestBaseRangeColumn(unittest.TestCase):
    CAR_TABLE = MARKUP.split('<caption id="caption"', 1)[1].split("</table>")[0]
    TYRE_TABLE = MARKUP.split('<caption class="sr-only">Settings of the selected tyre</caption>', 1)[1].split('id="tyre-rows"')[0]

    def test_the_header_sits_between_default_and_description_in_the_car_table_only(self):
        heads = [h.replace("<br>", " ") for h in re.findall(r'<th scope="col">(.*?)</th>', self.CAR_TABLE)]
        self.assertEqual(heads, ["Variable name", "Value", "Default (for the selected car)", "Range for base cars", "Description"])
        self.assertNotIn("Range for base cars", self.TYRE_TABLE)

    def test_the_colgroup_has_the_range_column_between_default_and_description(self):
        self.assertIn('<colgroup><col class="c-name"><col class="c-value"><col class="c-default"><col class="c-range"><col class="c-desc"></colgroup>',
                      self.CAR_TABLE)
        self.assertNotIn("c-range", self.TYRE_TABLE)
        self.assertRegex(STYLE, r"col\.c-range \{ width: \d+%; \}")

    def test_the_widths_of_the_car_table_add_up_to_100_and_the_tyre_table_keeps_its_own(self):
        car = {m[0]: int(m[1]) for m in re.findall(r"(?:#panel-car )?col\.(c-(?:name|value|default|range|desc)) \{ width: (\d+)%; \}",
                                                   "\n".join(l for l in STYLE.splitlines() if l.startswith("#panel-car ") or l.startswith("col.c-range")))}
        self.assertEqual(sorted(car), ["c-default", "c-desc", "c-name", "c-range", "c-value"])
        self.assertEqual(sum(car.values()), 100)
        tyre = [int(w) for w in re.findall(r"^col\.c-(?:name|value|default|desc) \{ width: (\d+)%; \}", STYLE, re.M)]
        self.assertEqual((len(tyre), sum(tyre)), (4, 100))

    def test_the_group_rows_span_the_columns_of_their_table(self):
        self.assertIn("th.colSpan = 5;", function_body("buildGroup"))
        self.assertIn("th.colSpan = 4;", function_body("buildTyreGroup"))

    def test_the_cell_is_added_by_the_car_table_only(self):
        self.assertIn("function buildRow(data, target, withRange) {", CODE)
        body = function_body("buildRow")
        self.assertIn("r.tr.append(nameCell, valueCell, defCell);", body)
        self.assertIn("if (withRange) r.tr.appendChild(buildRangeCell(data));", body)
        self.assertLess(body.index("buildRangeCell(data)"), body.index("r.tr.appendChild(descCell);"))
        self.assertIn("buildRow(data, target, true)", function_body("buildTable"))
        self.assertIn("buildRow(item, null);", function_body("buildTyreRows"))
        self.assertEqual(len(re.findall(r"\bbuildRow\(", CODE)), 3)

    def test_the_formatter_joins_low_and_high_with_an_en_dash_and_spaces(self):
        body = function_body("buildRangeCell")
        self.assertIn("const br = data.base_range;", body)
        self.assertIn('low + " \\u2013 " + high', body)
        self.assertIn("br.low === br.high ? low :", body)
        self.assertIn("fmtVal(data.type, br.low)", body)
        self.assertIn("fmtVal(data.type, br.high)", body)
        self.assertIn('(data.unit ? " " + data.unit : "")', body)

    def test_a_row_without_a_range_and_the_non_numeric_types_show_a_muted_en_dash(self):
        body = function_body("buildRangeCell")
        self.assertIn('if (!br || (data.type !== "int" && data.type !== "float")) {', body)
        self.assertIn('el("td", "default mono", "\\u2013")', body)
        self.assertIn('none.classList.add("range-none");', body)
        self.assertIn('none.setAttribute("aria-label", "no range");', body)
        self.assertIn(".range-none { color: var(--color-text-muted); }", STYLE)

    def test_the_cell_is_plain_text_without_tooltip_or_behaviour(self):
        body = function_body("buildRangeCell")
        for word in ("title", "addEventListener", "badge", "changed", "min", "max", "aria-description"):
            with self.subTest(word):
                self.assertNotIn(word, body)
        self.assertEqual(len(re.findall(r"\bbase_range\b", CODE)), 1)

    def test_the_server_sends_the_field_the_page_reads(self):
        self.assertIn('"base_range"', inspect.getsource(ts.row_json))


class TestPolling(unittest.TestCase):
    # R4-023
    def test_a_hidden_tab_polls_slowly_and_refreshes_at_once_when_shown(self):
        poll_hidden, poll_idle = (int(re.search(r"^const %s = (\d+);" % k, CODE, re.M).group(1)) for k in ("POLL_HIDDEN_MS", "POLL_IDLE_MS"))
        self.assertGreater(poll_hidden, poll_idle)
        handler = re.search(r'document\.addEventListener\("visibilitychange", \(\) => \{(.*?)\}\);', CODE, re.S)
        self.assertIsNotNone(handler, "no visibilitychange handler")
        self.assertRegex(handler.group(1), r"if \(!document\.hidden\) refresh\(\);")


class TestJobRunning(unittest.TestCase):
    # R4-001 (page part): no edits while a job runs, the server answers them with 409 anyway
    def test_the_value_fields_and_reset_buttons_are_disabled_while_a_job_runs(self):
        body = function_body("renderButtons")
        self.assertIn('const running = !!info && info.job.state === "running";', body)
        self.assertIn("r.field.disabled = running;", body)
        self.assertIn("r.reset.disabled = running;", body)
        self.assertIn('$("btn-reset-all").disabled = running;', body)

    def test_the_header_row_is_disabled_with_the_table_rows(self):
        self.assertIn("headerRow ? rows.concat(headerRow) : rows", function_body("renderButtons"))

    def test_a_refused_edit_shows_the_server_message_in_the_row(self):
        self.assertIn("setMsg(r, e.message, \"err\")", function_body("sendSet"))
        self.assertIn("setMsg(r, e.message, \"err\")", function_body("sendUnset"))

    # R4-002 (page part)
    def test_the_progress_panel_warns_not_to_close_the_console_while_a_job_runs(self):
        body = function_body("renderProgress")
        note = body.index("Do not close the console window while this runs.")
        self.assertLess(body.index('job.state === "running"'), note)
        self.assertLess(note, body.index('job.state === "done"'))


class TestInstallCars(unittest.TestCase):
    def test_the_init_panel_says_install_not_extract(self):
        panel = re.search(r'<section id="init-panel".*?</section>', MARKUP, re.S).group(0)
        self.assertIn("<h2>Car not installed yet</h2>", panel)
        self.assertIn("The tuner needs the car's files from the game as its starting point. Installing pulls them once (about 20 seconds).", panel)
        self.assertIn('<button id="btn-init" class="primary" type="button">Install car (pull game files)</button>', panel)
        self.assertIn("Installing pulls them once (about 20 seconds).", function_body("renderCars"))
        for old in ("Extract stock car", "not extracted yet", "stock car from the game files"):
            with self.subTest(old):
                self.assertNotIn(old, HTML)

    def test_the_install_button_starts_the_init_job(self):
        self.assertIn('$("btn-init").addEventListener("click", () => startJob("/api/init", {}));', CODE)

    def test_the_page_has_no_install_all_tested_cars_button_or_job(self):
        self.assertNotIn("btn-install-tested", HTML)
        self.assertNotIn("install_tested", HTML)

    def test_the_progress_panel_names_the_install_job(self):
        body = function_body("renderProgress")
        self.assertIn('job.kind === "init" ? "Install car" : "Apply"', body)
        self.assertIn('if (job.kind === "init") addLine(box, "The car is installed, the table is available.");', body)
        self.assertNotIn("Extract stock car", body)

    def test_the_table_is_not_loaded_while_the_install_job_runs(self):
        body = function_body("refresh")
        self.assertIn('const extracting = !!info && info.job.kind === "init" && info.job.state === "running";', body)
        self.assertIn("!tableLoaded && !extracting", body)

    def test_every_job_kind_the_progress_panel_knows_is_started_by_the_server(self):
        kinds = set(re.findall(r'job\.kind === "(\w+)"', function_body("renderProgress")))
        self.assertEqual(kinds, {"apply", "init"})
        self.assertEqual(kinds - set(re.findall(r'run_job\("(\w+)"', inspect.getsource(ts))), set())


class TestProgressDetails(unittest.TestCase):
    def test_the_applied_settings_are_a_collapsed_details_with_the_count_in_the_summary(self):
        body = function_body("summaryApply")
        self.assertIn("if (res.applied.length) {", body)
        self.assertIn('const details = el("details");', body)
        self.assertIn('el("summary", "", "Settings applied (" + res.applied.length + ")")', body)
        self.assertIn("details.appendChild(ul);", body)
        self.assertIn("box.appendChild(details);", body)
        self.assertNotIn("Settings applied:", HTML)
        self.assertNotRegex(body, r"\bopen\b")

    def test_the_list_sits_inside_the_details_and_the_closing_lines_stay_outside(self):
        body = function_body("summaryApply")
        self.assertLess(body.index('el("summary"'), body.index('const ul = el("ul");'))
        self.assertLess(body.index("details.appendChild(ul);"), body.index("box.appendChild(details);"))
        self.assertLess(body.index("box.appendChild(details);"), body.index('addLine(box, "Package: "'))
        for line in ('"Installed to: "', '"Backup of the previous install: "', "Close the game before applying again."):
            with self.subTest(line):
                self.assertLess(body.index("box.appendChild(details);"), body.index(line))

    def test_no_applied_setting_still_shows_the_plain_paragraph_without_details(self):
        body = function_body("summaryApply")
        empty = body[body.index("} else {"):body.index('addLine(box, "Package: "')]
        self.assertIn('addLine(box, "No setting was changed, the stock values were built.");', empty)
        self.assertNotIn("details", empty)

    def test_a_finished_job_wraps_the_build_log_in_a_collapsed_details(self):
        body = function_body("renderProgress")
        log = body[body.index("if (job.log.length) {"):]
        done = log[log.index('if (job.state === "done") {'):log.index("} else {")]
        self.assertIn('const details = el("details");', done)
        self.assertIn('el("summary", "", "Build log")', done)
        self.assertIn("details.appendChild(pre);", done)
        self.assertIn("box.appendChild(details);", done)
        self.assertNotRegex(done, r"\bopen\b")

    def test_a_running_or_failed_job_keeps_the_log_visible_and_scrolled_to_the_end(self):
        body = function_body("renderProgress")
        log = body[body.index("if (job.log.length) {"):]
        visible = log[log.index("} else {"):]
        self.assertIn("box.appendChild(pre);", visible)
        self.assertIn("pre.scrollTop = pre.scrollHeight;", visible)
        self.assertNotIn("details", visible)

    def test_the_details_are_native_and_styled_in_the_panel_without_a_new_class(self):
        self.assertIn(".panel summary { cursor: pointer; }", STYLE)
        self.assertIn(".panel summary:focus-visible { outline: 2px solid var(--color-accent); outline-offset: 1px; }", STYLE)
        for name in ("summaryApply", "renderProgress"):
            self.assertNotIn("addEventListener", function_body(name))

    def test_the_panel_is_rebuilt_only_when_the_job_or_the_errors_change_so_an_opened_details_stays_open(self):
        self.assertEqual(re.findall(r"\brenderProgress\(\)", CODE), ["renderProgress()", "renderProgress()"])
        self.assertEqual(len(re.findall(r"\bjobSig = ", CODE)), 2)
        self.assertIn("jobSig = sig;", function_body("renderProgress"))
        self.assertEqual(re.findall(r"\brenderProgress\(\);", function_body("refresh")), ["renderProgress();"])


class TestErrorHandling(unittest.TestCase):
    def test_a_failed_job_start_or_reset_shows_the_error(self):
        self.assertIn("localError = e.message;", function_body("startJob"))
        self.assertIn("localError = e.message;", function_body("resetAll"))
        self.assertIn("localError = e.message;", function_body("loadSettings"))

    def test_a_new_job_and_a_car_switch_clear_the_old_error(self):
        self.assertIn('localError = "";', function_body("startJob"))
        self.assertIn('localError = "";', function_body("switchCar"))

    def test_a_successful_settings_load_clears_the_old_error(self):
        body = function_body("loadSettings")
        success = body.index("tableLoaded = true;")
        self.assertIn('localError = "";', body[success:])

    def test_a_failing_api_call_becomes_an_error_with_the_server_text(self):
        body = function_body("api")
        self.assertIn('throw new Error("server not reachable")', body)
        self.assertIn("data.error", body)
        self.assertIn('"HTTP " + res.status', body)


class TestModdedCars(unittest.TestCase):
    def test_the_selector_has_the_three_groups_in_order(self):
        labels = re.findall(r'\["((?:Installed|Other|Modded) Cars)", ', function_body("renderCars"))
        self.assertEqual(labels, ["Installed Cars", "Other Cars", "Modded Cars"])
        self.assertIn('<select id="car-select" aria-label="Car"', MARKUP)
        self.assertEqual(MARKUP.count("<optgroup"), 0)

    def test_the_installed_group_holds_the_extracted_cars_and_the_other_group_the_rest(self):
        body = function_body("renderCars")
        self.assertIn('["Installed Cars", list.filter((c) => c.extracted).sort(byName)', body)
        self.assertIn('["Other Cars", list.filter((c) => !c.extracted).sort(byName)', body)
        self.assertNotIn("c.tested", body)
        self.assertNotIn("Base Cars", HTML)

    def test_an_option_is_the_name_of_the_car_without_flags(self):
        self.assertEqual(function_body("optionText").strip(), "return c.display_name || c.label;")
        for old in ("not extracted", "(installed", "flags", '" ("'):
            with self.subTest(old):
                self.assertNotIn(old, function_body("optionText"))
                self.assertNotIn(old, function_body("renderCars"))

    def test_the_note_for_untested_cars_stays(self):
        body = function_body("renderCars")
        self.assertIn('$("untested").hidden = !entry || entry.tested;', body)
        self.assertIn("This car has not been tested with the tuner yet; check the results before you trust them.", body)

    def test_the_option_values_encode_the_target(self):
        body = function_body("renderCars")
        self.assertEqual(re.findall(r'\["(base|mod):" \+ (\w)\.id, ', body), [("base", "c"), ("base", "c"), ("mod", "m")])
        self.assertIn("o.value = value;", body)
        self.assertIn('startsWith("base:")', function_body("choiceOf"))
        self.assertIn('startsWith("mod:")', function_body("choiceOf"))
        self.assertIn("{ car: value.slice(5), tune: DRAFT }", function_body("choiceOf"))
        self.assertIn("{ car: m.stock, tune: m.id }", function_body("choiceOf"))

    def test_a_modded_option_says_whether_the_car_is_installed(self):
        body = function_body("renderCars")
        self.assertIn('m.label + (m.installed ? " - installed" : " - not installed")', body)

    def test_the_modded_group_is_absent_while_the_list_is_empty(self):
        body = function_body("renderCars")
        self.assertIn("moddedList().map(", body)
        self.assertIn("if (!options.length) continue;", body)
        self.assertIn("info && info.modded ? info.modded : []", function_body("moddedList"))

    def test_the_selection_survives_a_poll_and_is_part_of_the_selector_signature(self):
        body = function_body("renderCars")
        self.assertIn("JSON.stringify([groupsOf, selection])", body)
        self.assertIn("select.value = choiceValue(selection);", body)
        self.assertIn("selection = { car: info.car, tune: info.tune };", function_body("refresh"))

    def test_the_selection_is_one_object_with_car_and_tune(self):
        self.assertRegex(CODE, r"(?m)^let selection = storedSelection\(\);")
        self.assertNotRegex(CODE, r"\bcarId\b")
        self.assertIn("{ car: null, tune: DRAFT }", CODE)
        self.assertIn('const DRAFT = "draft";', CODE)
        for name in ("sendSet", "sendUnset"):
            self.assertIn("r.target)", function_body(name))
        self.assertIn("target.tune === DRAFT", function_body("buildHeaderRow"))

    def test_a_damaged_modded_state_is_shown_in_the_message_area(self):
        body = function_body("renderProgress")
        self.assertIn("info.modded_error", body)
        self.assertIn("errors.push(", body)
        self.assertIn("for (const text of errors) addLine(box, text);", body)
        self.assertIn("JSON.stringify([job, errors])", body)

    def test_the_header_line_names_the_kind_of_car(self):
        body = function_body("buildHeaderRow")
        self.assertIn('"Base car: Apply creates a new modded car"', body)
        self.assertIn('"Modded car " + target.tune + " of " + carName()', body)
        self.assertIn('el("span", "tunenote"', body)

    def test_the_buttons_follow_the_kind_of_car(self):
        self.assertIn('<button id="btn-apply" class="primary" type="button" disabled>Create modded car&hellip;</button>', MARKUP)
        self.assertIn('<button id="btn-duplicate" type="button" disabled>Duplicate&hellip;</button>', MARKUP)
        body = function_body("renderButtons")
        self.assertIn('draft ? "Create modded car\\u2026" : "Apply (update this car)"', body)
        self.assertIn('$("btn-duplicate").disabled = whyDuplicate !== "";', body)
        self.assertIn('whyDuplicate = "select a modded car to duplicate it"', body)
        self.assertIn('whyDuplicate = info.base_present ? "" : "extract the stock car first"', body)

    def test_the_old_copy_flow_is_gone(self):
        for old in ("btn-copy", "askNewCopy", "Save as new copy", "new_copy", "window.prompt", "Apply (update my car)"):
            with self.subTest(old):
                self.assertNotIn(old, HTML)

    def test_the_dialog_is_an_inline_panel_with_two_labelled_inputs(self):
        panel = re.search(r'<section id="dialog".*?</section>', MARKUP, re.S).group(0)
        self.assertIn("hidden>", panel.split("\n")[0])
        self.assertIn('aria-labelledby="dialog-title"', panel)
        for field in ("dialog-id", "dialog-suffix"):
            with self.subTest(field):
                self.assertRegex(panel, r'<label for="%s">[^<]+</label>\s*<input id="%s"[^>]*type="text"' % (field, field))
        for button in ("dialog-ok", "dialog-cancel"):
            self.assertRegex(panel, r'<button id="%s"[^>]*type="button">' % button)
        self.assertIn(">OK</button>", panel)
        self.assertIn(">Cancel</button>", panel)
        self.assertNotIn("window.prompt", CODE)
        self.assertNotIn("window.alert", CODE)

    def test_the_dialog_is_prefilled_from_the_proposals_of_the_server(self):
        body = function_body("openDialog")
        self.assertIn('$("dialog-id").value = info.proposed_new_id || "";', body)
        self.assertIn('create ? info.proposed_suffix || "" : ""', body)
        self.assertIn('create ? "" : "automatic"', body)

    def test_enter_confirms_and_escape_cancels_the_dialog(self):
        body = function_body("dialogKey")
        self.assertIn('ev.key === "Escape"', body)
        self.assertIn("closeDialog(true)", body)
        self.assertIn('ev.key === "Enter" && ev.target.tagName === "INPUT"', body)
        self.assertIn("submitDialog()", body)
        self.assertIn('$("dialog").addEventListener("keydown", dialogKey);', CODE)

    def test_the_focus_moves_into_the_panel_and_back(self):
        self.assertIn('$("dialog-id").focus();', function_body("openDialog"))
        self.assertIn("opener", function_body("openDialog"))
        body = function_body("closeDialog")
        self.assertIn("if (restoreFocus) {", body)
        self.assertIn("back.focus();", body)

    def test_a_server_error_stays_inside_the_open_panel(self):
        body = function_body("submitDialog")
        failure = body[body.index("} catch (e) {"):]
        self.assertIn("showDialogError(e.message);", failure)
        self.assertNotIn("closeDialog", failure)
        self.assertIn("mine.busy = false;", failure)
        self.assertIn('$("dialog-error").textContent = text;', function_body("showDialogError"))

    def test_create_selects_the_new_car_when_the_job_has_created_it(self):
        body = function_body("submitDialog")
        self.assertIn("awaitCreated = { car: target.car, known: known };", body)
        self.assertIn("job.result.created", function_body("createdCar"))
        self.assertIn("{ car: awaitCreated.car, tune: job.result.new_id }", function_body("createdCar"))
        self.assertIn("if (createdCar()) return;", function_body("refresh"))

    def test_duplicate_selects_the_new_car_at_once(self):
        self.assertIn("switchCar({ car: res.stock, tune: res.id });", function_body("submitDialog"))

    def test_a_switch_closes_the_panel_and_reloads_the_table(self):
        body = function_body("switchCar")
        for part in ("storeSelection(next);", "closeDialog(false);", "tableLoaded = false;", "clearTable();", "refresh();"):
            self.assertIn(part, body)
        self.assertIn("sameSelection(next, selection)", body)

    def test_the_new_buttons_and_inputs_are_disabled_while_a_job_runs(self):
        body = function_body("renderButtons")
        self.assertIn('const locked = running || (dialog !== null && dialog.busy);', body)
        self.assertIn('for (const id of ["dialog-id", "dialog-suffix", "dialog-ok"]) $(id).disabled = locked;', body)
        self.assertIn('$("btn-duplicate").disabled = whyDuplicate !== "";', body)
        self.assertIn('if (why === "close the game first")', body)
        self.assertIn("whyDuplicate = why;", body)


class TestTabs(unittest.TestCase):
    CAR_PANEL = MARKUP[MARKUP.index('id="panel-car"'):MARKUP.index('id="panel-tyres"')]
    TYRES_PANEL = MARKUP[MARKUP.index('id="panel-tyres"'):]
    TAB_RULE = re.search(r'button\[role="tab"\] \{(.*?)\}', STYLE, re.S).group(1)

    @staticmethod
    def tag(ident):
        return re.search(r'<[a-z]+\b[^>]*\bid="%s"[^>]*>' % ident, MARKUP).group(0)

    def test_the_tabs_are_a_tablist_of_two_buttons_with_the_two_labels(self):
        self.assertEqual(re.findall(r'<div role="tablist" aria-label="Pages">', MARKUP), ['<div role="tablist" aria-label="Pages">'])
        strip = re.search(r'<div role="tablist".*?</div>', MARKUP, re.S).group(0)
        tabs = re.findall(r'<button\b[^>]*>.*?</button>', strip, re.S)
        self.assertEqual(len(tabs), 2)
        for tab, ident, label in zip(tabs, ("tab-car", "tab-tyres"), ("Car Tuner", "Tyre Creator")):
            with self.subTest(ident):
                self.assertIn('id="%s"' % ident, tab)
                self.assertIn('role="tab"', tab)
                self.assertIn('type="button"', tab)
                self.assertTrue(tab.endswith(">%s</button>" % label), tab)
        self.assertEqual(MARKUP.count('role="tab"'), 2)

    def test_the_two_panels_are_tabpanels_labelled_by_their_tabs(self):
        self.assertEqual(MARKUP.count('role="tabpanel"'), 2)
        for tab, panel in (("tab-car", "panel-car"), ("tab-tyres", "panel-tyres")):
            with self.subTest(tab):
                self.assertIn('aria-controls="%s"' % panel, self.tag(tab))
                self.assertIn('role="tabpanel"', self.tag(panel))
                self.assertIn('aria-labelledby="%s"' % tab, self.tag(panel))

    def test_every_aria_controls_and_labelledby_of_the_tabs_names_an_existing_id(self):
        ids = set(dom_ids())
        for ident in ("tab-car", "tab-tyres", "panel-car", "panel-tyres"):
            with self.subTest(ident):
                tag = self.tag(ident)
                for target in re.findall(r'aria-(?:controls|labelledby)="([^"]+)"', tag):
                    self.assertIn(target, ids)

    def test_the_car_tuner_is_selected_on_load_with_a_roving_tabindex(self):
        self.assertIn('aria-selected="true"', self.tag("tab-car"))
        self.assertIn('tabindex="0"', self.tag("tab-car"))
        self.assertIn('aria-selected="false"', self.tag("tab-tyres"))
        self.assertIn('tabindex="-1"', self.tag("tab-tyres"))
        self.assertEqual(MARKUP.count('aria-selected="true"'), 1)

    def test_the_inactive_panel_is_hidden_and_the_active_one_is_not(self):
        self.assertNotRegex(self.tag("panel-car"), r"\bhidden\b")
        self.assertRegex(self.tag("panel-tyres"), r"\bhidden>$")

    def test_the_car_tuner_elements_are_inside_the_car_panel(self):
        for ident in ("car-select", "btn-apply", "btn-duplicate", "dialog", "name-host", "untested", "status",
                      "progress", "init-panel", "tuner", "search", "rows"):
            with self.subTest(ident):
                self.assertIn('id="%s"' % ident, self.CAR_PANEL)
                self.assertNotIn('id="%s"' % ident, self.TYRES_PANEL)

    def test_the_tyre_panel_keeps_its_heading_and_its_first_paragraph(self):
        self.assertIn("<h2>Tyre Creator</h2>", self.TYRES_PANEL)
        self.assertEqual(re.findall(r"<p\b[^>]*>(.*?)</p>", self.TYRES_PANEL)[0],
                         "Tyres you create here are saved once and can be ticked in the garage list of any modded car in the Car Tuner tab.")
        self.assertTrue(self.TYRES_PANEL.split("<section", 1)[1].startswith(' class="panel">\n      <h2>Tyre Creator</h2>'))

    def test_the_header_holds_the_title_only_and_the_tab_strip_follows_it(self):
        header = re.search(r'<header class="bar">.*?</header>', MARKUP, re.S).group(0)
        self.assertEqual(re.findall(r"<[a-z0-9]+", header), ["<header", "<h1"])
        self.assertLess(MARKUP.index("</header>"), MARKUP.index('role="tablist"'))
        self.assertLess(MARKUP.index('role="tablist"'), MARKUP.index('id="panel-car"'))
        self.assertLess(MARKUP.index('id="panel-car"'), MARKUP.index('id="panel-tyres"'))

    def test_the_script_selects_a_tab_by_flipping_aria_selected_tabindex_and_hidden_without_removing_anything(self):
        body = function_body("selectTab")
        self.assertIn('tab.setAttribute("aria-selected", k === i ? "true" : "false");', body)
        self.assertIn("tab.tabIndex = k === i ? 0 : -1;", body)
        self.assertIn("panels[k].hidden = k !== i;", body)
        self.assertIn("activeTab = i;", body)
        for sink in ("remove", "replaceChildren", "localStorage", "aria-live", "role"):
            self.assertNotIn(sink, body)
        self.assertRegex(CODE, r'(?m)^const tabs = \[\$\("tab-car"\), \$\("tab-tyres"\)\];')
        self.assertRegex(CODE, r'(?m)^const panels = \[\$\("panel-car"\), \$\("panel-tyres"\)\];')
        self.assertRegex(CODE, r"(?m)^let activeTab = 0;")

    def test_the_script_handles_click_and_the_four_keys_with_wrap_around_and_moves_the_focus(self):
        self.assertIn('tab.addEventListener("click", () => selectTab(i));', CODE)
        self.assertIn('tab.addEventListener("keydown", tabKey);', CODE)
        body = function_body("tabKey")
        self.assertIn('ev.key === "ArrowRight") next = (activeTab + 1) % tabs.length;', body)
        self.assertIn('ev.key === "ArrowLeft") next = (activeTab + tabs.length - 1) % tabs.length;', body)
        self.assertIn('ev.key === "Home") next = 0;', body)
        self.assertIn('ev.key === "End") next = tabs.length - 1;', body)
        self.assertIn("selectTab(next);", body)
        self.assertIn("tabs[next].focus();", body)
        self.assertIn("ev.preventDefault();", body)
        self.assertIn("if (ev.altKey || ev.ctrlKey || ev.metaKey) return;", body)

    def test_the_active_tab_lives_in_a_variable_only_and_changes_nothing_of_the_car_tuner(self):
        self.assertEqual(CODE.count("localStorage"), 2)
        self.assertNotIn("activeTab", function_body("storeSelection") + function_body("storedSelection"))
        for name in ("refresh", "switchCar", "applyFilter", "renderButtons", "toggleGroup", "closeDialog", "openDialog"):
            with self.subTest(name):
                self.assertNotIn("activeTab", function_body(name))
        self.assertNotRegex(function_body("tabKey") + function_body("selectTab"), r"aria-live|setAttribute\(\"role\"")

    def test_the_selected_tab_is_styled_by_aria_selected_not_by_a_class(self):
        self.assertIn('button[role="tab"][aria-selected="true"] { border-bottom-color: var(--color-accent); color: var(--color-text); }', STYLE)
        self.assertNotRegex(STYLE, r"\.(?:selected|active|current)\b")
        self.assertNotRegex(CODE, r'classList\.[a-z]+\("(?:selected|active|current)"')
        self.assertNotIn("className", function_body("selectTab"))

    def test_the_tab_style_is_muted_on_the_page_background_with_a_hover_text_and_a_comfortable_height(self):
        self.assertIn("background: transparent; color: var(--color-text-muted);", self.TAB_RULE)
        self.assertRegex(self.TAB_RULE, r"min-height: (?:4\d|[5-9]\d)px;")
        self.assertIn('button[role="tab"]:hover { border-bottom-color: transparent; color: var(--color-text); }', STYLE)
        self.assertIn("border-bottom: 1px solid var(--color-border);", re.search(r'\[role="tablist"\] \{(.*?)\}', STYLE).group(0))
        self.assertIn("border-bottom-width: 2px;", self.TAB_RULE)

    def test_the_tabs_keep_the_focus_ring_and_add_no_animation(self):
        self.assertNotRegex(STYLE, r"outline:\s*(?:none|0)")
        self.assertNotIn("transition", self.TAB_RULE)
        self.assertNotIn("animation", STYLE)

    def test_the_tab_rules_come_after_the_general_button_rules_so_that_they_win_the_hover_tie(self):
        self.assertLess(STYLE.index("button:hover:not(:disabled)"), STYLE.index('button[role="tab"]:hover'))
        self.assertLess(STYLE.index('button[role="tab"]:hover'), STYLE.index('button[role="tab"][aria-selected="true"]'))


class TestTyreCreator(unittest.TestCase):
    PANEL = MARKUP[MARKUP.index('id="panel-tyres"'):]

    @staticmethod
    def tag(ident):
        return re.search(r'<[a-z]+\b[^>]*\bid="%s"[^>]*>' % ident, MARKUP).group(0)

    def test_the_toolbar_has_the_selector_and_the_three_buttons(self):
        bar = re.search(r'<div class="toolbar">.*?</div>', self.PANEL, re.S).group(0)
        self.assertIn('<select id="tyre-select" aria-label="Tyre"', bar)
        self.assertIn('<button id="btn-tyre-new" class="primary" type="button" disabled>New tyre&hellip;</button>', bar)
        self.assertIn('<button id="btn-tyre-rename" type="button" disabled>Rename&hellip;</button>', bar)
        self.assertIn('<button id="btn-tyre-delete" type="button" disabled>Delete</button>', bar)
        self.assertLess(bar.index("tyre-select"), bar.index("btn-tyre-new"))
        self.assertLess(bar.index("btn-tyre-new"), bar.index("btn-tyre-rename"))
        self.assertLess(bar.index("btn-tyre-rename"), bar.index("btn-tyre-delete"))

    def test_the_dialog_is_a_hidden_labelled_group_with_a_name_a_source_an_alert_and_two_buttons(self):
        panel = re.search(r'<section id="tyre-dialog".*?</section>', self.PANEL, re.S).group(0)
        first = panel.split("\n")[0]
        for part in ('class="panel dialog"', 'role="group"', 'aria-labelledby="tyre-dialog-title"'):
            self.assertIn(part, first)
        self.assertTrue(first.endswith("hidden>"), first)
        self.assertIn('<h2 id="tyre-dialog-title"></h2>', panel)
        self.assertRegex(panel, r'<label for="tyre-dialog-name">Name</label>\s*<input id="tyre-dialog-name"[^>]*type="text"')
        self.assertRegex(panel, r'<label for="tyre-dialog-source">Source tyre \(from your installed cars\)</label>\s*<select id="tyre-dialog-source">')
        self.assertIn('<p id="tyre-dialog-error" class="msg err" role="alert" hidden></p>', panel)
        self.assertIn('<button id="tyre-dialog-ok" class="primary" type="button">OK</button>', panel)
        self.assertIn('<button id="tyre-dialog-cancel" type="button">Cancel</button>', panel)
        self.assertIn('<p id="tyre-dialog-text" hidden></p>', panel)

    def test_the_editor_is_hidden_until_a_tyre_is_selected_and_has_the_source_the_reset_button_and_its_own_table(self):
        self.assertRegex(self.tag("tyre-editor"), r"\bhidden>$")
        editor = re.search(r'<section id="tyre-editor".*?</section>', self.PANEL, re.S).group(0)
        self.assertRegex(editor, r'<label class="carpick">Source:\s*<select id="tyre-source" aria-label="Source tyre"></select>')
        self.assertIn('<button id="btn-tyre-reset" type="button">Reset all values</button>', editor)
        self.assertIn('<tbody id="tyre-rows"></tbody>', editor)
        self.assertIn('<caption class="sr-only">Settings of the selected tyre</caption>', editor)
        self.assertEqual([h.replace("<br>", " ") for h in re.findall(r'<th scope="col">(.*?)</th>', editor)],
                         ["Variable name", "Value", "Default (source tyre)", "Description"])
        self.assertNotIn('id="rows"', self.PANEL)

    def test_the_error_line_is_a_visible_alert_of_the_panel_outside_the_dialog(self):
        self.assertIn('<p id="tyre-error" class="msg err" role="alert" hidden></p>', self.PANEL)
        self.assertLess(self.PANEL.index('id="tyre-dialog"'), self.PANEL.index('id="tyre-error"'))
        body = function_body("renderTyres")
        self.assertIn('$("tyre-error").textContent = tyreError;', body)
        self.assertIn('$("tyre-error").hidden = tyreError === "";', body)
        self.assertEqual(CODE.count('setAttribute("role", "alert")'), 1)

    def test_every_tyre_route_is_called_with_the_fields_of_the_server(self):
        calls = {
            "/api/tyre_new": r'api\("/api/tyre_new", \{ name: name, source: source \}, selection\)',
            "/api/tyre_rename": r'api\("/api/tyre_rename", \{ id: mine\.id, name: name \}, selection\)',
            "/api/tyre_source": r'api\("/api/tyre_source", \{ id: entry\.id, source: key \}, selection\)',
            "/api/tyre_set": r'api\("/api/tyre_set", \{ id: r\.tyre, setting: r\.data\.id, value: text \}, selection\)',
            "/api/tyre_unset": r'api\("/api/tyre_unset", \{ id: r\.tyre, setting: r\.data\.id \}, selection\)',
            "/api/tyre_reset": r'api\("/api/tyre_reset", \{ id: entry\.id \}, selection\)',
            "/api/tyre_delete": r'api\("/api/tyre_delete", \{ id: mine\.id \}, selection\)',
        }
        for route, call in calls.items():
            with self.subTest(route):
                self.assertIn(route, ts.POST_ROUTES)
                self.assertEqual(len(re.findall(call, CODE)), 1)
                fields = set(re.findall(r'\b(\w+):', re.search(r'api\("%s", (\{[^}]*\})' % route, CODE).group(1)))
                handler = inspect.getsource(ts.POST_ROUTES[route])
                self.assertEqual(fields, set(re.findall(r'body\.get\("(\w+)"\)', handler)))
        self.assertEqual(len(re.findall(r'api\("/api/tyres", undefined, selection\)', CODE)), 1)
        self.assertEqual(len(re.findall(r'api\("/api/tyre\?id=" \+ encodeURIComponent\(id\), undefined, selection\)', CODE)), 1)
        self.assertEqual(ts.QUERY_ROUTES, ("/api/tyre",))
        self.assertIn("(path.includes(\"?\") ? \"&\" : \"?\")", function_body("api"))

    def test_the_selected_tyre_is_remembered_in_a_variable_and_falls_back_to_the_first_valid_one(self):
        self.assertRegex(CODE, r"(?m)^let tyreId = null;")
        self.assertNotIn("tyreId", function_body("storeSelection") + function_body("storedSelection"))
        body = function_body("loadTyres")
        self.assertIn("if (tyreEntry() === null) {", body)
        self.assertIn("const first = tyres.find((t) => !t.error);", body)
        self.assertIn("tyreId = first ? first.id : null;", body)
        self.assertIn("if (reload || tyreId !== before) await loadTyre();", body)
        self.assertIn("tyres.find((t) => t.id === tyreId && !t.error) || null", function_body("tyreEntry"))
        self.assertIn("if (seq !== tyreSeq) return;", body)

    def test_the_library_is_loaded_when_the_tab_is_shown_after_every_write_and_when_a_job_ends(self):
        self.assertIn('if (tabs[i] === $("tab-tyres")) loadTyres(true);', function_body("selectTab"))
        self.assertIn("loadTyres(false);", function_body("sendTyreSet"))
        self.assertIn("loadTyres(false);", function_body("sendTyreUnset"))
        self.assertIn("await loadTyres(true);", function_body("changeTyreSource"))
        self.assertIn("await loadTyres(true);", function_body("resetTyre"))
        self.assertIn("await loadTyres(mine.kind !== \"rename\");", function_body("submitTyreDialog"))
        body = function_body("renderTyreControls")
        self.assertIn('if (tyreJobRunning && !running && !$("panel-tyres").hidden) loadTyres(true);', body)
        self.assertIn("renderTyreControls();", function_body("renderButtons"))
        self.assertEqual(re.findall(r"setTimeout\([^;]*[Tt]yre", CODE), [])
        self.assertEqual(len(re.findall(r"setInterval\(", CODE)), 0)

    def test_the_rows_are_loaded_when_a_tyre_is_selected_and_after_a_source_change_or_a_reset(self):
        self.assertIn('$("tyre-select").addEventListener("change", selectTyre);', CODE)
        body = function_body("selectTyre")
        self.assertIn("tyreId = id;", body)
        self.assertIn("loadTyre();", body)
        self.assertIn('$("tyre-source").addEventListener("change", changeTyreSource);', CODE)
        self.assertIn('$("btn-tyre-reset").addEventListener("click", resetTyre);', CODE)
        self.assertIn("buildTyreRows(res.rows, id);", function_body("loadTyre"))

    def test_the_empty_states_are_text_lines_not_hidden_controls(self):
        body = function_body("renderTyres")
        self.assertIn('if (tyreLoaded && tyres.length === 0) addLine(notes, "No tyres yet. Press New tyre to create one.", "empty");', body)
        self.assertIn('"No game tyres found: install a car in the Car Tuner tab first, its tyres become the sources."', body)
        self.assertIn("if (tyreLoaded && tyreSources.length === 0) {", body)
        self.assertNotRegex(body, r'btn-tyre-new"\)\.hidden')
        self.assertRegex(MARKUP, r'<div id="tyre-notes"></div>')

    def test_new_is_off_without_a_source_or_while_a_job_runs_and_rename_and_delete_without_a_tyre_or_while_a_job_runs(self):
        body = function_body("renderTyreControls")
        self.assertIn('const running = !!info && info.job.state === "running";', body)
        self.assertIn('if (running) whyNew = "a job is running";', body)
        self.assertIn('else if (tyreSources.length === 0) whyNew = "install a car first (Car Tuner tab), its game tyres are the sources";', body)
        self.assertIn('if (running) whyEdit = "a job is running";', body)
        self.assertIn('else if (tyreEntry() === null) whyEdit = "select a tyre first";', body)
        self.assertIn('$("btn-tyre-new").disabled = whyNew !== "";', body)
        self.assertIn('$("btn-tyre-new").title = whyNew;', body)
        self.assertIn('for (const id of ["btn-tyre-rename", "btn-tyre-delete"]) {', body)
        self.assertIn('$(id).disabled = whyEdit !== "";', body)
        self.assertIn('$("tyre-source").disabled = running;', body)
        self.assertIn('$("btn-tyre-reset").disabled = running;', body)
        self.assertIn('for (const id of ["tyre-dialog-name", "tyre-dialog-source", "tyre-dialog-ok"]) $(id).disabled = locked;', body)
        self.assertIn("r.field.disabled = running || r.data.applicable === false;", body)
        self.assertIn("r.reset.disabled = running;", body)

    def test_the_options_are_the_names_the_damaged_files_are_not_selectable_and_the_sources_are_labelled(self):
        body = function_body("renderTyres")
        self.assertIn('el("option", "", t.error ? t.id + " (damaged)" : t.name)', body)
        self.assertIn("o.disabled = true;", body)
        self.assertIn('el("option", "", s.label)', body)
        self.assertIn('sourceText(entry.source) + " (not offered by any installed car)"', body)
        self.assertIn("gone.disabled = true;", body)
        self.assertIn("box.value = key;", body)
        self.assertIn('$("tyre-editor").hidden = entry === null;', body)
        self.assertIn('tyres.filter((t) => !t.error)', function_body("neighbourOf"))

    def test_the_rows_get_a_group_row_per_axle_in_the_order_of_the_server(self):
        body = function_body("buildTyreRows")
        self.assertIn('for (const axle of ["front", "rear"]) {', body)
        self.assertIn('buildTyreGroup(axle === "front" ? "Front tyre" : "Rear tyre")', body)
        self.assertIn("list.filter((data) => data.axle === axle)", body)
        self.assertIn("buildRow(item, null)", body)
        self.assertIn("r.save = sendTyreSet;", body)
        self.assertIn("r.clear = sendTyreUnset;", body)
        self.assertIn("r.tyre = id;", body)
        group = function_body("buildTyreGroup")
        self.assertNotIn("button", group)
        self.assertNotIn("expanded", group)
        self.assertIn('el("tr", "group")', group)
        self.assertIn('th.scope = "rowgroup";', group)
        self.assertIn("tr.group th.plain", STYLE)

    def test_the_tyre_rows_share_the_builders_of_the_car_table(self):
        self.assertIn("r.save(r, text)", function_body("commit"))
        self.assertIn("r.save(r, on)", function_body("commit"))
        self.assertIn("r.clear(r)", function_body("buildReset"))
        self.assertIn("save: sendSet, clear: sendUnset", function_body("newRow"))
        self.assertIn("Array.isArray(d.choices) && d.choices.length", function_body("buildField"))
        row = function_body("buildRow")
        self.assertIn('el("span", "badge", "unverified")', row)
        self.assertIn("if (!data.verified) {", row)
        self.assertIn('if (data.applicable === false) valueCell.appendChild(el("div", "msg warn", "Not applicable: " + data.reason));', row)
        self.assertIn('r.tr.classList.toggle("changed", data.changed);', function_body("showRow"))
        self.assertIn("showRow(r, res.row, false);", function_body("sendTyreSet"))
        self.assertIn("showRow(r, res.row, false);", function_body("sendTyreUnset"))
        self.assertNotIn("applyFilter", function_body("buildTyreRows"))

    def test_a_row_shows_the_server_text_of_a_refused_value_and_the_warnings(self):
        body = function_body("sendTyreSet")
        self.assertIn('setMsg(r, res.warnings.join(" "), "warn");', body)
        self.assertIn("setField(r);", body)
        self.assertIn('setMsg(r, e.message, "err");', body)
        self.assertIn('setMsg(r, e.message, "err");', function_body("sendTyreUnset"))
        self.assertIn('setMsg(r, "", "");', function_body("sendTyreUnset"))

    def test_the_dialog_serves_new_rename_and_delete_with_its_confirm_text(self):
        body = function_body("openTyreDialog")
        self.assertIn('"New tyre" : remove ? "Delete tyre" : "Rename tyre"', body)
        self.assertIn('"Delete tyre " + entry.name + "? This cannot be undone."', body)
        self.assertIn('$("tyre-dialog-ok").textContent = remove ? "Delete" : "OK";', body)
        self.assertIn('$("tyre-dialog-name-field").hidden = remove;', body)
        self.assertIn('$("tyre-dialog-source-field").hidden = !create;', body)
        self.assertIn('s.label + " \\u2014 " + s.cars.join(", ")', body)
        self.assertIn("if (create ? tyreSources.length === 0 : entry === null) return;", body)

    def test_the_dialog_stays_open_with_the_message_of_the_server_when_a_write_is_refused(self):
        body = function_body("submitTyreDialog")
        failure = body[body.index("} catch (e) {"):body.index("await loadTyres(")]
        self.assertIn("showTyreDialogError(e.message);", failure)
        self.assertNotIn("closeTyreDialog", failure)
        self.assertIn("mine.busy = false;", failure)
        self.assertIn("return;", failure)
        self.assertIn("tyreId = res.tyre.id;", body)
        self.assertIn("tyreId = neighbourOf(mine.id);", body)
        self.assertIn("if (tyreDialog === mine) closeTyreDialog(true);", body)
        self.assertIn('$("tyre-dialog-error").textContent = text;', function_body("showTyreDialogError"))
        self.assertIn('if (!tyreDialog || tyreDialog.busy || (info && info.job.state === "running")) return;', body)

    def test_enter_confirms_and_escape_cancels_and_the_focus_goes_into_the_dialog_and_back(self):
        key = function_body("tyreDialogKey")
        self.assertIn('ev.key === "Escape"', key)
        self.assertIn("if (!tyreDialog.busy) closeTyreDialog(true);", key)
        self.assertIn('ev.key === "Enter" && ev.target.tagName === "INPUT"', key)
        self.assertIn("submitTyreDialog();", key)
        self.assertIn('$("tyre-dialog").addEventListener("keydown", tyreDialogKey);', CODE)
        opening = function_body("openTyreDialog")
        self.assertIn('$("tyre-dialog-name").focus();', opening)
        self.assertIn('$("tyre-dialog-cancel").focus();', opening)
        self.assertIn("const opener = tyreDialog ? tyreDialog.opener : document.activeElement;", opening)
        closing = function_body("closeTyreDialog")
        self.assertIn("if (restoreFocus) {", closing)
        self.assertIn('[opener, $("tyre-select"), $("btn-tyre-new")].find((n) => n && document.contains(n) && !n.disabled);', closing)
        self.assertIn('(back || $("tab-tyres")).focus();', closing)

    def test_the_new_buttons_are_wired_and_reset_all_asks_first(self):
        for kind, button in (("new", "btn-tyre-new"), ("rename", "btn-tyre-rename"), ("delete", "btn-tyre-delete")):
            with self.subTest(kind):
                self.assertIn('$("%s").addEventListener("click", () => openTyreDialog("%s"));' % (button, kind), CODE)
        self.assertIn('$("tyre-dialog-ok").addEventListener("click", submitTyreDialog);', CODE)
        self.assertIn('$("tyre-dialog-cancel").addEventListener("click", () => closeTyreDialog(true));', CODE)
        self.assertIn("window.confirm(", function_body("resetTyre"))

    def test_writes_to_the_library_go_through_the_one_queue_of_the_edits(self):
        for name in ("changeTyreSource", "resetTyre"):
            with self.subTest(name):
                self.assertIn("queue = queue.then(async () => {", function_body(name))

    def test_the_tab_neither_polls_nor_adds_a_second_fetch(self):
        self.assertEqual(len(re.findall(r"\bfetch\(", CODE)), 1)
        self.assertEqual(len(re.findall(r"\bpollTimer = setTimeout\(", CODE)), 1)

    def test_the_tyre_name_and_the_source_text_enter_the_page_as_text(self):
        for name in ("renderTyres", "openTyreDialog", "buildTyreGroup"):
            with self.subTest(name):
                body = function_body(name)
                self.assertIn("textContent" if name == "openTyreDialog" else "el(", body)
                self.assertNotRegex(body, r"\.html\b|innerHTML")


class TestGarage(unittest.TestCase):
    CAR_PANEL = MARKUP[MARKUP.index('id="panel-car"'):MARKUP.index('id="panel-tyres"')]
    PANEL = re.search(r'<div id="garage" class="panel garage">.*?\n      </div>\n', MARKUP, re.S).group(0)

    @staticmethod
    def tag(ident):
        return re.search(r'<[a-z]+\b[^>]*\bid="%s"[^>]*>' % ident, MARKUP).group(0)

    def test_the_panel_sits_in_the_settings_section_below_the_table(self):
        tuner = MARKUP[MARKUP.index('<section id="tuner"'):MARKUP.index('id="panel-tyres"')]
        self.assertIn('id="garage"', tuner)
        self.assertLess(tuner.index('<div class="toolbar">'), tuner.index('<div class="tablewrap">'))
        self.assertLess(tuner.index('<div class="tablewrap">'), tuner.index('id="garage"'))
        self.assertNotRegex(self.tag("garage"), r"\bhidden\b")
        self.assertIn('id="garage"', self.CAR_PANEL)
        self.assertNotIn('id="garage"', MARKUP[MARKUP.index('id="panel-tyres"'):])

    def test_the_panel_follows_the_table_and_ends_the_settings_section(self):
        tuner = MARKUP[MARKUP.index('<section id="tuner"'):MARKUP.index("</section>", MARKUP.index('<section id="tuner"'))]
        self.assertLess(tuner.index('id="empty"'), tuner.index('id="garage"'))
        self.assertEqual(tuner.count('id="garage"'), 1)

    def test_the_header_is_a_collapsed_toggle_button_with_a_chevron_the_name_and_the_summary(self):
        button = re.search(r'<button id="garage-toggle".*?</button>', self.PANEL, re.S).group(0)
        for part in ('class="grouptoggle"', 'type="button"', 'aria-expanded="false"', 'aria-controls="garage-body"'):
            self.assertIn(part, button)
        self.assertIn('<span class="chev" aria-hidden="true"></span>', button)
        self.assertIn('<span class="gname">Garage tyres</span>', button)
        self.assertIn('<span id="garage-count" class="gcount"></span>', button)
        self.assertIn("garage-body", dom_ids())

    def test_the_body_is_hidden_by_default_and_holds_the_help_the_list_the_reset_button_and_the_lines(self):
        self.assertRegex(self.tag("garage-body"), r"\bhidden>$")
        body = self.PANEL[self.PANEL.index('id="garage-body"'):]
        for text in ("Tick the tyres this car offers in the garage.", "The first ticked tyre in the list is the one the car starts on.",
                     "Own tyres (from the Tyre Creator tab) are listed first.",
                     "Unverified: whether the game accepts extra or removed tyres is not tested yet."):
            self.assertIn(text, body)
        self.assertRegex(body, r'<fieldset>\s*<legend class="sr-only">Tyres offered in the garage</legend>\s*<div id="garage-rows"></div>\s*</fieldset>')
        self.assertIn('<button id="btn-garage-reset" type="button" disabled>Reset to stock tyres</button>', body)
        self.assertIn('<p id="garage-error" class="msg err" role="alert" hidden></p>', body)
        self.assertIn('<p id="garage-missing" class="msg warn" hidden></p>', body)
        self.assertLess(body.index("<fieldset>"), body.index("btn-garage-reset"))
        self.assertLess(body.index("btn-garage-reset"), body.index('id="garage-error"'))

    def test_a_row_is_a_checkbox_in_a_label_with_the_name_and_muted_texts_for_the_kind_and_the_start(self):
        body = function_body("renderGarage")
        self.assertIn('input.type = "checkbox";', body)
        self.assertIn("input.checked = c.ticked;", body)
        self.assertIn('label.append(input, el("span", "", c.label));', body)
        self.assertIn('c.kind === "own" ? "own tyre" : "stock tyre"', body)
        self.assertIn('if (c.start) row.appendChild(el("span", "unit", "starts on this"));', body)
        self.assertIn('el("div", "garage-row")', body)
        self.assertIn("garageRows.push({ key: c.key, input: input });", body)
        self.assertNotRegex(body, r"innerHTML|\.html\b")

    def test_the_summary_counts_the_ticked_tyres_and_names_the_start(self):
        body = function_body("garageSummary")
        self.assertIn('"(" + garage.choices.filter((c) => c.ticked).length + " of " + garage.choices.length + " ticked"', body)
        self.assertIn('(start ? ", starts on " + start.label : "") + ")"', body)
        self.assertIn("garage.choices.find((c) => c.start)", body)
        self.assertIn('$("garage-count").textContent = garageSummary();', function_body("renderGarageToggle"))

    def test_the_panel_is_collapsed_by_default_and_the_toggle_flips_a_separate_variable(self):
        self.assertRegex(CODE, r"(?m)^let garageOpen = false;")
        self.assertNotRegex(CODE, r"garageOpen = true")
        body = function_body("toggleGarage")
        self.assertIn("garageOpen = !garageOpen;", body)
        self.assertNotIn("expanded", body)
        toggle = function_body("renderGarageToggle")
        self.assertIn('$("garage-toggle").setAttribute("aria-expanded", garageOpen ? "true" : "false");', toggle)
        self.assertIn('$("garage-body").hidden = !garageOpen;', toggle)
        self.assertNotIn("remove(", toggle)
        self.assertIn('$("garage-toggle").addEventListener("click", toggleGarage);', CODE)

    def test_expand_all_and_collapse_all_do_not_touch_the_garage(self):
        for name in ("setAllGroups", "toggleGroup", "applyFilter", "revealGroup"):
            with self.subTest(name):
                self.assertNotIn("garage", function_body(name).lower())
        self.assertNotIn("garage", re.search(r'<div class="toolbar">.*?</div>', MARKUP, re.S).group(0))

    def test_another_car_collapses_the_panel_and_forgets_the_old_answer(self):
        body = function_body("switchCar")
        for part in ("garageOpen = false;", "garage = null;", 'garageError = "";', "renderGarage();"):
            self.assertIn(part, body)
        self.assertEqual(len(re.findall(r"(?m)^  garageOpen = false;", CODE)), 1)

    def test_the_garage_is_read_with_the_selection_without_a_body_through_the_one_api_helper(self):
        body = function_body("loadGarage")
        self.assertIn('await api("/api/garage", undefined, target);', body)
        self.assertIn("if (!tableLoaded) return;", body)
        self.assertIn("if (seq !== garageSeq || target !== selection) return;", body)
        self.assertIn("garage = res;", body)
        self.assertIn("garageError = e.message;", body)
        self.assertIn("renderGarage();", body)
        self.assertEqual(len(re.findall(r"\bfetch\(", CODE)), 1)

    def test_the_garage_is_loaded_with_the_table_after_a_tab_change_after_a_job_and_after_create_and_apply(self):
        self.assertIn("loadGarage();", function_body("loadSettings"))
        self.assertLess(function_body("loadSettings").index("tableLoaded = true;"), function_body("loadSettings").index("loadGarage();"))
        self.assertIn('if (tabs[i] === $("tab-car")) loadGarage();', function_body("selectTab"))
        body = function_body("renderGarageControls")
        self.assertIn('if (garageJobRunning && !running && !$("panel-car").hidden) loadGarage();', body)
        self.assertIn("garageJobRunning = running;", body)
        self.assertIn("renderGarageControls();", function_body("renderButtons"))
        self.assertRegex(function_body("startJob"), r"await refresh\(\);\s*loadGarage\(\);")
        self.assertRegex(function_body("submitDialog"), r"await refresh\(\);\s*loadGarage\(\);")
        self.assertEqual(len(re.findall(r"\bpollTimer = setTimeout\(", CODE)), 1)
        self.assertEqual(len(re.findall(r"setInterval\(", CODE)), 0)
        self.assertEqual(re.findall(r"setTimeout\([^;]*[Gg]arage", CODE), [])

    def test_a_change_posts_the_ticked_keys_in_the_order_of_the_choices_through_the_shared_queue(self):
        self.assertIn('$("garage").addEventListener("change", garageChanged);', CODE)
        body = function_body("garageChanged")
        self.assertIn("garageRows.filter((g) => g.input.checked).map((g) => g.key)", body)
        self.assertIn("queue = queue.then(() => sendGarageSet(keys, target));", body)
        self.assertIn("const target = selection;", body)
        send = function_body("sendGarageSet")
        self.assertIn('await api("/api/garage_set", { keys: keys }, target);', send)
        self.assertIn("showGarage(target, res.garage);", send)
        self.assertEqual(set(re.findall(r'\b(\w+):', re.search(r'api\("/api/garage_set", (\{[^}]*\})', CODE).group(1))),
                         set(re.findall(r'body\.get\("(\w+)"\)', inspect.getsource(ts.api_garage_set))) - {"tune"})

    def test_unticking_the_last_tyre_is_prevented_with_a_message_and_no_call(self):
        body = function_body("garageChanged")
        refusal = body[body.index("if (keys.length === 0) {"):body.index("garageError = \"\";")]
        self.assertIn("row.input.checked = true;", refusal)
        self.assertIn('garageError = "Tick at least one tyre.";', refusal)
        self.assertIn("return;", refusal)
        self.assertNotIn("queue", refusal)
        self.assertNotIn("api(", refusal)
        self.assertIn("tick at least one tyre", inspect.getsource(ts.tune.set_garage))

    def test_reset_posts_garage_reset_through_the_queue_and_is_off_unless_the_selection_is_custom(self):
        self.assertIn('$("btn-garage-reset").addEventListener("click", resetGarage);', CODE)
        self.assertIn("queue = queue.then(() => sendGarageReset(target));", function_body("resetGarage"))
        self.assertIn('await api("/api/garage_reset", {}, target);', function_body("sendGarageReset"))
        self.assertIn("showGarage(target, res.garage);", function_body("sendGarageReset"))
        body = function_body("lockGarage")
        self.assertIn('if (!locked && !(garage && garage.custom)) why = "the car offers its stock tyres already";', body)
        self.assertIn('$("btn-garage-reset").disabled = why !== "";', body)
        self.assertIn('$("btn-garage-reset").title = why;', body)

    def test_the_server_answer_wins_and_a_failed_write_reads_the_garage_again_and_keeps_its_message(self):
        show = function_body("showGarage")
        self.assertIn("if (target !== selection) return;", show)
        self.assertIn("garageSeq += 1;", show)
        self.assertIn("garage = answer;", show)
        self.assertIn("renderGarage();", show)
        failed = function_body("garageFailed")
        self.assertLess(failed.index("await loadGarage();"), failed.index("garageError = e.message;"))
        self.assertIn("renderGarageLines();", failed)
        for name in ("sendGarageSet", "sendGarageReset"):
            with self.subTest(name):
                self.assertIn("await garageFailed(target, e);", function_body(name))
        self.assertEqual(inspect.getsource(ts.garage_json).count("tune.garage_choices"), 1)

    def test_the_missing_keys_are_a_warning_line_and_the_error_line_is_the_alert_of_the_panel(self):
        body = function_body("renderGarageLines")
        self.assertIn('"No longer available, Apply is refused until you change the tyre list or reset it: " + missing.join(", ")', body)
        self.assertIn("garage ? garage.missing : []", body)
        self.assertIn('$("garage-missing").hidden = missing.length === 0;', body)
        self.assertIn('$("garage-error").textContent = garageError;', body)
        self.assertIn('$("garage-error").hidden = garageError === "";', body)
        self.assertEqual(CODE.count('setAttribute("role", "alert")'), 1)
        self.assertNotIn("aria-live", self.PANEL)

    def test_the_checkboxes_and_the_reset_button_are_off_while_a_job_runs_or_without_a_base_car(self):
        body = function_body("lockGarage")
        self.assertIn('if (!info) why = serverError || "server not reachable";', body)
        self.assertIn('else if (info.job.state === "running") why = "a job is running";', body)
        self.assertIn('else if (!info.base_present) why = "extract the stock car first";', body)
        self.assertIn("for (const g of garageRows) g.input.disabled = locked;", body)
        self.assertIn("lockGarage();", function_body("renderGarage"))
        self.assertIn("lockGarage();", function_body("renderGarageControls"))

    def test_the_focus_goes_back_to_the_toggled_checkbox_by_its_key_after_the_redraw(self):
        body = function_body("renderGarage")
        self.assertIn("garageRows.find((g) => g.input === document.activeElement)", body)
        self.assertIn("garageRows.find((g) => g.key === focused.key)", body)
        self.assertIn("if (back && !back.input.disabled) back.input.focus();", body)
        self.assertLess(body.index("lockGarage();"), body.index("back.input.focus();"))
        self.assertNotIn("aria-live", function_body("renderGarage") + function_body("renderGarageToggle") + function_body("toggleGarage"))

    def test_the_styles_use_tokens_and_the_chevron_of_the_group_toggle(self):
        for cls in ("garage", "garage-body", "garage-help", "garage-row"):
            with self.subTest(cls):
                self.assertIn(cls, css_classes())
                self.assertIn(cls, used_classes())
        self.assertIn(".garage-help { font-size: 13px; color: var(--color-text-muted); }", STYLE)
        self.assertIn(".garage fieldset { min-width: 0;", STYLE)
        self.assertIn(".garage { padding: 0; overflow-wrap: anywhere; }", STYLE)

    def test_the_server_routes_the_page_calls_exist_and_the_exemption_list_is_gone(self):
        for route in ("/api/garage", "/api/garage_set", "/api/garage_reset"):
            with self.subTest(route):
                self.assertTrue(route in ts.GET_ROUTES or route in ts.POST_ROUTES)
                self.assertIn(route, called_paths())
        self.assertNotIn("SERVER_ONLY", globals())
        self.assertEqual(sorted(TestApiContract.ROUTES), sorted(list(ts.GET_ROUTES) + list(ts.POST_ROUTES)))

    def test_the_fields_of_a_choice_the_page_reads_are_sent_by_the_server(self):
        source = inspect.getsource(ts.tune.garage_choices) + inspect.getsource(ts.tune.garage_entries)
        sent = quoted_words(ts.tune.garage_choices, ts.tune.garage_entries) | set(re.findall(r"\b(\w+)=", source))
        read = set(re.findall(r"\b(?:c|garage)\.(\w+)", "".join(function_body(n) for n in ("renderGarage", "garageSummary", "lockGarage", "renderGarageLines"))))
        self.assertTrue({"key", "kind", "label", "ticked", "start", "choices", "custom", "missing"} <= read, sorted(read))
        self.assertEqual(sorted(read - sent), [])


class TestStartBat(unittest.TestCase):
    def test_it_starts_the_server_script_of_the_repo_from_the_repo_root(self):
        self.assertIn(r'tools\tuner_server.py', BAT)
        self.assertTrue((ROOT / "tools" / "tuner_server.py").is_file())
        self.assertIn(r'cd /d "%~dp0"', BAT)
        self.assertEqual((ROOT / "start_tuner.bat").parent, ROOT)

    def test_paths_are_relative_to_the_batch_file(self):
        self.assertIn("%~dp0", BAT)
        self.assertNotRegex(BAT, r"(?i)\b[a-z]:\\users\\")

    def test_python_runs_isolated_with_the_documented_port_flag(self):
        self.assertRegex(BAT, r'"%PY%" -I tools\\tuner_server\.py --port (?:\d+|%PORT%)')
        self.assertIn("--port", ts.__doc__)

    def test_the_port_is_the_default_port_of_the_server_and_the_readme(self):
        self.assertEqual(set(re.findall(r"(?:--port |127\.0\.0\.1:|PORT=)(\d+)", BAT)), {str(ts.DEFAULT_PORT)})
        self.assertEqual(ts.DEFAULT_PORT, 8080)

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
        self.assertRegex(BAT, r'start "" /min cmd /c "ping -n 3 127\.0\.0\.1 >nul & start http://127\.0\.0\.1:(?:\d+|%PORT%)/ACESCT/"')
        self.assertIn("http://127.0.0.1:%PORT%" + ts.BASE_PATH + "/", BAT)

    # R4-007: the game package is passed on only when the user set GAME in the file
    def test_the_game_package_is_optional_and_passed_on_only_when_set(self):
        self.assertIn('set "GAME="', BAT)
        self.assertIn("if defined GAME (", BAT)
        self.assertIn(r'"%PY%" -I tools\tuner_server.py --port %PORT% --game "%GAME%"', BAT)
        self.assertIn(r'"%PY%" -I tools\tuner_server.py --port %PORT%' + "\n", BAT)
        self.assertIn("--game", ts.__doc__)

    def test_the_file_is_plain_ascii_without_a_byte_order_mark(self):
        raw = (ROOT / "start_tuner.bat").read_bytes()
        raw.decode("ascii")
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))

    def test_every_line_ends_with_crlf(self):
        raw = (ROOT / "start_tuner.bat").read_bytes()
        self.assertEqual(raw.count(b"\n"), raw.count(b"\r\n"))
        self.assertTrue(raw.endswith(b"\r\n"))

    def test_it_tells_the_user_about_the_windows_firewall_question_before_the_server_starts(self):
        line = next(l for l in BAT.splitlines() if l.startswith("echo After the first start Windows asks"))
        self.assertIn("private network", line)
        self.assertIn("choose Allow", line)
        self.assertLess(BAT.index(line), BAT.index('"%PY%" -I tools'))


if __name__ == "__main__":
    unittest.main()
