from flask import Flask, jsonify, request
from flask_cors import CORS
import yfinance as yf
import requests

app = Flask(__name__)
CORS(app)

COINGECKO_BASE = "https://api.coingecko.com/api/v3"

# ─────────────────────────────────────────
#  주식: yfinance
# ─────────────────────────────────────────

@app.route("/api/stock/search")
def stock_search():
    """티커 심볼로 주식 현재가 + 기본 정보 조회"""
    symbol = request.args.get("symbol", "").upper().strip()
    if not symbol:
        return jsonify({"error": "symbol 파라미터가 필요합니다"}), 400
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.fast_info
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            return jsonify({"error": f"{symbol} 데이터를 찾을 수 없습니다"}), 404

        price = round(float(info.last_price), 2)
        prev_close = round(float(info.previous_close), 2)
        change = round(price - prev_close, 2)
        change_pct = round((change / prev_close) * 100, 2)

        return jsonify({
            "symbol": symbol,
            "price": price,
            "prev_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "open": round(float(info.open), 2),
            "high": round(float(info.day_high), 2),
            "low": round(float(info.day_low), 2),
            "volume": int(info.three_month_average_volume or 0),
            "currency": info.currency,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stock/candles")
def stock_candles():
    """주식 캔들 데이터 (OHLCV)"""
    symbol = request.args.get("symbol", "").upper().strip()
    period = request.args.get("period", "1mo")   # 1d 1wk 1mo 3mo 6mo 1y
    interval = request.args.get("interval", "1d") # 1m 5m 15m 1h 1d 1wk

    PERIOD_MAP = {
        "1D": ("1d",  "5m"),
        "1W": ("5d",  "30m"),
        "1M": ("1mo", "1d"),
        "3M": ("3mo", "1d"),
        "1Y": ("1y",  "1wk"),
    }
    period, interval = PERIOD_MAP.get(period, ("1mo", "1d"))

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return jsonify({"error": "데이터 없음"}), 404

        candles = [
            {
                "t": str(idx)[:19],
                "o": round(float(row["Open"]), 2),
                "h": round(float(row["High"]), 2),
                "l": round(float(row["Low"]), 2),
                "c": round(float(row["Close"]), 2),
                "v": int(row["Volume"]),
            }
            for idx, row in hist.iterrows()
        ]
        return jsonify(candles)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────
#  암호화폐: CoinGecko (무료, 키 불필요)
# ─────────────────────────────────────────

COIN_ID_MAP = {
    "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
    "SOL": "solana",  "XRP": "ripple",   "ADA": "cardano",
    "DOGE": "dogecoin", "DOT": "polkadot", "MATIC": "matic-network",
}

def resolve_coin_id(symbol: str) -> str:
    """심볼 → CoinGecko id 변환 (모르는 심볼은 소문자로 그대로 시도)"""
    return COIN_ID_MAP.get(symbol.upper(), symbol.lower())


@app.route("/api/crypto/search")
def crypto_search():
    """암호화폐 현재가 조회"""
    symbol = request.args.get("symbol", "BTC").upper().strip()
    coin_id = resolve_coin_id(symbol)
    try:
        url = f"{COINGECKO_BASE}/simple/price"
        params = {
            "ids": coin_id,
            "vs_currencies": "usd",
            "include_24hr_change": "true",
            "include_24hr_vol": "true",
            "include_market_cap": "true",
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json().get(coin_id)
        if not data:
            return jsonify({"error": f"{symbol} 데이터를 찾을 수 없습니다"}), 404

        price = data["usd"]
        change_pct = round(data.get("usd_24h_change", 0), 2)
        return jsonify({
            "symbol": symbol,
            "coin_id": coin_id,
            "price": price,
            "change_pct": change_pct,
            "volume_24h": int(data.get("usd_24h_vol", 0)),
            "market_cap": int(data.get("usd_market_cap", 0)),
            "currency": "USD",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/crypto/candles")
def crypto_candles():
    """암호화폐 캔들 데이터 (CoinGecko OHLC endpoint)"""
    symbol = request.args.get("symbol", "BTC").upper().strip()
    period = request.args.get("period", "1M")
    coin_id = resolve_coin_id(symbol)

    DAYS_MAP = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "1Y": 365}
    days = DAYS_MAP.get(period, 30)

    try:
        url = f"{COINGECKO_BASE}/coins/{coin_id}/ohlc"
        res = requests.get(url, params={"vs_currency": "usd", "days": days}, timeout=10)
        raw = res.json()
        if not isinstance(raw, list):
            return jsonify({"error": "데이터 없음"}), 404

        from datetime import datetime, timezone
        candles = [
            {
                "t": datetime.fromtimestamp(item[0] / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"),
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
