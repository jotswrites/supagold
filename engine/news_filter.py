import requests
from datetime import datetime, timedelta, timezone
from loguru import logger

NEWS_API_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.json"

def is_high_impact_news_within(minutes_before=15, minutes_after=30):
    try:
        resp = requests.get(NEWS_API_URL, timeout=10)
        events = resp.json()
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=minutes_before)
        window_end = now + timedelta(minutes=minutes_after)

        for event in events:
            impact = event.get("impact", "")
            currency = event.get("currency", "")
            if impact.lower() != "high" or "USD" not in currency:
                continue

            event_time_str = event.get("date", "") + " " + event.get("time", "00:00")
            try:
                event_time = datetime.strptime(event_time_str.strip(), "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
                if window_start <= event_time <= window_end:
                    return True, event.get("title", "Unknown event")
            except:
                continue

        return False, None
    except Exception as e:
        logger.error(f"News filter error: {e}")
        return False, None
