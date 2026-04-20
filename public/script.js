// ── 상태 ──
let currentSymbol = '';
let currentMarket = 'stock';
let currentPeriod = '1W';
let currentChartType = 'candlestick';
let chartInstance = null;
let favorites = JSON.parse(localStorage.getItem('mv_favs') || '[]');

// ── 검색 ──
async function doSearch() {
  const input = document.getElementById('search-input');
  const symbol = input.value.trim().toUpperCase();
  const market = document.getElementById('market').value;
  if (!symbol) return;
  currentMarket = market;
  await loadSymbol(symbol, market);
}

document.getElementById('search-input').addEventListener('keydown', e => {
  if (e.key === 'Enter') doSearch();
});

async function loadSymbol(symbol, market) {
  currentSymbol = symbol;
  currentMarket = market;

  showDetail(false);
  showLoading(true);

  try {
    const endpoint = market === 'crypto'
      ? `/api/crypto/search?symbol=${symbol}`
      : `/api/stock/search?symbol=${symbol}`;

    const res = await fetch(endpoint);
    const data = await res.json();
    if (data.error) { alert(data.error); showLoading(false); return; }

    renderHeader(data, market);
    showDetail(true);
    await loadCandles();
    renderFavList();
  } catch (e) {
    alert('데이터를 불러올 수 없습니다: ' + e.message);
    showLoading(false);
  }
}

// ── 헤더 렌더링 ──
function renderHeader(data, market) {
  const fmt = market === 'stock'
    ? v => (data.currency === 'KRW' ? '₩' : '$') + v.toLocaleString()
    : v => '$' + v.toLocaleString();

  document.getElementById('d-symbol').textContent = data.symbol;
  document.getElementById('d-name').textContent = market === 'crypto' ? data.coin_id : '';
  document.getElementById('d-market-badge').textContent = market === 'stock' ? '주식' : '암호화폐';
  document.getElementById('d-price').textContent = fmt(data.price);

  const chg = data.change_pct;
  const chgEl = document.getElementById('d-change');
  const sign = chg >= 0 ? '+' : '';
  chgEl.textContent = `${sign}${chg.toFixed(2)}%`;
  chgEl.className = 'change-badge ' + (chg > 0 ? 'up' : chg < 0 ? 'down' : 'flat');

  if (market === 'stock') {
    document.getElementById('m-open').textContent = fmt(data.open);
    document.getElementById('m-high').textContent = fmt(data.high);
    document.getElementById('m-low').textContent  = fmt(data.low);
    document.getElementById('m-vol').textContent  = fmtVolume(data.volume);
  } else {
    document.getElementById('m-open').textContent = '—';
    document.getElementById('m-high').textContent = '—';
    document.getElementById('m-low').textContent  = '—';
    document.getElementById('m-vol').textContent  = fmtVolume(data.volume_24h);
  }

  const isSaved = favorites.some(f => f.symbol === currentSymbol && f.market === currentMarket);
  const favBtn = document.getElementById('fav-btn');
  favBtn.textContent = isSaved ? '★ 저장됨' : '+ 즐겨찾기';
  favBtn.className = 'fav-btn' + (isSaved ? ' saved' : '');
}

// ── 캔들 차트 ──
async function loadCandles() {
  showLoading(true);
  const endpoint = currentMarket === 'crypto'
    ? `/api/crypto/candles?symbol=${currentSymbol}&period=${currentPeriod}`
    : `/api/stock/candles?symbol=${currentSymbol}&period=${currentPeriod}`;

  try {
    const res = await fetch(endpoint);
    const candles = await res.json();
    if (!Array.isArray(candles) || candles.length === 0) {
      showLoading(false); return;
    }
    renderChart(candles);
  } catch (e) {
    console.error(e);
  } finally {
    showLoading(false);
  }
}

function renderChart(candles) {
  if (chartInstance) { chartInstance.destroy(); chartInstance = null; }

  const ctx = document.getElementById('priceChart').getContext('2d');
  const isLine = currentChartType === 'line';

  if (isLine) {
    chartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: candles.map(c => c.t),
        datasets: [{
          label: currentSymbol,
          data: candles.map(c => c.c),
          borderColor: '#6366f1',
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.3,
          fill: false,
        }]
      },
      options: chartOptions(candles)
    });
  } else {
    const data = candles.map(c => ({
      x: new Date(c.t).getTime(),
      o: c.o, h: c.h, l: c.l, c: c.c
    }));
    chartInstance = new Chart(ctx, {
      type: 'candlestick',
      data: {
        datasets: [{
          label: currentSymbol,
          data,
          color: { up: '#16a34a', down: '#dc2626', unchanged: '#9ca3af' },
          borderColor: { up: '#16a34a', down: '#dc2626', unchanged: '#9ca3af' },
        }]
      },
      options: chartOptions(candles)
    });
  }
}

function chartOptions(candles) {
  const isCrypto = currentMarket === 'crypto';
  const prefix = isCrypto ? '$' : '';
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: {
        type: 'time',
        time: { tooltipFormat: 'yyyy-MM-dd HH:mm' },
        ticks: { color: '#9ca3af', font: { size: 11 }, maxTicksLimit: 7 },
        grid: { color: 'rgba(0,0,0,0.04)' },
      },
      y: {
        position: 'right',
        ticks: {
          color: '#9ca3af', font: { size: 11 },
          callback: v => prefix + v.toLocaleString()
        },
        grid: { color: 'rgba(0,0,0,0.04)' },
      }
    }
  };
}

// ── 기간 / 차트 타입 ──
function setPeriod(p) {
  currentPeriod = p;
  document.querySelectorAll('#period-btns .pbtn').forEach(b => {
    b.classList.toggle('active', b.textContent === p);
  });
  if (currentSymbol) loadCandles();
}

function setChartType(type) {
  currentChartType = type;
  document.getElementById('btn-candle').classList.toggle('active', type === 'candlestick');
  document.getElementById('btn-line').classList.toggle('active', type === 'line');
  if (currentSymbol) loadCandles();
}

// ── 즐겨찾기 ──
function toggleFavorite() {
  const idx = favorites.findIndex(f => f.symbol === currentSymbol && f.market === currentMarket);
  if (idx >= 0) {
    favorites.splice(idx, 1);
  } else {
    const priceEl = document.getElementById('d-price');
    favorites.push({ symbol: currentSymbol, market: currentMarket, price: priceEl.textContent });
  }
  saveFavs();
  renderFavList();
  const isSaved = idx < 0;
  const favBtn = document.getElementById('fav-btn');
  favBtn.textContent = isSaved ? '★ 저장됨' : '+ 즐겨찾기';
  favBtn.className = 'fav-btn' + (isSaved ? ' saved' : '');
}

function renderFavList() {
  const list = document.getElementById('fav-list');
  const empty = document.getElementById('fav-empty');
  list.innerHTML = '';

  if (favorites.length === 0) { empty.style.display = 'block'; return; }
  empty.style.display = 'none';

  favorites.forEach(f => {
    const isActive = f.symbol === currentSymbol && f.market === currentMarket;
    const div = document.createElement('div');
    div.className = 'fav-item' + (isActive ? ' active' : '');
    div.innerHTML = `
      <div class="fav-left" onclick="loadSymbol('${f.symbol}','${f.market}')">
        <div class="fav-symbol">${f.symbol}</div>
        <div class="fav-price">${f.price}</div>
      </div>
      <button class="fav-del" onclick="removeFav('${f.symbol}','${f.market}')">×</button>
    `;
    list.appendChild(div);
  });
}

function removeFav(symbol, market) {
  favorites = favorites.filter(f => !(f.symbol === symbol && f.market === market));
  saveFavs();
  renderFavList();
  if (currentSymbol === symbol) {
    const favBtn = document.getElementById('fav-btn');
    favBtn.textContent = '+ 즐겨찾기';
    favBtn.className = 'fav-btn';
  }
}

function saveFavs() { localStorage.setItem('mv_favs', JSON.stringify(favorites)); }

// ── 유틸 ──
function fmtVolume(n) {
  if (!n) return '—';
  if (n >= 1e9) return (n / 1e9).toFixed(1) + 'B';
  if (n >= 1e6) return (n / 1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n / 1e3).toFixed(1) + 'K';
  return n.toString();
}

function showDetail(show) {
  document.getElementById('detail').className      = show ? '' : 'hidden';
  document.getElementById('placeholder').className = show ? 'hidden' : 'placeholder';
}

function showLoading(show) {
  document.getElementById('chart-loading').className = 'chart-loading' + (show ? '' : ' hidden');
}

// ── 초기화 ──
renderFavList();
