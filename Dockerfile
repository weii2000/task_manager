FROM ghcr.io/astral-sh/uv:0.11.29-python3.12-trixie-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

COPY . .

RUN useradd --system --uid 10001 app
USER app

EXPOSE 8000

CMD [".venv/bin/fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
