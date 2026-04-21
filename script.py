import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os


def fetch_dr():
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)

    driver.get("https://www.dr.dk/lyd/p3/playlister")

    # 🔥 Vent på at noget overhovedet loader
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    time.sleep(5)  # ekstra buffer

    data = []

    # 🔥 Scroll (vigtigt for lazy loading)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(3)

    buttons = driver.find_elements(By.TAG_NAME, "button")

    print(f"Fundet {len(buttons)} knapper")

    for b in buttons[:10]:  # begræns
        try:
            driver.execute_script("arguments[0].click();", b)
            time.sleep(3)

            rows = driver.find_elements(By.CSS_SELECTOR, "[data-testid='playlist-track']")

            print(f"Tracks fundet i klik: {len(rows)}")

            for r in rows:
                text = r.text.strip()

                if " - " in text:
                    artist, title = text.split(" - ", 1)
                    data.append((artist, title))

        except Exception as e:
            print("Fejl ved klik:", e)
            continue

    driver.quit()

    print(f"Fundet {len(data)} tracks TOTAL")

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
