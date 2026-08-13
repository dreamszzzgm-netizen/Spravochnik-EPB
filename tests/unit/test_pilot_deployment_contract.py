from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_pilot_files_exist() -> None:
    for relative in (
        "Dockerfile.backend",
        "frontend/Dockerfile",
        "frontend/.dockerignore",
        "docker-compose.pilot.yml",
        "deploy/pilot/.env.pilot.example",
        "deploy/pilot/backup.sh",
        "deploy/pilot/start-pilot.ps1",
        "deploy/pilot/stop-pilot.ps1",
        "deploy/pilot/create-desktop-shortcuts.ps1",
        "docs/PILOT_DEPLOYMENT.md",
    ):
        assert (ROOT / relative).is_file(), relative


def test_pilot_compose_exposes_only_frontend_and_gates_migrations() -> None:
    compose = _read("docker-compose.pilot.yml")

    for service in (
        "postgres:",
        "migrate:",
        "backend:",
        "worker:",
        "scheduler:",
        "frontend:",
        "backup:",
    ):
        assert service in compose

    assert '${PILOT_HTTP_PORT:-3000}:3000' in compose
    assert "5432:5432" not in compose
    assert "8000:8000" not in compose
    assert "service_completed_successfully" in compose
    assert "service_healthy" in compose
    assert "/health/ready" in compose
    assert "./var/pilot/storage" in compose
    assert "./var/pilot/backups" in compose
    assert "maintenance" in compose
    assert "APP_ENV=production" in compose or "APP_ENV: production" in compose
    assert "spravoshnik:spravoshnik" not in compose


def test_pilot_environment_template_has_no_admin_or_default_production_password() -> None:
    env_example = _read("deploy/pilot/.env.pilot.example")

    assert "PILOT_HTTP_PORT=3000" in env_example
    assert "POSTGRES_PASSWORD=CHANGE_ME" in env_example
    assert "DATABASE_URL=" in env_example
    assert "SESSION_COOKIE_SECURE=false" in env_example
    assert "ADMIN_PASSWORD=" not in env_example
    assert "spravoshnik:spravoshnik" not in env_example


def test_backend_image_contains_runtime_and_migration_inputs() -> None:
    dockerfile = _read("Dockerfile.backend")

    assert "FROM python:3.12" in dockerfile
    assert "COPY alembic ./alembic" in dockerfile
    assert "COPY alembic.ini" in dockerfile
    assert "pip install" in dockerfile
    assert "/var/lib/spravoshnik/storage" in dockerfile
    assert 'CMD ["spravoshnik-api"]' in dockerfile
    assert "DATABASE_URL=" not in dockerfile


def test_frontend_image_is_standalone_and_uses_internal_backend() -> None:
    config = _read("frontend/next.config.mjs")
    dockerfile = _read("frontend/Dockerfile")

    assert 'output: "standalone"' in config
    assert "npm ci" in dockerfile
    assert "npm run build" in dockerfile
    assert ".next/standalone" in dockerfile
    assert ".next/static" in dockerfile
    assert "public" in dockerfile
    assert "BACKEND_ORIGIN=http://backend:8000" in dockerfile
    assert "HOSTNAME=0.0.0.0" in dockerfile
    assert "EXPOSE 3000" in dockerfile


def test_real_pilot_secrets_and_data_are_gitignored() -> None:
    gitignore = _read(".gitignore")

    assert "deploy/pilot/.env.pilot" in gitignore
    assert "var/pilot/storage/" in gitignore
    assert "var/pilot/backups/" in gitignore


def test_shell_scripts_are_checked_out_with_unix_line_endings() -> None:
    gitattributes = _read(".gitattributes")

    assert "*.sh text eol=lf" in gitattributes


def test_windows_smart_launcher_starts_docker_and_pilot_safely() -> None:
    launcher = _read("deploy/pilot/start-pilot.ps1")

    assert "spravoshnik-epb-work" in launcher
    assert "docker-compose.pilot.yml" in launcher
    assert "deploy\\pilot\\.env.pilot" in launcher or ".env.pilot" in launcher
    assert "Docker Desktop.exe" in launcher
    assert "docker info" in launcher or "& docker info" in launcher
    assert "docker compose" in launcher or "& docker compose" in launcher
    assert "up" in launcher and "-d" in launcher
    assert "/backend/health/live" in launcher
    assert "PILOT_HTTP_PORT" in launcher
    assert "Start-Process" in launcher
    assert "MessageBox" in launcher
    assert "down -v" not in launcher


def test_windows_stop_script_preserves_pilot_data() -> None:
    stopper = _read("deploy/pilot/stop-pilot.ps1")

    assert "spravoshnik-epb-work" in stopper
    assert "docker compose" in stopper or "& docker compose" in stopper
    assert "stop" in stopper
    assert "down -v" not in stopper
    assert "volume rm" not in stopper.lower()
    assert "MessageBox" in stopper


def test_windows_shortcut_creator_hides_terminal_and_targets_launcher() -> None:
    shortcuts = _read("deploy/pilot/create-desktop-shortcuts.ps1")

    assert "WScript.Shell" in shortcuts
    assert "Spravoshnik EPB.lnk" in shortcuts
    assert "Остановить Spravoshnik EPB.lnk" in shortcuts
    assert "start-pilot.ps1" in shortcuts
    assert "stop-pilot.ps1" in shortcuts
    assert "-WindowStyle Hidden" in shortcuts
    assert "-ExecutionPolicy Bypass" in shortcuts
    assert "WorkingDirectory" in shortcuts


def test_runbook_contains_required_safety_guards() -> None:
    runbook = _read("docs/PILOT_DEPLOYMENT.md")

    assert "spravoshnik-bootstrap-superuser" in runbook
    assert "down -v" in runbook
    assert "SESSION_COOKIE_SECURE" in runbook
    assert "VPN" in runbook
    assert "резерв" in runbook.lower()
    assert "восстанов" in runbook.lower()
