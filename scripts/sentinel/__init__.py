"""Sentinel: modular Antigravity lifecycle and safety engine."""

from .ast_gate import detect_secret_leak
from .lifecycle import post, pre, stop
from .policy import is_meaningful_verification_command, is_subagent
from .telemetry import extract_rule_tag, record_hook_event, summarize_telemetry

__all__ = [
    "pre",
    "post",
    "stop",
    "is_meaningful_verification_command",
    "is_subagent",
    "detect_secret_leak",
    "extract_rule_tag",
    "record_hook_event",
    "summarize_telemetry",
]
