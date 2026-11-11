/* Hina AE86 speed chime: local diagnostic/recovery prototype, 23 October 2026.
 * Cohtml WebM media; no engine-bank integration or audible acceptance claimed.
 * Source recording: drooler, Chime-Strong.flac, Freesound 660862, CC0.
 */
(function () {
    "use strict";
    var carId = "ks_ae86_beginner_h_01";
    var logged = {};
    var logCount = 0;
    function report(key, value) {
        // At most 32 short lines per native display context, never per frame.
        if (logged[key] || logCount >= 32) return;
        logged[key] = true; logCount++;
        try { console.log("HINA_CHIME " + carId + " " + key + " " + JSON.stringify(value)); } catch (_) {}
    }
    if (window.__hinaAe86ChimeInstalled) return;
    if (typeof CarDisplay !== "object" || typeof CarDisplay.process !== "function") {
        report("bootstrap-unavailable", {}); return;
    }
    window.__hinaAe86ChimeInstalled = true;

    var displayPath = "content/cars/" + carId + "/displays/chime.html";
    var thresholdKmh = 105;
    var staleAfterMs = 500;
    var video = null;
    var desired = false;
    var failed = false;
    var disposed = false;
    var lastUpdate = -Infinity;
    var timer = null;
    var generation = 0;
    var pending = false;
    var retryAt = null;
    var rejectedAttempts = 0;
    var originalProcess = CarDisplay.process;

    function path(value) {
        return typeof value === "string" ? value.replace(/^(?:file|coui):\/\/\/?/i, "")
            .replace(/\\/g, "/").replace(/^\/+/, "").toLowerCase() : "";
    }
    function primitive(value) {
        return { type: typeof value, value: typeof value === "string" ? value.slice(0, 160) :
            (typeof value === "number" || typeof value === "boolean" ? value : null) };
    }
    function snapshot(data) {
        var low = data && data.low_frequency;
        var pages = low && low.display_htmls;
        return {
            player: primitive(data && data.is_player_car), speed: primitive(data && data.display_speed_kmh),
            ignition: primitive(low && low.electronics && low.electronics.is_ignition_on),
            hidden: primitive(document.hidden), url: path(location.href),
            pagesType: typeof pages, pagesArray: Array.isArray(pages),
            pages: Array.isArray(pages) ? pages.slice(0, 4).map(path) : [],
            focus: primitive(data && data.focused_car_id), playerId: primitive(data && data.player_car_id)
        };
    }
    function gate(data) {
        if (!data) return "missing-model";
        if (data.is_player_car !== true) return "not-player";
        if (typeof data.display_speed_kmh !== "number" || !isFinite(data.display_speed_kmh)) return "invalid-speed";
        if (data.display_speed_kmh < thresholdKmh) return "below-threshold";
        if (!data.low_frequency || !data.low_frequency.electronics ||
            data.low_frequency.electronics.is_ignition_on !== true) return "ignition-off";
        if (data.focused_car_id && data.player_car_id && data.focused_car_id !== data.player_car_id) return "focus-mismatch";
        if (path(location.href) !== displayPath) return "wrong-page-url";
        // EVO leaves display_htmls empty for this optional part even while its
        // native display is loaded. The part owns this page's lifetime; checking
        // that unrelated list suppresses every valid threshold crossing.
        if (document.hidden === true) return "hidden";
        return "ready";
    }
    function canPlayNow() {
        return desired && !failed && !disposed && document.hidden !== true &&
            Date.now() - lastUpdate <= staleAfterMs;
    }
    function mediaState(error) {
        return {
            name: error && typeof error.name === "string" ? error.name.slice(0, 80) : "",
            message: error && typeof error.message === "string" ? error.message.slice(0, 160) : "",
            code: video && video.error ? video.error.code : null,
            readyState: video ? video.readyState : null, networkState: video ? video.networkState : null,
            paused: video ? video.paused : null, muted: video ? video.muted : null,
            currentTime: video ? video.currentTime : null
        };
    }
    function silence() {
        generation++; pending = false; retryAt = null;
        if (!video) return;
        // Mute synchronously before the native asynchronous pause.
        try { video.muted = true; } catch (_) {}
        try { video.pause(); } catch (_) {}
        try { video.currentTime = 0; } catch (_) {}
    }
    function ensureVideo() {
        if (video) return video;
        video = document.createElement("video");
        video.id = "hina-ae86-speed-chime";
        video.setAttribute("aria-hidden", "true");
        video.setAttribute("playsinline", "");
        video.preload = "auto"; video.loop = true; video.autoplay = false;
        video.muted = true; video.volume = 0.6;
        video.style.cssText = "position:absolute;left:0;top:0;width:2px;height:2px;pointer-events:none;";
        ["loadedmetadata", "canplay", "pause", "ended"].forEach(function (event) {
            video.addEventListener(event, function () { report("media-" + event, mediaState()); });
        });
        video.addEventListener("error", function () {
            report("media-error", mediaState()); failed = true; desired = false; silence();
        });
        video.addEventListener("playing", function () {
            report("media-playing", mediaState()); if (!canPlayNow()) silence();
        });
        video.src = "ae86_chime_strong.webm";
        document.body.appendChild(video);
        report("media-created", mediaState());
        return video;
    }
    function rejected(error, attempt, kind) {
        // A completed request from a superseded play must not silence its successor.
        if (attempt !== generation || disposed) { report("old-play-rejection", { kind: kind }); return; }
        report("play-" + kind + "-" + rejectedAttempts, mediaState(error));
        rejectedAttempts++;
        silence();
        if (rejectedAttempts >= 3) {
            failed = true; desired = false; report("play-retries-exhausted", {});
        } else if (canPlayNow()) {
            // Maximum two retries per view; preserve player/page/speed gates.
            retryAt = Date.now() + 1000;
        }
    }
    function start() {
        if (!canPlayNow() || pending) return;
        var attempt = ++generation;
        pending = true; retryAt = null;
        try {
            // Creation must be guarded too, so failure cannot skip native processing.
            var media = ensureVideo();
            media.muted = false;
            report("play-request", mediaState());
            var result = media.play();
            if (result && typeof result.then === "function") {
                result.then(function () {
                    if (attempt !== generation) return;
                    pending = false; report("play-resolved", mediaState());
                    if (!canPlayNow()) silence();
                }, function (error) { rejected(error, attempt, "rejected"); });
            } else {
                pending = false; report("play-returned-without-promise", mediaState());
            }
        } catch (error) { rejected(error, attempt, "threw"); }
    }
    function update(data) {
        lastUpdate = Date.now();
        var reason = disposed ? "disposed" : failed ? "failed" : gate(data);
        report("gate-" + reason, snapshot(data));
        if (data && typeof data.display_speed_kmh === "number" && data.display_speed_kmh >= thresholdKmh)
            report("first-at-threshold", snapshot(data));
        var next = reason === "ready";
        if (next === desired) return;
        desired = next;
        if (desired) start(); else silence();
    }
    CarDisplay.process = function () {
        try { update(arguments[0]); }
        catch (error) { report("controller-error", mediaState(error)); failed = true; desired = false; silence(); }
        return originalProcess.apply(this, arguments);
    };
    timer = setInterval(function () {
        if (desired && !canPlayNow()) {
            report("watchdog-stop", { ageMs: Date.now() - lastUpdate, hidden: document.hidden });
            desired = false; silence();
        } else if (retryAt !== null && Date.now() >= retryAt) {
            report("play-retry-" + rejectedAttempts, {}); start();
        }
    }, 100);
    document.addEventListener("visibilitychange", function () {
        report("visibility-change", { hidden: document.hidden });
        if (document.hidden === true) { desired = false; silence(); }
    });
    function dispose() {
        disposed = true; desired = false; report("dispose", {}); silence();
        if (timer !== null) { clearInterval(timer); timer = null; }
    }
    window.addEventListener("pagehide", dispose);
    window.addEventListener("beforeunload", dispose);
    window.addEventListener("unload", dispose);
    report("installed", { url: path(location.href), hidden: primitive(document.hidden), thresholdKmh: thresholdKmh });
}());
