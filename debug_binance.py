import requests

def test_binance(symbol):
    symbol = symbol.upper().strip().replace("USDT","").replace("BUSD","").replace("/","").replace("-","")
    pair = symbol + "USDT"
    print(f"Testing pair: {pair}")

    # Test price
    r = requests.get("https://api.binance.com/api/v3/ticker/price", params={"symbol": pair}, timeout=10)
    print(f"Price status: {r.status_code}")
    print(f"Price response: {r.text[:200]}")

    # Test klines
    r2 = requests.get("https://api.binance.com/api/v3/klines", params={"symbol": pair, "interval": "1h", "limit": 5}, timeout=10)
    print(f"Klines status: {r2.status_code}")
    print(f"Klines response: {str(r2.json())[:200]}")

test_binance("BTC")