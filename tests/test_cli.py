from clarchy.cli import main


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


def test_icons_for_gcp_and_open_source_come_bundled(capsys, monkeypatch):
    monkeypatch.delenv("CLARCHY_ICONS_GCP", raising=False)
    assert main(["icons", "--provider", "gcp"]) == 0
    out = capsys.readouterr().out
    assert "cloudrun-512-color-rgb.svg" in out and "litellm.png (open-source logos)" in out
    assert main(["icons", "--provider", "oss"]) == 0


def test_icons_for_aws_come_bundled(capsys, monkeypatch):
    monkeypatch.delenv("CLARCHY_ICONS_AWS", raising=False)
    assert main(["icons", "--provider", "aws"]) == 0
    out, err = capsys.readouterr()
    assert "Arch_AWS-Lambda_64.svg" in out and "NOT FOUND" not in out
    assert "38/38 icons found" in err
    assert main(["icons", "--provider", "azure"]) == 0
    assert "10029-icon-service-Function-Apps.svg" in capsys.readouterr().out


def test_plan_from_long_text_writes_spec_diagrams_and_explanations(tmp_path, capsys):
    text = (
        "A booking app for 40 clinics in the UK where patients sign in, book appointments "
        "and pay a deposit by card. The backend is already packaged in Docker. Reminders "
        "go out by SMS the day before. About 120,000 patients and 99.95% uptime. " * 2
    )
    assert len(text) > 255  # longer than any file name
    assert main(["plan", text, "--rules", "-o", str(tmp_path)]) == 0
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == sorted(
        [
            "spec.yaml",
            *(f"{p}.{ext}" for p in ("aws", "azure", "gcp", "oss") for ext in ("svg", "md")),
        ]
    )
    assert "Amazon ECR" in (tmp_path / "aws.md").read_text()
    err = capsys.readouterr().err
    assert "✔ Map to every cloud" in err and "rule-based planner" in err


def test_plan_from_a_file_with_region_override(tmp_path):
    brief = tmp_path / "brief.md"
    brief.write_text("# Photo app\n\nUsers upload photos; spiky traffic.\n")
    out = tmp_path / "out"
    assert main(["plan", str(brief), "--rules", "--region", "singapore", "-o", str(out)]) == 0
    assert "region: singapore" in (out / "spec.yaml").read_text()


def test_plan_reports_unreadable_input(tmp_path, capsys):
    bad = tmp_path / "brief.docx"
    bad.write_bytes(b"not a zip")
    assert main(["plan", str(bad), "--rules"]) == 2
    assert "not a valid Office document" in capsys.readouterr().err
