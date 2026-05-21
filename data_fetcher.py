cat > ~/supagoldbot/data_fetcher.py << 'ENDOFFILE'
import requests
import pandas as pd
from loguru import logger
import sys
from bot_config.settings import TWELVE_DATA_API_KEY, SYMBOL, TIMEFRAMES

logger.remove()
logger.add(sys.stdout, level="INFO")

class DataFetcher:
    BASE_URL = "https://api.twelvedata.com/time_series"

    def __init__(self):
        self.api_key = TWELVE_DATA_API_KEY
        self.symbol = SYMBOL

    def fetch_candles(self, interval: str, outputsize: int = 200) -> pd.DataFrame:
        params = {
            "symbol": self.symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": self.api_key
        }

        try:
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            if "values" not in data:
                logger.error(f"Unexpected API response: {data}")
                return pd.DataFrame()

            df = pd.DataFrame(data["values"])
            df["datetime"] = pd.to_datetime(df["datetime"])

            for col in ["open", "high", "low", "close"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col])

            if "volume" not in df.columns:
                df["volume"] = 0

            df = df.sort_values("datetime").reset_index(drop=True)
            logger.info(f"Fetched {len(df)} candles for {interval}")
            return df

        except requests.RequestException as e:
            logger.error(f"API request failed: {e}")
            return pd.DataFrame()
        except Exception as e:
            logger.error(f"Data fetch error: {e}")
            return pd.DataFrame()

    def fetch_all_timeframes(self) -> dict:
        data = {}
        for tf in TIMEFRAMES:
            df = self.fetch_candles(tf)
            if not df.empty:
                data[tf] = df
            else:
                logger.warning(f"Empty data for timeframe: {tf}")
        return data
ENDOFFILE