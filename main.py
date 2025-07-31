import requests
from bs4 import BeautifulSoup
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import threading

# Load environment variables
load_dotenv()
client_id = os.getenv("SPOTIFY_CLIENT_ID")
client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
playlist_id = os.getenv("SPOTIFY_PLAYLIST_ID")

# Scrape Billboard Hot 100 for #1 song
try:
    url = "https://www.billboard.com/charts/hot-100/"
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    song_element = soup.select_one("h3.c-title.a-no-trucate")
    artist_element = soup.select_one("span.c-label.a-no-trucate")
    song = song_element.text.strip() if song_element else "Unknown Song"
    artist = artist_element.text.strip() if artist_element else "Unknown Artist"
except requests.RequestException as e:
    print(f"Error fetching Billboard data: {e}")
    exit(1)

# Spotify setup
try:
    from flask import Flask, request
    import time

    app = Flask(__name__)
    code = [None]  # Use list for thread-safe global

    @app.route('/callback')
    def callback():
        code[0] = request.args.get('code')
        print(f"Callback hit with code: {code[0]}")  # Debug output
        return "Callback received", 200

    threading.Thread(target=app.run, kwargs={'host': '0.0.0.0', 'port': 8888}).start()

    # Wait briefly for the server to start and code to be set
    time.sleep(5)
    max_wait = 15
    while not code[0] and max_wait > 0:
        time.sleep(1)
        max_wait -= 1
        print(f"Waiting for code... {max_wait} seconds left")  # Debug wait
    if not code[0]:
        raise Exception("No authorization code received")

    sp_oauth = SpotifyOAuth(client_id=client_id,
        client_secret=client_secret,
        redirect_uri="https://09ab34cacede.ngrok-free.app/callback",
        scope="playlist-modify-public playlist-read-private",
        cache_path=".spotify_cache")
    token_info = sp_oauth.get_access_token(code[0])
    sp = spotipy.Spotify(auth=token_info['access_token'])

    # Search for the song on Spotify
    results = sp.search(q=f"track:{song} artist:{artist}", type="track", limit=1)
    track_id = results["tracks"]["items"][0]["id"] if results["tracks"]["items"] else None
    if not track_id:
        print(f"Could not find {song} by {artist} on Spotify")
        exit(1)

    # Check for duplicates in the playlist
    playlist_tracks = sp.playlist_tracks(playlist_id)
    existing_track_ids = [item["track"]["id"] for item in playlist_tracks["items"]]
    if track_id in existing_track_ids:
        print(f"{song} by {artist} is already in the playlist")
    else:
        sp.playlist_add_items(playlist_id=playlist_id, items=[f"spotify:track:{track_id}"])
        print(f"Added {song} by {artist} to playlist")
except spotipy.SpotifyException as e:
    print(f"Spotify error: {e}")
    exit(1)
