from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
COMPOSE = ROOT / "docker-compose.yml"
ENV_EXAMPLE = ROOT / ".env.example"
DOCKERIGNORE = ROOT / ".dockerignore"
GITIGNORE = ROOT / ".gitignore"


def test_docker_deployment_files_exist():
    assert DOCKERFILE.exists()
    assert COMPOSE.exists()
    assert ENV_EXAMPLE.exists()
    assert DOCKERIGNORE.exists()


def test_dockerfile_runs_arch0_server_with_vault_dir():
    text = DOCKERFILE.read_text()

    for required in [
        "FROM python:3.12-slim",
        "PYTHONPATH=/app/src",
        "ARCH0_VAULT_DIR=/data/arch-vault",
        "COPY pyproject.toml",
        "COPY src ./src",
        "pip install --no-cache-dir .",
        "useradd",
        "USER arch0",
        "EXPOSE 8000",
        "uvicorn",
        "arch0.app:app",
    ]:
        assert required in text


def test_compose_maps_host_port_and_persistent_vault():
    text = COMPOSE.read_text()

    for required in [
        "name: arch0",
        "container_name: arch0",
        "env_file:",
        "path: .env",
        "required: false",
        "ARCH0_VAULT_DIR: /data/arch-vault",
        '"8989:8000"',
        "${ARCH0_HOST_VAULT_DIR:-./Arch0Vault}:/data/arch-vault",
        "healthcheck:",
        "http://127.0.0.1:8000/healthz",
        "restart: unless-stopped",
    ]:
        assert required in text


def test_env_example_documents_required_runtime_values_without_secrets():
    text = ENV_EXAMPLE.read_text()

    for required in [
        "ARCH0_HOST_VAULT_DIR=./Arch0Vault",
        "ARCH0_LLM_API_KEY=",
        "ARCH0_LLM_BASE_URL=https://api.openai.com/v1",
        "ARCH0_LLM_MODEL=gpt-4.1-mini",
        "# ARCH0_API_TOKEN=",
    ]:
        assert required in text

    assert "sk-" not in text
    assert "gho_" not in text
    assert "tskey-" not in text


def test_private_env_and_vault_paths_are_ignored():
    gitignore = GITIGNORE.read_text()
    dockerignore = DOCKERIGNORE.read_text()

    for ignored in [
        ".env",
        ".env.private",
        "arch-vault/",
        "Arch0Vault/",
        "readme-private.md",
    ]:
        assert ignored in gitignore
        assert ignored in dockerignore

    for ignored in [
        "cli/node_modules/",
        "cli/dist/",
        "discussion_with_ai/",
        "TECH_DESIGN_*.md",
    ]:
        assert ignored in dockerignore
