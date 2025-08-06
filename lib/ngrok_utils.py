import subprocess
import time
import requests
import json

def start_ngrok(port=8888):
    print("Entering start_ngrok with port:", port)
    # Check for existing ngrok session
    print("Checking for existing ngrok session...")
    try:
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=15)
        response.raise_for_status()
        tunnels = response.json()
        print("API response (existing check):", json.dumps(tunnels, indent=2))
        for tunnel in tunnels.get("tunnels", []):
            print("Found tunnel (existing):", tunnel)
            if str(tunnel.get("local_port")) == str(port):
                forwarding_url = tunnel.get("public_url")
                print("Using existing tunnel with URL:", forwarding_url)
                return forwarding_url, None  # Moved return inside if to ensure early exit
    except requests.RequestException as e:
        print("Existing session check failed or Web Interface unavailable:", e)
        # Proceed to new process only if no existing tunnel is found

    # If no existing tunnel is detected or check fails, start a new ngrok process
    print("No existing tunnel detected or check failed, starting new ngrok on port:", port)
    process = subprocess.Popen(["ngrok", "http", str(port)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("New ngrok process started:", process)
    time.sleep(15)
    try:
        print("Querying ngrok Web Interface for tunnel...")
        response = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=15)
        response.raise_for_status()
        tunnels = response.json()
        print("API response (new tunnel):", json.dumps(tunnels, indent=2))
        for tunnel in tunnels.get("tunnels", []):
            print("Found tunnel:", tunnel)
            if str(tunnel.get("local_port")) == str(port) or tunnel.get("public_url") is not None:  # Accept any valid tunnel
                forwarding_url = tunnel.get("public_url")
                print("Matched tunnel with URL:", forwarding_url, "process:", process)
                return forwarding_url, process
            raise Exception("No matching tunnel found after starting ngrok")
    except requests.RequestException as e:
        raise Exception(f"Failed to query ngrok Web Interface: {e}")
    except Exception as e:
        raise Exception(f"Failed to get ngrok forwarding URL: {e}")

def stop_ngrok(process):
    # Stop the ngrok process if it exists
    if process:
        process.kill()
