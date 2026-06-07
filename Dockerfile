FROM python:3.12-slim

ARG APT_DEBIAN_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian
ARG APT_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security
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

RUN sed -i "s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g; s|http://deb.debian.org/debian|${APT_DEBIAN_MIRROR}|g" /etc/apt/sources.list.d/debian.sources \
    && apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir --upgrade pip \
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
