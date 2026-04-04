/* applications/sys_status/static/sys_status.js
   Live SSE updates for the System Status page.
   Updates each metric field in-place as data arrives — no full re-render.
*/

(function () {
    "use strict";

    var root = document.getElementById("sys-root");
    if (!root) return;

    var streamUrl = root.dataset.urlStream;
    if (!streamUrl) return;

    /* ── helpers ─────────────────────────────────────────────────────────── */

    function setText(id, value) {
        var el = document.getElementById(id);
        if (el) el.textContent = value;
    }

    function fmtMb(bytes) {
        return bytes === null ? "—" : (bytes / 1048576).toFixed(1) + " MB";
    }

    function fmtMs(ms) {
        return (ms === null || ms === undefined) ? "—" : ms.toFixed(1) + "ms";
    }

    function fmtAgo(sec) {
        if (sec === null || sec === undefined) return "—";
        return sec.toFixed(1) + "s ago";
    }

    /* ── SSE handler ─────────────────────────────────────────────────────── */

    function applySnapshot(snap) {
        var w = snap.writer || {};
        setText("w-alive",     w.thread_alive ? "Yes" : "No");
        setText("w-queue",     w.queue_depth  !== undefined ? w.queue_depth : "—");
        setText("w-total",     w.writes_total !== undefined ? w.writes_total : "—");
        setText("w-err",       w.writes_error !== undefined ? w.writes_error : "—");
        setText("w-latency",   fmtMs(w.last_write_latency_ms));
        setText("w-cp-ago",    fmtAgo(w.last_checkpoint_seconds_ago));
        setText("w-cp-ms",     fmtMs(w.last_checkpoint_ms));
        setText("w-cp-total",  w.checkpoints_total !== undefined ? w.checkpoints_total : "—");

        var db = snap.db_file || {};
        setText("db-size",     fmtMb(db.file_size_bytes));
        setText("db-wal",      db.wal_exists ? "Yes" : "No");
        setText("db-wal-size", (db.wal_size_bytes / 1048576).toFixed(2) + " MB");

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

    /* ── connect ─────────────────────────────────────────────────────────── */

    function connect() {
        var es = new EventSource(streamUrl);

        es.onmessage = function (event) {
            try {
                applySnapshot(JSON.parse(event.data));
            } catch (e) {
                /* swallow parse errors — keepalive comments don't reach here */
            }
        };

        es.onerror = function () {
            es.close();
            /* Retry after 8 s on error */
            setTimeout(connect, 8000);
        };
    }

    connect();
}());
