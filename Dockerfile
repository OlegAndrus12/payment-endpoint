FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY . .
RUN chmod +x docker-entrypoint.sh

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 5000

ENTRYPOINT ["./docker-entrypoint.sh"]
