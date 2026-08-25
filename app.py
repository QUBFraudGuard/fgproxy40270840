# app.py
import json
import time
import requests
import os
import threading
from flask import Flask, request, jsonify

app = Flask(__name__)
ROUTES_FILE = os.environ.get("ROUTES_FILE", "/etc/proxy-config/routes.json")

# --- C3: simple circuit breaker state, per backend ---
failures = {}          # backend_name -> consecutive failure count
breaker_open_until = {} # backend_name -> timestamp when breaker resets
lock = threading.Lock()
state = {}

FAILURE_THRESHOLD = 3
COOLDOWN_SECONDS = 15


def load_routes():
    # re-read the file on every request — this is what makes it
    # "configurable without redeploying": edit routes.json, no rebuild needed
    with open(ROUTES_FILE) as f:
        return json.load(f)


def get_state(name):
    now = time.time()
    current = state.get(name, "closed")
    if current == "open" and breaker_open_until.get(name, 0) <= now:
        state[name] = "half_open"
        return "half_open"
    return current


def call_backend(name, url, params):
    with lock:
        current_state = get_state(name)
        if current_state == "open":
            return None, "circuit open — backend temporarily unavailable"

    try:
        resp = requests.get(url + "/screen", params=params, timeout=2.0)
        resp.raise_for_status()
        with lock:
            failures[name] = 0
            state[name] = "closed"  # success closes the breaker, even from half-open
        return resp.json(), None
    except requests.RequestException:
        with lock:
            failures[name] = failures.get(name, 0) + 1
            if current_state == "half_open" or failures[name] >= FAILURE_THRESHOLD:
                state[name] = "open"
                breaker_open_until[name] = time.time() + COOLDOWN_SECONDS
        return None, "backend call failed"


@app.route("/screen/<backend_name>", methods=["GET"])
def proxy_screen(backend_name):
    routes = load_routes()
    if backend_name not in routes:
        return jsonify({"error": "unknown backend"}), 404

    data, error = call_backend(backend_name, routes[backend_name], dict(request.args))
    if error:
        return jsonify({"error": error}), 502
    return jsonify(data)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))