# ──────────────────────────────────────────────────────────────
# forecast-service image
#
# One image, two roles:
#   API     (default CMD below)          dashboard reads, "what if" scenarios
#   worker  (command: python -m app.worker)  recomputes forecasts from queue events
# ──────────────────────────────────────────────────────────────

# ── Stage 1: build wheels ─────────────────────────────────────
# Compilers are only needed to build scientific packages (numpy,
# pandas, statsmodels, prophet). They stay in this stage and never
# ship in the final image: smaller image, fewer tools for an attacker.
FROM python:3.12-slim AS builder

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

# ── Stage 2: slim runtime ─────────────────────────────────────
FROM python:3.12-slim

# PYTHONUNBUFFERED: logs stream straight to `kubectl logs`.
# HOME=/tmp: libraries that write caches under HOME (matplotlib,
# cmdstanpy) need a writable path, and /tmp is the one writable
# directory once Kubernetes makes the root filesystem read-only.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp

# Numeric UID on purpose: Kubernetes' runAsNonRoot check can only
# verify a numeric user. A named user makes the pod fail to start.
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser

WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels

COPY app/ ./app/

USER 10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
