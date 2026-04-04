/* Market Browser — tree navigation + search */
(function () {
    'use strict';

    var APP = document.getElementById('mb-app');
    var REGION_ID = parseInt(APP.dataset.regionId || '0', 10);
    var TYPE_ID   = parseInt(APP.dataset.typeId   || '0', 10);
    var _URL_TREE        = APP.dataset.urlTree;
    var _URL_GROUP_TYPES = APP.dataset.urlGroupTypes;  // contains '/0/' as placeholder
    var _URL_SEARCH      = APP.dataset.urlSearch;
    var _URL_ORDERS      = APP.dataset.urlOrders;

    // ── helpers ───────────────────────────────────────────────────────────────

    function esc(s) {
        return String(s || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
    }

    function ordersUrl(typeId) {
        return _URL_ORDERS + '?type_id=' + typeId + '&region_id=' + REGION_ID;
    }

    // ── tree state ────────────────────────────────────────────────────────────

    var childrenMap = {};   // parent_group_id -> [group objects]
    var loadedTypes = {};   // group_id -> true (already fetched)

    // ── render helpers ────────────────────────────────────────────────────────

    function makeGroupEl(g, depth) {
        var el = document.createElement('div');
        el.className = 'mb-tree-row mb-group';
        el.style.paddingLeft = (8 + depth * 14) + 'px';
        el.dataset.gid = g.market_group_id;
        el.innerHTML = '<span class="mb-arrow">▸</span> ' + esc(g.name_en);
        return el;
    }

    function makeTypeEl(t, depth) {
        var el = document.createElement('div');
        el.className = 'mb-tree-row mb-type' + (t.type_id === TYPE_ID ? ' mb-active' : '');
        el.style.paddingLeft = (8 + depth * 14) + 'px';
        el.textContent = t.name_en;
        el.dataset.tid = t.type_id;
        el.addEventListener('click', function () {
            window.location.href = ordersUrl(t.type_id);
        });
        return el;
    }

    function makeChildContainer(gid) {
        var el = document.createElement('div');
        el.className = 'mb-children';
        el.dataset.parent = gid;
        el.style.display = 'none';
        return el;
    }

    // ── recursive tree rendering ──────────────────────────────────────────────

    function renderChildren(container, children, depth) {
        children.forEach(function (g) {
            var isLeaf = !childrenMap[g.market_group_id];
            var groupEl = makeGroupEl(g, depth);
            var childCon = makeChildContainer(g.market_group_id);

            groupEl.addEventListener('click', function (e) {
                e.stopPropagation();
                toggleGroup(g, groupEl, childCon, isLeaf, depth);
            });

            container.appendChild(groupEl);
            container.appendChild(childCon);
        });
    }

    function toggleGroup(g, groupEl, childCon, isLeaf, depth) {
        var open = childCon.style.display !== 'none';

        if (open) {
            childCon.style.display = 'none';
            groupEl.querySelector('.mb-arrow').textContent = '▸';
            return;
        }

        groupEl.querySelector('.mb-arrow').textContent = '▾';
        childCon.style.display = 'block';

        if (childCon.children.length > 0) return;  // already populated

        // Render sub-groups (if any)
        var subGroups = childrenMap[g.market_group_id] || [];
        renderChildren(childCon, subGroups, depth + 1);

        // Fetch leaf types if this group (also) has types
        if (g.has_types && !loadedTypes[g.market_group_id]) {
            loadedTypes[g.market_group_id] = true;
            fetch(_URL_GROUP_TYPES.replace('/0/', '/' + g.market_group_id + '/'))
                .then(function (r) { return r.json(); })
                .then(function (types) {
                    types.forEach(function (t) {
                        childCon.appendChild(makeTypeEl(t, depth + 1));
                    });
                });
        }
    }

    // ── initial tree load ─────────────────────────────────────────────────────

    function buildTree(groups) {
        var rootGroups = [];
        groups.forEach(function (g) {
            var pid = g.parent_group_id;
            if (!pid) {
                rootGroups.push(g);
            } else {
                if (!childrenMap[pid]) childrenMap[pid] = [];
                childrenMap[pid].push(g);
            }
        });

        var treeEl = document.getElementById('mb-tree');
        treeEl.innerHTML = '';
        renderChildren(treeEl, rootGroups, 0);

        // Auto-expand to show the active type_id's group path
        if (TYPE_ID) expandToType(TYPE_ID, groups);
    }

    // Walk up from the active type's group to root and expand each ancestor
    function expandToType(typeId, groups) {
        // Find which group contains this type via the server
        fetch(_URL_TREE.replace('tree', 'group/for_type/' + typeId))
            .catch(function () { /* optional endpoint — graceful */ });
        // Simpler: we don't know the group id from the page alone without an extra call.
        // The sidebar will highlight the active type when its parent is opened naturally.
    }

        fetch(_URL_TREE)
        .then(function (r) { return r.json(); })
        .then(function (groups) {
            if (groups.error) {
                document.getElementById('mb-tree').textContent = 'SDE not loaded.';
                return;
            }
            buildTree(groups);
        })
        .catch(function () {
            document.getElementById('mb-tree').textContent = 'Could not load market groups.';
        });

    // ── search ────────────────────────────────────────────────────────────────

    var searchInput = document.getElementById('mb-search');
    var searchResults = document.getElementById('mb-search-results');
    var searchTimer = null;

    searchInput.addEventListener('input', function () {
        clearTimeout(searchTimer);
        var q = searchInput.value.trim();
        if (q.length < 2) {
            searchResults.innerHTML = '';
            searchResults.style.display = 'none';
            return;
        }
        searchTimer = setTimeout(function () {
            fetch(_URL_SEARCH + '?q=' + encodeURIComponent(q))
                .then(function (r) { return r.json(); })
                .then(function (types) {
                    searchResults.innerHTML = '';
                    if (!types.length) {
                        searchResults.innerHTML = '<div class="mb-tree-row muted" style="padding:.4rem .8rem;font-size:.8rem">No results</div>';
                    } else {
                        types.forEach(function (t) {
                            var el = document.createElement('div');
                            el.className = 'mb-tree-row mb-type' + (t.type_id === TYPE_ID ? ' mb-active' : '');
                            el.style.padding = '.3rem .8rem';
                            el.textContent = t.name_en;
                            el.addEventListener('click', function () {
                                window.location.href = ordersUrl(t.type_id);
                            });
                            searchResults.appendChild(el);
                        });
                    }
                    searchResults.style.display = 'block';
                });
        }, 200);
    });

    document.addEventListener('click', function (e) {
        if (!searchResults.contains(e.target) && e.target !== searchInput) {
            searchResults.style.display = 'none';
        }
    });

    // ── region selector ───────────────────────────────────────────────────────
    var regionSelect = document.getElementById('region-select');
    if (regionSelect) regionSelect.addEventListener('change', function () {
        document.getElementById('region-form').submit();
    });

}());
