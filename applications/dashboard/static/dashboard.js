/* Dashboard — client-side interactivity */
(function () {
  "use strict";

  /* ── Bus WebSocket (sub-phase 5d) ────────────────────────────────── */
  var root = document.getElementById("dash-app");
  if (!root) return;

  var wsUrl = root.dataset.urlWs;
  if (!wsUrl) return;

  var protocol = location.protocol === "https:" ? "wss:" : "ws:";
  var ws = new WebSocket(protocol + "//" + location.host + wsUrl);

  ws.onmessage = function (event) {
    try {
      var msg = JSON.parse(event.data);
      if (msg.type !== "publish" || !msg.topic) return;

      if (msg.topic.endsWith("/training")) {
        /* Skill training update — could refresh a badge */
      } else if (msg.topic.endsWith("/wallet")) {
        /* Wallet balance change */
      } else if (msg.topic.endsWith("/notifications")) {
        /* New notification count */
      }
    } catch (e) {
      /* ignore parse errors */
    }
  };

  ws.onopen = function () {
    /* Auto-subscribe to character topics */
    var ownerId = root.dataset.ownerId;
    if (ownerId) {
      ws.send(JSON.stringify({
        action: "subscribe",
        topics: [
          "character/" + ownerId + "/training",
          "character/" + ownerId + "/wallet",
          "character/" + ownerId + "/notifications"
        ]
      }));
    }
  };
}());
