(() => {
  const dataElement = document.querySelector('#sales-data');
  const canvas = document.querySelector('#sales-chart');
  if (!dataElement || !canvas || typeof Chart === 'undefined') return;
  const series = JSON.parse(dataElement.textContent);
  const money = (value) => `KSh ${Math.round(value).toLocaleString()}`;
  const totalNode = document.querySelector('#chart-total');
  const ordersNode = document.querySelector('#chart-orders');
  const averageNode = document.querySelector('#chart-average');
  let chart;
  const draw = (range) => {
    const selected = series.slice(-range);
    const total = selected.reduce((sum, point) => sum + point.sales, 0);
    const orders = selected.reduce((sum, point) => sum + point.orders, 0);
    totalNode.textContent = money(total);
    ordersNode.textContent = orders.toLocaleString();
    averageNode.textContent = money(orders ? total / orders : 0);
    if (chart) chart.destroy();
    chart = new Chart(canvas, {type: 'line', data: {labels: selected.map((point) => point.date), datasets: [{data: selected.map((point) => point.sales), borderColor: '#2f8cff', backgroundColor: 'rgba(47,140,255,.22)', borderWidth: 2, pointRadius: selected.length <= 30 ? 3 : 0, pointHoverRadius: 5, fill: true, tension: .35}]}, options: {responsive: true, maintainAspectRatio: false, interaction: {intersect: false, mode: 'index'}, plugins: {legend: {display: false}, tooltip: {callbacks: {label: (context) => money(context.raw)}}}, scales: {x: {grid: {color: 'rgba(145,182,232,.12)'}, ticks: {color: '#9bb4d4', maxTicksLimit: 8}}, y: {beginAtZero: true, grid: {color: 'rgba(145,182,232,.12)'}, ticks: {color: '#9bb4d4', callback: (value) => `KSh ${Number(value).toLocaleString()}`}}}}});
  };
  document.querySelectorAll('.chart-range').forEach((button) => button.addEventListener('click', () => {document.querySelectorAll('.chart-range').forEach((item) => item.classList.remove('active')); button.classList.add('active'); draw(Number(button.dataset.range));}));
  draw(7);
})();
