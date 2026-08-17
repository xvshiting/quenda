"""Workspace-scoped Web attachment publishing."""

from pathlib import Path

from quenda.web.tools import PublishAttachmentTool


def test_publish_attachment_copies_workspace_file(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = workspace / "chart.png"
    source.write_bytes(b"png-data")
    tool = PublishAttachmentTool(workspace, tmp_path / "session" / "attachments")

    result = tool.execute(path="chart.png", name="result.png")

    assert not result.is_error
    assert result.result_summary.startswith("published_attachment:")
    assert len(tool.published) == 1
    assert tool.published[0].name == "result.png"
    assert Path(tool.published[0].path).read_bytes() == b"png-data"
    assert tool.published[0].media_type == "image/png"


def test_publish_attachment_rejects_path_outside_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("secret")
    tool = PublishAttachmentTool(workspace, tmp_path / "attachments")

    result = tool.execute(path=str(outside))

    assert result.is_error
    assert "inside the current workspace" in result.content
    assert tool.published == []
