"""The Hugging Face Space mirror: its card and which files a publish changes."""

import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("hf_space", ROOT / "scripts" / "hf_space.py")
hf_space = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(hf_space)


def test_card_configures_a_static_space():
    text = hf_space.card("0123456789abcdef")
    _, front, body = text.split("---\n", 2)
    meta = yaml.safe_load(front)
    assert (meta["sdk"], meta["app_file"], meta["license"]) == (
        "static",
        "index.html",
        "apache-2.0",
    )
    colours = {"red", "yellow", "green", "blue", "indigo", "purple", "pink", "gray"}
    assert {meta["colorFrom"], meta["colorTo"]} <= colours
    assert len(meta["short_description"]) <= 60
    assert "commit 0123456" in body and "replay a recorded run" in body


def test_a_publish_deletes_only_what_the_build_dropped(tmp_path):
    (tmp_path / "fonts").mkdir()
    for name in ("index.html", "README.md", "fonts/archivo.woff2"):
        (tmp_path / name).write_text("x")
    remote = [".gitattributes", "index.html", "old.html", "fonts/old.woff2"]
    upload, delete = hf_space.changes(tmp_path, remote)
    assert upload == ["README.md", "fonts/archivo.woff2", "index.html"]
    assert delete == ["fonts/old.woff2", "old.html"], "the Space's .gitattributes stays"


def test_publish_refuses_to_run_without_a_token_or_a_build(tmp_path, monkeypatch, capsys):
    import pytest

    monkeypatch.delenv("HF_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        hf_space.main([str(tmp_path)])
    assert "HF_TOKEN" in capsys.readouterr().err
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    with pytest.raises(SystemExit):
        hf_space.main([str(tmp_path)])
    assert "no index.html" in capsys.readouterr().err
