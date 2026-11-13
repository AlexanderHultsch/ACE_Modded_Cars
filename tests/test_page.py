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


# server routes the page does not call yet: take a route out of this list when the page starts to use it
SERVER_ONLY = ("/api/tyres", "/api/tyre", "/api/tyre_new", "/api/tyre_rename", "/api/tyre_source", "/api/tyre_set", "/api/tyre_unset",
               "/api/tyre_reset", "/api/tyre_delete", "/api/garage", "/api/garage_set", "/api/garage_reset")


class TestApiContract(unittest.TestCase):
    ROUTES = [r for r in list(ts.GET_ROUTES) + list(ts.POST_ROUTES) if r not in SERVER_ONLY]

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
        for route in (r for r in ts.GET_ROUTES if r in self.ROUTES):
            with self.subTest(route):
                self.assertRegex(CODE, r'api\("%s", undefined' % route)
                self.assertNotRegex(CODE, r'(?:api|startJob)\("%s", \{' % route)
        for route in (r for r in ts.POST_ROUTES if r in self.ROUTES):
            with self.subTest(route):
                self.assertRegex(CODE, r'(?:api|startJob)\("%s", \{' % route)
                self.assertNotRegex(CODE, r'api\("%s", undefined' % route)

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
        self.assertEqual(len(calls), 8, calls)
        for call in calls:
            with self.subTest(call):
                self.assertRegex(call, r", (?:want|target|r\.target|selection)$")
        self.assertEqual(sorted(set(re.findall(r'\b(?:api|startJob)\("(/api/[a-z_]+)"', CODE))), sorted(self.ROUTES))
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
        self.assertEqual(set(re.findall(r'"(/api/[^"?]*)"', CODE)), set(self.ROUTES))

    def test_the_state_fields_the_page_reads_are_sent_by_the_server(self):
        sent = quoted_words(ts.api_state, ts.installed_info, ts.modded_cars, ts.tune_proposals) | set(ts.JOB)
        read = set(re.findall(r"\binfo\.(\w+)", CODE)) | set(re.findall(r"\binst\.(\w+)", CODE)) | set(re.findall(r"\bjob\.(\w+)", CODE))
        self.assertTrue({"base_present", "game_running", "job", "installed", "cars", "car", "work", "tune", "modded", "modded_error",
                         "proposed_new_id", "proposed_suffix", "stock_id_length"} <= read, sorted(read))
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
        for label in ("Extract stock car", "changed only", "reset", "Reset all"):
            self.assertIn(label, README)

    def test_the_table_has_the_four_documented_columns_in_order(self):
        heads = re.findall(r'<th scope="col">(.*?)</th>', MARKUP)
        self.assertEqual(heads, ["Variable name", "Value", "Default (for the selected car)", "Description"])

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
        self.assertIn('"(" + g.rows.length + (g.rows.length === 1 ? " setting, " : " settings, ") + changed + " changed)"', body)
        self.assertIn("if (r.data.changed) changed += 1;", body)
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

    def test_the_install_button_sits_in_the_selector_row_next_to_the_car_selector_and_is_off_until_the_page_knows_better(self):
        panel = MARKUP[MARKUP.index('id="panel-car"'):MARKUP.index('id="panel-tyres"')]
        row = re.search(r'<div class="bar">.*?<section id="dialog"', panel, re.S).group(0)
        button = '<button id="btn-install-tested" type="button" disabled>Install the tested cars</button>'
        self.assertIn(button, row)
        self.assertLess(row.index('id="car-select"'), row.index(button))
        self.assertLess(row.index(button), row.index('<div class="actions">'))

    def test_the_label_counts_the_tested_cars_of_the_state(self):
        body = function_body("renderButtons")
        self.assertIn("const tested = info && info.cars ? info.cars.filter((c) => c.tested) : [];", body)
        self.assertIn('$("btn-install-tested").textContent = tested.length ? "Install the " + tested.length + " tested cars" : "Install the tested cars";', body)
        self.assertNotRegex(CODE, r"Install the \d")

    def test_the_install_button_is_off_while_a_job_runs_without_info_or_with_every_tested_car_installed(self):
        body = function_body("renderButtons")
        self.assertIn('if (!info) whyInstall = serverError || "server not reachable";', body)
        self.assertIn('else if (running) whyInstall = "a job is running";', body)
        self.assertIn('else if (tested.every((c) => c.extracted)) whyInstall = "every tested car is installed already";', body)
        self.assertIn('$("btn-install-tested").disabled = whyInstall !== "";', body)
        self.assertIn('$("btn-install-tested").title = whyInstall;', body)

    def test_the_install_button_starts_the_job_of_all_tested_cars(self):
        self.assertIn('$("btn-install-tested").addEventListener("click", () => startJob("/api/install_tested", {}));', CODE)
        self.assertIn('$("btn-init").addEventListener("click", () => startJob("/api/init", {}));', CODE)

    def test_the_progress_panel_names_both_install_jobs(self):
        body = function_body("renderProgress")
        self.assertIn('job.kind === "init" ? "Install car" : job.kind === "install_tested" ? "Install the tested cars" : "Apply"', body)
        self.assertIn('if (job.kind === "init") addLine(box, "The car is installed, the table is available.");', body)
        self.assertIn('if (job.kind === "install_tested") addLine(box, "The tested cars are installed.");', body)
        self.assertNotIn("Extract stock car", body)

    def test_the_table_is_not_loaded_while_either_install_job_runs(self):
        body = function_body("refresh")
        self.assertIn('const extracting = !!info && ["init", "install_tested"].includes(info.job.kind) && info.job.state === "running";', body)
        self.assertIn("!tableLoaded && !extracting", body)

    def test_every_job_kind_the_progress_panel_knows_is_started_by_the_server(self):
        kinds = set(re.findall(r'job\.kind === "(\w+)"', function_body("renderProgress")))
        self.assertEqual(kinds, {"apply", "init", "install_tested"})
        self.assertEqual(kinds - set(re.findall(r'run_job\("(\w+)"', inspect.getsource(ts))), set())


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
        for ident in ("car-select", "btn-install-tested", "btn-apply", "btn-duplicate", "dialog", "name-host", "untested", "status",
                      "progress", "init-panel", "tuner", "search", "rows"):
            with self.subTest(ident):
                self.assertIn('id="%s"' % ident, self.CAR_PANEL)
                self.assertNotIn('id="%s"' % ident, self.TYRES_PANEL)

    def test_the_tyre_panel_is_a_placeholder_with_a_heading_and_one_paragraph(self):
        self.assertIn("<h2>Tyre Creator</h2>", self.TYRES_PANEL)
        self.assertEqual(re.findall(r"<p\b[^>]*>(.*?)</p>", self.TYRES_PANEL),
                         ["Tyres you create here are saved once and can be ticked in the garage list of any modded car in the Car Tuner tab."])
        self.assertEqual(re.findall(r'\bid="([^"]+)"', self.TYRES_PANEL), ["panel-tyres"])

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
        self.assertRegex(BAT, r'"%PY%" -I tools\\tuner_server\.py --port (?:\d+|%PORT%)')
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
        self.assertRegex(BAT, r'start "" /min cmd /c "ping -n 3 127\.0\.0\.1 >nul & start http://127\.0\.0\.1:(?:\d+|%PORT%)/"')

    # R4-007: the game package is passed on only when the user set GAME in the file
    def test_the_game_package_is_optional_and_passed_on_only_when_set(self):
        self.assertIn('set "GAME="', BAT)
        self.assertIn("if defined GAME (", BAT)
        self.assertIn(r'"%PY%" -I tools\tuner_server.py --port %PORT% --game "%GAME%"', BAT)
        self.assertIn(r'"%PY%" -I tools\tuner_server.py --port %PORT%' + "\n", BAT)
        self.assertIn("--game", ts.__doc__)

    def test_the_file_is_plain_ascii_without_a_byte_order_mark(self):
        raw = (ROOT / "tuner" / "start_tuner.bat").read_bytes()
        raw.decode("ascii")
        self.assertFalse(raw.startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
