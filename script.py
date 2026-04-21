import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os


import requests

def fetch_dr():
    url = "https://www.dr.dk/mu-online/api/1.4/playlist/get?channel=p3"

    res = requests.get(url)
    data = res.json()

    tracks = []

    for item in data.get("playlist", []):
        artist = item.get("primaryArtist")
        title = item.get("title")

        if artist and title:
            tracks.append((artist, title))

    print(f"Fundet {len(tracks)} tracks fra API")

    return pd.DataFrame(tracks, columns=["artist", "title"])

def filter_songs(df):
    counts = df.groupby(["artist", "title"]).size().reset_index(name="count")
    return counts[counts["count"] >= 2]


def spotify_create(songs):
    sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.environ["SPOTIFY_CLIENT_ID"],
        client_secret=os.environ["SPOTIFY_CLIENT_SECRET"],
        redirect_uri="http://localhost:8888/callback",
        scope="playlist-modify-private"
    ))

    user = sp.current_user()["id"]

    playlist = sp.user_playlist_create(
        user,
        "DR P3 Most Played",
        public=False
    )

    ids = []

    for _, row in songs.iterrows():
        q = f"artist:{row['artist']} track:{row['title']}"
        res = sp.search(q=q, type="track", limit=1)

        if res["tracks"]["items"]:
            ids.append(res["tracks"]["items"][0]["id"])

    if ids:
        sp.playlist_add_items(playlist["id"], ids)


if __name__ == "__main__":
    df = fetch_dr()

    if not df.empty:
        top = filter_songs(df)
        if not top.empty:
            spotify_create(top)
