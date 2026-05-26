FROM ghcr.io/astral-sh/uv:0.9.30@sha256:538e0b39736e7feae937a65983e49d2ab75e1559d35041f9878b7b7e51de91e4 AS uv

FROM python:3.12-slim@sha256:46cb7cc2877e60fbd5e21a9ae6115c30ace7a077b9f8772da879e4590c18c2e3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_CACHE=1 \
    PATH="/app/.venv/bin:${PATH}"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

COPY pyproject.toml uv.lock README.md LICENSE ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable \
    && rm -rf /root/.cache/uv

ENV FOVUX_HOME=/data/.fovux
ENV FOVUX_LOG_LEVEL=INFO

VOLUME ["/data"]
EXPOSE 7823

ENTRYPOINT ["fovux-mcp"]
# Containers listen on their bridge interface; docker-compose keeps host exposure on loopback.
CMD ["serve", "--http", "--host", "0.0.0.0", "--port", "7823"]
