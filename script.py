import requests
from bs4 import BeautifulSoup
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
from datetime import datetime, timedelta
 
# ─── DR Scraping ──────────────────────────────────────────────────────────────
 
def get_playlist_urls(channel="p3", days_back=7):
    """Generate DR playlist URLs for the past N days."""
    urls = []
    for i in range(days_back):
        date = (datetime.today() - timedelta(days=i)).strftime("%Y-%m-%d")
        urls.append(f"https://www.dr.dk/lyd/playlister/{channel}/{date}")
    return urls
 
def fetch_dr_playlist_page(url):
    """Scrape track list from a single DR playlist page."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "da-DK,da;q=0.9,en;q=0.8",
    }
    try:
        res = requests.get(url, headers=headers, timeout=15)
        print(f"  {url} → {res.status_code}")
        if res.status_code != 200:
            return []
    except Exception as e:
        print(f"  Request fejl for {url}: {e}")
        return []
 
    soup = BeautifulSoup(res.text, "html.parser")
    tracks = []
 
    # DR.dk embeds playlist data as JSON in a <script id="__NEXT_DATA__"> tag
    import json
    script_tag = soup.find("script", {"id": "__NEXT_DATA__"})
    if script_tag:
        try:
            data = json.loads(script_tag.string)
            # Navigate the Next.js page props to find track listings
            page_props = data.get("props", {}).get("pageProps", {})
            # Try common locations for track data
            playlist_items = (
                page_props.get("playlist", {}).get("items")
                or page_props.get("items")
                or page_props.get("tracks")
                or []
            )
            for item in playlist_items:
                artist = (
                    item.get("primaryArtist")
                    or item.get("artist")
                    or item.get("artistName")
                )
                title = item.get("title") or item.get("trackTitle")
                if artist and title:
                    tracks.append((artist.strip(), title.strip()))
        except Exception as e:
            print(f"  JSON parse fejl: {e}")
 
    # Fallback: parse HTML directly if JSON approach yields nothing
    if not tracks:
        for row in soup.select("[class*='playlist'] [class*='track'], [class*='PlaylistItem']"):
            artist_el = row.select_one("[class*='artist'], [class*='Artist']")
            title_el = row.select_one("[class*='title'], [class*='Title']")
            if artist_el and title_el:
                tracks.append((artist_el.get_text(strip=True), title_el.get_text(strip=True)))
 
    print(f"    Fandt {len(tracks)} tracks")
    return tracks
 
 
def fetch_dr(channel="p3", days_back=7):
    print(f"Henter DR {channel.upper()} playlister for de seneste {days_back} dage...")
    all_tracks = []
    for url in get_playlist_urls(channel, days_back):
        all_tracks.extend(fetch_dr_playlist_page(url))
 
    print(f"Total tracks hentet: {len(all_tracks)}")
    if not all_tracks:
        return pd.DataFrame(columns=["artist", "title"])
    return pd.DataFrame(all_tracks, columns=["artist", "title"])
 
 
# ─── Filtering ────────────────────────────────────────────────────────────────
 
def filter_songs(df, min_plays=2):
    print(f"Filtrerer sange (minimum {min_plays} afspilninger)...")
    if df.empty:
        return pd.DataFrame()
    counts = df.groupby(["artist", "title"]).size().reset_index(name="count")
    result = counts[counts["count"] >= min_plays].sort_values("count", ascending=False)
    print(f"Sange efter filter: {len(result)}")
    return result
 
 
# ─── Spotify ──────────────────────────────────────────────────────────────────
 
def get_spotify_client():
    """
    Auth via refresh token (required for headless/CI environments).
    Set SPOTIFY_REFRESH_TOKEN as a GitHub secret.
    See README for how to generate it once locally.
    """
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri="http://localhost:8888/callback",
        scope="playlist-modify-private playlist-modify-public",
        cache_path=".spotify_cache",
    ))
    # If a pre-generated refresh token is available, inject it
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN")
    if refresh_token:
        token_info = sp.auth_manager.refresh_access_token(refresh_token)
        sp = spotipy.Spotify(auth=token_info["access_token"])
    return sp
 
 
def get_or_create_playlist(sp, user_id, playlist_name):
    """Reuse existing playlist instead of creating a new one every run."""
    playlists = sp.user_playlists(user_id)
    while playlists:
        for pl in playlists["items"]:
            if pl["name"] == playlist_name:
                print(f"Genbruger eksisterende playlist: {pl['id']}")
                return pl["id"]
        playlists = sp.next(playlists) if playlists["next"] else None
 
    print("Opretter ny playlist...")
    pl = sp.user_playlist_create(user_id, playlist_name, public=False,
                                  description="Auto-genereret fra DR P3. Opdateres hver mandag.")
    return pl["id"]
 
 
def create_spotify_playlist(song_df, playlist_name="DR P3 Most Played (auto)"):
    print("Opdaterer Spotify playlist...")
    if song_df.empty:
        print("Ingen sange at tilføje")
        return
 
    sp = get_spotify_client()
    user_id = sp.current_user()["id"]
    playlist_id = get_or_create_playlist(sp, user_id, playlist_name)
 
    # Clear existing tracks
    sp.playlist_replace_items(playlist_id, [])
 
    track_ids = []
    for _, row in song_df.iterrows():
        query = f"artist:{row['artist']} track:{row['title']}"
        print(f"  Søger: {query}")
        try:
            result = sp.search(q=query, type="track", limit=1)
            items = result.get("tracks", {}).get("items", [])
            if items:
                track_ids.append(items[0]["id"])
            else:
                print(f"    Ikke fundet på Spotify")
        except Exception as e:
            print(f"    Spotify søgning fejlede: {e}")
 
    if track_ids:
        # Add in batches of 100 (Spotify API limit)
        for i in range(0, len(track_ids), 100):
            sp.playlist_add_items(playlist_id, track_ids[i:i+100])
        print(f"Tilføjede {len(track_ids)} tracks til playlist")
    else:
        print("Ingen tracks fundet på Spotify")
 
 
# ─── Main ─────────────────────────────────────────────────────────────────────
 
if __name__ == "__main__":
    print("Starter script...")
    df = fetch_dr(channel="p3", days_back=7)
 
    if df.empty:
        print("Ingen data hentet — stopper")
    else:
        filtered = filter_songs(df, min_plays=2)
        if filtered.empty:
            print("Ingen sange efter filter — stopper")
        else:
            create_spotify_playlist(filtered)
    print("Færdig!")
