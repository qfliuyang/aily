FROM python:3.11-slim-bookworm AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN printf '%s\n' \
        'Acquire::Retries "5";' \
        'Acquire::http::Timeout "60";' \
        'Acquire::https::Timeout "60";' \
        > /etc/apt/apt.conf.d/80-aily-retries

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        libmagic1 \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
RUN for attempt in 1 2 3; do \
        python -m playwright install --with-deps chromium && break; \
        if [ "$attempt" = "3" ]; then exit 1; fi; \
        apt-get clean; \
        rm -rf /var/lib/apt/lists/*; \
        sleep $((attempt * 10)); \
    done

COPY aily ./aily
COPY scripts ./scripts
COPY pyproject.toml README.md ./

RUN mkdir -p /data/runs /vault /chaos

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()"

CMD ["uvicorn", "aily.main:app", "--host", "0.0.0.0", "--port", "8000"]
