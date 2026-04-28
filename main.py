from fastapi import FastAPI
from pydantic import BaseModel
from typing import List,Optional
import httpx


app = FastAPI()

@app.get('/search/movies')
def search_movies(
    q: str,
    genre: str = 'All',
    page: int = 1,
    limit: int = 20,
    min_rating: int = 0
):
    resp = httpx.get('https://yts.mx/api/v2/list_movies.json',params = {
        'query_term': q,
        'genre': genre,
        'page': page,
        'limit': limit,
        'minimum_rating':min_rating,
        'sort_by':'seeds'
    })

    data = resp.json()

    if data['status'] != 'ok':
        raise HTTPException(status_code = 502, detail = 'YTS API ERROR')
    
    movies = data['data'].get('movies',[])

    results = []

    for movie in movies:
        for torrent in movie['torrents']:
            magnet = build_magnet(torrent['hash'], movie['title'])
            results.append({
                'title':movie['title'],
                'year':movie['year'],
                'rating':movie['rating'],
                'quality':torrent['quality'],
                'size':torrent['size'],
                'seeders':torrent['seeds'],
                'leechers':torrent['peers'],
                'magnet':magnet
            })

    return results

def build_magnet(info_hash: str,title:str) -> str:
    trackers = [
        'udp://tracker.opentrackr.org:1337/announce',
        'udp://open.stealth.si:80/announce',
        'udp://tracker.torrent.eu.org:451/announce',
    ]

    tracker_params = '&'.join(f'tr={t}' for t in trackers)
    encoded_title = title.replace(' ','+')
    return f'magnet:?xt=urn:btih:{info_hash}&dn={encoded_title}&{tracker_params}'