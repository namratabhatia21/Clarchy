from cloudarchie.cli import main


def test_patterns_lists_builtins(capsys):
    assert main(["patterns"]) == 0
    out = capsys.readouterr().out
    assert "serverless-web-app" in out and "rag-chatbot" in out


def test_validate_pattern(capsys):
    assert main(["validate", "container-api"]) == 0
    assert capsys.readouterr().out.startswith("ok: Containerised API")


def test_render_and_explain_to_files(tmp_path):
    svg, md = tmp_path / "d.svg", tmp_path / "d.md"
    assert main(["render", "data-pipeline", "-o", str(svg)]) == 0
    assert main(["explain", "data-pipeline", "-o", str(md)]) == 0
    assert svg.read_text().startswith("<svg")
    assert "Amazon Kinesis Data Streams" in md.read_text()


def test_render_spec_file(tmp_path, capsys):
    spec = tmp_path / "mine.yaml"
    spec.write_text(
        "name: Mine\n"
        "components:\n"
        "  - {id: users, capability: client}\n"
        "  - {id: web, capability: container-service}\n"
        "edges:\n"
        "  - {from: users, to: web}\n"
    )
    assert main(["render", str(spec)]) == 0
    assert 'data-capability="container-service"' in capsys.readouterr().out


def test_invalid_spec_reports_error(tmp_path, capsys):
    spec = tmp_path / "bad.yaml"
    spec.write_text("name: Bad\ncomponents:\n  - {id: x, capability: teleporter}\n")
    assert main(["validate", str(spec)]) == 2
    assert "unknown capability" in capsys.readouterr().err


def test_icons_without_directory(capsys, monkeypatch):
    monkeypatch.delenv("CLOUDARCHIE_ICONS_AWS", raising=False)
    assert main(["icons", "--provider", "aws"]) == 1
    assert "CLOUDARCHIE_ICONS_AWS" in capsys.readouterr().err
