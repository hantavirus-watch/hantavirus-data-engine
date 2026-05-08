import feedparser
import json
import os
from datetime import datetime
import urllib.parse

def fetch_hantavirus_alerts():
    # Definiamo le parole chiave per la ricerca
    # "when:7d" limita ai risultati dell'ultima settimana per massima freschezza
    query = 'hantavirus OR "hantavirus outbreak" OR "orthohantavirus" OR "hps virus" when:7d'
    encoded_query = urllib.parse.quote(query)
    
    # URL di Google News RSS (Global/English)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    print(f"Connecting to: {rss_url}")
    feed = feedparser.parse(rss_url)
    
    outbreaks = []
    
    # Parole chiave per il filtraggio di sicurezza nel contenuto
    critical_keywords = ["outbreak", "focolaio", "cases", "confirmed", "infection", "hospital", "alert"]
    
    for entry in feed.entries:
        title_lower = entry.title.lower()
        summary_lower = entry.summary.lower()
        
        # Se troviamo "hantavirus" E almeno una parola critica, lo salviamo
        if "hantavirus" in title_lower or "hantavirus" in summary_lower:
            # Opzionale: ulteriore filtro per focalizzarsi sui focolai
            is_outbreak = any(k in title_lower or k in summary_lower for k in critical_keywords)
            
            outbreak = {
                "id": entry.get('id', entry.link),
                "title": entry.title,
                "link": entry.link,
                "published": entry.published,
                "is_confirmed_outbreak": is_outbreak,
                "source": entry.source.get('title', 'Unknown Source') if hasattr(entry, 'source') else 'Google News',
                "fetch_timestamp": datetime.now().isoformat()
            }
            outbreaks.append(outbreak)
            
    return outbreaks

def save_data(data):
    # Crea la cartella 'data' se non esiste (soluzione pro)
    if not os.path.exists('data'):
        os.makedirs('data')
        print("Created 'data' directory.")
        
    file_path = 'data/outbreaks.json'
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return file_path

if __name__ == "__main__":
    print("🚀 HantaWatch Global Engine: Starting fetch...")
    try:
        alerts = fetch_hantavirus_alerts()
        path = save_data(alerts)
        print(f"✅ Success! Saved {len(alerts)} potential alerts to {path}")
        
        # Debug: stampa i titoli trovati
        for i, a in enumerate(alerts[:5], 1):
            print(f"   {i}. {a['title']}")
            
    except Exception as e:
        print(f"❌ Error during execution: {e}")