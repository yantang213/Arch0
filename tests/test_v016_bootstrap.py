import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install.sh"
SKILL = ROOT / "skills" / "arch0" / "SKILL.md"


def test_installer_exists_is_executable_and_has_valid_shell_syntax():
    assert INSTALLER.exists()
    assert os.access(INSTALLER, os.X_OK)

    result = subprocess.run(
        ["sh", "-n", str(INSTALLER)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_installer_has_expected_bootstrap_controls():
    text = INSTALLER.read_text()

    for required in [
        "set -eu",
        "ARCH0_REPO_URL",
        "https://github.com/yantang213/Arch0.git",
        "ARCH0_REF",
        "ARCH0_INSTALL_DIR",
        "ARCH0_BIN_DIR",
        "ARCH0_SKIP_SKILL_INSTALL",
        "ARCH0_SKILL_SOURCE",
        "node",
        "npm install",
        "npm run build",
        "npx -y skills add",
        "arch0 setup remote",
        "arch0 status",
    ]:
        assert required in text

    assert "<owner>" not in text
    assert "sudo " not in text
    assert "apt " not in text
    assert "brew " not in text


def test_installer_fails_fast_when_prerequisites_are_missing():
    env = {**os.environ, "PATH": "/nonexistent"}
    result = subprocess.run(
        [str(INSTALLER)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "missing required command: git" in result.stderr


def test_arch0_skill_covers_remote_setup_usage_and_safety_rules():
    assert SKILL.exists()
    text = SKILL.read_text()

    for required in [
        "arch0 --help",
        "arch0 setup remote",
        "arch0 status",
        "arch0 doctor",
        "arch0 insert",
        "arch0 config show",
        "Do not write to `arch-vault/` directly.",
        "Do not include secrets in archive content.",
        "Do not duplicate Arch0 server decision logic in the client.",
    ]:
        assert required in text
