import argparse
import feedparser
import json
import os
import re
import time
import urllib.parse
from datetime import datetime

from bs4 import BeautifulSoup
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim, Photon

# Inizializzazione del geolocalizzatore con User Agent specifico
geolocator = Nominatim(user_agent="hantawatch_global_tracker")
fallback_geolocator = Photon(user_agent="hantawatch_global_tracker")
GEOCODE_CACHE = {}

# Lista di termini che spesso ingannano il geocoder
STOP_LOCATIONS = [
    "a cruise ship", "the center", "sea", "suspected", "deaths", 
    "contact", "victims", "people", "ocean", "atlantic", "ny?", "cases"
]

LOCATION_TRIGGERS = [
    " in ",
    " near ",
    " at ",
    " across ",
    " from ",
    " to ",
    " aboard ",
    " outside ",
    " back in ",
    " back to ",
    " heads to ",
    " monitoring ",
]

INVALID_LOCATION_FRAGMENTS = {
    "outbreak",
    "cruise",
    "passenger",
    "passengers",
    "ship",
    "virus",
    "health",
    "authorities",
    "officials",
    "cluster",
    "response",
    "guidance",
    "symptoms",
    "treatment",
    "spread",
    "travel",
    "cases",
    "monitoring",
    "people",
    "public",
    "pandemic",
    "doctor",
    "residents",
}


def clean_location_candidate(value):
    """Normalizza una stringa candidata a localita'."""
    candidate = re.sub(r"\s+", " ", value or "").strip(" -,:;.?()[]{}\"'")
    candidate = re.split(r"\s+-\s+", candidate, maxsplit=1)[0].strip()
    if not candidate:
        return None

    lower_candidate = candidate.lower()
    if lower_candidate in STOP_LOCATIONS:
        return None

    if any(fragment in lower_candidate for fragment in INVALID_LOCATION_FRAGMENTS):
        return None

    if not re.search(r"[A-Z]", candidate):
        return None

    return candidate


def split_location_group(group):
    """Divide gruppi tipo 'Georgia, California and Arizona' in localita' singole."""
    normalized = re.sub(r"\s+(and|or)\s+", ",", group)
    parts = [clean_location_candidate(part) for part in normalized.split(",")]
    return [part for part in parts if part]


def extract_location_candidates(text):
    """Estrae candidati localita' da una stringa libera."""
    candidates = []
    sanitized = re.sub(r"\s+", " ", text or "").strip()
    if not sanitized:
        return candidates

    working_text = sanitized.split(" - ")[0]

    for trigger in LOCATION_TRIGGERS:
        if trigger not in working_text:
            continue

        tail = working_text.split(trigger, 1)[1]
        tail = re.split(r"[?.!:]", tail, maxsplit=1)[0]
        tail = re.split(r"\b(?:after|before|as|while|because|that|which|who)\b", tail, maxsplit=1)[0]
        candidates.extend(split_location_group(tail))

    list_pattern = re.compile(
        r"\b(?:in|from|to|monitoring|across)\s+([A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)*(?:\s*,\s*[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)*)+(?:\s*(?:and|or)\s*[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+)*)?)"
    )
    for match in list_pattern.findall(working_text):
        candidates.extend(split_location_group(match))

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        if candidate.lower() in seen:
            continue
        seen.add(candidate.lower())
        unique_candidates.append(candidate)

    return unique_candidates


def get_entry_location_candidates(entry):
    """Combina titolo e descrizione HTML del feed per trovare piu' localita'."""
    text_blocks = [entry.get("title", "")]
    description = entry.get("description", "")
    if description:
        soup = BeautifulSoup(description, "html.parser")
        text_blocks.extend(anchor.get_text(" ", strip=True) for anchor in soup.find_all("a"))

    candidates = []
    seen = set()
    for block in text_blocks:
        for candidate in extract_location_candidates(block):
            normalized = candidate.lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            candidates.append(candidate)
    return candidates

def get_coordinates(location_name):
    """Converte il nome di un luogo in coordinate [lat, lon]."""
    normalized_name = (location_name or "").strip()
    if not normalized_name:
        return None

    cache_key = normalized_name.lower()
    if cache_key in GEOCODE_CACHE:
        return GEOCODE_CACHE[cache_key]

    try:
        # Pausa per rispettare i ToS di Nominatim
        time.sleep(1.1)
        location = geolocator.geocode(normalized_name)
        if location:
            coordinates = [location.latitude, location.longitude]
            GEOCODE_CACHE[cache_key] = coordinates
            return coordinates
        location = fallback_geolocator.geocode(normalized_name)
        if location:
            coordinates = [location.latitude, location.longitude]
            GEOCODE_CACHE[cache_key] = coordinates
            return coordinates
    except (GeocoderTimedOut, Exception):
        GEOCODE_CACHE[cache_key] = None
        return None
    GEOCODE_CACHE[cache_key] = None
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
        location_candidates = get_entry_location_candidates(entry)
        geocoded_locations = []

        for candidate in location_candidates[:5]:
            coords = get_coordinates(candidate)
            if not coords:
                continue

            geocoded_locations.append({
                "name": candidate,
                "coordinates": coords,
            })

            print(f"   📍 Geocoded: '{candidate}' -> {coords}")

            if len(geocoded_locations) >= 3:
                break

        primary_location = geocoded_locations[0] if geocoded_locations else None

        outbreak = {
            "id": entry.get('id', entry.link),
            "title": title,
            "link": entry.link,
            "location_name": primary_location["name"] if primary_location else None,
            "coordinates": primary_location["coordinates"] if primary_location else None,
            "locations": geocoded_locations,
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