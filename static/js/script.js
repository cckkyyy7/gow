document.addEventListener('DOMContentLoaded', function () {
    fetchStats();
    loadComparisonTable();
    initScrollReveal();
    initTiltEffect();
});

// Chart instance
let myChart = null;

async function fetchStats() {
    try {
        const response = await fetch('/api/stats');
        const data = await response.json();

        if (data.daily_hpr !== undefined) {
            document.getElementById('val-daily').innerText = formatPct(data.daily_hpr);
            // In a real app, 'vs previous' would be calculated backend or fetched
        }
        if (data.monthly_hpr !== undefined) {
            document.getElementById('val-monthly').innerText = formatPct(data.monthly_hpr);
        }
        if (data.yearly_hpr !== undefined) {
            document.getElementById('val-yearly').innerText = formatPct(data.yearly_hpr);
        }
    } catch (error) {
        console.error('Error fetching stats:', error);
    }
}

function formatPct(val) {
    return (val * 100).toFixed(2) + '%';
}

async function loadComparisonTable() {
    try {
        const response = await fetch('/api/comparison');
        const data = await response.json();

        if (data.error) {
            console.error('Error loading comparison:', data.error);
            return;
        }

        const table = document.getElementById('comparison-table');
        table.innerHTML = ''; // Clear existing

        // Header
        const headerRow = document.createElement('tr');
        // Check if headers exist
        if (data.headers && data.headers.length > 0) {
            // The first column in CSV seems to be empty or named 'Unnamed: 0', let's name it 'Comparison Point' if empty
            data.headers.forEach((header, index) => {
                let text = header;
                if (index === 0 && (header.includes('Unnamed') || header === '')) {
                    text = 'Comparison Point';
                }
                const th = document.createElement('th');
                th.innerText = text;
                headerRow.appendChild(th);
            });
            table.appendChild(headerRow);
        }

        // Rows
        data.rows.forEach(row => {
            const tr = document.createElement('tr');
            // Assuming order matches headers. Pandas to_dict('records') keys match headers.
            data.headers.forEach(header => {
                const td = document.createElement('td');
                // Access content by header key
                td.innerText = row[header];
                tr.appendChild(td);
            });
            table.appendChild(tr);
        });

    } catch (error) {
        console.error('Error fetching comparison table:', error);
    }
}

// Modal & Chart Logic
window.openModal = async function (type) {
    const modal = document.getElementById('chartModal');
    modal.style.display = 'block';

    // Fetch History
    try {
        const response = await fetch('/api/history');
        const history = await response.json();

        renderChart(type, history);

    } catch (error) {
        console.error('Error fetching history:', error);
    }
}

window.closeModal = function () {
    document.getElementById('chartModal').style.display = 'none';
    if (myChart) {
        myChart.destroy();
    }
}

function renderChart(type, history) {
    const ctx = document.getElementById('performanceChart').getContext('2d');

    // Process data based on type
    // type: 'daily', 'monthly', 'yearly'
    // Actually prompt says:
    // Daily card -> Daily view (Day granularity)
    // Monthly card -> Weekly view (Week granularity)
    // Yearly card -> Weekly view (Week granularity)

    let labels = [];
    let dataPoints = [];

    // For demo, we just dump all data or subset
    // If empty history, mock some data for visual appeal in demo
    if (!history || history.length === 0) {
        history = generateMockHistory(); // Fallback for pure demo look
    }

    if (type === 'daily') {
        document.getElementById('modalTitle').innerText = '歷史收益 (每日)';
        labels = history.map(h => h.date);
        dataPoints = history.map(h => (h.daily_hpr * 100).toFixed(2));
    } else if (type === 'monthly') {
        document.getElementById('modalTitle').innerText = '歷史收益 (每月)';

        // Group by Month (YYYY-MM)
        const monthlyData = [];
        const seenMonths = {};

        history.forEach(h => {
            // Date format YYYY-MM-DD
            const monthStr = h.date.substring(0, 7); // YYYY-MM

            if (!seenMonths[monthStr]) {
                seenMonths[monthStr] = { date: monthStr, val: h.cumulative_twr };
                monthlyData.push(seenMonths[monthStr]);
            } else {
                // Update with latest in that month (chronological update)
                seenMonths[monthStr].val = h.cumulative_twr;
            }
        });

        labels = monthlyData.map(m => m.date);
        dataPoints = monthlyData.map(m => (m.val * 100).toFixed(2));

    } else if (type === 'yearly') {
        document.getElementById('modalTitle').innerText = '歷史收益 (每年)';
        const yearlyData = [];
        const seenYears = {};
        history.forEach(h => {
            const year = h.date.split('-')[0];
            if (!seenYears[year]) {
                seenYears[year] = { year: year, val: h.cumulative_twr };
                yearlyData.push(seenYears[year]);
            } else {
                seenYears[year].val = h.cumulative_twr;
            }
        });
        labels = yearlyData.map(y => y.year);
        dataPoints = yearlyData.map(y => (y.val * 100).toFixed(2));
    }

    if (myChart) myChart.destroy();

    // Enable horizontal scrolling by expanding canvas width
    const container = document.querySelector('.chart-container');

    // Determine min width based on type to force scroll if needed or at least ensure good spacing
    let minWidthPerPoint = 50;
    if (type === 'monthly') minWidthPerPoint = 150; // Wider for weekly to ensure scroll feel
    if (type === 'yearly') minWidthPerPoint = 300;  // Very wide for yearly

    // Ensure total width is at least slightly larger than container if we want to force "swipe" 
    // feel even for small data, or just let it fit if really small?
    // User wants "slide left". If it fits, sliding does nothing.
    // Let's force a minimum total width > container width IF we really want that interaction,
    // but usually it's better to just respect data density. 
    // However, if we only have 2 points for yearly, 2 * 300 = 600. Container might be 800. No scroll.
    // If the user insists on sliding left to see history, implying they want the LATEST on the right 
    // and maybe empty space on left? Or just the ability to drag?
    // Let's just trust minWidthPerPoint. 

    // NOTE: To strictly satisfy "always swipable to left", we might need `flex-direction: row-reverse` or similar, 
    // but standard scroll is fine.

    const totalWidth = Math.max(container.clientWidth, labels.length * minWidthPerPoint);
    container.style.overflowX = 'auto';
    container.style.cursor = 'grab'; // Indicate draggable

    let canvasWrapper = document.getElementById('canvasWrapper');
    if (!canvasWrapper) {
        canvasWrapper = document.createElement('div');
        canvasWrapper.id = 'canvasWrapper';
        canvasWrapper.style.height = '100%';
        const canvas = document.getElementById('performanceChart');
        container.appendChild(canvasWrapper);
        canvasWrapper.appendChild(canvas);
    }
    canvasWrapper.style.width = `${totalWidth}px`;

    // Drag to Scroll Logic
    let isDown = false;
    let startX;
    let scrollLeft;

    container.addEventListener('mousedown', (e) => {
        isDown = true;
        container.style.cursor = 'grabbing';
        startX = e.pageX - container.offsetLeft;
        scrollLeft = container.scrollLeft;
    });

    container.addEventListener('mouseleave', () => {
        isDown = false;
        container.style.cursor = 'grab';
    });

    container.addEventListener('mouseup', () => {
        isDown = false;
        container.style.cursor = 'grab';
    });

    container.addEventListener('mousemove', (e) => {
        if (!isDown) return;
        e.preventDefault();
        const x = e.pageX - container.offsetLeft;
        const walk = (x - startX) * 2; // Scroll-fast
        container.scrollLeft = scrollLeft - walk;
    });

    // Scroll handling for Toasts
    container.addEventListener('scroll', function () {
        if (container.scrollLeft === 0) {
            showToast('已是最早數據');
        }
    });

    // Initial scroll to right (latest)
    setTimeout(() => {
        container.scrollLeft = container.scrollWidth;
    }, 100);

    myChart = new Chart(document.getElementById('performanceChart').getContext('2d'), {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Cumulative Return (%)',
                data: dataPoints,

                // Color Logic
                pointBackgroundColor: (ctx) => {
                    return ctx.parsed.y < 0 ? '#ff4d4d' : '#00f2ff';
                },
                pointBorderColor: (ctx) => {
                    return ctx.parsed.y < 0 ? '#ff4d4d' : '#00f2ff';
                },

                // Gradient Border for precise 0-crossing color
                borderColor: function (context) {
                    const chart = context.chart;
                    const { ctx, chartArea, scales } = chart;

                    if (!chartArea) {
                        // Initial load
                        return '#00f2ff';
                    }

                    const yAxis = scales.y;
                    const zeroPixel = yAxis.getPixelForValue(0);
                    const top = yAxis.top;
                    const bottom = yAxis.bottom;
                    const height = bottom - top;

                    // Calculate stop point
                    // Gradient goes top to bottom
                    // Pixel 0 is at top? No, pixel coordinate increases downwards.
                    // topPixel = yAxis.top (min Y coord, max value usually).
                    // bottomPixel = yAxis.bottom (max Y coord, min value usually).
                    // zeroPixel is somewhere in between.

                    let stop = (zeroPixel - top) / height;

                    // Clamp stop to 0-1 (if 0 is out of view)
                    if (stop < 0) stop = 0;
                    if (stop > 1) stop = 1;

                    const gradient = ctx.createLinearGradient(0, top, 0, bottom);
                    gradient.addColorStop(0, '#00f2ff');
                    gradient.addColorStop(stop, '#00f2ff');
                    gradient.addColorStop(stop, '#ff4d4d');
                    gradient.addColorStop(1, '#ff4d4d');

                    return gradient;
                },

                fill: {
                    target: 'origin',
                    above: 'rgba(0, 242, 255, 0.1)',   // Area above the origin
                    below: 'rgba(255, 77, 77, 0.1)'    // Area below the origin
                },

                borderWidth: 2,
                pointRadius: 4,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            preserveAspectRatio: false, // Allow stretching
            scales: {
                x: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#888' }
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.05)' },
                    ticks: { color: '#888' }
                }
            },
            plugins: {
                legend: { display: false }
            },
            interaction: {
                intersect: false,
                mode: 'index',
            }
        }
    });
}

function showToast(msg) {
    let toast = document.getElementById('toast');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast';
        toast.style.position = 'absolute';
        toast.style.top = '10px';
        toast.style.left = '50%';
        toast.style.transform = 'translateX(-50%)';
        toast.style.background = 'rgba(255, 215, 0, 0.9)';
        toast.style.color = '#000';
        toast.style.padding = '5px 15px';
        toast.style.borderRadius = '20px';
        toast.style.fontSize = '0.8rem';
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        document.querySelector('.modal-content').appendChild(toast);
    }
    toast.innerText = msg;
    toast.style.opacity = '1';
    setTimeout(() => {
        toast.style.opacity = '0';
    }, 2000);
}


function generateMockHistory() {
    // Generate 30 days of mock data
    let data = [];
    let val = 0;
    for (let i = 30; i > 0; i--) {
        let date = new Date();
        date.setDate(date.getDate() - i);
        let daily = (Math.random() - 0.4) * 0.05; // Random move
        val = (1 + val) * (1 + daily) - 1;

        data.push({
            date: date.toISOString().split('T')[0],
            daily_hpr: daily,
            cumulative_twr: val
        });
    }
    return data;
}

// Close modal when clicking outside
window.onclick = function (event) {
    const modal = document.getElementById('chartModal');
    if (event.target == modal) {
        closeModal();
    }
}

// Scroll Reveal
function initScrollReveal() {
    const reveals = document.querySelectorAll('.reveal');

    // Add reveal class to cards and sections if they don't have it yet (will do in HTML, 
    // but here we can check or just observe generic elements)
    // Actually, let's keep it simple: we observe '.reveal'.

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('active');
            }
        });
    }, { threshold: 0.1 });

    reveals.forEach(el => observer.observe(el));
}

// Tilt Effect
function initTiltEffect() {
    // Select cards to apply tilt
    const cards = document.querySelectorAll('.data-card, .strategy-card');

    cards.forEach(card => {
        card.addEventListener('mousemove', (e) => {
            const rect = card.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const centerX = rect.width / 2;
            const centerY = rect.height / 2;

            const rotateX = ((y - centerY) / centerY) * -10; // Max 10 deg
            const rotateY = ((x - centerX) / centerX) * 10;

            card.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02, 1.02, 1.02)`;
        });

        card.addEventListener('mouseleave', () => {
            card.style.transform = 'perspective(1000px) rotateX(0) rotateY(0) scale3d(1, 1, 1)';
        });
    });
}
