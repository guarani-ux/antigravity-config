#!/usr/bin/env python3
"""
Clean Audio-Video (A/V) Script Exporter
Part of the `av-scriptwriting` skill pack.

Typography & Layout Standard:
- Landscape Letter page orientation
- Title: Arial 14pt Bold
- Section Headings & Table Headers: Arial 12pt Bold
- Body & Table Cells: Arial 10pt Regular
- Strictly zero timecodes/timestamps and zero WPM telemetry clutter in the output.
- Supports 3-Column (SECTION / BEAT | AUDIO | VIDEO) and 2-Column (VIDEO | AUDIO).
"""

import argparse
from html import escape
import json
from pathlib import Path
import re
import sys


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{title} - A/V Script</title>
<style>
  @page {{
    size: letter landscape;
    margin: 0.5in;
  }}
  body {{
    font-family: Arial, Helvetica, sans-serif;
    color: #111111;
    background-color: #ffffff;
    margin: 20px;
    padding: 0;
  }}
  .header {{
    border-bottom: 2px solid #222222;
    padding-bottom: 10px;
    margin-bottom: 14px;
  }}
  .doc-title {{
    font-size: 14pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.4px;
    margin: 0 0 4px 0;
  }}
  .meta-info {{
    font-size: 10pt;
    color: #444444;
  }}
  .spine-box {{
    background-color: #f8f9fa;
    border-left: 4px solid #222222;
    padding: 8px 12px;
    margin-bottom: 14px;
    font-size: 10pt;
    line-height: 1.4;
  }}
  .spine-box h2 {{
    font-size: 12pt;
    font-weight: bold;
    margin: 0 0 6px 0;
    text-transform: uppercase;
  }}
  .interview-box {{
    border: 1px solid #cccccc;
    padding: 10px 14px;
    margin-bottom: 16px;
    font-size: 10pt;
    line-height: 1.4;
    page-break-inside: avoid;
  }}
  .interview-box h2 {{
    font-size: 12pt;
    font-weight: bold;
    margin: 0 0 8px 0;
    text-transform: uppercase;
  }}
  .interview-box ul {{
    margin: 4px 0 8px 18px;
    padding: 0;
  }}
  .interview-box li {{
    margin-bottom: 6px;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  thead {{
    display: table-header-group;
  }}
  tr {{
    page-break-inside: avoid;
  }}
  th {{
    font-size: 12pt;
    font-weight: bold;
    text-align: left;
    background-color: #efefef;
    border: 1px solid #222222;
    padding: 8px 10px;
    text-transform: uppercase;
  }}
  td {{
    font-size: 10pt;
    vertical-align: top;
    border: 1px solid #333333;
    padding: 8px 10px;
    line-height: 1.45;
    word-wrap: break-word;
  }}
  .col-beat {{
    width: 20%;
    background-color: #fafafa;
  }}
  .col-audio-3 {{
    width: 40%;
  }}
  .col-video-3 {{
    width: 40%;
  }}
  .col-video-2 {{
    width: 50%;
  }}
  .col-audio-2 {{
    width: 50%;
  }}
  .shift-tag {{
    display: inline-block;
    margin-top: 6px;
    font-size: 9.5pt;
    color: #333333;
    font-style: italic;
  }}
  @media print {{
    body {{
      margin: 0;
    }}
  }}
</style>
</head>
<body>
  <div class="header">
    <div class="doc-title">{title}</div>
    <div class="meta-info">{meta_line}</div>
  </div>
  {spine_block}
  {interview_block}
  <table>
    <thead>
      <tr>
        {table_headers}
      </tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</body>
</html>
"""


def _format_cell_html(text: str) -> str:
    """Formats markdown bold/italic and newlines cleanly for HTML table cells."""
    escaped = escape(text.strip())
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\*(.+?)\*", r"<em>\1</em>", escaped)
    return escaped.replace("\n", "<br>")


def render_html(data: dict, columns: int = 3) -> str:
    title = escape(data.get("title", "UNTITLED A/V SCRIPT"))
    meta_parts = []
    for key, label in [
        ("client", "Organization"),
        ("platform", "Platform"),
        ("audience", "Audience"),
        ("mode", "Production Mode"),
    ]:
        if data.get(key):
            meta_parts.append(f"<strong>{label}:</strong> {escape(str(data[key]))}")
    meta_line = " &nbsp;|&nbsp; ".join(meta_parts)

    spine_block = ""
    if data.get("story_spine"):
        spine_block = (
            '<div class="spine-box">'
            "<h2>Story Spine &amp; Causal Premise</h2>"
            f"<div>{_format_cell_html(data['story_spine'])}</div>"
            "</div>"
        )

    interview_block = ""
    prompts = data.get("interview_guide", [])
    if prompts:
        items_html = []
        for item in prompts:
            subject = escape(item.get("subject", "Interviewee"))
            questions = item.get("questions", [])
            q_list = "".join(f"<li>{_format_cell_html(q)}</li>" for q in questions)
            items_html.append(f"<div><strong>{subject}:</strong><ul>{q_list}</ul></div>")
        interview_block = (
            '<div class="interview-box">'
            "<h2>Director's Field Interview Guide</h2>"
            + "".join(items_html)
            + "</div>"
        )

    if columns == 2:
        table_headers = (
            '<th class="col-video-2">VIDEO (FRAMING / ACTION / COVERAGE)</th>'
            '<th class="col-audio-2">AUDIO (VOICE / NAT SOUND / SFX)</th>'
        )
    else:
        table_headers = (
            '<th class="col-beat">SECTION / BEAT</th>'
            '<th class="col-audio-3">AUDIO (VOICE / NAT SOUND / SFX)</th>'
            '<th class="col-video-3">VIDEO (FRAMING / ACTION / COVERAGE)</th>'
        )

    rows_html = []
    for row in data.get("beats", []):
        beat_title = _format_cell_html(row.get("beat", ""))
        shift = row.get("value_shift", "")
        if shift:
            beat_cell = f"<strong>{beat_title}</strong><br><span class=\"shift-tag\">{_format_cell_html(shift)}</span>"
        else:
            beat_cell = f"<strong>{beat_title}</strong>"

        audio_cell = _format_cell_html(row.get("audio", ""))
        video_cell = _format_cell_html(row.get("video", ""))

        if columns == 2:
            rows_html.append(
                f"<tr><td><strong>[{beat_title}]</strong><br><br>{video_cell}</td>"
                f"<td>{audio_cell}</td></tr>"
            )
        else:
            rows_html.append(
                f"<tr><td>{beat_cell}</td><td>{audio_cell}</td><td>{video_cell}</td></tr>"
            )

    return HTML_TEMPLATE.format(
        title=title,
        meta_line=meta_line,
        spine_block=spine_block,
        interview_block=interview_block,
        table_headers=table_headers,
        table_rows="\n      ".join(rows_html),
    )


def render_markdown(data: dict, columns: int = 3) -> str:
    lines = [f"# {data.get('title', 'UNTITLED A/V SCRIPT')}", ""]
    for key, label in [
        ("client", "Organization"),
        ("platform", "Platform"),
        ("audience", "Audience"),
        ("mode", "Production Mode"),
    ]:
        if data.get(key):
            lines.append(f"- **{label}:** {data[key]}")
    if len(lines) > 2:
        lines.append("")

    if data.get("story_spine"):
        lines.extend(["## Story Spine", data["story_spine"].strip(), ""])

    prompts = data.get("interview_guide", [])
    if prompts:
        lines.append("## Director's Field Interview Guide")
        for item in prompts:
            lines.append(f"### {item.get('subject', 'Interviewee')}")
            for q in item.get("questions", []):
                lines.append(f"- {q}")
            lines.append("")

    lines.append("## A/V Script")
    if columns == 2:
        lines.append("| VIDEO (FRAMING / ACTION / COVERAGE) | AUDIO (VOICE / NAT SOUND / SFX) |")
        lines.append("| :--- | :--- |")
    else:
        lines.append("| SECTION / BEAT | AUDIO (VOICE / NAT SOUND / SFX) | VIDEO (FRAMING / ACTION / COVERAGE) |")
        lines.append("| :--- | :--- | :--- |")

    for row in data.get("beats", []):
        beat = row.get("beat", "").strip().replace("\n", "<br>")
        shift = row.get("value_shift", "").strip().replace("\n", "<br>")
        beat_col = f"**{beat}**<br>*{shift}*" if shift else f"**{beat}**"
        audio_col = row.get("audio", "").strip().replace("\n", "<br>")
        video_col = row.get("video", "").strip().replace("\n", "<br>")

        if columns == 2:
            lines.append(f"| **{beat}**<br><br>{video_col} | {audio_col} |")
        else:
            lines.append(f"| {beat_col} | {audio_col} | {video_col} |")

    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export clean A/V script (no timecodes, no WPM clutter).")
    parser.add_argument("--input", "-i", required=True, help="Path to input JSON script file.")
    parser.add_argument("--html", help="Output path for print-ready landscape HTML.")
    parser.add_argument("--md", help="Output path for Markdown script.")
    parser.add_argument("--columns", type=int, choices=[2, 3], default=3, help="2 or 3 column layout (default: 3).")
    args = parser.parse_args()

    input_path = Path(args.input)
    data = json.loads(input_path.read_text(encoding="utf-8"))

    if args.html:
        out_html = Path(args.html)
        out_html.parent.mkdir(parents=True, exist_ok=True)
        out_html.write_text(render_html(data, columns=args.columns), encoding="utf-8")
        print(f"Wrote HTML: {out_html}")

    if args.md:
        out_md = Path(args.md)
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(render_markdown(data, columns=args.columns), encoding="utf-8")
        print(f"Wrote Markdown: {out_md}")

    if not args.html and not args.md:
        sys.stdout.reconfigure(encoding="utf-8")
        print(render_markdown(data, columns=args.columns))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
