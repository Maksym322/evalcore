"""Reporters: render a RunReport to JSON / Markdown / other sinks."""

from evalcore.reporters.json_reporter import render_json
from evalcore.reporters.markdown_reporter import render_markdown

__all__ = ["render_json", "render_markdown"]
