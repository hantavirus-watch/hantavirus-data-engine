import feedparser
import json
import os
from datetime import datetime
import urllib.parse
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time

# Inizializziamo il geolocalizzatore (usando un user_agent unico per evitare blocchi)
geolocator = Nominatim(user_agent="hantawatch_global_tracker")

def get_coordinates(location_name):
    try:
        # Nominatim richiede pause tra le richieste per i termini di servizio
        time.sleep(1) 
        location = geolocator.geocode(location_name)
        if location:
            return [location.latitude, location.longitude]
    except (GeocoderTimedOut, Exception):
        return None
    return None

def fetch_hantavirus_alerts():
    query = 'hantavirus OR "hantavirus outbreak" OR "orthohantavirus" when:7d'
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    feed = feedparser.parse(rss_url)
    outbreaks = []
    
    print(f"Analyzing {len(feed.entries)} entries for locations...")

    for entry in feed.entries:
        title = entry.title
        # Logica semplificata: cerchiamo nomi propri (maiuscole) nel titolo per il geocoding
        # In una fase avanzata useremo una libreria NER (Named Entity Recognition)
        
        # Per ora, proviamo a estrarre potenziali luoghi dopo parole come "in", "near", "at"
        potential_location = None
        for trigger in [" in ", " near ", " at ", " around "]:
            if trigger in title:
                potential_location = title.split(trigger)[-1].split(" - ")[0].split(",")[0].strip()
                break

        coords = None
        if potential_location:
            print(f"   Found location hint: '{potential_location}'. Geocoding...")
            coords = get_coordinates(potential_location)

        outbreak = {
            "id": entry.get('id', entry.link),
            "title": title,
            "link": entry.link,
            "location_name": potential_location,
            "coordinates": coords, # [lat, lon]
            "published": entry.published,
            "source": entry.source.get('title', 'Unknown') if hasattr(entry, 'source') else 'Google News',
            "fetch_timestamp": datetime.now().isoformat()
        }
        outbreaks.append(outbreak)
            
    return outbreaks

def save_data(data):
    if not os.path.exists('data'):
        os.makedirs('data')
    
    with open('data/outbreaks.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

if __name__ == "__main__":
    print("🚀 Starting HantaWatch Engine with Geocoding...")
    alerts = fetch_hantavirus_alerts()
    save_data(alerts)
    # Contiamo quanti hanno coordinate valide
    geocoded_count = sum(1 for a in alerts if a['coordinates'] is not None)
    print(f"✅ Done! Found {len(alerts)} alerts, {geocoded_count} successfully geocoded.")