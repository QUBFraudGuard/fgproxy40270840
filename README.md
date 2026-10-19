# fgproxy40270840

A custom reverse proxy for QUBCloud-FraudGuard, built from scratch (no off-the-shelf proxy or managed load balancer). It sits between the frontend and the backend services.

Part of [QUBCloud-FraudGuard](https://github.com/QUBFraudGuard).

## What it does

- Forwards requests from the frontend to the right backend
- Loads its routes from a config file, so routes can change without rebuilding the proxy
- Protects backends with a circuit breaker
- Exposes `/health`

## Routing

Routes live in a flat JSON file (`routes.json`) mounted from a Kubernetes ConfigMap. It maps a route name to a backend URL

- The file is re-read on every request, so editing the ConfigMap takes effect without a redeploy.
- If the file contains invalid JSON, the proxy keeps using the last routes that loaded successfully.
- The proxy holds no state.

## Circuit breaker

| Parameter | Value | Why |
| --- | --- | --- |
| `FAILURE_THRESHOLD` | 3 | Tolerates a couple of transient failures |
| `COOLDOWN_SECONDS` | 15 | Time for a backend to recover without staying degraded long |
| Request timeout | 10 s | An earlier 2 s timeout caused false failures on large batches |

States: **closed** (normal), **open** (calls refused during cool-down), **half-open** (one probe request; success closes the circuit, failure restarts the cool-down). The half-open state stops a recovering backend being flooded by queued requests.

## Run locally

```bash
git clone https://github.com/QUBFraudGuard/fgproxy40270840.git
cd fgproxy40270840
pip install -r requirements.txt
python app.py
```
