"""CheckResult 리스트 -> 사람이 보기 좋은 standalone HTML 리포트.

외부 서버/프레임워크/CDN 없음. CSS는 <style> 태그로 파일 안에 인라인 포함.
기존 검사 로직(checks.py/subtitles.py)에는 의존만 하고 손대지 않는다 — report 레이어 전용.
"""

import html
from datetime import datetime
from pathlib import Path

from .checks import Status

_STATUS_FG = {
    Status.PASS: "#1b5e20",
    Status.WARN: "#8a6100",
    Status.FAIL: "#b3261e",
    Status.SKIP: "#5f6368",
}
_STATUS_BG = {
    Status.PASS: "#e6f4ea",
    Status.WARN: "#fff4d6",
    Status.FAIL: "#fce8e6",
    Status.SKIP: "#eeeeee",
}

_STATUS_ORDER = (Status.PASS, Status.WARN, Status.FAIL, Status.SKIP)

_CSS = """
  :root { color-scheme: light; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 32px 24px 64px;
    background: #f7f7f8; color: #1a1a1a;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Pretendard, Roboto, sans-serif;
    line-height: 1.5;
  }
  .wrap { max-width: 860px; margin: 0 auto; }
  header.header {
    background: #fff; border: 1px solid #e2e2e5; border-radius: 12px;
    padding: 20px 24px; margin-bottom: 20px;
  }
  header.header h1 { margin: 0 0 12px; font-size: 20px; }
  .meta { display: flex; flex-wrap: wrap; gap: 20px; font-size: 14px; }
  .meta .label { display: block; color: #6b6b70; font-size: 12px; margin-bottom: 2px; }
  .badge {
    display: inline-block; padding: 2px 10px; border-radius: 999px;
    font-size: 12px; font-weight: 600; letter-spacing: .02em;
  }
  section { margin-bottom: 24px; }
  section h2 { font-size: 15px; margin: 0 0 10px; color: #3c3c40; }
  .summary { display: flex; gap: 12px; flex-wrap: wrap; }
  .card {
    flex: 1 1 100px; background: #fff; border: 1px solid; border-radius: 10px;
    padding: 14px 16px; text-align: center;
  }
  .card-count { font-size: 26px; font-weight: 700; line-height: 1.1; }
  .card-label { font-size: 12px; color: #6b6b70; margin-top: 4px; }
  table.checks-table {
    width: 100%; border-collapse: collapse; background: #fff;
    border: 1px solid #e2e2e5; border-radius: 10px; overflow: hidden;
  }
  table.checks-table th, table.checks-table td {
    text-align: left; padding: 10px 12px; font-size: 14px;
    border-bottom: 1px solid #eee; vertical-align: top;
  }
  table.checks-table th { background: #fafafa; font-size: 12px; color: #6b6b70; }
  table.checks-table tr:last-child td { border-bottom: none; }
  .detail-section {
    background: #fff; border: 1px solid #e2e2e5; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 12px;
  }
  .detail-section h3 { margin: 0 0 6px; font-size: 14px; display: flex; align-items: center; gap: 8px; }
  .detail-section .message { margin: 0 0 10px; font-size: 13px; color: #444; }
  .detail-nested { padding-left: 2px; }
  .detail-row {
    display: flex; gap: 10px; padding: 3px 0; font-size: 13px;
    border-top: 1px dashed #eee;
  }
  .detail-row:first-child { border-top: none; }
  .detail-key { color: #6b6b70; min-width: 160px; flex-shrink: 0; }
  .detail-value { color: #1a1a1a; word-break: break-word; }
  table.detail-table { border-collapse: collapse; margin: 4px 0; font-size: 12px; }
  table.detail-table th, table.detail-table td { border: 1px solid #eee; padding: 4px 8px; text-align: left; }
  table.detail-table th { background: #fafafa; }
  .muted { color: #9a9a9e; }
"""


def _esc(value) -> str:
    return html.escape(str(value))


def _humanize_key(key: str) -> str:
    return key.replace("_", " ").strip().title()


_MUTED_DASH = '<span class="muted">—</span>'


def _plain_scalar(value) -> str:
    """이스케이프하지 않은 텍스트 표현. 호출부에서 필요할 때 한 번에 escape한다."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        if value != value:  # NaN (이론상 여기까지 안 와야 하지만 방어적으로 처리)
            return "—"
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def _format_scalar(value) -> str:
    if value is None:
        return _MUTED_DASH
    text = _plain_scalar(value)
    return text if text == "—" else _esc(text)


def _render_value(value) -> str:
    if isinstance(value, dict):
        if not value:
            return _MUTED_DASH
        rows = "".join(
            f'<div class="detail-row"><span class="detail-key">{_esc(_humanize_key(k))}</span>'
            f'<span class="detail-value">{_render_value(v)}</span></div>'
            for k, v in value.items()
        )
        return f'<div class="detail-nested">{rows}</div>'
    if isinstance(value, list):
        if not value:
            return _MUTED_DASH
        if all(isinstance(v, dict) for v in value):
            return _render_dict_list_table(value)
        return _esc(", ".join(_plain_scalar(v) for v in value))
    return _format_scalar(value)


def _render_dict_list_table(items: list) -> str:
    columns = []
    for item in items:
        for k in item.keys():
            if k not in columns:
                columns.append(k)
    header = "".join(f"<th>{_esc(_humanize_key(c))}</th>" for c in columns)
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{_render_value(item.get(c))}</td>" for c in columns) + "</tr>" for item in items
    )
    return f'<table class="detail-table"><thead><tr>{header}</tr></thead><tbody>{body_rows}</tbody></table>'


def _render_summary_card(status: Status, count: int) -> str:
    return (
        f'<div class="card" style="border-color:{_STATUS_FG[status]}">'
        f'<div class="card-count" style="color:{_STATUS_FG[status]}">{count}</div>'
        f'<div class="card-label">{status.value}</div>'
        f"</div>"
    )


def _badge(status: Status) -> str:
    return f'<span class="badge" style="background:{_STATUS_BG[status]};color:{_STATUS_FG[status]}">{status.value}</span>'


def _render_check_row(result) -> str:
    return (
        f"<tr><td>{_esc(result.name)}</td><td>{_badge(result.status)}</td>"
        f"<td>{_esc(result.message)}</td></tr>"
    )


def _render_check_detail_section(result) -> str:
    details_html = _render_value(result.details) if result.details else '<p class="muted">No additional details.</p>'
    return (
        f'<div class="detail-section">'
        f"<h3>{_badge(result.status)} {_esc(result.name)}</h3>"
        f'<p class="message">{_esc(result.message)}</p>'
        f"{details_html}"
        f"</div>"
    )


def generate_html_report(video_path: str, results: list, overall: Status, generated_at: datetime = None) -> str:
    generated_at = generated_at or datetime.now().astimezone()
    counts = {s: 0 for s in _STATUS_ORDER}
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1

    summary_html = "".join(_render_summary_card(s, counts[s]) for s in _STATUS_ORDER)
    rows_html = "".join(_render_check_row(r) for r in results)
    details_html = "".join(_render_check_detail_section(r) for r in results)
    file_name = Path(video_path).name

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>video-lint report — {_esc(file_name)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <header class="header">
    <h1>video-lint</h1>
    <div class="meta">
      <div><span class="label">File</span><span>{_esc(video_path)}</span></div>
      <div><span class="label">Generated</span><span>{_esc(generated_at.strftime("%Y-%m-%d %H:%M:%S %Z"))}</span></div>
      <div><span class="label">Overall Status</span>{_badge(overall)}</div>
    </div>
  </header>

  <section class="summary">
    {summary_html}
  </section>

  <section class="checks">
    <h2>Checks</h2>
    <table class="checks-table">
      <thead><tr><th>Check</th><th>Status</th><th>Message</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
  </section>

  <section class="details">
    <h2>Details</h2>
    {details_html}
  </section>
</div>
</body>
</html>
"""


def write_html_report(video_path: str, results: list, overall: Status, output_path: str) -> Path:
    path = Path(output_path)
    path.write_text(generate_html_report(video_path, results, overall), encoding="utf-8")
    return path
