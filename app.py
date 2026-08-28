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

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


_last_good_routes = {}

def load_routes():
    global _last_good_routes
    try:
        with open(ROUTES_FILE) as f:
            routes = json.load(f)
        _last_good_routes = routes
        return routes
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        print(f"[proxy] failed to load routes config, using last known good config: {e}", flush=True)
        return _last_good_routes


def get_state(name):
    now = time.time()
    current = state.get(name, "closed")
    if current == "open" and breaker_open_until.get(name, 0) <= now:
        state[name] = "half_open"
        return "half_open"
    return current


def call_backend(name, url, endpoint, params):
    with lock:
        current_state = get_state(name)
        if current_state == "open":
            return None, "circuit open — backend temporarily unavailable"

    try:
        resp = requests.get(f"{url}/{endpoint}", params=params, timeout=10.0)
        resp.raise_for_status()
        with lock:
            failures[name] = 0
            state[name] = "closed"
        return resp.json(), None
    except requests.RequestException:
        with lock:
            failures[name] = failures.get(name, 0) + 1
            if current_state == "half_open" or failures[name] >= FAILURE_THRESHOLD:
                state[name] = "open"
                breaker_open_until[name] = time.time() + COOLDOWN_SECONDS
        return None, "backend call failed"


@app.route("/<endpoint>/<backend_name>", methods=["GET"])
def proxy_forward(endpoint, backend_name):
    routes = load_routes()
    if backend_name not in routes:
        return jsonify({"error": "unknown backend"}), 404

    data, error = call_backend(backend_name, routes[backend_name], endpoint, dict(request.args))
    if error:
        return jsonify({"error": error}), 502
    return jsonify(data)


@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))