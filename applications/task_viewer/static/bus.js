/**
 * bus.js — shared /bus WebSocket manager.
 *
 * Usage:
 *   1. Add a marker element to any page that needs live data:
 *        <div id="bus-root" data-subscriptions='["esi/rate","task/events"]'></div>
 *   2. Load this script. It connects once on DOMContentLoaded.
 *   3. Other scripts listen for the 'bus:message' event on document:
 *        document.addEventListener('bus:message', function(e) {
 *          var topic = e.detail.topic;
 *          var data  = e.detail.data;
 *          ...
 *        });
 *   4. To change subscriptions when switching views (e.g. modal/tab):
 *        window.Bus.setSubscriptions(["esi/rate"]);
 *
 * Only one WebSocket is opened per page. Reconnects automatically on close.
 */
(function () {
  'use strict';

  var _ws = null;
  var _subscribed = [];
  var _reconnectDelay = 3000;
  var _intentionallyClosed = false;

  function dispatch(topic, data, full) {
    var ev = new CustomEvent('bus:message', {
      detail: { topic: topic, data: data, _raw: full },
    });
    document.dispatchEvent(ev);
  }

  function subscribe(topics) {
    if (!_ws || _ws.readyState !== WebSocket.OPEN) return;
    _ws.send(JSON.stringify({ action: 'subscribe', topics: topics }));
  }

  function unsubscribe(topics) {
    if (!_ws || _ws.readyState !== WebSocket.OPEN || !topics.length) return;
    _ws.send(JSON.stringify({ action: 'unsubscribe', topics: topics }));
  }

  function connect(initialTopics) {
    if (_ws && _ws.readyState <= WebSocket.OPEN) return; // already open/connecting
    _intentionallyClosed = false;

    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try {
      _ws = new WebSocket(proto + '//' + location.host + '/bus');
    } catch (e) {
      setTimeout(function () { connect(initialTopics); }, _reconnectDelay);
      return;
    }

    _ws.onopen = function () {
      _reconnectDelay = 3000;
      if (initialTopics && initialTopics.length) {
        subscribe(initialTopics);
        _subscribed = initialTopics.slice();
      }
    };

    _ws.onmessage = function (ev) {
      try {
        var msg = JSON.parse(ev.data);
        if (msg.type === 'publish' && msg.data) {
          dispatch(msg.topic, msg.data, msg);
        } else if (msg.type === 'history') {
          // Replay historical entries as individual bus:message events
          (msg.entries || []).forEach(function (entry) {
            if (entry.data) dispatch(msg.topic, entry.data, entry);
          });
        }
        // 'entry' type (log lines) — dispatched generically so log viewers can listen
        if (msg.type === 'entry') {
          dispatch(msg.topic || 'log', null, msg);
        }
      } catch (e) {}
    };

    _ws.onclose = function () {
      _ws = null;
      if (!_intentionallyClosed) {
        setTimeout(function () { connect(_subscribed); }, _reconnectDelay);
        _reconnectDelay = Math.min(_reconnectDelay * 1.5, 30000);
      }
    };

    _ws.onerror = function () {
      _ws && _ws.close();
    };
  }

  var Bus = {
    /** Change the active subscriptions. Unsubscribes removed topics, subscribes added. */
    setSubscriptions: function (topics) {
      var toRemove = _subscribed.filter(function (t) { return topics.indexOf(t) === -1; });
      var toAdd    = topics.filter(function (t) { return _subscribed.indexOf(t) === -1; });
      unsubscribe(toRemove);
      subscribe(toAdd);
      _subscribed = topics.slice();
    },

    /** Request history replay for a topic. */
    requestHistory: function (topic, limit, afterId) {
      if (!_ws || _ws.readyState !== WebSocket.OPEN) return;
      _ws.send(JSON.stringify({
        action: 'history',
        topic: topic,
        limit: limit || 100,
        after_id: afterId || 0,
      }));
    },

    /** True if the connection is open. */
    isConnected: function () { return !!_ws && _ws.readyState === WebSocket.OPEN; },
  };

  window.Bus = Bus;

  // Auto-connect on page load if a bus-root marker element is present
  document.addEventListener('DOMContentLoaded', function () {
    var root = document.getElementById('bus-root');
    if (!root) return;
    var subs;
    try {
      subs = JSON.parse(root.dataset.subscriptions || '[]');
    } catch (e) {
      subs = [];
    }
    connect(subs);
  });
}());
