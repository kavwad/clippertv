// Chart.js dark theme defaults
Chart.defaults.color = '#a0a0a0';
Chart.defaults.borderColor = '#2d3139';

// Track chart instances for cleanup on rider switch
const charts = {};

function getChartOptions() {
    const mobile = window.innerWidth < 640;
    return {
        responsive: true,
        maintainAspectRatio: true,
        aspectRatio: mobile ? 1.2 : 2,
        interaction: {
            mode: 'index',
            intersect: false,
        },
        plugins: {
            legend: {
                position: mobile ? 'bottom' : 'top',
                labels: {
                    boxWidth: 12,
                    padding: 8,
                }
            },
            tooltip: {
                yAlign: 'bottom',
                caretPadding: 32,
                filter: item => item.raw !== 0,
                callbacks: {
                    footer: items => {
                        const total = items.reduce((sum, item) => sum + item.raw, 0);
                        return `Total: ${total}`;
                    }
                }
            }
        },
        scales: {
            x: {
                stacked: true,
                ticks: {
                    maxRotation: 45,
                    minRotation: 45,
                }
            },
            y: {
                stacked: true,
                beginAtZero: true,
            }
        }
    };
}

function destroyChart(name) {
    if (charts[name]) {
        charts[name].destroy();
        charts[name] = null;
    }
}

function loadCharts(rider) {
    const opts = getChartOptions();

    // Trip chart
    const tripCanvas = document.getElementById('tripChart');
    if (tripCanvas) {
        destroyChart('trip');
        fetch(`/api/trips/${rider}`)
            .then(r => r.json())
            .then(data => {
                charts.trip = new Chart(tripCanvas, {
                    type: 'bar',
                    data: data,
                    options: {
                        ...opts,
                        plugins: {
                            ...opts.plugins,
                            title: {
                                display: true,
                                text: 'Monthly trips',
                                align: 'start',
                                font: { size: 16, weight: 'normal' }
                            }
                        }
                    }
                });
            });
    }

    // Cost chart
    const costCanvas = document.getElementById('costChart');
    if (costCanvas) {
        destroyChart('cost');
        fetch(`/api/costs/${rider}`)
            .then(r => r.json())
            .then(data => {
                charts.cost = new Chart(costCanvas, {
                    type: 'bar',
                    data: data,
                    options: {
                        ...opts,
                        plugins: {
                            ...opts.plugins,
                            title: {
                                display: true,
                                text: 'Monthly transit cost',
                                align: 'start',
                                font: { size: 16, weight: 'normal' }
                            },
                            tooltip: {
                                yAlign: 'bottom',
                                caretPadding: 32,
                                filter: item => item.raw !== 0,
                                callbacks: {
                                    label: ctx => `${ctx.dataset.label}: $${Math.round(ctx.raw)}`,
                                    footer: items => {
                                        const total = items.reduce((sum, item) => sum + item.raw, 0);
                                        return `Total: $${Math.round(total)}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            ...opts.scales,
                            y: {
                                ...opts.scales.y,
                                ticks: {
                                    callback: val => `$${val}`
                                }
                            }
                        }
                    }
                });
            });
    }

}

function loadComparisonChart() {
    const compCanvas = document.getElementById('comparisonChart');
    if (!compCanvas) return;
    if (charts.comparison) return; // already loaded

    fetch('/api/comparison')
        .then(r => r.json())
        .then(data => {
            charts.comparison = new Chart(compCanvas, {
                type: 'line',
                data: data,
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    aspectRatio: window.innerWidth < 640 ? 1.2 : 2,
                    interaction: {
                        mode: 'index',
                        intersect: false,
                    },
                    plugins: {
                        title: {
                            display: true,
                            text: 'Trips per month',
                            align: 'start',
                            font: { size: 16, weight: 'normal' }
                        },
                        legend: {
                            position: 'top',
                        }
                    },
                    scales: {
                        x: {
                            ticks: {
                                maxRotation: 45,
                                minRotation: 45,
                            }
                        },
                        y: {
                            beginAtZero: true,
                        }
                    }
                }
            });
        });
}

// Re-init charts and tabs after HTMX swaps dashboard content
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'dashboard-content') {
        destroyChart('comparison');
        const rider = new URLSearchParams(window.location.search).get('rider');
        if (rider) {
            loadCharts(rider);
        }

        // Re-bind tab click handlers for newly swapped content
        bindTabHandlers();
    }
});

function bindTabHandlers() {
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tabGroup = btn.closest('.tab-group');
            switchTab(tabGroup.id, btn.dataset.tab);
            // Lazy-load comparison chart when its tab is first opened
            if (btn.dataset.tab === 'comparison') {
                loadComparisonChart();
            }
        });
    });
}

// Bind on initial page load
bindTabHandlers();

// Toggle active class on rider buttons immediately on click
document.body.addEventListener('htmx:beforeRequest', function(event) {
    const el = event.detail.elt;
    if (el.classList.contains('rider-btn')) {
        document.querySelectorAll('.rider-btn').forEach(btn => btn.classList.remove('active'));
        el.classList.add('active');
    }
});
