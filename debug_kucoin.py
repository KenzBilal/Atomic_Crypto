import requests

symbol = "BTC-USDT"

# Test price
r = requests.get("https://api.kucoin.com/api/v1/market/orderbook/level1", params={"symbol": symbol}, timeout=10)
print(f"Price status: {r.status_code}")
print(f"Price: {r.json()}")

# Test klines
r2 = requests.get("https://api.kucoin.com/api/v1/market/candles", params={"symbol": symbol, "type": "1hour"}, timeout=10)
print(f"Klines status: {r2.status_code}")
print(f"Klines sample: {str(r2.json())[:200]}")