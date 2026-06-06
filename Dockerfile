FROM python:3.12-slim

ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG PIP_TRUSTED_HOST=

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    ARCH0_HOST=0.0.0.0 \
    ARCH0_PORT=8000 \
    ARCH0_VAULT_DIR=/data/arch-vault \
    PIP_INDEX_URL=${PIP_INDEX_URL} \
    PIP_TRUSTED_HOST=${PIP_TRUSTED_HOST} \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

COPY pyproject.toml ./

RUN pip install --no-cache-dir --upgrade pip \
    && python -c "import tomllib; deps = tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']; print('\n'.join(deps))" > /tmp/arch0-requirements.txt \
    && pip install --no-cache-dir -r /tmp/arch0-requirements.txt

COPY src ./src

RUN pip install --no-cache-dir --no-deps .

RUN useradd --create-home --shell /usr/sbin/nologin arch0 \
    && mkdir -p /data/arch-vault \
    && chown -R arch0:arch0 /data

USER arch0

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "arch0.app:app", "--host", "0.0.0.0", "--port", "8000"]
