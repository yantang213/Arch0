FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    ARCH0_HOST=0.0.0.0 \
    ARCH0_PORT=8000 \
    ARCH0_VAULT_DIR=/data/arch-vault

WORKDIR /app

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

RUN useradd --create-home --shell /usr/sbin/nologin arch0 \
    && mkdir -p /data/arch-vault \
    && chown -R arch0:arch0 /data

USER arch0

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "arch0.app:app", "--host", "0.0.0.0", "--port", "8000"]
