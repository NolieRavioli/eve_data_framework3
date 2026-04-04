/* applications/sys_status/static/sys_status.js
   Enhanced System Status — SSE for metrics + WebSocket for live telemetry logs.
*/

(function () {
    "use strict";

    var root = document.getElementById("sys-root");
    if (!root) return;

    var streamUrl    = root.dataset.urlStream;
    var tableStatsUrl = root.dataset.urlTableStats;
    var wsBase       = root.dataset.urlWsBase || "";

    /* ── helpers ─────────────────────────────────────────────────────────── */

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function fmtMb(bytes) {
        if (bytes === null || bytes === undefined) return "—";
        return (bytes / 1048576).toFixed(1) + " MB";
    }

    function fmtMs(ms) {
        if (ms === null || ms === undefined) return "—";
        return parseFloat(ms).toFixed(1) + "ms";
    }

    function fmtAgo(sec) {
        if (sec === null || sec === undefined) return "—";
        return parseFloat(sec).toFixed(1) + "s ago";
    }

    /* ── SSE: metric snapshots ───────────────────────────────────────────── */

    function applySnapshot(snap) {
        var w = snap.writer || {};
        setText("w-alive",   w.thread_alive ? "Yes" : "No");
        setText("w-queue",   w.queue_depth  !== undefined ? w.queue_depth : "—");
        setText("w-total",   w.writes_total !== undefined ? w.writes_total : "—");
        setText("w-err",     w.writes_error !== undefined ? w.writes_error : "—");
        setText("w-cp-ago",  fmtAgo(w.last_checkpoint_seconds_ago));
        setText("w-cp-ms",   fmtMs(w.last_checkpoint_ms));
        setText("w-cp-total", w.checkpoints_total !== undefined ? w.checkpoints_total : "—");
        // Performance panel
        setText("w-wait",    fmtMs(w.last_enqueue_wait_ms));
        setText("w-exec",    fmtMs(w.last_execute_ms));
        setText("w-p50",     w.p50_ms !== null && w.p50_ms !== undefined ? Math.round(w.p50_ms) + "ms" : "—");
        setText("w-p95",     w.p95_ms !== null && w.p95_ms !== undefined ? Math.round(w.p95_ms) + "ms" : "—");
        setText("w-p99",     w.p99_ms !== null && w.p99_ms !== undefined ? Math.round(w.p99_ms) + "ms" : "—");

        var db = snap.db_file || {};
        setText("db-size",     fmtMb(db.file_size_bytes));
        setText("db-wal",      db.wal_exists ? "Yes" : "No");
        setText("db-wal-size", fmtMb(db.wal_size_bytes));

        // Refresh hints panel in-place
        if (snap.hints && snap.hints.length) {
            var container = document.getElementById("hints-container");
            if (container) {
                var html = snap.hints.map(function(h) {
                    var color = h.severity === "critical" ? "#e74c3c"
                              : h.severity === "warn"     ? "#f8a84b"
                              : "#4a9eda";
                    return '<div style="border-left:3px solid ' + color + ';padding:0.4rem 0.75rem;background:rgba(0,0,0,.15);border-radius:0 4px 4px 0;margin-bottom:0.4rem">'
                         + '<span style="font-size:0.75rem;text-transform:uppercase;opacity:.6">' + h.severity + ' / ' + h.category + '</span>'
                         + '<div style="font-size:0.9rem;margin:0.15rem 0">' + h.message + '</div>'
                         + '<div style="font-size:0.8rem;opacity:.7">' + h.recommendation + '</div>'
                         + '</div>';
                }).join("");
                container.innerHTML = html;
            }
        }

        var tc = snap.task_counts || {};
        var qc = snap.queue_counts || {};
        setText("tq-pending",  tc.pending  || 0);
        setText("tq-running",  tc.running  || 0);
        setText("tq-complete", tc.complete || 0);
        setText("tq-failed",   tc.failed   || 0);
        setText("tq-pub",      qc.public   || 0);
        setText("tq-prv",      qc.private  || 0);

        var proc = snap.process || {};
        if (proc.memory_rss_mb !== null && proc.memory_rss_mb !== undefined) {
            setText("proc-rss", proc.memory_rss_mb + " MB");
        }
    }

    function connectSSE() {
        if (!streamUrl) return;
        var es = new EventSource(streamUrl);
        es.onmessage = function (event) {
            try { applySnapshot(JSON.parse(event.data)); } catch (e) {}
        };
        es.onerror = function () {
            es.close();
            setTimeout(connectSSE, 8000);
        };
    }

    connectSSE();

    /* ── Table stats (async load on demand) ──────────────────────────────── */

    window.loadTableStats = function() {
        var btn = document.getElementById("btn-load-tables");
        var status = document.getElementById("table-stats-status");
        var container = document.getElementById("table-stats-container");
        if (btn) btn.disabled = true;
        if (status) status.textContent = "Loading…";

        fetch(tableStatsUrl)
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (status) status.textContent = (data.tables || []).length + " tables";
                if (btn) btn.disabled = false;
                renderTableStats(data.tables || [], data.hints || [], container);
            })
            .catch(function(e) {
                if (status) status.textContent = "Error: " + e.message;
                if (btn) btn.disabled = false;
            });
    };

    function renderTableStats(tables, hints, container) {
        if (!container) return;
        var hintHtml = hints.map(function(h) {
            var color = h.severity === "critical" ? "#e74c3c"
                      : h.severity === "warn"     ? "#f8a84b"
                      : "#4a9eda";
            return '<div style="border-left:3px solid ' + color + ';padding:0.3rem 0.6rem;background:rgba(0,0,0,.15);border-radius:0 4px 4px 0;margin-bottom:0.3rem;font-size:0.82rem">'
                 + '<strong>' + h.message + '</strong><br>'
                 + '<span style="opacity:.7">' + h.recommendation + '</span>'
                 + '</div>';
        }).join("");

        var rows = tables.map(function(t) {
            var rows     = t.rows !== null ? t.rows.toLocaleString() : "—";
            var sizeKb   = t.estimated_size_bytes !== null ? Math.round(t.estimated_size_bytes / 1024) + " KB" : "—";
            var cols     = t.column_count !== null ? t.column_count : "—";
            return "<tr>"
                 + "<td class='mono'>" + t.table_name + "</td>"
                 + "<td style='text-align:right'>" + rows + "</td>"
                 + "<td style='text-align:right'>" + sizeKb + "</td>"
                 + "<td style='text-align:right'>" + cols + "</td>"
                 + "</tr>";
        }).join("");

        container.innerHTML = hintHtml
            + "<table class='data-tbl' style='width:100%;margin-top:0.5rem'>"
            + "<thead><tr><th>Table</th><th style='text-align:right'>Rows</th><th style='text-align:right'>Est. Size</th><th style='text-align:right'>Cols</th></tr></thead>"
            + "<tbody>" + rows + "</tbody></table>";
    }

    /* ── WebSocket: live telemetry logs ──────────────────────────────────── */

    var ws = null;
    var logCount = 0;
    var wsReconnectTimer = null;

    var TOPIC_COLORS = {
        db:         "#4a9eda",
        esi:        "#9b59b6",
        market:     "#27ae60",
        scheduler:  "#f39c12",
        structures: "#16a085",
        character:  "#2980b9",
        auth:       "#e74c3c",
        web:        "#95a5a6",
        system:     "#7f8c8d",
        app:        "#1abc9c"
    };

    function getTopicColor(topic) {
        return TOPIC_COLORS[topic] || "#aaa";
    }

    function getSelectedTopics() {
        var cbs = document.querySelectorAll(".topic-cb:checked");
        return Array.prototype.map.call(cbs, function(cb) { return cb.dataset.topic; });
    }

    function wsSetStatus(msg, ok) {
        var el = document.getElementById("ws-status");
        if (el) {
            el.textContent = msg;
            el.style.color = ok ? "#27ae60" : "#e74c3c";
        }
    }

    function wsSubscribe(topics) {
        if (ws && ws.readyState === WebSocket.OPEN && topics.length) {
            ws.send(JSON.stringify({ action: "subscribe", topics: topics }));
            // Fetch history for each subscribed topic
            topics.forEach(function(t) {
                ws.send(JSON.stringify({ action: "history", topic: t, limit: 50 }));
            });
        }
    }

    function addLogEntry(entry, prepend) {
        var feed = document.getElementById("log-feed");
        if (!feed) return;

        // Clear the placeholder
        var placeholder = feed.querySelector(".muted");
        if (placeholder && placeholder.textContent.indexOf("Waiting") >= 0) {
            feed.innerHTML = "";
        }

        logCount++;
        var el = document.createElement("div");
        el.style.cssText = "border-left:2px solid " + getTopicColor(entry.topic)
            + ";padding:0.1rem 0.4rem;margin-bottom:0.15rem;line-height:1.4;word-break:break-word";

        var ts = (entry.ts || "").replace("T", " ").replace("Z", "").slice(0, 19);
        var levelColor = entry.level === "WARNING" || entry.level === "WARN" ? "#f8a84b"
                       : entry.level === "ERROR" || entry.level === "CRITICAL" ? "#e74c3c"
                       : "#aaa";
        el.innerHTML = '<span style="color:#666;font-size:0.7rem">' + ts + '</span>'
                     + ' <span style="color:' + levelColor + ';font-size:0.7rem">[' + (entry.level || '?') + ']</span>'
                     + ' <span style="color:' + getTopicColor(entry.topic) + ';font-size:0.7rem">' + (entry.topic || '') + '</span>'
                     + ' <span>' + (entry.message || '') + '</span>';

        if (prepend) {
            feed.insertBefore(el, feed.firstChild);
        } else {
            feed.appendChild(el);
        }

        var countEl = document.getElementById("log-count");
        if (countEl) countEl.textContent = logCount + " entries";

        var autoScroll = document.getElementById("log-autoscroll");
        if (autoScroll && autoScroll.checked && !prepend) {
            feed.scrollTop = feed.scrollHeight;
        }
    }

    window.logFeedClear = function() {
        var feed = document.getElementById("log-feed");
        if (feed) {
            feed.innerHTML = '';
            logCount = 0;
            var countEl = document.getElementById("log-count");
            if (countEl) countEl.textContent = "0 entries";
        }
    };

    function connectWS() {
        if (wsReconnectTimer) {
            clearTimeout(wsReconnectTimer);
            wsReconnectTimer = null;
        }
        // Build WebSocket URL from current protocol + host
        var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
        var wsUrl = proto + "//" + window.location.host + "/telemetry/ws";

        try {
            ws = new WebSocket(wsUrl);
        } catch (e) {
            wsSetStatus("unavailable", false);
            return;
        }

        ws.onopen = function() {
            wsSetStatus("connected", true);
            var topics = getSelectedTopics();
            wsSubscribe(topics);
        };

        ws.onmessage = function(event) {
            try {
                var msg = JSON.parse(event.data);
                if (msg.type === "entry") {
                    addLogEntry(msg, false);
                } else if (msg.type === "history") {
                    // History entries arrive newest-last; insert them in order but
                    // they represent past data so we don't trigger autoscroll.
                    (msg.entries || []).forEach(function(e) { addLogEntry(e, false); });
                } else if (msg.type === "error") {
                    wsSetStatus("error: " + msg.message, false);
                }
            } catch (e) {}
        };

        ws.onclose = function() {
            wsSetStatus("disconnected — reconnecting…", false);
            wsReconnectTimer = setTimeout(connectWS, 5000);
        };

        ws.onerror = function() {
            wsSetStatus("error", false);
            ws.close();
        };
    }

    // Topic checkbox change — re-subscribe
    document.addEventListener("change", function(evt) {
        if (!evt.target || !evt.target.classList.contains("topic-cb")) return;
        var topic = evt.target.dataset.topic;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        if (evt.target.checked) {
            wsSubscribe([topic]);
        } else {
            ws.send(JSON.stringify({ action: "unsubscribe", topics: [topic] }));
        }
    });

    connectWS();

}());

