from fastapi import FastAPI, HTTPException
from typing import List, Optional
import httpx

app = FastAPI()

# build_magnet defined FIRST before it's used
def build_magnet(info_hash: str, title: str) -> str:
    trackers = [
        'udp://tracker.opentrackr.org:1337/announce',
        'udp://open.stealth.si:80/announce',
        'udp://tracker.torrent.eu.org:451/announce',
    ]
    tracker_params = '&'.join(f'tr={t}' for t in trackers)
    encoded_title = title.replace(' ', '+')
    return f'magnet:?xt=urn:btih:{info_hash}&dn={encoded_title}&{tracker_params}'


@app.get('/search/movies')
def search_movies(
    q: str,
    genre: str = 'All',
    page: int = 1,
    limit: int = 20,
    min_rating: int = 0
):
    try:
        resp = httpx.get('https://yts.mx/api/v2/list_movies.json', params={
            'query_term': q,
            'genre': genre,
            'page': page,
            'limit': limit,
            'minimum_rating': min_rating,
            'sort_by': 'seeds'
        }, timeout=10)
        resp.raise_for_status()
    except httpx.ConnectError:
        raise HTTPException(status_code=502, detail="Cannot reach YTS")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="YTS took too long to respond")

    data = resp.json()

    if data['status'] != 'ok':
        raise HTTPException(status_code=502, detail='YTS API ERROR')

    movies = data['data'].get('movies', [])

    results = []
    for movie in movies:
        for torrent in movie['torrents']:
            magnet = build_magnet(torrent['hash'], movie['title'])
            results.append({
                'title': movie['title'],
                'year': movie['year'],
                'rating': movie['rating'],
                'quality': torrent['quality'],
                'size': torrent['size'],
                'seeders': torrent['seeds'],
                'leechers': torrent['peers'],
                'magnet': magnet
            })

    return results