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

function revealChart(canvasId, skeletonId) {
    const skeleton = document.getElementById(skeletonId);
    const canvas = document.getElementById(canvasId);
    if (skeleton) skeleton.style.display = 'none';
    if (canvas) canvas.style.display = '';
}

function loadCharts() {
    destroyChart('trip');
    destroyChart('cost');

    const opts = getChartOptions();

    // Trip chart
    const tripCanvas = document.getElementById('tripChart');
    if (tripCanvas) {
        fetch('/api/trips')
            .then(r => r.json())
            .then(data => {
                revealChart('tripChart', 'tripSkeleton');
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
        fetch('/api/costs')
            .then(r => r.json())
            .then(data => {
                revealChart('costChart', 'costSkeleton');
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

// Re-init charts after HTMX swaps dashboard content
document.body.addEventListener('htmx:afterSwap', function(event) {
    if (event.detail.target.id === 'dashboard-content') {
        destroyChart('comparison');
        loadCharts();
    }
});

// Tab click handling via event delegation (works across HTMX swaps)
document.body.addEventListener('click', function(event) {
    const btn = event.target.closest('.tab-btn');
    if (!btn) return;
    const tabGroup = btn.closest('.tab-group');
    switchTab(tabGroup.id, btn.dataset.tab);
    if (btn.dataset.tab === 'comparison') {
        loadComparisonChart();
    }
});
