import argparse
import json
import os
import re
import time
import urllib.parse
from datetime import datetime
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim, Photon

GOOGLE_NEWS_QUERY = 'hantavirus OR "hantavirus outbreak" OR "orthohantavirus" OR "hps virus" when:7d'
GOOGLE_NEWS_URL = (
    "https://news.google.com/rss/search?"
    f"q={urllib.parse.quote(GOOGLE_NEWS_QUERY)}&hl=en-US&gl=US&ceid=US:en"
)

SOURCE_CONFIGS = [
    {
        "name": "Google News",
        "kind": "google-news",
        "url": GOOGLE_NEWS_URL,
    },
    {
        "name": "PAHO RSS",
        "kind": "rss",
        "url": "https://www.paho.org/en/rss.xml",
    },
    {
        "name": "ECDC News",
        "kind": "rss",
        "url": "https://www.ecdc.europa.eu/en/taxonomy/term/1307/feed",
    },
    {
        "name": "ECDC Threat Report",
        "kind": "rss",
        "url": "https://www.ecdc.europa.eu/en/taxonomy/term/1505/feed",
    },
]

KEYWORDS = ("hantavirus", "orthohantavirus", "hps")
REQUEST_HEADERS = {"User-Agent": "hantawatch_global_tracker/1.0"}
REQUEST_TIMEOUT = 20
MAX_PAGE_TEXT_BLOCKS = 12
MAX_LOCATION_CANDIDATES = 8
MAX_GEOCODED_LOCATIONS = 3

STOP_LOCATIONS = [
    "a cruise ship",
    "the center",
    "sea",
    "suspected",
    "deaths",
    "contact",
    "victims",
    "people",
    "ocean",
    "atlantic",
    "ny?",
    "cases",
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
    " heads for ",
    " heads to ",
    " monitoring ",
    " linked to ",
    " associated with ",
    " registered in ",
    " land in ",
    " lands in ",
    " arrive in ",
    " arrives in ",
    " landed in ",
    " evacuated to ",
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
    "resident returns",
    "residents who",
    "live updates",
    "infection",
    "science",
    "rare type",
    "experts",
    "official",
    "briefing",
    "statement",
    "cluster linked",
    "global effort",
    "international effort",
    "hantavirus",
    "british",
}

INVALID_LOCATION_PREFIXES = {"first", "second", "third", "fourth"}
INVALID_LOCATION_FIRST_WORDS = {
    "a",
    "an",
    "another",
    "are",
    "as",
    "can",
    "could",
    "deadly",
    "dozens",
    "figure",
    "get",
    "head",
    "here",
    "here's",
    "how",
    "i've",
    "inside",
    "is",
    "it",
    "it's",
    "key",
    "live",
    "may",
    "medical",
    "more",
    "next",
    "opinion",
    "out",
    "rare",
    "should",
    "suspected",
    "that",
    "the",
    "these",
    "this",
    "those",
    "watch",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "would",
    "you",
}
VALID_SHORT_LOCATION_CODES = {"AZ", "CA", "DC", "GA", "NJ", "NY", "TX", "UK", "US", "VA"}
LOCATION_CONNECTOR_WORDS = {"and", "della", "de", "del", "di", "du", "la", "las", "los", "of", "the", "y"}
BROAD_LOCATION_NAMES = {
    "africa",
    "americas",
    "asia",
    "europe",
    "north america",
    "region of the americas",
    "south america",
    "southern cone",
    "the eu",
    "u.s",
    "u.s.",
    "united states",
}

LEADING_LOCATION_PATTERNS = [
    re.compile(
        r"^([A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+){0,2})\s+(?:health agencies|health officials|authorities|officials|department)\b"
    ),
    re.compile(
        r"^([A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+){0,2})\s+(?:among|investigates?|readies?|confirms?|supports?|monitors?|tracking|tracks?|reports?|warns?|detects?|records?)\b"
    ),
    re.compile(
        r"\b(?:are|were|was|is)\s+([A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+){0,2})\s+(?:resident|residents|traveler|travellers)\b"
    ),
]

LOCATION_ALIASES = {
    "central california": "Central California, California, USA",
    "canary islands": "Canary Islands, Spain",
    "spain's canary islands": "Canary Islands, Spain",
    "spain’s canary islands": "Canary Islands, Spain",
    "johannesburg": "Johannesburg, South Africa",
    "georgia": "Georgia, USA",
    "ny": "New York, USA",
    "new york": "New York, USA",
    "washington, d.c": "Washington, DC, USA",
    "washington, d.c.": "Washington, DC, USA",
    "washington dc": "Washington, DC, USA",
}

MANUAL_COORDINATES = {
    "central california": [36.587, -120.072],
    "canary islands": [28.2935785, -16.6214471],
    "spain's canary islands": [28.2935785, -16.6214471],
    "spain’s canary islands": [28.2935785, -16.6214471],
}

DISPLAY_LOCATION_ALIASES = {
    "central california": "Central California",
    "canary islands": "Canary Islands",
    "spain's canary islands": "Canary Islands",
    "spain’s canary islands": "Canary Islands",
    "georgia": "Georgia",
    "johannesburg": "Johannesburg",
    "ny": "New York",
    "new york": "New York",
    "washington, d.c": "Washington, D.C.",
    "washington, d.c.": "Washington, D.C.",
    "washington dc": "Washington, D.C.",
}

PAGE_TEXT_ROOT_SELECTORS = {
    "paho.org": ["section.col-sm-8"],
    "ecdc.europa.eu": ["article.ct-news", "#block-zika-content article.ct-news"],
}

PAGE_TEXT_STOP_HEADINGS = {
    "paho.org": {"more information", "other news", "latest news", "additional links"},
    "ecdc.europa.eu": {"about hantavirus", "read the threat assessment brief", "view all updates on the outbreak", "additional links"},
}

LOCATION_NAME_PATTERN = r"(?:the\s+)?[A-Z][A-Za-z.'’-]+(?:\s+(?:[A-Z][A-Za-z.'’-]+|of|de|del|la|las|los|the|y)){0,3}"
LOCATION_GROUP_PATTERN = rf"({LOCATION_NAME_PATTERN}(?:\s*,\s*{LOCATION_NAME_PATTERN})*(?:\s*(?:and|or)\s*{LOCATION_NAME_PATTERN})?)"
LEADING_LOCATION_GROUP_PATTERN = re.compile(rf"^{LOCATION_GROUP_PATTERN}")
DATELINE_LOCATION_PATTERN = re.compile(
    r"^([A-Z][A-Za-z.'’-]+(?:,\s+(?:D\.C\.|[A-Z][A-Za-z.'’-]+))?)\s*,\s+[A-Z][a-z]+\s+\d{1,2},\s+\d{4}\b"
)

geolocator = Nominatim(user_agent="hantawatch_global_tracker")
fallback_geolocator = Photon(user_agent="hantawatch_global_tracker")
GEOCODE_CACHE = {}
PAGE_TEXT_CACHE = {}


def normalize_text(value):
    return re.sub(r"\s+", " ", (value or "").replace("’", "'")).strip()


def contains_keyword(text):
    lower_text = normalize_text(text).lower()
    return any(keyword in lower_text for keyword in KEYWORDS)


def normalize_location_label(location_name):
    normalized = normalize_text(location_name)
    return DISPLAY_LOCATION_ALIASES.get(normalized.lower(), normalized)


def clean_location_candidate(value):
    candidate = normalize_text(value).strip(" -,:;.?()[]{}\"'")
    candidate = re.split(r"\s+-\s+", candidate, maxsplit=1)[0].strip()
    candidate = re.split(r"\.(?=\s+[A-Z])|[;:!?]", candidate, maxsplit=1)[0].strip()
    candidate = re.sub(r"^(?:heads?|heading)\s+(?:to|for)\s+", "", candidate, flags=re.IGNORECASE)
    candidate = re.sub(r"\b(?:after|before|as|while|because|that|which|who|with|where)\b.*$", "", candidate, flags=re.IGNORECASE).strip()
    candidate = re.sub(r"^[Tt]he\s+", "", candidate).strip()
    if not candidate:
        return None

    lower_candidate = candidate.lower()
    if any(stop in lower_candidate for stop in STOP_LOCATIONS):
        return None

    if any(fragment in lower_candidate for fragment in INVALID_LOCATION_FRAGMENTS):
        return None

    first_token = lower_candidate.split()[0]
    if first_token in INVALID_LOCATION_PREFIXES:
        return None

    if first_token in INVALID_LOCATION_FIRST_WORDS:
        return None

    if lower_candidate.startswith("who ") or lower_candidate.endswith(" says"):
        return None

    if lower_candidate in BROAD_LOCATION_NAMES:
        return None

    if any(fragment in lower_candidate for fragment in {"alliance", "airlines", "vaccine"}):
        return None

    if len(candidate) < 3 and candidate.upper() not in VALID_SHORT_LOCATION_CODES:
        return None

    normalized_code = re.sub(r"[^A-Za-z]", "", candidate).upper()
    if candidate.upper() == candidate and normalized_code not in VALID_SHORT_LOCATION_CODES:
        return None

    tokens = [token for token in re.split(r"\s+", candidate) if token]
    if len(tokens) > 4:
        return None

    if any(len(token) == 1 for token in tokens) and candidate.upper() not in VALID_SHORT_LOCATION_CODES:
        return None

    if not re.match(r"^[A-Z]", candidate):
        return None

    for token in tokens:
        cleaned_token = token.strip(".,;:()[]{}\"'")
        alpha_token = re.sub(r"[^A-Za-z]", "", cleaned_token)
        lower_token = cleaned_token.lower()
        if cleaned_token.upper() == cleaned_token and len(alpha_token) > 1 and alpha_token not in VALID_SHORT_LOCATION_CODES:
            return None
        if not re.match(r"^[A-Z]", cleaned_token) and lower_token not in LOCATION_CONNECTOR_WORDS:
            return None

    if not re.search(r"[A-Z]", candidate):
        return None

    return candidate


def split_location_group(group):
    normalized = re.sub(r"\s+(and|or)\s+", ",", group)
    parts = [clean_location_candidate(part) for part in normalized.split(",")]
    return [part for part in parts if part]


def extract_leading_location_group(text):
    match = LEADING_LOCATION_GROUP_PATTERN.match(normalize_text(text))
    if not match:
        return None
    return match.group(1)


def extract_location_candidates(text):
    candidates = []
    working_text = normalize_text(text)
    if not working_text:
        return candidates

    headline = working_text.split(" - ")[0]

    dateline_match = DATELINE_LOCATION_PATTERN.search(working_text)
    if dateline_match:
        cleaned = clean_location_candidate(dateline_match.group(1))
        if cleaned:
            candidates.append(cleaned)

    for trigger in LOCATION_TRIGGERS:
        if trigger not in headline:
            continue

        tail = headline.split(trigger, 1)[1]
        tail = re.split(r"[?.!:;]", tail, maxsplit=1)[0]
        tail = re.split(r"\b(?:after|before|as|while|because|that|which|who|with|where)\b", tail, maxsplit=1)[0]
        location_group = extract_leading_location_group(tail)
        candidates.extend(split_location_group(location_group or tail))

    list_pattern = re.compile(
        rf"\b(?:in|from|to|monitoring|across|between)\s+{LOCATION_GROUP_PATTERN}"
    )
    for match in list_pattern.findall(headline):
        candidates.extend(split_location_group(match))

    route_pattern = re.compile(
        r"\bfrom\s+([A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+)*)\s+to\s+([A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+)*)"
    )
    route_match = route_pattern.search(headline)
    if route_match:
        for part in route_match.groups():
            cleaned = clean_location_candidate(part)
            if cleaned:
                candidates.append(cleaned)

    resident_pattern = re.compile(
        r"\b([A-Z][A-Za-z.'’-]+(?:\s+[A-Z][A-Za-z.'’-]+)*)\s+(?:resident|residents|traveler|travellers|health agencies)\b"
    )
    for match in resident_pattern.findall(headline):
        cleaned = clean_location_candidate(match)
        if cleaned:
            candidates.append(cleaned)

    for pattern in LEADING_LOCATION_PATTERNS:
        for match in pattern.findall(headline):
            cleaned = clean_location_candidate(match)
            if cleaned:
                candidates.append(cleaned)

    seen = set()
    unique_candidates = []
    for candidate in candidates:
        lowered = candidate.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_candidates.append(candidate)

    return unique_candidates


def build_text_blocks(entry):
    text_blocks = [entry.get("title", "")]
    description = entry.get("description") or entry.get("summary") or ""
    if description:
        soup = BeautifulSoup(description, "html.parser")
        rendered = soup.get_text(" ", strip=True)
        if rendered:
            text_blocks.append(rendered)
        text_blocks.extend(anchor.get_text(" ", strip=True) for anchor in soup.find_all("a"))

    return [normalize_text(block) for block in text_blocks if normalize_text(block)]


def dedupe_text_blocks(text_blocks):
    deduped_blocks = []
    seen = set()
    for block in text_blocks:
        lowered = block.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped_blocks.append(block)
    return deduped_blocks


def url_domain(url):
    return urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")


def fetch_source_page_text_blocks(soup, url):
    domain = url_domain(url)
    selectors = PAGE_TEXT_ROOT_SELECTORS.get(domain, [])
    stop_headings = PAGE_TEXT_STOP_HEADINGS.get(domain, set())

    for selector in selectors:
        root = soup.select_one(selector)
        if not root:
            continue

        text_blocks = []
        for node in root.find_all(["h1", "h2", "h3", "p"]):
            text = normalize_text(node.get_text(" ", strip=True))
            if not text:
                continue

            if node.name in {"h2", "h3"} and text.lower() in stop_headings:
                break

            if node.name == "p" and len(text) < 40:
                continue

            text_blocks.append(text)
            if len(text_blocks) >= MAX_PAGE_TEXT_BLOCKS:
                break

        if text_blocks:
            return dedupe_text_blocks(text_blocks)

    return []


def fetch_page_text_blocks(url):
    if not url or "news.google.com/rss/articles/" in url:
        return []

    if url in PAGE_TEXT_CACHE:
        return PAGE_TEXT_CACHE[url]

    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text_blocks = []
        title = soup.find("title")
        if title:
            text_blocks.append(title.get_text(" ", strip=True))

        for meta_name in ("description", "og:description"):
            meta = soup.find("meta", attrs={"name": meta_name}) or soup.find("meta", attrs={"property": meta_name})
            if meta and meta.get("content"):
                text_blocks.append(meta["content"])

        source_blocks = fetch_source_page_text_blocks(soup, url)
        if source_blocks:
            text_blocks.extend(source_blocks)
        else:
            for selector in ("h1", "h2", "p", "li"):
                for node in soup.select(selector):
                    text = normalize_text(node.get_text(" ", strip=True))
                    if len(text) >= 40:
                        text_blocks.append(text)
                    if len(text_blocks) >= MAX_PAGE_TEXT_BLOCKS:
                        break
                if len(text_blocks) >= MAX_PAGE_TEXT_BLOCKS:
                    break

        deduped_blocks = dedupe_text_blocks(text_blocks)

        PAGE_TEXT_CACHE[url] = deduped_blocks
        return deduped_blocks
    except requests.RequestException:
        PAGE_TEXT_CACHE[url] = []
        return []


def canonicalize_location_query(location_name):
    normalized = normalize_location_label(location_name)
    return LOCATION_ALIASES.get(normalized.lower(), normalized)


def get_coordinates(location_name):
    normalized_name = normalize_location_label(location_name)
    if not normalized_name:
        return None

    cache_key = normalized_name.lower()
    if cache_key in MANUAL_COORDINATES:
        return MANUAL_COORDINATES[cache_key]

    if cache_key in GEOCODE_CACHE:
        return GEOCODE_CACHE[cache_key]

    geocode_query = canonicalize_location_query(normalized_name)

    try:
        time.sleep(1.1)
        location = geolocator.geocode(geocode_query)
        if location:
            coordinates = [location.latitude, location.longitude]
            GEOCODE_CACHE[cache_key] = coordinates
            return coordinates

        location = fallback_geolocator.geocode(geocode_query)
        if location:
            coordinates = [location.latitude, location.longitude]
            GEOCODE_CACHE[cache_key] = coordinates
            return coordinates
    except (GeocoderTimedOut, Exception):
        GEOCODE_CACHE[cache_key] = None
        return None

    GEOCODE_CACHE[cache_key] = None
    return None


def get_entry_location_candidates(entry):
    text_blocks = build_text_blocks(entry)
    candidates = []
    seen = set()

    for block in text_blocks:
        for candidate in extract_location_candidates(block):
            lowered = candidate.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            candidates.append(candidate)

    if len(candidates) < 2 and entry.get("link"):
        for block in fetch_page_text_blocks(entry["link"]):
            for candidate in extract_location_candidates(block):
                lowered = candidate.lower()
                if lowered in seen:
                    continue
                seen.add(lowered)
                candidates.append(candidate)
                if len(candidates) >= MAX_LOCATION_CANDIDATES:
                    break
            if len(candidates) >= MAX_LOCATION_CANDIDATES:
                break

    return candidates[:MAX_LOCATION_CANDIDATES]


def keyword_filtered_entries(feed):
    matched_entries = []
    for entry in feed.entries:
        combined_text = " ".join(build_text_blocks(entry))
        if contains_keyword(combined_text):
            matched_entries.append(entry)
    return matched_entries


def published_value(entry):
    return entry.get("published") or entry.get("updated") or datetime.now().isoformat()


def entry_datetime(entry):
    try:
        return parsedate_to_datetime(published_value(entry))
    except (TypeError, ValueError, IndexError):
        return datetime.now()


def geocode_entry_locations(entry):
    geocoded_locations = []
    seen_names = set()
    for candidate in get_entry_location_candidates(entry):
        display_name = normalize_location_label(candidate)
        display_key = display_name.lower()
        if display_key in seen_names:
            continue

        coords = get_coordinates(display_name)
        if not coords:
            continue

        geocoded_locations.append({
            "name": display_name,
            "coordinates": coords,
        })
        seen_names.add(display_key)
        print(f"   📍 Geocoded: '{display_name}' -> {coords}")

        if len(geocoded_locations) >= MAX_GEOCODED_LOCATIONS:
            break

    return geocoded_locations


def build_outbreak(entry, default_source):
    geocoded_locations = geocode_entry_locations(entry)
    primary_location = geocoded_locations[0] if geocoded_locations else None
    source_title = default_source
    if hasattr(entry, "source") and entry.source:
        source_title = entry.source.get("title", source_title)

    return {
        "id": entry.get("id", entry.get("link", entry.get("title", default_source))),
        "title": entry.get("title", "Untitled"),
        "link": entry.get("link"),
        "location_name": primary_location["name"] if primary_location else None,
        "coordinates": primary_location["coordinates"] if primary_location else None,
        "locations": geocoded_locations,
        "published": published_value(entry),
        "source": source_title,
        "fetch_timestamp": datetime.now().isoformat(),
    }


def fetch_source_entries(source_config):
    print(f"📡 Connecting to: {source_config['url']}")
    feed = feedparser.parse(source_config["url"])
    if source_config["kind"] == "google-news":
        entries = feed.entries
    else:
        entries = keyword_filtered_entries(feed)

    print(f"🔍 {source_config['name']}: {len(entries)} relevant entries")
    return entries


def dedupe_entries(entries):
    unique_entries = []
    seen = set()
    for entry, source_name in entries:
        fingerprint = (
            normalize_text(entry.get("title", "")).lower(),
            normalize_text(entry.get("link", "")).lower(),
        )
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique_entries.append((entry, source_name))

    unique_entries.sort(key=lambda item: entry_datetime(item[0]), reverse=True)
    return unique_entries


def fetch_hantavirus_alerts():
    entries = []
    for source_config in SOURCE_CONFIGS:
        source_entries = fetch_source_entries(source_config)
        entries.extend((entry, source_config["name"]) for entry in source_entries)

    unique_entries = dedupe_entries(entries)
    print(f"🧭 Processing {len(unique_entries)} unique entries across {len(SOURCE_CONFIGS)} sources...")

    outbreaks = []
    for entry, source_name in unique_entries:
        outbreaks.append(build_outbreak(entry, source_name))

    return outbreaks


def save_data(data):
    if not os.path.exists("data"):
        os.makedirs("data")
        print("📁 Created 'data' directory.")

    file_path = "data/outbreaks.json"
    with open(file_path, "w", encoding="utf-8") as file_handle:
        json.dump(data, file_handle, indent=4, ensure_ascii=False)
    return file_path


def run_fetch_cycle():
    print("🚀 HantaWatch Global Engine: Starting fetch and geocode...")
    alerts = fetch_hantavirus_alerts()
    path = save_data(alerts)

    total = len(alerts)
    geocoded = sum(1 for alert in alerts if alert["coordinates"] is not None)
    coverage = (geocoded / total) * 100 if total else 0

    print(f"\n✅ Success! Saved {total} alerts to {path}")
    print(f"🌍 Geocoding coverage: {geocoded}/{total} ({coverage:.1f}%)")


def parse_args():
    parser = argparse.ArgumentParser(description="Fetch and save hantavirus outbreak data.")
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
