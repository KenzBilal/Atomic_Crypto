"""
⚡ ATOMIC CRYPTO BOT — PROFESSIONAL EDITION v2.0
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Author: Atomic Crypto
Features:
  ✅ Free / Premium tiers (Telegram Stars)
  ✅ 15+ Technical indicators
  ✅ Auto daily signals (user sets time)
  ✅ Top gainers & losers
  ✅ Coin fundamentals
  ✅ Portfolio tracker
  ✅ Referral system
  ✅ Leaderboard
  ✅ Admin panel
  ✅ Price alerts (auto check)
  ✅ Watchlist
  ✅ Fear & Greed index
  ✅ Live crypto news
  ✅ Market overview
  ✅ Affiliate links (BingX + Binance)
  ✅ Dark & gold UI
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import requests
import pandas as pd
import numpy as np
import json
import os
import asyncio
import logging
from datetime import datetime, timezone
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    LabeledPrice, PreCheckoutQuery
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, PreCheckoutQueryHandler,
    filters
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── CONFIG ────────────────────────────────────────────────────────────────────
TELEGRAM_TOKEN = "8726083513:AAGxtqLZeBLGOy6RRdoKYzHmJjo8Vr1C5pU"
ADMIN_ID       = 8466348943
DATA_FILE      = "atomic_data.json"
GROK_API_KEY   = "YOUR_GROK_API_KEY"  # Replace with your key from console.x.ai

# Pricing (Telegram Stars)
PREMIUM_MONTHLY_STARS   = 500    # ~$4.99
PREMIUM_LIFETIME_STARS  = 2500   # ~$29.99

# Channel
CHANNEL_USERNAME = "@AtomicCryptoSignals"
CHANNEL_LINK     = "https://t.me/AtomicCryptoSignals"

# Affiliate Links
BINGX_LINK   = "https://bingx.pro/invite/IYJKPY/"
BINGX_CODE   = "IYJKPY"
BINANCE_LINK = "https://www.binance.com/referral/earn-together/refer2earn-usdc/claim?ref=GRO_28502_7P65U"

# Daily signal coins
SIGNAL_COINS = ["BTC", "ETH", "BNB", "SOL", "XRP"]
TOP_COINS    = ["BTC", "ETH", "BNB", "SOL", "XRP"]

# Free tier limits
FREE_ANALYSES_PER_DAY = 3
FREE_COINS            = ["BTC", "ETH"]
FREE_TIMEFRAMES       = ["1d"]

# ── LOGO HEADER ───────────────────────────────────────────────────────────────
LOGO = "⚡ *ATOMIC CRYPTO*"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── DATA PERSISTENCE ──────────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(uid: str) -> dict:
    data = load_data()
    if uid not in data:
        data[uid] = {
            "watchlist":       [],
            "alerts":          [],
            "portfolio":       {},
            "premium":         False,
            "premium_type":    None,
            "premium_expiry":  None,
            "referral_code":   f"REF{uid[-6:]}",
            "referred_by":     None,
            "referrals":       [],
            "analyses_today":  0,
            "analyses_date":   "",
            "signal_time":     "09:00",
            "signal_enabled":  True,
            "join_date":       datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            "username":        "",
            "total_analyses":  0,
        }
        save_data(data)
    return data[uid]

def update_user(uid: str, user: dict):
    data = load_data()
    data[uid] = user
    save_data(data)

def is_premium(uid: str) -> bool:
    user = get_user(uid)
    if not user.get("premium"):
        return False
    if user.get("premium_type") == "lifetime":
        return True
    expiry = user.get("premium_expiry")
    if expiry:
        exp_date = datetime.fromisoformat(expiry)
        if datetime.now(timezone.utc) < exp_date:
            return True
        else:
            user["premium"] = False
            update_user(uid, user)
            return False
    return False

def check_daily_limit(uid: str) -> tuple[bool, int]:
    """Returns (can_analyze, remaining)"""
    if is_premium(uid):
        return True, 999
    user = get_user(uid)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if user.get("analyses_date") != today:
        user["analyses_today"] = 0
        user["analyses_date"] = today
        update_user(uid, user)
    remaining = FREE_ANALYSES_PER_DAY - user.get("analyses_today", 0)
    return remaining > 0, remaining

def increment_analysis(uid: str):
    user = get_user(uid)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if user.get("analyses_date") != today:
        user["analyses_today"] = 0
        user["analyses_date"] = today
    user["analyses_today"] = user.get("analyses_today", 0) + 1
    user["total_analyses"]  = user.get("total_analyses", 0) + 1
    update_user(uid, user)

# ── API HELPERS ───────────────────────────────────────────────────────────────
def clean_symbol(symbol: str) -> str:
    return symbol.upper().strip().replace("USDT","").replace("BUSD","").replace("/","").replace("-","")

def fetch_ohlcv(symbol: str, interval: str, limit: int = 200):
    symbol = clean_symbol(symbol)
    interval_map = {"1h": "1hour", "4h": "4hour", "1d": "1day"}
    kc_interval = interval_map.get(interval, "1hour")
    pair = f"{symbol}-USDT"
    try:
        r = requests.get(
            "https://api.kucoin.com/api/v1/market/candles",
            params={"symbol": pair, "type": kc_interval},
            timeout=10
        )
        data = r.json().get("data", [])
        if not data:
            return None
        data = list(reversed(data))[-limit:]
        df = pd.DataFrame(data, columns=["open_time","open","close","high","low","volume","turnover"])
        for col in ["open","high","low","close","volume"]:
            df[col] = df[col].astype(float)
        return df
    except:
        return None

def fetch_price(symbol: str) -> float | None:
    symbol = clean_symbol(symbol)
    try:
        r = requests.get(
            "https://api.kucoin.com/api/v1/market/orderbook/level1",
            params={"symbol": f"{symbol}-USDT"},
            timeout=5
        )
        return float(r.json()["data"]["price"])
    except:
        return None

def fetch_24h(symbol: str) -> dict | None:
    symbol = clean_symbol(symbol)
    try:
        r = requests.get(
            "https://api.kucoin.com/api/v1/market/stats",
            params={"symbol": f"{symbol}-USDT"},
            timeout=5
        )
        d = r.json().get("data", {})
        if not d:
            return None
        last   = float(d.get("last", 0))
        open_  = float(d.get("open", 1))
        change = ((last - open_) / open_ * 100) if open_ else 0
        return {
            "price":  last,
            "change": round(change, 2),
            "high":   float(d.get("high", 0)),
            "low":    float(d.get("low", 0)),
            "vol":    float(d.get("volValue", 0)),
        }
    except:
        return None

def fetch_fear_greed() -> dict:
    try:
        r = requests.get("https://api.alternative.me/fng/", timeout=5)
        d = r.json()["data"][0]
        return {"value": int(d["value"]), "label": d["value_classification"]}
    except:
        return {"value": 50, "label": "Unknown"}

def fetch_news() -> list:
    try:
        r = requests.get(
            "https://min-api.cryptocompare.com/data/v2/news/?lang=EN&sortOrder=latest",
            timeout=8
        )
        items = r.json().get("Data", [])[:5]
        return [{"title": i["title"], "url": i["url"], "source": i["source_info"]["name"]} for i in items]
    except:
        return []

def fetch_top_movers() -> dict:
    """Fetch top gainers and losers from KuCoin"""
    try:
        r = requests.get("https://api.kucoin.com/api/v1/market/allTickers", timeout=10)
        tickers = r.json().get("data", {}).get("ticker", [])
        usdt = [t for t in tickers if t["symbol"].endswith("-USDT") and t.get("changeRate")]
        usdt = [t for t in usdt if float(t.get("vol", 0)) > 100000]
        usdt.sort(key=lambda x: float(x.get("changeRate", 0)), reverse=True)
        gainers = usdt[:5]
        losers  = list(reversed(usdt))[:5]
        return {"gainers": gainers, "losers": losers}
    except:
        return {"gainers": [], "losers": []}

def fetch_coin_info(symbol: str) -> dict | None:
    """Fetch coin fundamentals from CoinGecko"""
    id_map = {
        "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
        "SOL": "solana",  "XRP": "ripple",   "ADA": "cardano",
        "DOGE": "dogecoin", "MATIC": "matic-network", "DOT": "polkadot",
        "LINK": "chainlink", "AVAX": "avalanche-2", "ATOM": "cosmos",
        "UNI": "uniswap", "LTC": "litecoin", "BCH": "bitcoin-cash",
    }
    coin_id = id_map.get(clean_symbol(symbol).upper())
    if not coin_id:
        coin_id = clean_symbol(symbol).lower()
    try:
        r = requests.get(
            f"https://api.coingecko.com/api/v3/coins/{coin_id}",
            params={"localization": "false", "tickers": "false", "community_data": "false"},
            timeout=10
        )
        d = r.json()
        if "error" in d:
            return None
        md = d.get("market_data", {})
        return {
            "name":        d.get("name", symbol),
            "symbol":      d.get("symbol", "").upper(),
            "rank":        d.get("market_cap_rank", "N/A"),
            "price":       md.get("current_price", {}).get("usd", 0),
            "market_cap":  md.get("market_cap", {}).get("usd", 0),
            "volume_24h":  md.get("total_volume", {}).get("usd", 0),
            "change_24h":  md.get("price_change_percentage_24h", 0),
            "change_7d":   md.get("price_change_percentage_7d", 0),
            "change_30d":  md.get("price_change_percentage_30d", 0),
            "ath":         md.get("ath", {}).get("usd", 0),
            "ath_change":  md.get("ath_change_percentage", {}).get("usd", 0),
            "supply":      md.get("circulating_supply", 0),
            "max_supply":  md.get("max_supply", 0),
            "description": d.get("description", {}).get("en", "")[:300],
        }
    except:
        return None

# ── TECHNICAL INDICATORS ──────────────────────────────────────────────────────
def compute_all(df: pd.DataFrame) -> dict:
    c = df["close"]; h = df["high"]; l = df["low"]
    o = df["open"];  v = df["volume"]; n = len(df)

    delta = c.diff()
    gain  = delta.clip(lower=0).rolling(14).mean()
    loss  = (-delta.clip(upper=0)).rolling(14).mean()
    rsi   = 100 - (100 / (1 + gain / loss.replace(0, np.nan)))
    rsi_slope   = rsi.iloc[-1] - rsi.iloc[-5]
    price_slope = c.iloc[-1] - c.iloc[-5]
    rsi_div = "bullish" if price_slope < 0 and rsi_slope > 0 else \
              "bearish" if price_slope > 0 and rsi_slope < 0 else "none"

    ema12 = c.ewm(span=12, adjust=False).mean()
    ema26 = c.ewm(span=26, adjust=False).mean()
    macd  = ema12 - ema26
    sig   = macd.ewm(span=9, adjust=False).mean()
    hist  = macd - sig
    macd_cross    = "bullish" if macd.iloc[-1] > sig.iloc[-1] else "bearish"
    hist_momentum = "accelerating" if abs(hist.iloc[-1]) > abs(hist.iloc[-2]) else "decelerating"

    sma20    = c.rolling(20).mean()
    std20    = c.rolling(20).std()
    bb_upper = sma20 + 2 * std20
    bb_lower = sma20 - 2 * std20
    bb_pct_b = (c - bb_lower) / (bb_upper - bb_lower).replace(0, np.nan)
    bb_bw    = (bb_upper - bb_lower) / sma20
    bb_squeeze = bb_bw.iloc[-1] < bb_bw.rolling(20).mean().iloc[-1]

    ema9   = c.ewm(span=9,   adjust=False).mean()
    ema21  = c.ewm(span=21,  adjust=False).mean()
    ema50  = c.ewm(span=50,  adjust=False).mean()
    ema200 = c.ewm(span=200, adjust=False).mean()
    golden_cross   = ema50.iloc[-1] > ema200.iloc[-1] and ema50.iloc[-2] <= ema200.iloc[-2]
    death_cross    = ema50.iloc[-1] < ema200.iloc[-1] and ema50.iloc[-2] >= ema200.iloc[-2]
    ema_stack_bull = ema9.iloc[-1] > ema21.iloc[-1] > ema50.iloc[-1] > ema200.iloc[-1]
    ema_stack_bear = ema9.iloc[-1] < ema21.iloc[-1] < ema50.iloc[-1] < ema200.iloc[-1]

    rsi14   = rsi.rolling(14)
    stoch_r = (rsi - rsi14.min()) / (rsi14.max() - rsi14.min()).replace(0, np.nan)
    stoch_k = stoch_r.rolling(3).mean() * 100
    stoch_d = stoch_k.rolling(3).mean()

    tr    = pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    atr14 = tr.rolling(14).mean()
    atr_pct = atr14.iloc[-1] / c.iloc[-1] * 100

    obv = (np.sign(c.diff()) * v).fillna(0).cumsum()
    obv_trend = "bullish" if obv.iloc[-1] > obv.iloc[-10] else "bearish"

    typical = (h + l + c) / 3
    vwap    = (typical * v).rolling(20).sum() / v.rolling(20).sum()
    price_vs_vwap = "above" if c.iloc[-1] > vwap.iloc[-1] else "below"

    highest_h = h.rolling(14).max()
    lowest_l  = l.rolling(14).min()
    willr     = (highest_h - c) / (highest_h - lowest_l).replace(0, np.nan) * -100

    tp  = (h + l + c) / 3
    cci = (tp - tp.rolling(20).mean()) / (0.015 * tp.rolling(20).std())

    af, max_af = 0.02, 0.2
    sar = c.copy(); bull = True; ep = l.iloc[0]; _af = af
    for i in range(2, n):
        prev = sar.iloc[i-1]
        if bull:
            sar.iloc[i] = min(prev + _af*(ep-prev), l.iloc[i-1], l.iloc[i-2])
            if l.iloc[i] < sar.iloc[i]:
                bull=False; sar.iloc[i]=ep; ep=h.iloc[i]; _af=af
            elif h.iloc[i] > ep:
                ep=h.iloc[i]; _af=min(_af+af,max_af)
        else:
            sar.iloc[i] = max(prev + _af*(ep-prev), h.iloc[i-1], h.iloc[i-2])
            if h.iloc[i] > sar.iloc[i]:
                bull=True; sar.iloc[i]=ep; ep=l.iloc[i]; _af=af
            elif l.iloc[i] < ep:
                ep=l.iloc[i]; _af=min(_af+af,max_af)
    psar_bull = c.iloc[-1] > sar.iloc[-1]

    plus_dm  = h.diff().clip(lower=0)
    minus_dm = (-l.diff()).clip(lower=0)
    plus_dm[plus_dm < minus_dm]  = 0
    minus_dm[minus_dm < plus_dm] = 0
    atr14s   = tr.rolling(14).sum()
    plus_di  = 100 * plus_dm.rolling(14).sum() / atr14s.replace(0,np.nan)
    minus_di = 100 * minus_dm.rolling(14).sum() / atr14s.replace(0,np.nan)
    dx       = (abs(plus_di-minus_di)/(plus_di+minus_di).replace(0,np.nan))*100
    adx      = dx.rolling(14).mean()
    trend_strength = "Strong" if adx.iloc[-1] > 25 else "Weak"

    tenkan   = (h.rolling(9).max()  + l.rolling(9).min())  / 2
    kijun    = (h.rolling(26).max() + l.rolling(26).min()) / 2
    senkou_a = ((tenkan+kijun)/2).shift(26)
    senkou_b = ((h.rolling(52).max()+l.rolling(52).min())/2).shift(26)
    ichi_bull = c.iloc[-1] > senkou_a.iloc[-1] and c.iloc[-1] > senkou_b.iloc[-1]
    ichi_bear = c.iloc[-1] < senkou_a.iloc[-1] and c.iloc[-1] < senkou_b.iloc[-1]
    tk_cross_bull = tenkan.iloc[-1] > kijun.iloc[-1] and tenkan.iloc[-2] <= kijun.iloc[-2]
    tk_cross_bear = tenkan.iloc[-1] < kijun.iloc[-1] and tenkan.iloc[-2] >= kijun.iloc[-2]

    atr_m    = 3.0
    st_upper = (h+l)/2 + atr_m*atr14
    st_lower = (h+l)/2 - atr_m*atr14
    direction = pd.Series(1, index=df.index)
    for i in range(1, n):
        if c.iloc[i] > st_upper.iloc[i-1]:   direction.iloc[i] = 1
        elif c.iloc[i] < st_lower.iloc[i-1]: direction.iloc[i] = -1
        else:                                  direction.iloc[i] = direction.iloc[i-1]
    st_bull = direction.iloc[-1] == 1

    patterns = []
    o1,h1,l1,c1 = df.iloc[-1][["open","high","low","close"]]
    o2,h2,l2,c2 = df.iloc[-2][["open","high","low","close"]]
    o3,h3,l3,c3 = df.iloc[-3][["open","high","low","close"]]
    body1=abs(c1-o1); range1=h1-l1 if h1!=l1 else 0.0001
    body2=abs(c2-o2); body3=abs(c3-o3)
    bull1=c1>o1; bear1=c1<o1; bull2=c2>o2; bear2=c2<o2; bull3=c3>o3; bear3=c3<o3
    lw1=min(o1,c1)-l1; uw1=h1-max(o1,c1)
    if body1 < range1*0.1:                                      patterns.append(("Doji","neutral"))
    if lw1>body1*2 and uw1<body1*0.3:                           patterns.append(("Hammer" if bear2 else "Hanging Man","bullish" if bear2 else "bearish"))
    if uw1>body1*2 and lw1<body1*0.3:                           patterns.append(("Shooting Star" if bull2 else "Inv. Hammer","bearish" if bull2 else "bullish"))
    if bull1 and bear2 and c1>o2 and o1<c2:                    patterns.append(("Bullish Engulfing","bullish"))
    if bear1 and bull2 and c1<o2 and o1>c2:                    patterns.append(("Bearish Engulfing","bearish"))
    if bear3 and body2<(h2-l2)*0.3 and bull1 and c1>(o3+c3)/2: patterns.append(("Morning Star","bullish"))
    if bull3 and body2<(h2-l2)*0.3 and bear1 and c1<(o3+c3)/2: patterns.append(("Evening Star","bearish"))
    if bull1 and bull2 and bull3 and c1>c2>c3:                  patterns.append(("3 White Soldiers","bullish"))
    if bear1 and bear2 and bear3 and c1<c2<c3:                  patterns.append(("3 Black Crows","bearish"))
    if abs(l1-l2)<range1*0.05 and bear2 and bull1:              patterns.append(("Tweezer Bottom","bullish"))
    if abs(h1-h2)<range1*0.05 and bull2 and bear1:              patterns.append(("Tweezer Top","bearish"))

    vol_avg20 = v.rolling(20).mean().iloc[-1]
    vol_ratio = v.iloc[-1] / vol_avg20 if vol_avg20 > 0 else 1

    return {
        "price": round(c.iloc[-1], 6),
        "rsi": round(rsi.iloc[-1], 2),
        "rsi_div": rsi_div,
        "macd_cross": macd_cross,
        "macd_hist": round(hist.iloc[-1], 8),
        "hist_momentum": hist_momentum,
        "bb_pct_b": round(bb_pct_b.iloc[-1]*100, 1),
        "bb_squeeze": bb_squeeze,
        "ema50": round(ema50.iloc[-1], 6),
        "ema200": round(ema200.iloc[-1], 6),
        "golden_cross": golden_cross,
        "death_cross": death_cross,
        "ema_stack_bull": ema_stack_bull,
        "ema_stack_bear": ema_stack_bear,
        "stoch_k": round(stoch_k.iloc[-1], 2),
        "stoch_d": round(stoch_d.iloc[-1], 2),
        "atr_pct": round(atr_pct, 2),
        "obv_trend": obv_trend,
        "price_vs_vwap": price_vs_vwap,
        "willr": round(willr.iloc[-1], 2),
        "cci": round(cci.iloc[-1], 2),
        "psar_bull": psar_bull,
        "adx": round(adx.iloc[-1], 2),
        "trend_strength": trend_strength,
        "ichi_bull": ichi_bull,
        "ichi_bear": ichi_bear,
        "tk_cross_bull": tk_cross_bull,
        "tk_cross_bear": tk_cross_bear,
        "st_bull": st_bull,
        "patterns": patterns,
        "vol_surge": vol_ratio > 1.5,
        "vol_ratio": round(vol_ratio, 2),
    }

# ── SCORING ENGINE ────────────────────────────────────────────────────────────
def score(ind: dict) -> dict:
    b = 0; br = 0; sigs = []

    def add(bp, brp, label):
        nonlocal b, br
        b += bp; br += brp
        if bp > 0: sigs.append(f"✅ {label}")
        if brp > 0: sigs.append(f"❌ {label}")

    if ind["rsi"] < 30:    add(8,0,f"RSI Oversold ({ind['rsi']})")
    elif ind["rsi"] > 70:  add(0,8,f"RSI Overbought ({ind['rsi']})")
    elif ind["rsi"] > 55:  add(3,0,f"RSI Bullish Zone")
    elif ind["rsi"] < 45:  add(0,3,f"RSI Bearish Zone")
    if ind["rsi_div"] == "bullish":   add(10,0,"Bullish RSI Divergence")
    elif ind["rsi_div"] == "bearish": add(0,10,"Bearish RSI Divergence")
    if ind["macd_cross"] == "bullish": add(7,0,"MACD Bullish Cross")
    else:                               add(0,7,"MACD Bearish Cross")
    if ind["hist_momentum"] == "accelerating":
        if ind["macd_cross"] == "bullish": add(3,0,"MACD Momentum ↑")
        else:                               add(0,3,"MACD Momentum ↓")
    if ind["bb_pct_b"] < 10:   add(6,0,"BB Lower Band Touch")
    elif ind["bb_pct_b"] > 90: add(0,6,"BB Upper Band Touch")
    if ind["bb_squeeze"]:       add(2,2,"BB Squeeze Detected")
    if ind["ema_stack_bull"]:   add(9,0,"Full Bullish EMA Stack")
    elif ind["ema_stack_bear"]: add(0,9,"Full Bearish EMA Stack")
    elif ind["ema50"] > ind["ema200"]: add(4,0,"EMA50 > EMA200")
    else:                              add(0,4,"EMA50 < EMA200")
    if ind["golden_cross"]: add(12,0,"🌟 Golden Cross")
    if ind["death_cross"]:  add(0,12,"💀 Death Cross")
    if ind["stoch_k"] < 20 and ind["stoch_k"] > ind["stoch_d"]: add(6,0,"Stoch RSI Oversold Cross")
    elif ind["stoch_k"] > 80 and ind["stoch_k"] < ind["stoch_d"]: add(0,6,"Stoch RSI Overbought Cross")
    if ind["obv_trend"] == "bullish": add(5,0,"OBV Bullish")
    else:                              add(0,5,"OBV Bearish")
    if ind["price_vs_vwap"] == "above": add(5,0,"Price Above VWAP")
    else:                                add(0,5,"Price Below VWAP")
    if ind["willr"] < -80:   add(5,0,"Williams %R Oversold")
    elif ind["willr"] > -20: add(0,5,"Williams %R Overbought")
    if ind["cci"] < -100:  add(5,0,"CCI Oversold")
    elif ind["cci"] > 100: add(0,5,"CCI Overbought")
    if ind["psar_bull"]: add(6,0,"Parabolic SAR Bullish")
    else:                 add(0,6,"Parabolic SAR Bearish")
    if ind["ichi_bull"]:     add(8,0,"Above Ichimoku Cloud")
    elif ind["ichi_bear"]:   add(0,8,"Below Ichimoku Cloud")
    if ind["tk_cross_bull"]: add(5,0,"Ichimoku TK Bull Cross")
    if ind["tk_cross_bear"]: add(0,5,"Ichimoku TK Bear Cross")
    if ind["st_bull"]: add(7,0,"Supertrend Bullish")
    else:               add(0,7,"Supertrend Bearish")
    for name, bias in ind["patterns"]:
        if bias == "bullish":   add(6,0,f"Pattern: {name}")
        elif bias == "bearish": add(0,6,f"Pattern: {name}")
    if ind["vol_surge"]:
        if b > br: add(4,0,f"Volume Surge ({ind['vol_ratio']}x)")
        else:       add(0,4,f"Volume Surge ({ind['vol_ratio']}x)")

    adx_mult = 1.2 if ind["trend_strength"] == "Strong" else 0.9
    total    = b + br
    if total == 0:
        return {"direction":"NEUTRAL","confidence":50,"signal":"HOLD","risk":"MEDIUM",
                "bull_signals":[],"bear_signals":[],"bull_score":0,"bear_score":0}
    net      = (b - br) * adx_mult
    conf     = min(85, max(50, round(50 + (abs(net)/(total*adx_mult))*45)))
    direction= "UP" if net > 0 else "DOWN" if net < 0 else "NEUTRAL"
    signal   = "BUY" if direction=="UP" and conf>=65 else \
               "SELL" if direction=="DOWN" and conf>=65 else "HOLD"
    risk     = "HIGH" if ind["atr_pct"]>3 else "MEDIUM" if ind["atr_pct"]>1.5 else "LOW"

    return {
        "direction":    direction,
        "confidence":   conf,
        "signal":       signal,
        "risk":         risk,
        "bull_signals": [s for s in sigs if s.startswith("✅")][:5],
        "bear_signals": [s for s in sigs if s.startswith("❌")][:5],
        "bull_score":   round(b),
        "bear_score":   round(br),
    }

# ── FORMAT ANALYSIS ───────────────────────────────────────────────────────────

# ── GROK AI ANALYSIS ──────────────────────────────────────────────────────────
async def get_grok_analysis(symbol: str, ind: dict, pred: dict) -> str:
    """Call Grok API for AI-powered analysis with X/Twitter sentiment"""
    try:
        prompt = f"""You are an expert crypto analyst. Analyze {symbol}/USDT and provide a sharp, confident 3-4 sentence analysis.

Technical data:
- Price: {ind['price']}
- RSI: {ind['rsi']} ({'Overbought' if ind['rsi']>70 else 'Oversold' if ind['rsi']<30 else 'Neutral'})
- MACD: {ind['macd_cross']} crossover
- EMA Trend: {'Bullish stack' if ind['ema_stack_bull'] else 'Bearish stack' if ind['ema_stack_bear'] else 'Mixed'}
- Ichimoku: {'Above cloud' if ind['ichi_bull'] else 'Below cloud' if ind['ichi_bear'] else 'Inside cloud'}
- Supertrend: {'Bullish' if ind['st_bull'] else 'Bearish'}
- Volume: {ind['vol_ratio']}x average {'(surge)' if ind['vol_surge'] else ''}
- Signal: {pred['signal']} with {pred['confidence']}% confidence
- Patterns: {', '.join([p[0] for p in ind['patterns']]) if ind['patterns'] else 'None'}

Also check current X/Twitter sentiment for {symbol} crypto. What are people saying?

Respond in exactly this format (no extra text):
SENTIMENT: [Bullish/Bearish/Neutral] (X/Twitter sentiment score X/10)
ANALYSIS: [3-4 sentences combining technicals + X sentiment]
KEY_LEVEL: [Most important price level to watch]
OUTLOOK: [One line short-term outlook]"""

        r = requests.post(
            "https://api.x.ai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROK_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "grok-3-latest",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.7
            },
            timeout=15
        )
        result = r.json()
        return result["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"Grok error: {e}")
        return None

def format_grok_section(grok_text: str) -> str:
    """Parse and format Grok response into clean message"""
    if not grok_text:
        return ""
    lines = {}
    for line in grok_text.strip().splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            lines[k.strip()] = v.strip()

    sentiment  = lines.get("SENTIMENT", "").replace("*","").replace("_","").replace("`","")
    analysis   = lines.get("ANALYSIS", "").replace("*","").replace("_","").replace("`","")
    key_level  = lines.get("KEY_LEVEL", "").replace("*","").replace("_","").replace("`","")
    outlook    = lines.get("OUTLOOK", "").replace("*","").replace("_","").replace("`","")

    sent_e = "🟢" if "Bullish" in sentiment else "🔴" if "Bearish" in sentiment else "🟡"

    return (
        f"\n{DIVIDER}\n"
        f"🤖 GROK AI + X SENTIMENT\n"
        f"{sent_e} {sentiment}\n\n"
        f"{analysis}\n\n"
        f"🎯 Key Level: {key_level}\n"
        f"🔭 Outlook: {outlook}\n"
        f"{DIVIDER}"
    )

def format_analysis(symbol, tf_label, ind, pred, premium=False, grok_text=None) -> str:
    dir_e  = "📈" if pred["direction"]=="UP" else "📉" if pred["direction"]=="DOWN" else "➡️"
    sig_e  = "🟢" if pred["signal"]=="BUY" else "🔴" if pred["signal"]=="SELL" else "🟡"
    risk_e = "🟢" if pred["risk"]=="LOW" else "🟡" if pred["risk"]=="MEDIUM" else "🔴"
    bar    = "█"*(pred["confidence"]//10) + "░"*(10-pred["confidence"]//10)
    rsi_s  = "🔥 Overbought" if ind["rsi"]>70 else "🧊 Oversold" if ind["rsi"]<30 else "✅ Neutral"
    pats   = ", ".join([p[0] for p in ind["patterns"]]) if ind["patterns"] else "None"
    bulls  = "\n".join(pred["bull_signals"]) or "  —"
    bears  = "\n".join(pred["bear_signals"]) or "  —"
    tier   = "⭐ PREMIUM" if premium else "🆓 FREE"
    grok_section = ""
    if premium and grok_text:
        grok_section = format_grok_section(grok_text)
    elif not premium:
        grok_section = (
            f"\n{DIVIDER}\n"
            "🤖 GROK AI + X SENTIMENT\n"
            "🔒 Premium Feature\n"
            "Upgrade to unlock AI analysis\n"
            "and live X/Twitter sentiment!\n"
            f"{DIVIDER}"
        )

    return f"""
{LOGO} {tier}
{DIVIDER}
🪙 *{symbol}/USDT* — _{tf_label}_
{DIVIDER}

💰 *Price:* `{ind['price']}`

┌─── 🤖 PREDICTION ──────────────
│ {dir_e} Direction:   `{pred['direction']}`
│ 📊 Confidence: `{pred['confidence']}%`  {bar}
│ {sig_e} Signal:      `{pred['signal']}`
│ {risk_e} Risk Level:  `{pred['risk']}`
│ ⚡ ADX Trend:  `{ind['trend_strength']}` ({ind['adx']:.1f})
└────────────────────────────────

🏆 Bull: `{pred['bull_score']}`  🩸 Bear: `{pred['bear_score']}`

┌─── 🟢 BULL SIGNALS ────────────
{bulls}
└────────────────────────────────

┌─── 🔴 BEAR SIGNALS ────────────
{bears}
└────────────────────────────────

┌─── 📐 KEY INDICATORS ──────────
│ RSI(14):     `{ind['rsi']}` {rsi_s}
│ Stoch RSI:   `K={ind['stoch_k']} / D={ind['stoch_d']}`
│ MACD:        `{ind['macd_cross'].capitalize()}` ({ind['hist_momentum']})
│ BB %B:       `{ind['bb_pct_b']}%`{'  🔲 Squeeze!' if ind['bb_squeeze'] else ''}
│ Williams %R: `{ind['willr']}`
│ CCI:         `{ind['cci']:.1f}`
│ ATR:         `{ind['atr_pct']}%`
└────────────────────────────────

┌─── 🌐 TREND ANALYSIS ──────────
│ EMA Stack:  {'🟢 Full Bull' if ind['ema_stack_bull'] else '🔴 Full Bear' if ind['ema_stack_bear'] else '🟡 Mixed'}
│ Ichimoku:   {'🟢 Above Cloud' if ind['ichi_bull'] else '🔴 Below Cloud' if ind['ichi_bear'] else '🟡 Inside'}
│ Supertrend: {'🟢 Bullish' if ind['st_bull'] else '🔴 Bearish'}
│ PSAR:       {'🟢 Bullish' if ind['psar_bull'] else '🔴 Bearish'}
│ VWAP:       `{ind['price_vs_vwap'].capitalize()}`
│ OBV:        `{ind['obv_trend'].capitalize()}`
│ Volume:     `{ind['vol_ratio']}x avg` {'🔥 SURGE' if ind['vol_surge'] else ''}
└────────────────────────────────

🕯️ *Patterns:* _{pats}_
{grok_section}

{DIVIDER}
⚠️ _Not financial advice. DYOR._
💹 _Trade on BingX:_ [Join Here]({BINGX_LINK}) `{BINGX_CODE}`
""".strip()

# ── KEYBOARDS ─────────────────────────────────────────────────────────────────
def main_menu_kb(uid: str):
    premium = is_premium(uid)
    tier_btn = "⭐ Premium Active" if premium else "🔓 Upgrade to Premium"
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Analyze Coin",     callback_data="menu_analyze"),
         InlineKeyboardButton("🌍 Market Overview",  callback_data="menu_market")],
        [InlineKeyboardButton("📈 Top Movers",        callback_data="menu_movers"),
         InlineKeyboardButton("😨 Fear & Greed",     callback_data="menu_fg")],
        [InlineKeyboardButton("⭐ Watchlist",         callback_data="menu_watchlist"),
         InlineKeyboardButton("🚨 Price Alerts",     callback_data="menu_alerts")],
        [InlineKeyboardButton("💼 Portfolio",         callback_data="menu_portfolio"),
         InlineKeyboardButton("📰 Crypto News",      callback_data="menu_news")],
        [InlineKeyboardButton("🔍 Coin Info",         callback_data="menu_coininfo"),
         InlineKeyboardButton("🏅 Leaderboard",      callback_data="menu_leaderboard")],
        [InlineKeyboardButton("👥 Refer & Earn",      callback_data="menu_referral"),
         InlineKeyboardButton("⚙️ Settings",         callback_data="menu_settings")],
        [InlineKeyboardButton(f"💎 {tier_btn}",       callback_data="menu_premium")],
        [InlineKeyboardButton("🏦 Exchanges",         callback_data="menu_exchanges")],
        [InlineKeyboardButton("📣 Join Our Channel 🚀", url=CHANNEL_LINK)],
    ])

def coin_select_kb(action="analyze"):
    rows = [[InlineKeyboardButton(c, callback_data=f"{action}_coin|{c}") for c in TOP_COINS]]
    rows.append([InlineKeyboardButton("🔍 Search Any Coin", callback_data=f"{action}_search")])
    rows.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
    return InlineKeyboardMarkup(rows)

def timeframe_kb(symbol: str, uid: str):
    premium = is_premium(uid)
    if premium:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱ 1H", callback_data=f"tf|{symbol}|1h"),
             InlineKeyboardButton("⏱ 4H", callback_data=f"tf|{symbol}|4h"),
             InlineKeyboardButton("📅 1D", callback_data=f"tf|{symbol}|1d")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_analyze")],
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 1D (Free)", callback_data=f"tf|{symbol}|1d"),
             InlineKeyboardButton("⏱ 1H 🔒", callback_data="upgrade_prompt"),
             InlineKeyboardButton("⏱ 4H 🔒", callback_data="upgrade_prompt")],
            [InlineKeyboardButton("🔙 Back", callback_data="menu_analyze")],
        ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")]])

def premium_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⭐ Monthly — 500 Stars", callback_data="buy_monthly")],
        [InlineKeyboardButton("💎 Lifetime — 2500 Stars", callback_data="buy_lifetime")],
        [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
    ])

# ── HANDLERS ──────────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid      = str(update.effective_user.id)
    name     = update.effective_user.first_name or "Trader"
    username = update.effective_user.username or ""
    user     = get_user(uid)
    user["username"] = username
    update_user(uid, user)

    # Handle referral
    args = context.args
    if args and args[0].startswith("REF") and not user.get("referred_by"):
        ref_code = args[0]
        data = load_data()
        for rid, ruser in data.items():
            if ruser.get("referral_code") == ref_code and rid != uid:
                user["referred_by"] = rid
                ruser.setdefault("referrals", []).append(uid)
                update_user(rid, ruser)
                break
        update_user(uid, user)

    premium = is_premium(uid)
    tier    = "⭐ Premium" if premium else "🆓 Free"

    await update.message.reply_text(
        f"{LOGO}\n"
        f"{DIVIDER}\n"
        f"👋 *Welcome, {name}!*\n\n"
        f"Your professional crypto analysis assistant.\n"
        f"Powered by *15+ indicators* & real-time data.\n\n"
        f"📊 Current Plan: *{tier}*\n"
        f"🔑 Your Referral Code: `{user['referral_code']}`\n\n"
        f"📣 Join our channel: {CHANNEL_LINK}\n\n"
        f"Select an option below 👇",
        reply_markup=main_menu_kb(uid),
        parse_mode="Markdown"
    )

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data  = query.data
    uid   = str(query.from_user.id)
    user  = get_user(uid)
    premium = is_premium(uid)

    # ── MAIN MENU ──
    if data == "menu_main":
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            f"📊 Plan: *{'⭐ Premium' if premium else '🆓 Free'}*\n\n"
            "Select an option 👇",
            reply_markup=main_menu_kb(uid),
            parse_mode="Markdown"
        )

    # ── ANALYZE ──
    elif data == "menu_analyze":
        can, remaining = check_daily_limit(uid)
        if not can:
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n"
                "⚠️ *Daily limit reached!*\n\n"
                f"Free users get *{FREE_ANALYSES_PER_DAY} analyses/day*.\n"
                "Upgrade to Premium for *unlimited* analysis! 🚀",
                reply_markup=premium_kb(),
                parse_mode="Markdown"
            )
            return
        limit_text = "" if premium else f"\n_({remaining} analyses remaining today)_"
        coins_text = "Any coin" if premium else "BTC & ETH only (Free)"
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            f"📊 *Analyze a Coin*\n"
            f"🪙 Available: _{coins_text}_\n"
            f"{limit_text}\n\n"
            "Select a coin or search:",
            reply_markup=coin_select_kb("analyze"),
            parse_mode="Markdown"
        )

    elif data.startswith("analyze_coin|"):
        symbol = data.split("|")[1]
        if not premium and symbol not in FREE_COINS:
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n"
                f"🔒 *{symbol} is Premium only*\n\n"
                "Free users can analyze BTC & ETH.\n"
                "Upgrade to analyze *any coin!* 🚀",
                reply_markup=premium_kb(),
                parse_mode="Markdown"
            )
            return
        await query.edit_message_text(
            f"🪙 *{symbol}/USDT* — Select timeframe:",
            reply_markup=timeframe_kb(symbol, uid),
            parse_mode="Markdown"
        )

    elif data == "analyze_search":
        context.user_data["action"] = "analyze"
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            "🔍 *Search Any Coin*\n\n"
            "Type the coin symbol:\n"
            "_(e.g. PEPE, AVAX, LINK, DOT)_",
            parse_mode="Markdown"
        )

    elif data == "upgrade_prompt":
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            "🔒 *Premium Feature*\n\n"
            "1H and 4H timeframes are available for Premium users.\n\n"
            "Upgrade now to unlock:\n"
            "• All timeframes (1H, 4H, 1D)\n"
            "• Any coin analysis\n"
            "• Unlimited daily analyses\n"
            "• Price alerts & watchlist\n"
            "• And much more! 🚀",
            reply_markup=premium_kb(),
            parse_mode="Markdown"
        )

    elif data.startswith("tf|"):
        _, symbol, tf = data.split("|")
        if not premium and tf != "1d":
            await query.edit_message_text(
                f"🔒 *{tf.upper()} timeframe is Premium only*",
                reply_markup=premium_kb(),
                parse_mode="Markdown"
            )
            return
        tf_labels = {"1h": "1 Hour", "4h": "4 Hours", "1d": "1 Day"}
        tf_label  = tf_labels.get(tf, tf)
        await query.edit_message_text(
            f"⏳ Analyzing *{symbol}/USDT* on {tf_label}...\n"
            "_Running 15+ indicators_ 📊",
            parse_mode="Markdown"
        )
        df = fetch_ohlcv(symbol, tf)
        if df is None or len(df) < 60:
            await query.edit_message_text(
                f"❌ *{symbol}/USDT* not found.\nCheck the symbol and try again.",
                reply_markup=back_kb(), parse_mode="Markdown"
            )
            return
        ind  = compute_all(df)
        pred = score(ind)
        grok_text = None
        if premium:
            await query.edit_message_text(
                f"⏳ Running Grok AI analysis for *{symbol}/USDT*...\n"
                "_Checking X sentiment + technicals_ 🤖",
                parse_mode="Markdown"
            )
            grok_text = await get_grok_analysis(symbol, ind, pred)
        msg  = format_analysis(symbol, tf_label, ind, pred, premium, grok_text)
        increment_analysis(uid)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"tf|{symbol}|{tf}"),
             InlineKeyboardButton("⭐ Watchlist", callback_data=f"wl_add|{symbol}")],
            [InlineKeyboardButton("🔍 Coin Info", callback_data=f"coininfo|{symbol}"),
             InlineKeyboardButton("🏠 Menu", callback_data="menu_main")],
        ])
        await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown", disable_web_page_preview=True)

    # ── MARKET OVERVIEW ──
    elif data == "menu_market":
        await query.edit_message_text("⏳ Fetching market data...", parse_mode="Markdown")
        fg   = fetch_fear_greed()
        fg_e = "🟢" if fg["value"] >= 60 else "🔴" if fg["value"] <= 40 else "🟡"
        lines = [
            f"{LOGO}\n{DIVIDER}",
            f"🌍 *Market Overview*\n",
            f"{fg_e} Fear & Greed: *{fg['value']}/100* — _{fg['label']}_\n",
            f"{DIVIDER}",
        ]
        for coin in TOP_COINS:
            d = fetch_24h(coin)
            if d:
                e = "📈" if d["change"] >= 0 else "📉"
                lines.append(f"{e} *{coin}:* `${d['price']:,.4f}` `{d['change']:+.2f}%`")
        lines.append(f"\n{DIVIDER}")
        lines.append("_Powered by KuCoin • Real-time data_")
        await query.edit_message_text(
            "\n".join(lines), reply_markup=back_kb(), parse_mode="Markdown"
        )

    # ── TOP MOVERS ──
    elif data == "menu_movers":
        await query.edit_message_text("⏳ Fetching top movers...", parse_mode="Markdown")
        movers = fetch_top_movers()
        lines  = [f"{LOGO}\n{DIVIDER}", "📈 *TOP GAINERS (24H)*\n"]
        for i, t in enumerate(movers["gainers"], 1):
            sym  = t["symbol"].replace("-USDT","")
            chg  = float(t.get("changeRate", 0)) * 100
            price= float(t.get("last", 0))
            lines.append(f"`{i}.` 🟢 *{sym}* `+{chg:.2f}%` — `${price:,.6f}`")
        lines.append(f"\n{DIVIDER}")
        lines.append("📉 *TOP LOSERS (24H)*\n")
        for i, t in enumerate(movers["losers"], 1):
            sym  = t["symbol"].replace("-USDT","")
            chg  = float(t.get("changeRate", 0)) * 100
            price= float(t.get("last", 0))
            lines.append(f"`{i}.` 🔴 *{sym}* `{chg:.2f}%` — `${price:,.6f}`")
        lines.append(f"\n{DIVIDER}\n_Source: KuCoin_")
        await query.edit_message_text(
            "\n".join(lines), reply_markup=back_kb(), parse_mode="Markdown"
        )

    # ── FEAR & GREED ──
    elif data == "menu_fg":
        fg  = fetch_fear_greed()
        val = fg["value"]
        if val >= 75:   e,desc = "🤑","Extreme Greed — Market may be overheated"
        elif val >= 55: e,desc = "😀","Greed — Bullish sentiment dominates"
        elif val >= 45: e,desc = "😐","Neutral — No clear sentiment"
        elif val >= 25: e,desc = "😨","Fear — Bearish sentiment dominates"
        else:           e,desc = "😱","Extreme Fear — Potential buying opportunity"
        bar = "█"*(val//10) + "░"*(10-val//10)
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            f"😨 *Fear & Greed Index*\n\n"
            f"{e} *{val}/100* — _{fg['label']}_\n\n"
            f"`{bar}`\n\n"
            f"📝 _{desc}_\n\n"
            f"_0 = Extreme Fear  |  100 = Extreme Greed_\n"
            f"_Source: alternative.me_",
            reply_markup=back_kb(), parse_mode="Markdown"
        )

    # ── WATCHLIST ──
    elif data == "menu_watchlist":
        wl = user.get("watchlist", [])
        if not wl:
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n"
                "⭐ *My Watchlist*\n\nEmpty! Analyze a coin and tap ⭐ to add it.",
                reply_markup=back_kb(), parse_mode="Markdown"
            )
            return
        buttons = [
            [InlineKeyboardButton(f"📊 {c}", callback_data=f"analyze_coin|{c}"),
             InlineKeyboardButton(f"🗑 Remove", callback_data=f"wl_remove|{c}")]
            for c in wl
        ]
        buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            f"⭐ *My Watchlist* — {len(wl)} coins\n\nTap 📊 to analyze or 🗑 to remove:",
            reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
        )

    elif data.startswith("wl_add|"):
        symbol = data.split("|")[1]
        if symbol not in user["watchlist"]:
            user["watchlist"].append(symbol)
            update_user(uid, user)
            await query.answer(f"⭐ {symbol} added to watchlist!")
        else:
            await query.answer(f"{symbol} already in watchlist.")

    elif data.startswith("wl_remove|"):
        symbol = data.split("|")[1]
        if symbol in user["watchlist"]:
            user["watchlist"].remove(symbol)
            update_user(uid, user)
        await query.answer(f"🗑 {symbol} removed.")
        wl = get_user(uid).get("watchlist", [])
        if not wl:
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n⭐ *Watchlist is empty.*",
                reply_markup=back_kb(), parse_mode="Markdown"
            )
        else:
            buttons = [
                [InlineKeyboardButton(f"📊 {c}", callback_data=f"analyze_coin|{c}"),
                 InlineKeyboardButton(f"🗑 Remove", callback_data=f"wl_remove|{c}")]
                for c in wl
            ]
            buttons.append([InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")])
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n⭐ *My Watchlist* — {len(wl)} coins",
                reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown"
            )

    # ── PRICE ALERTS ──
    elif data == "menu_alerts":
        alerts = user.get("alerts", [])
        msg    = f"{LOGO}\n{DIVIDER}\n\n🚨 *Price Alerts*\n\n"
        if alerts:
            for a in alerts:
                e = "📈" if a["direction"] == "above" else "📉"
                msg += f"{e} *{a['symbol']}* {a['direction']} `${a['target']:,.2f}`\n"
        else:
            msg += "No alerts set.\n"
        msg += f"\n{DIVIDER}\n📌 _Set alert:_ `/alert BTC above 70000`\n_or_ `/alert ETH below 3000`"
        await query.edit_message_text(msg, reply_markup=back_kb(), parse_mode="Markdown")

    # ── PORTFOLIO ──
    elif data == "menu_portfolio":
        portfolio = user.get("portfolio", {})
        if not portfolio:
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n"
                "💼 *Portfolio Tracker*\n\n"
                "Empty! Add coins with:\n"
                "`/add BTC 0.5 42000`\n"
                "_(symbol, amount, buy price)_",
                reply_markup=back_kb(), parse_mode="Markdown"
            )
            return
        await query.edit_message_text("⏳ Calculating portfolio...", parse_mode="Markdown")
        total_invested = 0
        total_current  = 0
        lines = [f"{LOGO}\n{DIVIDER}", "💼 *My Portfolio*\n"]
        for sym, holding in portfolio.items():
            price = fetch_price(sym)
            if price is None:
                continue
            invested = holding["amount"] * holding["buy_price"]
            current  = holding["amount"] * price
            pnl      = current - invested
            pnl_pct  = (pnl / invested * 100) if invested else 0
            pnl_e    = "📈" if pnl >= 0 else "📉"
            total_invested += invested
            total_current  += current
            lines.append(
                f"{pnl_e} *{sym}:* `{holding['amount']}` @ `${holding['buy_price']:,.4f}`\n"
                f"   Now: `${price:,.4f}` | PnL: `{pnl_pct:+.2f}%` (`${pnl:+.2f}`)"
            )
        total_pnl     = total_current - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested else 0
        lines.append(f"\n{DIVIDER}")
        lines.append(f"💰 *Total Invested:* `${total_invested:,.2f}`")
        lines.append(f"💎 *Current Value:*  `${total_current:,.2f}`")
        lines.append(f"{'📈' if total_pnl>=0 else '📉'} *Total PnL:* `{total_pnl_pct:+.2f}%` (`${total_pnl:+.2f}`)")
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🗑 Clear Portfolio", callback_data="portfolio_clear")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ])
        await query.edit_message_text("\n".join(lines), reply_markup=kb, parse_mode="Markdown")

    elif data == "portfolio_clear":
        user["portfolio"] = {}
        update_user(uid, user)
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n💼 Portfolio cleared!",
            reply_markup=back_kb(), parse_mode="Markdown"
        )

    # ── NEWS ──
    elif data == "menu_news":
        await query.edit_message_text("⏳ Fetching latest news...", parse_mode="Markdown")
        news = fetch_news()
        if not news:
            await query.edit_message_text(
                "📰 Could not fetch news. Try again later.",
                reply_markup=back_kb(), parse_mode="Markdown"
            )
            return
        msg = f"{LOGO}\n{DIVIDER}\n\n📰 *Latest Crypto News*\n\n"
        for i, n in enumerate(news, 1):
            msg += f"*{i}. {n['title']}*\n_{n['source']}_ — [Read →]({n['url']})\n\n"
        await query.edit_message_text(
            msg, reply_markup=back_kb(), parse_mode="Markdown", disable_web_page_preview=True
        )

    # ── COIN INFO ──
    elif data == "menu_coininfo":
        context.user_data["action"] = "coininfo"
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            "🔍 *Coin Fundamentals*\n\n"
            "Type a coin symbol:\n_(e.g. BTC, ETH, SOL, DOGE)_",
            parse_mode="Markdown"
        )

    elif data.startswith("coininfo|"):
        symbol = data.split("|")[1]
        await query.edit_message_text(f"⏳ Fetching {symbol} info...", parse_mode="Markdown")
        info = fetch_coin_info(symbol)
        if not info:
            await query.edit_message_text(
                f"❌ Could not fetch info for *{symbol}*.",
                reply_markup=back_kb(), parse_mode="Markdown"
            )
            return
        mc  = info["market_cap"]
        vol = info["volume_24h"]
        mc_str  = f"${mc/1e9:.2f}B" if mc > 1e9 else f"${mc/1e6:.2f}M"
        vol_str = f"${vol/1e9:.2f}B" if vol > 1e9 else f"${vol/1e6:.2f}M"
        sup_str = f"{info['supply']:,.0f}" if info['supply'] else "N/A"
        max_str = f"{info['max_supply']:,.0f}" if info['max_supply'] else "∞"
        msg = (
            f"{LOGO}\n{DIVIDER}\n\n"
            f"🔍 *{info['name']} ({info['symbol']})*\n"
            f"📊 Rank: *#{info['rank']}*\n\n"
            f"{DIVIDER}\n"
            f"💰 *Price:*        `${info['price']:,.6f}`\n"
            f"📈 *24h Change:*   `{info['change_24h']:+.2f}%`\n"
            f"📅 *7d Change:*    `{info['change_7d']:+.2f}%`\n"
            f"🗓 *30d Change:*   `{info['change_30d']:+.2f}%`\n\n"
            f"{DIVIDER}\n"
            f"💎 *Market Cap:*   `{mc_str}`\n"
            f"📦 *Volume 24H:*   `{vol_str}`\n"
            f"🔄 *Circulating:*  `{sup_str}`\n"
            f"🏁 *Max Supply:*   `{max_str}`\n\n"
            f"{DIVIDER}\n"
            f"🏆 *ATH:* `${info['ath']:,.4f}` `({info['ath_change']:+.1f}% from ATH)`\n\n"
            f"_{info['description'][:200]}..._\n\n"
            f"{DIVIDER}\n"
            f"_Source: CoinGecko_"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Analyze", callback_data=f"analyze_coin|{symbol}"),
             InlineKeyboardButton("⭐ Watchlist", callback_data=f"wl_add|{symbol}")],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
        ])
        await query.edit_message_text(msg, reply_markup=kb, parse_mode="Markdown")

    # ── LEADERBOARD ──
    elif data == "menu_leaderboard":
        all_data = load_data()
        sorted_users = sorted(
            all_data.items(),
            key=lambda x: x[1].get("total_analyses", 0),
            reverse=True
        )[:10]
        lines = [f"{LOGO}\n{DIVIDER}", "🏅 *Leaderboard — Top Analysts*\n"]
        medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
        for i, (lid, luser) in enumerate(sorted_users):
            name     = luser.get("username") or f"User{lid[-4:]}"
            analyses = luser.get("total_analyses", 0)
            tier_e   = "⭐" if is_premium(lid) else "🆓"
            lines.append(f"{medals[i]} {tier_e} *@{name}* — `{analyses}` analyses")
        user_rank = next((i+1 for i,(lid,_) in enumerate(sorted(all_data.items(), key=lambda x: x[1].get("total_analyses",0), reverse=True)) if lid==uid), "N/A")
        lines.append(f"\n{DIVIDER}\n📍 *Your Rank:* #{user_rank} with `{user.get('total_analyses',0)}` analyses")
        await query.edit_message_text(
            "\n".join(lines), reply_markup=back_kb(), parse_mode="Markdown"
        )

    # ── REFERRAL ──
    elif data == "menu_referral":
        ref_code  = user.get("referral_code", f"REF{uid[-6:]}")
        referrals = user.get("referrals", [])
        bot_info  = await context.bot.get_me()
        bot_username = bot_info.username
        ref_link  = f"https://t.me/{bot_username}?start={ref_code}"
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            f"👥 *Refer & Earn*\n\n"
            f"Share your link and earn rewards!\n\n"
            f"🔗 *Your Link:*\n`{ref_link}`\n\n"
            f"👥 *Total Referrals:* `{len(referrals)}`\n\n"
            f"{DIVIDER}\n"
            f"🎁 *Rewards:*\n"
            f"• 5 referrals = 1 week Premium FREE\n"
            f"• 20 referrals = 1 month Premium FREE\n"
            f"• 50 referrals = Lifetime Premium FREE\n\n"
            f"_Share with friends who love crypto!_ 🚀",
            reply_markup=back_kb(), parse_mode="Markdown"
        )

    # ── SETTINGS ──
    elif data == "menu_settings":
        signal_time    = user.get("signal_time", "09:00")
        signal_enabled = user.get("signal_enabled", True)
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            f"⚙️ *Settings*\n\n"
            f"📅 Daily Signal Time: `{signal_time} UTC`\n"
            f"🔔 Daily Signals: `{'ON ✅' if signal_enabled else 'OFF ❌'}`\n\n"
            f"{DIVIDER}\n"
            f"📌 *Commands:*\n"
            f"`/settime 08:00` — Change signal time\n"
            f"`/signals on` — Enable signals\n"
            f"`/signals off` — Disable signals",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Toggle Signals", callback_data="toggle_signals")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
            parse_mode="Markdown"
        )

    elif data == "toggle_signals":
        user["signal_enabled"] = not user.get("signal_enabled", True)
        update_user(uid, user)
        status = "ON ✅" if user["signal_enabled"] else "OFF ❌"
        await query.answer(f"Daily signals: {status}")
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n⚙️ *Settings*\n\n"
            f"🔔 Daily Signals: `{status}`",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔔 Toggle Signals", callback_data="toggle_signals")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="menu_main")],
            ]),
            parse_mode="Markdown"
        )

    # ── PREMIUM ──
    elif data == "menu_premium":
        if premium:
            ptype  = user.get("premium_type","")
            expiry = user.get("premium_expiry","")
            exp_str= "Never (Lifetime)" if ptype=="lifetime" else expiry[:10] if expiry else "N/A"
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n"
                f"⭐ *Premium Active!*\n\n"
                f"Plan: *{ptype.capitalize()}*\n"
                f"Expires: `{exp_str}`\n\n"
                f"✅ All features unlocked!\n"
                f"✅ Unlimited analyses\n"
                f"✅ All timeframes\n"
                f"✅ Any coin\n"
                f"✅ Priority support",
                reply_markup=back_kb(), parse_mode="Markdown"
            )
        else:
            await query.edit_message_text(
                f"{LOGO}\n{DIVIDER}\n\n"
                f"💎 *Upgrade to Premium*\n\n"
                f"🆓 *Free Plan:*\n"
                f"• BTC & ETH only\n"
                f"• 1D timeframe only\n"
                f"• 3 analyses/day\n\n"
                f"⭐ *Premium Plan:*\n"
                f"• Any coin on KuCoin\n"
                f"• All timeframes (1H/4H/1D)\n"
                f"• Unlimited analyses\n"
                f"• Price alerts\n"
                f"• Full watchlist\n"
                f"• Daily auto signals\n"
                f"• Priority support\n\n"
                f"{DIVIDER}\n"
                f"💰 *Monthly:* 500 ⭐ Stars (~$4.99)\n"
                f"💎 *Lifetime:* 2500 ⭐ Stars (~$29.99)",
                reply_markup=premium_kb(), parse_mode="Markdown"
            )

    elif data == "buy_monthly":
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="⭐ Atomic Crypto Premium — Monthly",
            description="Unlock all features: any coin, all timeframes, unlimited analyses, alerts & more!",
            payload="premium_monthly",
            currency="XTR",
            prices=[LabeledPrice("Monthly Premium", PREMIUM_MONTHLY_STARS)],
        )

    elif data == "buy_lifetime":
        await context.bot.send_invoice(
            chat_id=query.message.chat_id,
            title="💎 Atomic Crypto Premium — Lifetime",
            description="One-time payment. Unlock everything forever — all coins, timeframes, signals & more!",
            payload="premium_lifetime",
            currency="XTR",
            prices=[LabeledPrice("Lifetime Premium", PREMIUM_LIFETIME_STARS)],
        )

    # ── EXCHANGES ──
    elif data == "menu_exchanges":
        await query.edit_message_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            f"🏦 *Recommended Exchanges*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚡ *BingX* — Best for India & Pakistan\n"
            f"🎁 Get trading rewards on signup!\n"
            f"🔗 [Join BingX]({BINGX_LINK})\n"
            f"🔑 Code: `{BINGX_CODE}`\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🌍 *Binance* — World's #1 Exchange\n"
            f"🎁 Earn USDC rewards on signup!\n"
            f"🔗 [Join Binance]({BINANCE_LINK})\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"_Use our links to support Atomic Crypto_ ❤️",
            reply_markup=back_kb(), parse_mode="Markdown", disable_web_page_preview=False
        )

# ── PAYMENT HANDLERS ──────────────────────────────────────────────────────────
async def precheckout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.pre_checkout_query
    await query.answer(ok=True)

async def payment_success(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid     = str(update.effective_user.id)
    user    = get_user(uid)
    payload = update.message.successful_payment.invoice_payload
    from datetime import timedelta

    if payload == "premium_monthly":
        from datetime import timedelta
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        user["premium"]        = True
        user["premium_type"]   = "monthly"
        user["premium_expiry"] = expiry.isoformat()
        update_user(uid, user)
        await update.message.reply_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            "🎉 *Payment Successful!*\n\n"
            "⭐ *Premium Monthly activated!*\n"
            "Valid for 30 days.\n\n"
            "All features are now unlocked! 🚀",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Go to Menu", callback_data="menu_main")]]),
            parse_mode="Markdown"
        )
    elif payload == "premium_lifetime":
        user["premium"]        = True
        user["premium_type"]   = "lifetime"
        user["premium_expiry"] = None
        update_user(uid, user)
        await update.message.reply_text(
            f"{LOGO}\n{DIVIDER}\n\n"
            "🎉 *Payment Successful!*\n\n"
            "💎 *Lifetime Premium activated!*\n"
            "All features unlocked *forever!* 🚀\n\n"
            "Thank you for supporting Atomic Crypto! ❤️",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Go to Menu", callback_data="menu_main")]]),
            parse_mode="Markdown"
        )

# ── COMMANDS ──────────────────────────────────────────────────────────────────
async def alert_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    args = context.args
    if len(args) != 3 or args[1] not in ("above","below"):
        await update.message.reply_text(
            "⚠️ Usage: `/alert BTC above 70000`\nor `/alert ETH below 3000`",
            parse_mode="Markdown"
        )
        return
    symbol, direction = args[0].upper(), args[1]
    try:
        target = float(args[2])
    except:
        await update.message.reply_text("⚠️ Invalid price.", parse_mode="Markdown")
        return
    user = get_user(uid)
    user["alerts"].append({
        "symbol": clean_symbol(symbol),
        "direction": direction,
        "target": target,
        "chat_id": update.effective_chat.id
    })
    update_user(uid, user)
    e = "📈" if direction == "above" else "📉"
    await update.message.reply_text(
        f"✅ *Alert Set!*\n\n{e} *{clean_symbol(symbol)}* {direction} `${target:,.2f}`\n"
        "_I'll notify you when triggered!_",
        parse_mode="Markdown"
    )

async def add_portfolio_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    args = context.args
    if len(args) != 3:
        await update.message.reply_text(
            "⚠️ Usage: `/add BTC 0.5 42000`\n_(symbol, amount, buy price)_",
            parse_mode="Markdown"
        )
        return
    symbol = clean_symbol(args[0])
    try:
        amount    = float(args[1])
        buy_price = float(args[2])
    except:
        await update.message.reply_text("⚠️ Invalid amount or price.", parse_mode="Markdown")
        return
    user = get_user(uid)
    user["portfolio"][symbol] = {"amount": amount, "buy_price": buy_price}
    update_user(uid, user)
    await update.message.reply_text(
        f"✅ *Portfolio Updated!*\n\n"
        f"💼 *{symbol}:* `{amount}` @ `${buy_price:,.4f}`\n\n"
        "_View portfolio from main menu_ 📊",
        parse_mode="Markdown"
    )

async def settime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    args = context.args
    if not args:
        await update.message.reply_text(
            "⚠️ Usage: `/settime 08:00`\n_(UTC time for daily signals)_",
            parse_mode="Markdown"
        )
        return
    time_str = args[0]
    try:
        h, m = map(int, time_str.split(":"))
        assert 0 <= h <= 23 and 0 <= m <= 59
    except:
        await update.message.reply_text("⚠️ Invalid time. Use format: `08:30`", parse_mode="Markdown")
        return
    user = get_user(uid)
    user["signal_time"] = f"{h:02d}:{m:02d}"
    update_user(uid, user)
    await update.message.reply_text(
        f"✅ Daily signal time set to `{h:02d}:{m:02d} UTC`",
        parse_mode="Markdown"
    )

async def signals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = str(update.effective_user.id)
    args = context.args
    if not args or args[0] not in ("on","off"):
        await update.message.reply_text("Usage: `/signals on` or `/signals off`", parse_mode="Markdown")
        return
    user = get_user(uid)
    user["signal_enabled"] = args[0] == "on"
    update_user(uid, user)
    await update.message.reply_text(
        f"✅ Daily signals: `{'ON' if user['signal_enabled'] else 'OFF'}`",
        parse_mode="Markdown"
    )

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid    = str(update.effective_user.id)
    action = context.user_data.get("action")
    text   = update.message.text.upper().strip()

    if action == "analyze":
        symbol = text.replace("USDT","").replace("/","")
        context.user_data["action"] = None
        await update.message.reply_text(
            f"🪙 *{symbol}/USDT* — Select timeframe:",
            reply_markup=timeframe_kb(symbol, uid),
            parse_mode="Markdown"
        )
    elif action == "coininfo":
        symbol = text.replace("USDT","").replace("/","")
        context.user_data["action"] = None
        await update.message.reply_text(f"⏳ Fetching *{symbol}* info...", parse_mode="Markdown")
        info = fetch_coin_info(symbol)
        if not info:
            await update.message.reply_text(
                f"❌ Could not find *{symbol}*. Check the symbol.",
                parse_mode="Markdown"
            )
            return
        mc  = info["market_cap"]
        vol = info["volume_24h"]
        mc_str  = f"${mc/1e9:.2f}B" if mc > 1e9 else f"${mc/1e6:.2f}M"
        vol_str = f"${vol/1e9:.2f}B" if vol > 1e9 else f"${vol/1e6:.2f}M"
        msg = (
            f"{LOGO}\n{DIVIDER}\n\n"
            f"🔍 *{info['name']} ({info['symbol']})*\n"
            f"📊 Rank: *#{info['rank']}*\n\n"
            f"💰 Price: `${info['price']:,.6f}`\n"
            f"📈 24h: `{info['change_24h']:+.2f}%`\n"
            f"📅 7d:  `{info['change_7d']:+.2f}%`\n"
            f"💎 Market Cap: `{mc_str}`\n"
            f"📦 Volume 24H: `{vol_str}`\n"
            f"🏆 ATH: `${info['ath']:,.4f}`\n\n"
            f"_{info['description'][:200]}..._"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 Analyze", callback_data=f"analyze_coin|{symbol}"),
             InlineKeyboardButton("🏠 Menu", callback_data="menu_main")],
        ])
        await update.message.reply_text(msg, reply_markup=kb, parse_mode="Markdown")
    else:
        await update.message.reply_text(
            f"{LOGO}\n\nUse the menu below 👇",
            reply_markup=main_menu_kb(uid),
            parse_mode="Markdown"
        )

# ── ADMIN COMMANDS ────────────────────────────────────────────────────────────
async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = str(update.effective_user.id)
    if int(uid) != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return
    all_data  = load_data()
    total     = len(all_data)
    premiums  = sum(1 for u in all_data.values() if is_premium(str(list(all_data.keys())[list(all_data.values()).index(u)])))
    free      = total - premiums
    analyses  = sum(u.get("total_analyses", 0) for u in all_data.values())
    referrals = sum(len(u.get("referrals", [])) for u in all_data.values())

    await update.message.reply_text(
        f"{LOGO}\n{DIVIDER}\n\n"
        f"🛡️ *ADMIN PANEL*\n\n"
        f"👥 Total Users:    `{total}`\n"
        f"⭐ Premium Users:  `{premiums}`\n"
        f"🆓 Free Users:     `{free}`\n"
        f"📊 Total Analyses: `{analyses}`\n"
        f"👥 Total Referrals:`{referrals}`\n\n"
        f"{DIVIDER}\n"
        f"*Admin Commands:*\n"
        f"`/grant <user_id> monthly` — Grant premium\n"
        f"`/grant <user_id> lifetime` — Grant lifetime\n"
        f"`/revoke <user_id>` — Revoke premium\n"
        f"`/broadcast <message>` — Message all users\n"
        f"`/userinfo <user_id>` — View user info",
        parse_mode="Markdown"
    )

async def grant_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if int(update.effective_user.id) != ADMIN_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("Usage: `/grant <user_id> monthly|lifetime`", parse_mode="Markdown")
        return
    target_uid, plan = args[0], args[1]
    user = get_user(target_uid)
    from datetime import timedelta
    if plan == "monthly":
        expiry = datetime.now(timezone.utc) + timedelta(days=30)
        user["premium"] = True; user["premium_type"] = "monthly"
        user["premium_expiry"] = expiry.isoformat()
    elif plan == "lifetime":
        user["premium"] = True; user["premium_type"] = "lifetime"
        user["premium_expiry"] = None
    update_user(target_uid, user)
    await update.message.reply_text(f"✅ Granted *{plan}* premium to `{target_uid}`", parse_mode="Markdown")
    try:
        await context.bot.send_message(
            chat_id=int(target_uid),
            text=f"{LOGO}\n\n🎁 *You've been granted {plan.capitalize()} Premium!*\n\nAll features are now unlocked! 🚀",
            parse_mode="Markdown"
        )
    except:
        pass

async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if int(update.effective_user.id) != ADMIN_ID:
        return
    args = context.args
    if not args:
        await update.message.reply_text("Usage: `/revoke <user_id>`", parse_mode="Markdown")
        return
    target_uid = args[0]
    user = get_user(target_uid)
    user["premium"] = False; user["premium_type"] = None; user["premium_expiry"] = None
    update_user(target_uid, user)
    await update.message.reply_text(f"✅ Revoked premium from `{target_uid}`", parse_mode="Markdown")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if int(update.effective_user.id) != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: `/broadcast Your message here`", parse_mode="Markdown")
        return
    msg      = " ".join(context.args)
    all_data = load_data()
    sent = 0; failed = 0
    for target_uid in all_data:
        try:
            await context.bot.send_message(
                chat_id=int(target_uid),
                text=f"{LOGO}\n{DIVIDER}\n\n📢 *Announcement*\n\n{msg}",
                parse_mode="Markdown"
            )
            sent += 1
        except:
            failed += 1
    await update.message.reply_text(
        f"✅ Broadcast complete!\nSent: `{sent}` | Failed: `{failed}`",
        parse_mode="Markdown"
    )

async def userinfo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if int(update.effective_user.id) != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("Usage: `/userinfo <user_id>`", parse_mode="Markdown")
        return
    target_uid = context.args[0]
    user = get_user(target_uid)
    await update.message.reply_text(
        f"👤 *User Info: {target_uid}*\n\n"
        f"Username: @{user.get('username','N/A')}\n"
        f"Premium: `{user.get('premium', False)}`\n"
        f"Plan: `{user.get('premium_type','free')}`\n"
        f"Expiry: `{user.get('premium_expiry','N/A')}`\n"
        f"Analyses: `{user.get('total_analyses',0)}`\n"
        f"Referrals: `{len(user.get('referrals',[]))}`\n"
        f"Watchlist: `{user.get('watchlist',[])}`\n"
        f"Joined: `{user.get('join_date','N/A')}`",
        parse_mode="Markdown"
    )

# ── BACKGROUND JOBS ───────────────────────────────────────────────────────────
async def check_alerts_job(context):
    """Check price alerts every 60 seconds"""
    all_data = load_data()
    for uid, user in all_data.items():
        alerts    = user.get("alerts", [])
        remaining = []
        for a in alerts:
            price = fetch_price(a["symbol"])
            if price is None:
                remaining.append(a); continue
            hit = (a["direction"]=="above" and price >= a["target"]) or \
                  (a["direction"]=="below" and price <= a["target"])
            if hit:
                e = "📈" if a["direction"]=="above" else "📉"
                try:
                    await context.bot.send_message(
                        chat_id=a["chat_id"],
                        text=f"{LOGO}\n{DIVIDER}\n\n"
                             f"🚨 *ALERT TRIGGERED!*\n\n"
                             f"{e} *{a['symbol']}* hit `${price:,.4f}`\n"
                             f"Target: {a['direction']} `${a['target']:,.2f}`\n\n"
                             f"_Check the market now!_ 📊",
                        parse_mode="Markdown"
                    )
                except:
                    pass
            else:
                remaining.append(a)
        if len(remaining) != len(alerts):
            user["alerts"] = remaining
            update_user(uid, user)

async def build_signal_message(now: datetime) -> str:
    """Build the daily signal message for channel + users"""
    lines = [
        f"{LOGO}",
        f"{DIVIDER}",
        f"📅 *Daily Signals — {now.strftime('%d %b %Y')} UTC*",
        f"⏰ {now.strftime('%H:%M')} UTC\n",
    ]
    for coin in SIGNAL_COINS:
        df = fetch_ohlcv(coin, "1d", 200)
        if df is None or len(df) < 60:
            continue
        ind  = compute_all(df)
        pred = score(ind)
        sig_e = "🟢" if pred["signal"]=="BUY" else "🔴" if pred["signal"]=="SELL" else "🟡"
        dir_e = "📈" if pred["direction"]=="UP" else "📉"
        bar   = "█"*(pred["confidence"]//10) + "░"*(10-pred["confidence"]//10)
        grok  = await get_grok_analysis(coin, ind, pred)
        grok_sentiment = ""
        if grok:
            for line in grok.splitlines():
                if line.startswith("SENTIMENT:"):
                    grok_sentiment = line.replace("SENTIMENT:","").strip()
                    break
        sent_e = "🟢" if "Bullish" in grok_sentiment else "🔴" if "Bearish" in grok_sentiment else "🟡"
        lines.append(
            f"{sig_e} *{coin}/USDT*\n"
            f"   Price: {ind['price']:,.4f} USDT\n"
            f"   {dir_e} Direction: {pred['direction']}\n"
            f"   Confidence: {pred['confidence']}% {bar}\n"
            f"   Signal: *{pred['signal']}*  Risk: {pred['risk']}\n"
            f"   {sent_e} X Sentiment: {grok_sentiment}\n"
        )
    lines.append(f"{DIVIDER}")
    lines.append("Powered by 15+ indicators")
    lines.append("Full analysis: @AtomicCrypto_bot")
    lines.append(f"Trade on BingX: {BINGX_LINK}")
    lines.append(f"Join Channel: {CHANNEL_LINK}")
    return "\n".join(lines)

async def daily_signals_job(context):
    """Post daily signals to channel at 09:00 UTC & send to premium users at their set time"""
    now      = datetime.now(timezone.utc)
    now_time = f"{now.hour:02d}:{now.minute:02d}"

    # ── Post to public channel at 09:00 UTC every day ──
    if now_time == "09:00":
        try:
            msg = await build_signal_message(now)
            await context.bot.send_message(
                chat_id=CHANNEL_USERNAME,
                text=msg,
                parse_mode=None,
                disable_web_page_preview=True
            )
            logger.info("✅ Daily signals posted to channel")
        except Exception as e:
            logger.error(f"Channel post error: {e}")

    # ── Send to premium users at their preferred time ──
    all_data = load_data()
    for uid, user in all_data.items():
        if not user.get("signal_enabled", True):
            continue
        if not is_premium(uid):
            continue
        user_time = user.get("signal_time", "09:00")
        if user_time != now_time:
            continue
        try:
            msg = await build_signal_message(now)
            await context.bot.send_message(
                chat_id=int(uid),
                text=msg,
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Daily signal error for {uid}: {e}")

async def postsignals_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin: manually trigger a channel signal post"""
    if int(update.effective_user.id) != ADMIN_ID:
        return
    await update.message.reply_text("⏳ Posting signals to channel...", parse_mode="Markdown")
    try:
        now = datetime.now(timezone.utc)
        msg = await build_signal_message(now)
        await context.bot.send_message(
            chat_id=CHANNEL_USERNAME,
            text=msg,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await update.message.reply_text("✅ Signals posted to channel!", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}", parse_mode="Markdown")

# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Commands
    app.add_handler(CommandHandler("start",     start))
    app.add_handler(CommandHandler("alert",     alert_cmd))
    app.add_handler(CommandHandler("add",       add_portfolio_cmd))
    app.add_handler(CommandHandler("settime",   settime_cmd))
    app.add_handler(CommandHandler("signals",   signals_cmd))
    app.add_handler(CommandHandler("admin",     admin_cmd))
    app.add_handler(CommandHandler("grant",     grant_cmd))
    app.add_handler(CommandHandler("revoke",    revoke_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("userinfo",  userinfo_cmd))
    app.add_handler(CommandHandler("postsignals", postsignals_cmd))

    # Callbacks & messages
    app.add_handler(CallbackQueryHandler(menu_handler))
    app.add_handler(PreCheckoutQueryHandler(precheckout))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_success))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

    # Background jobs
    app.job_queue.run_repeating(check_alerts_job,  interval=60,   first=10)
    app.job_queue.run_repeating(daily_signals_job, interval=60,   first=30)

    print("⚡ Atomic Crypto Bot v2.0 — Professional Edition")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("✅ All features loaded")
    print("✅ Background jobs running")
    print("✅ Admin panel ready")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()