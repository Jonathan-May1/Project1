import requests
from bs4 import BeautifulSoup
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), 'lib'))
from lib.ngrok_utils import start_ngrok, stop_ngrok
import flask
import threading
import time

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
    # Updated to target the correct div container and ul
    chart_container = soup.select_one("div.o-chart-results-list-row-container")
    chart_items = chart_container.select("ul.o-chart-results-list-row li.o-chart-results-list__item") if chart_container else []
    print(f"Chart container found: {chart_container is not None}")
    print(f"Number of chart items: {len(chart_items)}")
    chart_item = chart_items[0] if chart_items else None
    # Debug all items to find the correct one
    for i, item in enumerate(chart_items):
        print(f"Item {i} HTML: {item.prettify()[:200]}...")  # Limit to 200 chars for readability
    for i, item in enumerate(chart_items):
        song_el = item.select_one("h3.c-title, h3.c-title.a-no-trucate")
        artist_el = item.select_one("span.c-label, span.c-label.a-no-trucate")
        print(f"Item {i}: Song element found: {song_el is not None}, Artist element found: {artist_el is not None}")
    chart_item = next((item for item in chart_items if item.select_one("h3.c-title") and item.select_one("span.c-label")), None)
    print(f"Selected chart item HTML: {chart_item.prettify() if chart_item else 'None'}")  # Debug the content
    song_element = chart_item.select_one("h3.c-title.a-no-trucate, h3.c-title") if chart_item else None  # Try both variations
    artist_element = chart_item.select_one("span.c-label.a-no-trucate, span.c-label") if chart_item else None  # Try both variations
    song = song_element.text.strip() if song_element else "Unknown Song"
    artist = artist_element.text.strip() if artist_element else "Unknown Artist"
    print(f"Scraped song: {song}, artist: {artist}")  # Debug output
except requests.RequestException as e:
    print(f"Error fetching Billboard data: {e}")
    exit(1)

try:
    # Start ngrok and get dynamic redirect URI
    result = start_ngrok(8888)
    if isinstance(result, tuple) and len(result) == 2:
        forwarding_url, ngrok_process = result
        print("Forwarding URL:", forwarding_url)
        print("ngrok process:", ngrok_process)
        if ngrok_process is None:
            print("Using existing ngrok tunnel, no new process started.")
        else:
            print("Started new ngrok process.")
    else:
        raise Exception("Invalid return from start_ngrok: expected (url, process) tuple")
    redirect_uri = f"{forwarding_url}/callback"
    print(f"Using dynamic redirect URI: {redirect_uri}")
    print("Pause to update Spotify Dashboard:")
    input("Update the Spotify Developer Dashboard with the new redirect URI and press Enter to continue...")
    print(f"If the browser does not open automatically, please visit this URL to log in and approve the app:")
    print(f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope=playlist-modify-public+playlist-read-private")

    # Set up Flask server to handle callback
    app = flask.Flask(__name__)
    code = [""]  # Use list to allow modification in inner function

    @app.route('/callback')
    def callback():
        code[0] = flask.request.args.get('code')
        print("Callback received with code:", code[0])  # Debug log
        return "Authentication successful! You can close this window."

    def run_server():
        app.run(host='0.0.0.0', port=8888)

    # Spotify setup
    try:
        sp_oauth = SpotifyOAuth(client_id=client_id,
                                client_secret=client_secret,
                                redirect_uri=redirect_uri,
                                scope="playlist-modify-public playlist-read-private",
                                cache_path=".spotify_cache",
                                open_browser=False)
        server = threading.Thread(target=run_server, daemon=True)
        server.start()
        import webbrowser
        webbrowser.open(f"https://accounts.spotify.com/authorize?client_id={client_id}&response_type=code&redirect_uri={redirect_uri}&scope=playlist-modify-public+playlist-read-private")
        while not code[0]:
            time.sleep(1)
        print("Received code:", code[0])
        token_info = sp_oauth.get_access_token(code=code[0])
        sp = spotipy.Spotify(auth=token_info['access_token'])

        # Search for the song on Spotify
        results = sp.search(q=f"track:{song} artist:{artist}", type="track", limit=1)
        track_id = results["tracks"]["items"][0]["id"] if results["tracks"]["items"] else None
        if not track_id:
            print(f"Could not find {song} by {artist} on Spotify")
            stop_ngrok(ngrok_process)
            exit(1)

        # Check for duplicates in the playlist
        playlist_tracks = sp.playlist_tracks(playlist_id)
        existing_track_ids = [item["track"]["id"] for item in playlist_tracks["items"]]
        if track_id in existing_track_ids:
            print(f"{song} by {artist} is already in the playlist")
        else:
            sp.playlist_add_items(playlist_id=playlist_id, items=[f"spotify:track:{track_id}"])
            print(f"Added {song} by {artist} to playlist")

        stop_ngrok(ngrok_process)  # Stop ngrok at the end
    except spotipy.SpotifyException as e:
        print(f"Spotify error: {e}")
        stop_ngrok(ngrok_process)
        exit(1)
except Exception as e:
    print(f"Error starting ngrok: {e}")
    exit(1)
