from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import requests

app = Flask(__name__)
CORS(app)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def resolve_stock_symbol(symbol: str) -> str:
    s = symbol.upper().strip()
    if '.' in s:
        return s
    if s.isdigit():
        return s + '.KS'
    return s


def fetch_ticker_info(symbol: str):
    raw = symbol.replace('.KS', '').replace('.KQ', '')
    candidates = [raw + '.KS', raw + '.KQ'] if raw.isdigit() else [symbol]

    for sym in candidates:
        try:
            ticker = yf.Ticker(sym)
            info = ticker.fast_info
            hist = ticker.history(period='2d', interval='1d')
            if not hist.empty and float(info.last_price) > 0:
                return sym, ticker, info
        except Exception:
            continue
    return None, None, None


def _safe_round(val, currency):
    try:
        v = float(val)
        return int(v) if currency == 'KRW' else round(v, 2)
    except Exception:
        return 0


PERIOD_MAP = {
    "1D": ("1d",   "5m"),
    "1W": ("5d",   "30m"),
    "1M": ("1mo",  "1d"),
    "3M": ("3mo",  "1d"),
    "1Y": ("1y",   "1d"),
    "3Y": ("3y",   "1wk"),
}


@app.route("/api/stock/search")
def stock_search():
    raw_symbol = request.args.get("symbol", "").strip()
    if not raw_symbol:
        return jsonify({"error": "symbol 파라미터가 필요합니다"}), 400

    symbol = resolve_stock_symbol(raw_symbol)
    resolved, ticker, info = fetch_ticker_info(symbol)

    if not ticker:
        return jsonify({
            "error": f"'{raw_symbol}' 데이터를 찾을 수 없습니다. "
                     f"한국 주식은 종목코드 6자리(예: 005930), "
                     f"미국 주식은 티커(예: AAPL)를 입력하세요."
        }), 404

    try:
        # 회사명 가져오기
        try:
            t_info = ticker.info
            long_name = (
                t_info.get("longName")
                or t_info.get("shortName")
                or resolved
            )
        except Exception:
            long_name = resolved

        currency   = getattr(info, 'currency', 'USD')
        price      = float(info.last_price)
        prev_close = float(info.previous_close)
        change     = round(price - prev_close, 4)
        change_pct = round((change / prev_close) * 100, 2) if prev_close else 0

        if currency == 'KRW':
            price = int(price)
            prev_close = int(prev_close)
            change = int(change)

        return jsonify({
            "symbol":     resolved,
            "display":    raw_symbol.upper(),
            "name":       long_name,
            "price":      price,
            "prev_close": prev_close,
            "change":     change,
            "change_pct": change_pct,
            "open":       _safe_round(info.open, currency),
            "high":       _safe_round(info.day_high, currency),
            "low":        _safe_round(info.day_low, currency),
            "volume":     int(getattr(info, 'three_month_average_volume', 0) or 0),
            "currency":   currency,
        })
    except Exception as e:
        return jsonify({"error": f"데이터 파싱 오류: {str(e)}"}), 500


@app.route("/api/stock/candles")
def stock_candles():
    raw_symbol = request.args.get("symbol", "").strip()
    period_key = request.args.get("period", "1M")

    symbol = resolve_stock_symbol(raw_symbol)
    resolved, ticker, _ = fetch_ticker_info(symbol)

    if not ticker:
        return jsonify({"error": "데이터 없음"}), 404

    period, interval = PERIOD_MAP.get(period_key, ("1mo", "1d"))

    try:
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return jsonify({"error": "캔들 데이터 없음"}), 404

        currency = getattr(ticker.fast_info, 'currency', 'USD')
        candles = []
        for idx, row in hist.iterrows():
            o = int(row['Open'])  if currency == 'KRW' else round(float(row['Open']),  2)
            h = int(row['High'])  if currency == 'KRW' else round(float(row['High']),  2)
            l = int(row['Low'])   if currency == 'KRW' else round(float(row['Low']),   2)
            c = int(row['Close']) if currency == 'KRW' else round(float(row['Close']), 2)
            candles.append({
                "t": str(idx)[:19],
                "o": o, "h": h, "l": l, "c": c,
                "v": int(row['Volume']),
            })
        return jsonify(candles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


COIN_ID_MAP = {
    "BTC": "bitcoin",    "ETH": "ethereum",      "BNB": "binancecoin",
    "SOL": "solana",     "XRP": "ripple",         "ADA": "cardano",
    "DOGE": "dogecoin",  "DOT": "polkadot",      "MATIC": "matic-network",
    "AVAX": "avalanche-2", "LINK": "chainlink",  "UNI": "uniswap",
    "LTC": "litecoin",   "BCH": "bitcoin-cash",  "ATOM": "cosmos",
}

def resolve_coin_id(symbol: str) -> str:
    return COIN_ID_MAP.get(symbol.upper(), symbol.lower())


@app.route("/api/crypto/search")
def crypto_search():
    symbol = request.args.get("symbol", "BTC").upper().strip()
    coin_id = resolve_coin_id(symbol)
    try:
        res = requests.get(
            f"{COINGECKO_BASE}/simple/price",
            params={
                "ids": coin_id,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_24hr_vol": "true",
                "include_market_cap": "true",
            },
            timeout=10
        )
        data = res.json().get(coin_id)
        if not data:
            return jsonify({"error": f"'{symbol}' 코인을 찾을 수 없습니다."}), 404

        return jsonify({
            "symbol":     symbol,
            "coin_id":    coin_id,
            "name":       coin_id.replace('-', ' ').title(),
            "price":      data["usd"],
            "change_pct": round(data.get("usd_24h_change", 0), 2),
            "volume_24h": int(data.get("usd_24h_vol", 0)),
            "market_cap": int(data.get("usd_market_cap", 0)),
            "currency":   "USD",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/crypto/candles")
def crypto_candles():
    symbol  = request.args.get("symbol", "BTC").upper().strip()
    period  = request.args.get("period", "1M")
    coin_id = resolve_coin_id(symbol)

    # CoinGecko는 최대 365일 → 3Y는 market_chart 로 대체
    DAYS_MAP = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "1Y": 365, "3Y": 365}
    days = DAYS_MAP.get(period, 30)

    try:
        res = requests.get(
            f"{COINGECKO_BASE}/coins/{coin_id}/ohlc",
            params={"vs_currency": "usd", "days": days},
            timeout=10
        )
        raw = res.json()
        if not isinstance(raw, list):
            return jsonify({"error": "데이터 없음"}), 404

        from datetime import datetime, timezone
        candles = [
            {
                "t": datetime.fromtimestamp(item[0]/1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
                "o": item[1], "h": item[2], "l": item[3], "c": item[4],
            }
            for item in raw
        ]
        return jsonify(candles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return app.send_static_file("index.html")


app = app
