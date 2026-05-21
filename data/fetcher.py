import requests
import pandas as pd
from loguru import logger
import sys
import time
from bot_config.settings import TWELVE_DATA_API_KEY, SYMBOL as DEFAULT_SYMBOL, TIMEFRAMES

logger.remove()
logger.add(sys.stdout, level="INFO")

class DataFetcher:
    BASE_URL = "https://api.twelvedata.com/time_series"

    def __init__(self, symbol=None):
        self.api_key = TWELVE_DATA_API_KEY
        self.symbol = symbol if symbol else DEFAULT_SYMBOL

    def fetch_candles(self, interval: str, outputsize: int = 200, retries: int = 3) -> pd.DataFrame:
        params = {
            "symbol": self.symbol,
            "interval": interval,
            "outputsize": outputsize,
            "apikey": self.api_key
        }

        for attempt in range(retries):
            try:
                response = requests.get(self.BASE_URL, params=params, timeout=30)
                
                if response.status_code == 503:
                    logger.warning(f"503 for {self.symbol} {interval}, retry {attempt+1}/{retries}")
                    time.sleep(5)
                    continue
                    
                response.raise_for_status()
                data = response.json()

                if "values" not in data:
                    logger.error(f"Bad response for {self.symbol}: {data}")
                    return pd.DataFrame()

                df = pd.DataFrame(data["values"])
                df["datetime"] = pd.to_datetime(df["datetime"])

                for col in ["open", "high", "low", "close"]:
                    if col in df.columns:
                        df[col] = pd.to_numeric(df[col])

                if "volume" not in df.columns:
                    df["volume"] = 0

                df = df.sort_values("datetime").reset_index(drop=True)
                logger.info(f"Fetched {len(df)} candles for {self.symbol} {interval}")
                return df

            except requests.RequestException as e:
                logger.error(f"Request failed for {self.symbol} {interval}: {e}")
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    return pd.DataFrame()
            except Exception as e:
                logger.error(f"Error for {self.symbol} {interval}: {e}")
                return pd.DataFrame()

        return pd.DataFrame()

    def fetch_all_timeframes(self) -> dict:
        data = {}
        for tf in TIMEFRAMES:
            df = self.fetch_candles(tf)
            if not df.empty:
                data[tf] = df
            else:
                logger.warning(f"Empty data for {self.symbol} {tf}")
        return data
