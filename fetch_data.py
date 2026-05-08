import argparse
import feedparser
import json
import os
import time
import urllib.parse
from datetime import datetime

from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim

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


def run_fetch_cycle():
    """Esegue un ciclo completo di fetch e salvataggio."""
    print("🚀 HantaWatch Global Engine: Starting fetch and geocode...")
    alerts = fetch_hantavirus_alerts()
    path = save_data(alerts)

    total = len(alerts)
    geocoded = sum(1 for alert in alerts if alert['coordinates'] is not None)
    coverage = (geocoded / total) * 100 if total else 0

    print(f"\n✅ Success! Saved {total} alerts to {path}")
    print(f"🌍 Geocoding coverage: {geocoded}/{total} ({coverage:.1f}%)")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Fetch and save hantavirus outbreak data."
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="keep the process running and refresh data on a fixed interval",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=1800,
        help="refresh interval in seconds when --watch is enabled (default: 1800)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.watch and args.interval <= 0:
        raise ValueError("--interval must be greater than 0 when --watch is enabled")

    while True:
        try:
            run_fetch_cycle()
        except Exception as error:
            print(f"❌ Error during execution: {error}")

        if not args.watch:
            break

        next_run = datetime.now().isoformat(timespec="seconds")
        print(f"⏳ Waiting {args.interval} seconds before next refresh. Current time: {next_run}")
        time.sleep(args.interval)

if __name__ == "__main__":
    main()