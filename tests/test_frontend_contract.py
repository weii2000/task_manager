from pathlib import Path


def test_frontend_uses_current_plan_contract() -> None:
    source = Path("frontend/app.js").read_text()
    styles = Path("frontend/styles.css").read_text()

    assert "/api/projects" not in source
    assert "project_id" not in source
    assert '"todo"' not in source
    assert "/api/plans" in source
    assert "plan_id" in source
    assert '"pending"' in source
    assert '"completed"' in source
    assert "Math.min(task.level, 3)" in source
    assert "const indentRatio = maxLevel === 1 ? 0 : (level - 1) / (maxLevel - 1)" in source
    assert "--desktop-indent:${indentRatio * 96}px" in source
    assert "--mobile-indent:${indentRatio * 48}px" in source
    assert "--indent: var(--desktop-indent, 0px)" in styles
    assert "--indent: var(--mobile-indent, 0px)" in styles
