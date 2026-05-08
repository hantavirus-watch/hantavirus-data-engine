import feedparser
import json
import os
from datetime import datetime
import urllib.parse
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time

# Inizializzazione del geolocalizzatore con User Agent specifico
geolocator = Nominatim(user_agent="hantawatch_global_tracker")

# Lista di termini che spesso ingannano il geocoder
STOP_LOCATIONS = [
    "a cruise ship", "the center", "sea", "suspected", "deaths", 
    "contact", "victims", "people", "ocean", "atlantic", "ny?", "cases"
]

def get_coordinates(location_name):
    """Converte il nome di un luogo in coordinate [lat, lon]."""
    if not location_name or location_name.lower() in STOP_LOCATIONS:
        return None
    try:
        # Pausa per rispettare i ToS di Nominatim
        time.sleep(1.1) 
        location = geolocator.geocode(location_name)
        if location:
            return [location.latitude, location.longitude]
    except (GeocoderTimedOut, Exception):
        return None
    return None

def fetch_hantavirus_alerts():
    """Recupera e processa i dati sui focolai."""
    # Query mirata per massimizzare i risultati sui focolai recenti
    query = 'hantavirus OR "hantavirus outbreak" OR "orthohantavirus" OR "hps virus" when:7d'
    encoded_query = urllib.parse.quote(query)
    rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
    
    print(f"📡 Connecting to: {rss_url}")
    feed = feedparser.parse(rss_url)
    outbreaks = []
    
    print(f"🔍 Analyzing {len(feed.entries)} entries for outbreaks and locations...")

    for entry in feed.entries:
        title = entry.title
        potential_location = None
        
        # Estrazione semplificata della località dal titolo
        for trigger in [" in ", " near ", " at ", " across "]:
            if trigger in title:
                # Estrae la parte dopo il trigger e pulisce la stringa
                potential_location = title.split(trigger)[-1].split(" - ")[0].split(",")[0].split("?")[0].strip()
                break

        coords = None
        if potential_location:
            coords = get_coordinates(potential_location)
            if coords:
                print(f"   📍 Geocoded: '{potential_location}' -> {coords}")

        outbreak = {
            "id": entry.get('id', entry.link),
            "title": title,
            "link": entry.link,
            "location_name": potential_location,
            "coordinates": coords,
            "published": entry.published,
            "source": entry.source.get('title', 'Unknown') if hasattr(entry, 'source') else 'Google News',
            "fetch_timestamp": datetime.now().isoformat()
        }
        outbreaks.append(outbreak)
            
    return outbreaks

def save_data(data):
    """Salva i dati in formato JSON creando la cartella se necessario."""
    if not os.path.exists('data'):
        os.makedirs('data')
        print("📁 Created 'data' directory.")
    
    file_path = 'data/outbreaks.json'
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    return file_path

if __name__ == "__main__":
    print("🚀 HantaWatch Global Engine: Starting fetch and geocode...")
    try:
        alerts = fetch_hantavirus_alerts()
        path = save_data(alerts)
        
        # Statistiche finali
        total = len(alerts)
        geocoded = sum(1 for a in alerts if a['coordinates'] is not None)
        
        print(f"\n✅ Success! Saved {total} alerts to {path}")
        print(f"🌍 Geocoding coverage: {geocoded}/{total} ({(geocoded/total)*100:.1f}%)")
        
    except Exception as e:
        print(f"❌ Error during execution: {e}")