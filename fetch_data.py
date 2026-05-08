import feedparser
import json
from datetime import datetime

def fetch_hantavirus_alerts():
    # URL di esempio (ProMED o Google News RSS per parole chiave specifiche)
    rss_url = "https://trends.google.com/trends/trendingsearches/daily/rss?geo=US" # Esempio generico
    feed = feedparser.parse(rss_url)
    
    outbreaks = []
    
    for entry in feed.entries:
        if "hantavirus" in entry.title.lower() or "outbreak" in entry.summary.lower():
            outbreak = {
                "title": entry.title,
                "link": entry.link,
                "published": entry.published,
                "summary": entry.summary,
                "timestamp": datetime.now().isoformat()
            }
            outbreaks.append(outbreak)
            
    return outbreaks

def save_data(data):
    with open('data/outbreaks.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    print("Fetching global alerts...")
    alerts = fetch_hantavirus_alerts()
    save_data(alerts)
    print(f"Saved {len(alerts)} potential alerts to data/outbreaks.json")