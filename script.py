import requests
import pandas as pd
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os


def fetch_dr():
    print("Henter data fra DR...")

    url = "https://www.dr.dk/mu-online/api/1.4/playlist/get?channel=p3"

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "Referer": "https://www.dr.dk/lyd/p3/playlister"
    }

    res = requests.get(url, headers=headers)

    print("Status code:", res.status_code)

    if res.status_code != 200:
        print("Fejl i request")
        print(res.text[:500])
        return pd.DataFrame(columns=["artist", "title"])

    try:
        data = res.json()
    except Exception as e:
        print("JSON fejl:", e)
        print(res.text[:500])
        return pd.DataFrame(columns=["artist", "title"])

    tracks = []

    for item in data.get("playlist", []):
        artist = item.get("primaryArtist")
        title = item.get("title")

        if artist and title:
            tracks.append((artist, title))

    print(f"Fundet {len(tracks)} tracks")

    return pd.DataFrame(tracks, columns=["artist", "title"])


def filter_songs(df):
    print("Filtrerer sange...")

    if df.empty:
        return pd.DataFrame()

    counts = df.groupby(["artist", "title"]).size().reset_index(name="count")

    result = counts[counts["count"] >= 2]

    print(f"Sange efter filter: {len(result)}")

    return result


def create_spotify_playlist(song_df):
    print("Opretter Spotify playlist...")

    if song_df.empty:
        print("Ingen sange at tilføje")
        return

    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri="http://localhost:8888/callback",
        scope="playlist-modify-private"
    ))

    user_id = sp.current_user()["id"]

    playlist = sp.user_playlist_create(
        user_id,
        "DR P3 Most Played (auto)",
        public=False
    )

    track_ids = []

    for _, row in song_df.iterrows():
        query = f"artist:{row['artist']} track:{row['title']}"
        print("Søger:", query)

        result = sp.search(q=query, type="track", limit=1)

        items = result.get("tracks", {}).get("items", [])

        if items:
            track_ids.append(items[0]["id"])

    if track_ids:
        sp.playlist_add_items(playlist["id"], track_ids)

    print("Playlist oprettet")


if __name__ == "__main__":
    print("Starter script...")

    df = fetch_dr()

    if df.empty:
        print("Ingen data hentet — stopper")
    else:
        filtered = filter_songs(df)

        if filtered.empty:
            print("Ingen sange efter filter — stopper")
        else:
            create_spotify_playlist(filtered)
