from fastapi import FastAPI, HTTPException
from typing import List, Optional
import httpx
import threading
import time
import re


app = FastAPI(title="Torrent API")

# ─── Quality Rankings ───────────────────────────────
SOURCE_RANK = {
    'remux': 7,
    'bluray': 6, 'blu-ray': 6, 'bdrip': 6,
    'web-dl': 5, 'webdl': 5, 'webrip': 5, 'web': 5,
    'hdrip': 4, 'hd': 4,
    'dvdrip': 3, 'dvd': 3,
    'ts': 2, 'hdts': 2,
    'cam': 1
}

RESOLUTION_RANK = {
    '2160p': 5, '4k': 5,
    '1080p': 4,
    '720p': 3,
    '480p': 2,
    '360p': 1
}

ADULT_KEYWORDS = ['18+', 'xxx', 'porn', 'adult', 'erotic']

# ─── Helper Functions ───────────────────────────────
def get_resolution_label(name: str) -> str:
    name_lower = name.lower()
    
    # Explicit resolution in name
    for res in RESOLUTION_RANK.keys():
        if res in name_lower:
            return res
    
    # Infer from source type
    if 'remux' in name_lower or 'bdremux' in name_lower:
        return '2160p/1080p'
    if 'bluray' in name_lower or 'bdrip' in name_lower:
        return '1080p'
    if 'web-dl' in name_lower or 'webrip' in name_lower:
        return '1080p'
    if 'hdrip' in name_lower:
        return '720p'
    if 'dvdrip' in name_lower or 'dvd' in name_lower:
        return '480p'
    
    return 'Unknown'

def is_adult(name: str) -> bool:
    name_lower = name.lower()
    return any(kw in name_lower for kw in ADULT_KEYWORDS)

def get_source_rank(name: str) -> int:
    name_lower = name.lower()
    for source, rank in SOURCE_RANK.items():
        if source in name_lower:
            return rank
    return 0

def get_resolution_rank(name: str) -> int:
    name_lower = name.lower()
    for res, rank in RESOLUTION_RANK.items():
        if res in name_lower:
            return rank
    return 0


def build_magnet(info_hash: str, name: str) -> str:
    trackers = [
        "udp://tracker.opentrackr.org:1337/announce",
        "udp://open.stealth.si:80/announce",
        "udp://tracker.torrent.eu.org:451/announce",
    ]
    tracker_params = "&".join(f"tr={t}" for t in trackers)
    return f"magnet:?xt=urn:btih:{info_hash}&dn={name.replace(' ', '+')}&{tracker_params}"

def bytes_to_readable(size_bytes: str) -> str:
    size = int(size_bytes)
    if size >= 1_000_000_000:
        return f"{size / 1_000_000_000:.2f} GB"
    elif size >= 1_000_000:
        return f"{size / 1_000_000:.2f} MB"
    return f"{size} bytes"

# ─── Routes ─────────────────────────────────────────
@app.get('/search')
def search(q: str, cat: str = "201"):
    try:
        resp = httpx.get("https://apibay.org/q.php",
            params={"q": q, "cat": cat},
            timeout=10
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot reach TPB")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TPB timeout")

    data = resp.json()

    if not data or data[0].get('id') == '0':
        raise HTTPException(status_code=404, detail="No results found")

    results = []
    for t in data:
        name = t['name']
        seeders = int(t.get('seeders', 0))

        if is_adult(name):
            continue
        if seeders == 0:
            continue

        results.append({
            'name': name,
            'resolution': get_resolution_label(name),
            'source': next((s for s in SOURCE_RANK if s in name.lower()), 'unknown'),
            'seeders': seeders,
            'leechers': int(t.get('leechers', 0)),
            'size': bytes_to_readable(t['size']),
            'magnet': build_magnet(t['info_hash'], name),
            '_score': (get_resolution_rank(name) * 1000) +
                      (get_source_rank(name) * 100) +
                      min(seeders, 99)
        })

    results.sort(key=lambda x: x['_score'], reverse=True)

    for r in results:
        r.pop('_score')

    return results


@app.get('/ping')
def ping():
    return {"status": "alive"}


# ─── Self Ping ───────────────────────────────────────
def ping_self():
    while True:
        time.sleep(840)
        try:
            httpx.get("https://torrent-api-91z3.onrender.com/ping")
        except:
            pass

thread = threading.Thread(target=ping_self, daemon=True)
thread.start()