# Deployment Probes: `/health` for liveness, `/ready` for readiness

This backend uses split probe semantics:
- `GET /health`: process liveness only (lightweight, no dependency checks)
- `GET /ready`: strict readiness (DB + LLM config + cached LLM `who are you` probe)
- when `APP_LLM_GATEWAY_MODE=worker`, backend `/ready` checks worker readiness instead of probing upstream LLM directly.

## Kubernetes

Templates are provided in:
- `deploy/k8s/rpg-backend-deployment.yaml`
- `deploy/k8s/rpg-backend-configmap.yaml`
- `deploy/k8s/rpg-backend-secret.example.yaml`

### Apply

```bash
kubectl apply -f deploy/k8s/rpg-backend-configmap.yaml
kubectl apply -f deploy/k8s/rpg-backend-secret.example.yaml
kubectl apply -f deploy/k8s/rpg-backend-deployment.yaml
kubectl apply -f deploy/k8s/rpg-llm-worker-deployment.yaml
kubectl apply -f deploy/k8s/rpg-llm-worker-service.yaml
kubectl apply -f deploy/k8s/rpg-llm-worker-hpa.yaml
```

### Probe wiring

- `livenessProbe`: `GET /health`
- `readinessProbe`: `GET /ready`
- `startupProbe`: `GET /health`

Notes:
- Keep readiness period moderate (default template uses 15s) to avoid unnecessary probe traffic.
- `/ready` LLM check uses in-process cache (`APP_READY_LLM_PROBE_CACHE_TTL_SECONDS`, default `30`).

## systemd (process manager)

Units are provided in:
- `deploy/systemd/rpg-backend.service`
- `deploy/systemd/rpg-backend-readiness.service`
- `deploy/systemd/rpg-backend-readiness.timer`
- `deploy/systemd/rpg-llm-worker.service`
- `deploy/systemd/rpg-llm-worker-readiness.service`
- `deploy/systemd/rpg-llm-worker-readiness.timer`

### Install

```bash
sudo cp deploy/systemd/rpg-backend.service /etc/systemd/system/
sudo cp deploy/systemd/rpg-backend-readiness.service /etc/systemd/system/
sudo cp deploy/systemd/rpg-backend-readiness.timer /etc/systemd/system/
sudo cp deploy/systemd/rpg-llm-worker.service /etc/systemd/system/
sudo cp deploy/systemd/rpg-llm-worker-readiness.service /etc/systemd/system/
sudo cp deploy/systemd/rpg-llm-worker-readiness.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now rpg-backend.service
sudo systemctl enable --now rpg-backend-readiness.timer
sudo systemctl enable --now rpg-llm-worker.service
sudo systemctl enable --now rpg-llm-worker-readiness.timer
```

### Verify

```bash
systemctl status rpg-backend.service
systemctl status rpg-backend-readiness.timer
systemctl list-timers | rg rpg-backend-readiness
systemctl status rpg-llm-worker.service
systemctl status rpg-llm-worker-readiness.timer
systemctl list-timers | rg rpg-llm-worker-readiness
```

The timer runs `curl --fail http://127.0.0.1:8000/ready` every 30s.
If readiness fails, the probe unit will show failure in `systemctl status` and journal logs.
