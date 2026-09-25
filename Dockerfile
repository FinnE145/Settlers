FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY settlers ./settlers

RUN useradd --system --uid 10001 --no-create-home settlers \
    && mkdir -p /data && chown settlers /data
USER settlers

# The running game is saved here after every move, so a restart doesn't lose it.
ENV SETTLERS_SAVE_FILE=/data/game.json
# Only answer Tailscale addresses (IPv4 and IPv6) and the container itself.
ENV SETTLERS_ALLOWED_NETWORKS=100.64.0.0/10,fd7a:115c:a1e0::/48,127.0.0.0/8,::1/128

VOLUME /data
EXPOSE 8000

# One worker: the game lives in that process. Threads serve the live-update sockets.
CMD ["gunicorn", "--worker-class", "gthread", "--workers", "1", "--threads", "32", \
     "--bind", "0.0.0.0:8000", "--access-logfile", "-", "settlers.app:create_app()"]
