FROM python:3.13-slim-bookworm
ENV PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir aiohttp==3.14.5 livekit==1.0.23
WORKDIR /app
COPY worker/ /app/
CMD ["python", "/app/server.py"]
