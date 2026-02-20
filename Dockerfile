# syntax=docker/dockerfile:1.6
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# System deps:
# - ca-certificates/curl: TLS + downloads
# - gnupg: importer la clé GPG Docker
# - lsb-release: utile pour certains environnements (codename)
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      gnupg \
      lsb-release; \
    rm -rf /var/lib/apt/lists/*

# Install Docker CLI + Compose plugin (Docker official repository)
# => évite docker.io / docker-compose-plugin Debian qui peuvent être absents/instables selon la base.
RUN set -eux; \
    install -m 0755 -d /etc/apt/keyrings; \
    curl -fsSL "https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg" \
      | gpg --dearmor -o /etc/apt/keyrings/docker.gpg; \
    chmod a+r /etc/apt/keyrings/docker.gpg; \
    . /etc/os-release; \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${ID} ${VERSION_CODENAME} stable" \
      > /etc/apt/sources.list.d/docker.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
      docker-ce-cli \
      docker-compose-plugin; \
    rm -rf /var/lib/apt/lists/*; \
    docker --version; \
    docker compose version

# Python build
COPY pyproject.toml /app/pyproject.toml

RUN pip install --upgrade pip \
 && pip install .

COPY src/ /app/src/
ENV PYTHONPATH=/app/src

EXPOSE 8088

CMD ["python", "-m", "azursmartmix_control.main"]
