/* sde_browser.js — SDE Browser client-side enhancements */

(function () {
  "use strict";

  /* Auto-focus search input on lookup pages */
  var searchInput = document.querySelector('input[name="q"]');
  if (searchInput && !searchInput.value) {
    searchInput.focus();
  }
}());
