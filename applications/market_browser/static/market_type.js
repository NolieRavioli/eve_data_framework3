/* Market Type Detail — price history chart + range toggles */
(function () {
    'use strict';

    var el = document.getElementById('type-data');
    if (!el) return;

    var typeId    = el.dataset.typeId;
    var regionId  = el.dataset.regionId || '10000002';
    var baseUrl   = el.dataset.historyUrl;

    var chart     = null;
    var allData   = [];
    var activeDays = 90;

    // ── helpers ───────────────────────────────────────────────────────

    function formatISK(v) {
        if (v >= 1e9) return (v / 1e9).toFixed(2) + 'B';
        if (v >= 1e6) return (v / 1e6).toFixed(2) + 'M';
        if (v >= 1e3) return (v / 1e3).toFixed(1) + 'K';
        return v.toFixed(2);
    }

    function filterDays(data, days) {
        if (!data.length) return data;
        var cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - days);
        var cutStr = cutoff.toISOString().slice(0, 10);
        return data.filter(function (d) { return d.date >= cutStr; });
    }

    // ── chart rendering ──────────────────────────────────────────────

    function renderChart(data) {
        var ctx = document.getElementById('price-chart');
        var loading = document.getElementById('chart-loading');
        if (loading) loading.style.display = 'none';

        if (!data.length) {
            if (loading) { loading.textContent = 'No history data available.'; loading.style.display = 'flex'; }
            return;
        }

        // Sort ascending by date
        data.sort(function (a, b) { return a.date < b.date ? -1 : 1; });

        var labels  = data.map(function (d) { return d.date; });
        var avgLine = data.map(function (d) { return d.average; });
        var highLine = data.map(function (d) { return d.highest; });
        var lowLine  = data.map(function (d) { return d.lowest; });
        var volumes  = data.map(function (d) { return d.volume; });

        // Find max volume for secondary axis scaling
        var maxVol = Math.max.apply(null, volumes) || 1;

        if (chart) { chart.destroy(); }

        chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Average',
                        data: avgLine,
                        borderColor: 'rgba(56,189,248,1)',
                        backgroundColor: 'rgba(56,189,248,0.08)',
                        fill: false,
                        tension: 0.2,
                        pointRadius: 0,
                        borderWidth: 2,
                        yAxisID: 'y'
                    },
                    {
                        label: 'High',
                        data: highLine,
                        borderColor: 'rgba(248,113,113,.5)',
                        fill: false,
                        tension: 0.2,
                        pointRadius: 0,
                        borderWidth: 1,
                        borderDash: [4, 3],
                        yAxisID: 'y'
                    },
                    {
                        label: 'Low',
                        data: lowLine,
                        borderColor: 'rgba(74,222,128,.5)',
                        fill: false,
                        tension: 0.2,
                        pointRadius: 0,
                        borderWidth: 1,
                        borderDash: [4, 3],
                        yAxisID: 'y'
                    },
                    {
                        label: 'Volume',
                        data: volumes,
                        type: 'bar',
                        backgroundColor: 'rgba(148,163,184,.2)',
                        borderWidth: 0,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: { color: 'rgba(226,232,240,.7)', font: { size: 11 }, boxWidth: 14 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function (ctx) {
                                if (ctx.dataset.yAxisID === 'y1') return ctx.dataset.label + ': ' + ctx.parsed.y.toLocaleString();
                                return ctx.dataset.label + ': ' + formatISK(ctx.parsed.y) + ' ISK';
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: 'rgba(226,232,240,.5)', font: { size: 10 }, maxTicksLimit: 12 },
                        grid: { color: 'rgba(226,232,240,.06)' }
                    },
                    y: {
                        position: 'left',
                        ticks: {
                            color: 'rgba(56,189,248,.7)',
                            font: { size: 10 },
                            callback: function (v) { return formatISK(v); }
                        },
                        grid: { color: 'rgba(226,232,240,.06)' }
                    },
                    y1: {
                        position: 'right',
                        ticks: {
                            color: 'rgba(148,163,184,.5)',
                            font: { size: 10 },
                            callback: function (v) { return v.toLocaleString(); }
                        },
                        grid: { drawOnChartArea: false },
                        suggestedMax: maxVol * 1.3
                    }
                }
            }
        });
    }

    // ── data fetching ────────────────────────────────────────────────

    function fetchHistory(rid) {
        var url = baseUrl + '?region_id=' + rid;
        fetch(url)
            .then(function (r) { return r.json(); })
            .then(function (data) {
                allData = data;
                renderChart(filterDays(allData, activeDays));
            })
            .catch(function () {
                var loading = document.getElementById('chart-loading');
                if (loading) { loading.textContent = 'Failed to load history.'; loading.style.display = 'flex'; }
            });
    }

    // ── range toggles ────────────────────────────────────────────────

    document.querySelectorAll('#range-btns [data-range]').forEach(function (btn) {
        btn.addEventListener('click', function () {
            activeDays = parseInt(btn.dataset.range, 10);
            document.querySelectorAll('#range-btns .btn').forEach(function (b) {
                b.classList.remove('btn-a');
            });
            btn.classList.add('btn-a');
            if (allData.length) renderChart(filterDays(allData, activeDays));
        });
    });

    // ── region selector ──────────────────────────────────────────────

    var regionSelect = document.getElementById('history-region');
    if (regionSelect) {
        regionSelect.addEventListener('change', function () {
            regionId = regionSelect.value;
            fetchHistory(regionId);
        });
    }

    // ── init ─────────────────────────────────────────────────────────
    fetchHistory(regionId);

}());
