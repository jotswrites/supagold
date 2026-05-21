import requests
import json

url = "https://api.twelvedata.com/time_series"
params = {
    "symbol": "XAU/USD",
    "interval": "15min",
    "apikey": "19fa80f862554d8293d5cdff56cfe386"
}

r = requests.get(url, params=params)
print("Status:", r.status_code)
data = r.json()
print("Top-level keys:", list(data.keys()))

if "values" in data:
    print("First candle keys:", list(data["values"][0].keys()))
    print("First candle:", json.dumps(data["values"][0], indent=2))
else:
    print(json.dumps(data, indent=2)[:1000])