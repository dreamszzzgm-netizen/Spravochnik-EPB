from pathlib import Path

from app.web.routes.health import check_storage


def test_storage_health_probe(tmp_path: Path) -> None:
    assert check_storage(tmp_path)
    assert not (tmp_path / ".health-probe").exists()
