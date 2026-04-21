import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os


def fetch_dr():
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)

    driver.get("https://www.dr.dk/lyd/p3/playlister")
    time.sleep(8)

    data = []

    buttons = driver.find_elements(By.CSS_SELECTOR, "button")

    clicked = 0

    for b in buttons:
        label = b.text.strip()

        if "." in label or "-" in label:
            driver.execute_script("arguments[0].click();", b)
            time.sleep(5)

            # 🔥 VIGTIG: mere præcis selector
            rows = driver.find_elements(By.CSS_SELECTOR, "[data-testid='playlist-track']")

            for r in rows:
                try:
                    text = r.text.strip()

                    if " - " in text:
                        artist, title = text.split(" - ", 1)
                        data.append((artist, title))
                except:
                    continue

            clicked += 1
            if clicked >= 5:
                break

    driver.quit()

    print(f"Fundet {len(data)} tracks")

    return pd.DataFrame(data, columns=["artist", "title"])

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
