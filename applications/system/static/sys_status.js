/* applications/sys_status/static/sys_status.js
   System Status — process health + thread breakdown + live bus log viewer.
   Process stats are received via the shared /bus connection (system/process topic)
   rather than a separate /system/ws/process socket.
*/

(function () {
    "use strict";

    var root = document.getElementById("sys-root");
    if (!root) return;

    /* ── helpers ─────────────────────────────────────────────────────────── */

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function escHtml(s) {
        if (!s) return '';
        return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
    }

    /* ── Process stats handler (called from bus message) ─────────────────── */

    function applyProcessSnapshot(p) {
        if (!p) return;
        if (p.memory_rss_mb != null) setText("proc-rss", p.memory_rss_mb + " MB");
        if (p.thread_count  != null) setText("proc-threads", p.thread_count);
        if (p.cpu_percent   != null) setText("proc-cpu", p.cpu_percent + "%");
        if (p.threads       != null) renderThreadTable(p.threads, p.thread_cpu || {});
    }

    /* ── Thread breakdown table ──────────────────────────────────────────── */

    function renderThreadTable(threads, threadCpu) {
        var card  = document.getElementById("thread-breakdown-card");
        var tbody = document.getElementById("thread-tbody");
        if (!card || !tbody || !threads.length) return;

        card.style.display = "";
        var html = "";
        threads.forEach(function (t) {
            var cpu = threadCpu[String(t.native_id)] || {};
            var userTime = cpu.user_time != null ? cpu.user_time.toFixed(3) : "—";
            var sysTime  = cpu.system_time != null ? cpu.system_time.toFixed(3) : "—";
            var daemonMark = t.daemon ? '<span style="opacity:.5">D</span>' : "";
            html +=
                "<tr style=\"border-top:1px solid rgba(255,255,255,.06)\">" +
                  "<td style=\"padding:0.2rem 0.5rem;font-family:monospace;font-size:0.78rem\">" +
                    escHtml(t.name || "?") + "</td>" +
                  "<td style=\"padding:0.2rem 0.5rem;text-align:center\">" + daemonMark + "</td>" +
                  "<td style=\"padding:0.2rem 0.5rem;text-align:right;font-variant-numeric:tabular-nums\">" +
                    userTime + "</td>" +
                  "<td style=\"padding:0.2rem 0.5rem;text-align:right;font-variant-numeric:tabular-nums\">" +
                    sysTime + "</td>" +
                "</tr>";
        });
        tbody.innerHTML = html;
    }

    /* ── WebSocket: live bus logs + system/process topic ────────────────── */

    var ws = null;
    var logCount = 0;
    var wsReconnectTimer = null;

    var TOPIC_COLORS = {
        "log/db":         "#4a9eda",
        "log/esi":        "#9b59b6",
        "log/market":     "#27ae60",
        "log/scheduler":  "#f39c12",
        "log/structures": "#16a085",
        "log/character":  "#2980b9",
        "log/auth":       "#e74c3c",
        "log/web":        "#95a5a6",
        "log/system":     "#7f8c8d",
        "log/app":        "#1abc9c",
        "esi/rate":       "#8e44ad",
        "db/stats":       "#3498db"
    };

    function getTopicColor(topic) {
        return TOPIC_COLORS[topic] || "#aaa";
    }

    function getSelectedTopics() {
        var cbs = document.querySelectorAll(".topic-cb:checked");
        return Array.prototype.map.call(cbs, function (cb) { return cb.dataset.topic; });
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
            topics.forEach(function (t) {
                ws.send(JSON.stringify({ action: "history", topic: t, limit: 50 }));
            });
        }
    }

    function addLogEntry(entry) {
        var feed = document.getElementById("log-feed");
        if (!feed) return;

        // Clear placeholder
        var ph = feed.querySelector(".muted");
        if (ph && ph.textContent.indexOf("Waiting") >= 0) feed.innerHTML = "";

        logCount++;
        var el = document.createElement("div");
        el.style.cssText = "border-left:2px solid " + getTopicColor(entry.topic)
            + ";padding:0.1rem 0.4rem;margin-bottom:0.15rem;line-height:1.4;word-break:break-word";

        var ts = (entry.ts || "").replace("T", " ").replace("Z", "").slice(0, 19);
        var levelColor = (entry.level === "WARNING" || entry.level === "WARN") ? "#f8a84b"
                       : (entry.level === "ERROR" || entry.level === "CRITICAL") ? "#e74c3c"
                       : "#aaa";
        el.innerHTML =
            '<span style="color:#666;font-size:0.7rem">' + escHtml(ts) + '</span>' +
            ' <span style="color:' + levelColor + ';font-size:0.7rem">[' + escHtml(entry.level || '?') + ']</span>' +
            ' <span style="color:' + getTopicColor(entry.topic) + ';font-size:0.7rem">' + escHtml(entry.topic || '') + '</span>' +
            ' <span>' + escHtml(entry.message || '') + '</span>';

        feed.appendChild(el);

        var countEl = document.getElementById("log-count");
        if (countEl) countEl.textContent = logCount + " entries";

        var autoScroll = document.getElementById("log-autoscroll");
        if (autoScroll && autoScroll.checked) feed.scrollTop = feed.scrollHeight;
    }

    function clearLog() {
        var feed = document.getElementById("log-feed");
        if (feed) {
            feed.innerHTML = "";
            logCount = 0;
            setText("log-count", "0 entries");
        }
    }

    function connectWS() {
        if (wsReconnectTimer) { clearTimeout(wsReconnectTimer); wsReconnectTimer = null; }

        var proto = location.protocol === "https:" ? "wss:" : "ws:";
        var wsUrl = proto + "//" + location.host + "/bus";

        try { ws = new WebSocket(wsUrl); } catch (e) { wsSetStatus("unavailable", false); return; }

        ws.onopen = function () {
            wsSetStatus("connected", true);
            // Always subscribe to system/process for the process stats panel.
            var logTopics = getSelectedTopics();
            var allTopics = ["system/process"].concat(
                logTopics.filter(function (t) { return t !== "system/process"; })
            );
            wsSubscribe(allTopics);
        };
        ws.onmessage = function (event) {
            try {
                var msg = JSON.parse(event.data);
                if (msg.type === "entry") {
                    addLogEntry(msg);
                } else if (msg.type === "history") {
                    if (msg.topic === "system/process") {
                        // Use the most recent entry for initial process stats.
                        var entries = msg.entries || [];
                        if (entries.length) applyProcessSnapshot(entries[entries.length - 1].data);
                    } else {
                        (msg.entries || []).forEach(function (e) { addLogEntry(e); });
                    }
                } else if (msg.type === "publish") {
                    if (msg.topic === "system/process") {
                        applyProcessSnapshot(msg.data);
                    }
                } else if (msg.type === "error") {
                    wsSetStatus("error: " + msg.message, false);
                }
            } catch (e) {}
        };
        ws.onclose = function () {
            wsSetStatus("disconnected — reconnecting…", false);
            wsReconnectTimer = setTimeout(connectWS, 5000);
        };
        ws.onerror = function () { wsSetStatus("error", false); ws.close(); };
    }

    // Topic checkbox change — re-subscribe (log topics only; system/process is always on)
    document.addEventListener("change", function (evt) {
        if (!evt.target || !evt.target.classList.contains("topic-cb")) return;
        var topic = evt.target.dataset.topic;
        if (!ws || ws.readyState !== WebSocket.OPEN) return;
        if (evt.target.checked) {
            wsSubscribe([topic]);
        } else {
            ws.send(JSON.stringify({ action: "unsubscribe", topics: [topic] }));
        }
    });

    // Clear button
    var clearBtn = document.getElementById("btn-clear-log");
    if (clearBtn) clearBtn.addEventListener("click", clearLog);

    connectWS();

}());
