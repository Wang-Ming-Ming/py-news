import json
from pathlib import Path

from client.server_settings import load_env_file, load_server_settings


def test_load_env_file_supports_quotes_and_export(tmp_path: Path) -> None:
    target = tmp_path / ".env"
    target.write_text(
        "# comment\nexport STOCK_DATA_SERVER='http://example.test:8765/'\n"
        'STOCK_DATA_TOKEN="secret-token"\n',
        encoding="utf-8",
    )

    assert load_env_file(target) == {
        "STOCK_DATA_SERVER": "http://example.test:8765/",
        "STOCK_DATA_TOKEN": "secret-token",
    }


def test_project_env_precedes_legacy_json(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'STOCK_DATA_SERVER="http://project.test:8765"\nSTOCK_DATA_TOKEN="project-token"\n',
        encoding="utf-8",
    )
    user_json = tmp_path / "config.json"
    user_json.write_text(
        json.dumps({"server": "http://legacy.test:8765", "token": "legacy-token"}),
        encoding="utf-8",
    )
    monkeypatch.setenv("STOCK_DATA_ENV_FILE", str(env_file))
    monkeypatch.setenv("STOCK_DATA_CONFIG", str(user_json))
    monkeypatch.delenv("STOCK_DATA_SERVER", raising=False)
    monkeypatch.delenv("STOCK_DATA_TOKEN", raising=False)

    settings = load_server_settings()

    assert settings["server"] == "http://project.test:8765"
    assert settings["token"] == "project-token"
    assert settings["source"] == "project_env_file"


def test_process_environment_has_highest_priority(monkeypatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'STOCK_DATA_SERVER="http://project.test:8765"\nSTOCK_DATA_TOKEN="project-token"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("STOCK_DATA_ENV_FILE", str(env_file))
    monkeypatch.setenv("STOCK_DATA_SERVER", "http://process.test:9000/")
    monkeypatch.setenv("STOCK_DATA_TOKEN", "process-token")

    settings = load_server_settings()

    assert settings["server"] == "http://process.test:9000"
    assert settings["token"] == "process-token"
    assert settings["source"] == "process_environment"
