# Development containers only: host input and microphone require the desktop app.
FROM node:24-alpine AS webui
WORKDIR /build
COPY webui/package.json webui/package-lock.json ./
RUN npm ci
COPY webui/ ./
RUN npm run build

FROM python:3.11-slim AS base
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    VOICE_CONTROL_HOME=/data
WORKDIR /app
COPY requirements-docker.txt ./
RUN pip install --no-cache-dir -r requirements-docker.txt
COPY app/ ./app/
COPY server/ ./server/
COPY controller/ ./controller/
COPY controls/ ./controls/
COPY data/ ./data/
COPY tools/ ./tools/
COPY main.py version.json pyproject.toml ./
RUN mkdir -p /data && \
    adduser --disabled-password --gecos "" --uid 10001 voicecontrol && \
    chown -R voicecontrol:voicecontrol /app /data

FROM base AS runtime
COPY --from=webui --chown=voicecontrol:voicecontrol /build/dist ./webui/dist
USER voicecontrol
EXPOSE 21337
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "tools/healthcheck.py"]
CMD ["python", "-m", "uvicorn", "server.api:app", "--host", "0.0.0.0", "--port", "21337"]

FROM base AS dev
USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir pytest pytest-asyncio httpx ruff
COPY tests/ ./tests/
RUN chown -R voicecontrol:voicecontrol /app
USER voicecontrol
CMD ["python", "-m", "pytest", "-q", "-m", "not slow and not audio"]
