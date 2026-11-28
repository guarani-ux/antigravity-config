#!/usr/bin/env python3
"""Self-diagnostic Machine Doctor CLI for antigravity-config.

Checks constitution parity, hook/MCP manifest integrity across Windows/Unix,
Python interpreter & module imports, skill frontmatter & broken local links,
and local hook flight-recorder telemetry.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import re
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from sentinel.telemetry import summarize_telemetry

REQUIRED_HOOKS = (
    ("sentinel", "PreToolUse", True),
    ("sentinel", "PostToolUse", True),
    ("sentinel", "Stop", False),
    ("operator-router", "SessionStart", False),
    ("operator-router", "PreInvocation", False),
)

SCRIPT_PATH_RE = re.compile(r"scripts[/\\]([A-Za-z0-9_.\-/\\]+\.py)")
FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
BACKTICK_REF_RE = re.compile(r"`((?:scripts|references|examples|assets)/[A-Za-z0-9_.\-/]+)(?:\s+[^`]*)?`")
MD_LINK_REF_RE = re.compile(r"\[[^\]]+\]\(((?:scripts|references|examples|assets)/[A-Za-z0-9_.\-/]+)\)")
MAX_SKILL_LINES_WARN = 120


def _first_cmd_token(cmd: str) -> str:
    try:
        parts = shlex.split(cmd, posix=False)
        if parts:
            return parts[0].strip("\"'")
    except ValueError:
        pass
    return cmd.strip().split()[0].strip("\"'") if cmd.strip() else ""


def _check_hooks_manifest(
    path: Path,
    config_dir: Path,
    errors: list[str],
    warnings: list[str],
    *,
    check_installed_cmds: bool,
) -> None:
    if not path.is_file():
        errors.append(f"Missing hook manifest: {path.name}")
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return
    if not isinstance(data, dict):
        errors.append(f"Hook manifest {path.name} must be a JSON object")
        return

    for group, event, needs_matcher in REQUIRED_HOOKS:
        g_obj = data.get(group)
        if not isinstance(g_obj, dict) or not g_obj.get("enabled"):
            errors.append(f"{path.name}: missing or disabled hook group '{group}'")
            continue
        entries = g_obj.get(event)
        if not isinstance(entries, list) or not entries:
            errors.append(f"{path.name}: missing required hook event '{group}.{event}'")
            continue

        for e_idx, entry in enumerate(entries):
            if not isinstance(entry, dict):
                errors.append(f"{path.name}: malformed entry #{e_idx} in '{group}.{event}'")
                continue
            if needs_matcher and not entry.get("matcher"):
                errors.append(f"{path.name}: '{group}.{event}[{e_idx}]' missing matcher")
            if not needs_matcher and "matcher" in entry:
                errors.append(f"{path.name}: '{group}.{event}[{e_idx}]' must not contain a 'matcher' key")
            hooks_list = entry.get("hooks")
            if not isinstance(hooks_list, list) or not hooks_list:
                errors.append(f"{path.name}: '{group}.{event}[{e_idx}]' missing hooks[] commands")
                continue

            for h_idx, hook_item in enumerate(hooks_list):
                if not isinstance(hook_item, dict):
                    errors.append(f"{path.name}: '{group}.{event}[{e_idx}].hooks[{h_idx}]' must be an object")
                    continue
                cmd = str(hook_item.get("command") or "").strip()
                if not cmd:
                    errors.append(f"{path.name}: '{group}.{event}[{e_idx}].hooks[{h_idx}]' has empty command")
                    continue
                if check_installed_cmds:
                    if "__PYTHON__" in cmd or "__CONFIG_DIR__" in cmd:
                        errors.append(f"{path.name}: unresolved placeholder in '{group}.{event}[{e_idx}]'")
                    exe = _first_cmd_token(cmd)
                    if exe and not Path(exe).is_file() and not shutil.which(exe):
                        errors.append(f"{path.name}: hook interpreter not found on PATH: '{exe}'")
                m_script = SCRIPT_PATH_RE.search(cmd)
                if not m_script:
                    errors.append(f"{path.name}: '{group}.{event}[{e_idx}]' command does not reference a scripts/*.py file")
                    continue
                rel_script = m_script.group(1).replace("\\", "/")
                script_path = config_dir / "scripts" / rel_script
                if not script_path.is_file():
                    errors.append(f"{path.name}: referenced hook script not found: scripts/{rel_script}")


def _check_mcp_manifest(path: Path, errors: list[str], *, required: bool, check_placeholders: bool) -> None:
    if not path.is_file():
        if required:
            errors.append(f"Missing {path.name}")
        return
    try:
        raw = path.read_text(encoding="utf-8")
        obj = json.loads(raw)
    except (OSError, ValueError) as exc:
        errors.append(f"Invalid JSON in {path.name}: {exc}")
        return
    if not isinstance(obj, dict) or not isinstance(obj.get("mcpServers"), dict):
        errors.append(f"{path.name}: missing 'mcpServers' object")
    if check_placeholders and ("__PYTHON__" in raw or "__CONFIG_DIR__" in raw):
        errors.append(f"{path.name}: unresolved template placeholder")


def _check_skills(config_dir: Path, errors: list[str], warnings: list[str]) -> list[dict[str, Any]]:
    skills_dir = config_dir / "skills"
    results: list[dict[str, Any]] = []
    if not skills_dir.is_dir():
        errors.append("Missing skills/ directory")
        return results

    for entry in sorted(skills_dir.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        skill_md = entry / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"skills/{entry.name}: directory missing SKILL.md")
            continue

        text = skill_md.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        line_count = len(lines)
        name = entry.name

        fm_end = -1
        if len(lines) >= 3 and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    fm_end = i
                    break

        if fm_end < 0:
            errors.append(f"skills/{name}/SKILL.md: missing YAML frontmatter")
        else:
            fm_fields: dict[str, str] = {}
            for ln in lines[1:fm_end]:
                if ":" in ln and not ln.startswith((" ", "\t")):
                    k, v = ln.split(":", 1)
                    fm_fields[k.strip()] = v.strip().strip("\"'")
            if "name" not in fm_fields or not fm_fields["name"]:
                errors.append(f"skills/{name}/SKILL.md: frontmatter missing 'name'")
            elif fm_fields["name"] != name:
                errors.append(f"skills/{name}/SKILL.md: frontmatter name '{fm_fields['name']}' != directory '{name}'")
            if "description" not in fm_fields or not fm_fields["description"]:
                errors.append(f"skills/{name}/SKILL.md: frontmatter missing 'description'")

        if line_count > MAX_SKILL_LINES_WARN:
            warnings.append(f"skills/{name}/SKILL.md: {line_count} lines (exceeds {MAX_SKILL_LINES_WARN}-line lean budget)")

        prose = FENCED_CODE_RE.sub("", text)
        refs = {m.group(1) for m in BACKTICK_REF_RE.finditer(prose)} | {m.group(1) for m in MD_LINK_REF_RE.finditer(prose)}
        for rel in sorted(refs):
            if not (entry / rel).exists() and not (config_dir / rel).exists():
                errors.append(f"skills/{name}/SKILL.md: broken local reference `{rel}`")

        results.append({"name": name, "lines": line_count})
    return results


def _check_python_scripts_and_imports(config_dir: Path, errors: list[str]) -> int:
    scripts_root = config_dir / "scripts"
    if not scripts_root.is_dir():
        errors.append("Missing scripts/ directory")
        return 0
    count = 0
    for py_file in sorted(scripts_root.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue
        count += 1
        try:
            ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except (SyntaxError, OSError, UnicodeError) as exc:
            errors.append(f"Python syntax error in {py_file.relative_to(config_dir)}: {exc}")
    if count == 0:
        errors.append("No Python scripts found under scripts/")
        return 0

    # Smoke-check core hook imports resolve cleanly
    for mod_name, rel_file in (("sentinel", "sentinel/__init__.py"), ("operator_router", "operator_router.py")):
        mod_path = scripts_root / rel_file
        if not mod_path.is_file():
            errors.append(f"Core hook module missing: scripts/{rel_file}")
            continue
        probe_name = f"_doctor_probe_{mod_name}"
        spec = importlib.util.spec_from_file_location(probe_name, mod_path)
        if spec is None or spec.loader is None:
            errors.append(f"Cannot load spec for scripts/{rel_file}")
            continue
        try:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[probe_name] = mod
            spec.loader.exec_module(mod)
        except Exception as exc:
            errors.append(f"Core hook import failed for scripts/{rel_file}: {type(exc).__name__}: {exc}")
        finally:
            for k in [k for k in sys.modules if k == probe_name or k.startswith(probe_name + ".")]:
                sys.modules.pop(k, None)
    return count


def _check_script_reachability(config_dir: Path, errors: list[str]) -> list[str]:
    """Verify every non-test Python script under scripts/ is reachable from hooks, CI, bootstrap, or imports."""
    scripts_root = config_dir / "scripts"
    if not scripts_root.is_dir():
        return []

    all_scripts: dict[str, Path] = {}
    for py_file in sorted(scripts_root.rglob("*.py")):
        rel_parts = py_file.relative_to(scripts_root).parts
        if "__pycache__" in rel_parts or (rel_parts and rel_parts[0] == "tests"):
            continue
        all_scripts[py_file.relative_to(scripts_root).as_posix()] = py_file

    seeds: set[str] = set()
    for cli_seed in ("doctor.py", "eval_harness.py"):
        if cli_seed in all_scripts:
            seeds.add(cli_seed)
    for manifest in (
        config_dir / "hooks.json.portable",
        config_dir / ".github" / "workflows" / "ci.yml",
        config_dir / "bootstrap.sh",
        config_dir / "bootstrap.ps1",
    ):
        if not manifest.is_file():
            continue
        raw = manifest.read_text(encoding="utf-8", errors="replace")
        if manifest.suffix != ".json":
            raw = "\n".join(ln for ln in raw.splitlines() if not ln.lstrip().startswith("#"))
        for m in SCRIPT_PATH_RE.finditer(raw):
            rel = m.group(1).replace("\\", "/")
            if rel in all_scripts:
                seeds.add(rel)

    def _resolve_import(curr_rel: str, module: str | None, level: int, names: list[str]) -> set[str]:
        found: set[str] = set()
        curr_dir = Path(curr_rel).parent
        base_parts = list(curr_dir.parts) if level > 0 else []
        if level > 1:
            base_parts = base_parts[: max(0, len(base_parts) - (level - 1))]
        mod_parts = [p for p in (module or "").split(".") if p]
        candidates: list[list[str]] = []
        if mod_parts:
            candidates.append(base_parts + mod_parts)
        for nm in names:
            if nm != "*":
                candidates.append(base_parts + mod_parts + [nm])
        for parts in candidates:
            if not parts:
                continue
            as_file = "/".join(parts) + ".py"
            as_pkg = "/".join(parts) + "/__init__.py"
            if as_file in all_scripts:
                found.add(as_file)
            if as_pkg in all_scripts:
                found.add(as_pkg)
        return found

    visited: set[str] = set()
    queue = sorted(seeds)
    while queue:
        rel = queue.pop(0)
        if rel in visited or rel not in all_scripts:
            continue
        visited.add(rel)
        try:
            tree = ast.parse(all_scripts[rel].read_text(encoding="utf-8"), filename=rel)
        except (SyntaxError, OSError, UnicodeError):
            continue
        for node in ast.walk(tree):
            targets: set[str] = set()
            if isinstance(node, ast.Import):
                for alias in node.names:
                    targets |= _resolve_import(rel, alias.name, 0, [])
            elif isinstance(node, ast.ImportFrom):
                targets |= _resolve_import(rel, node.module, node.level, [a.name for a in node.names])
            for t in sorted(targets):
                if t not in visited:
                    queue.append(t)

    dead = sorted(set(all_scripts) - visited)
    for rel in dead:
        errors.append(f"Unreachable script (not wired to hooks, CI, bootstrap, or imports): scripts/{rel}")
    return dead


def _resolve_gemini_dir(config_dir: Path, gemini_dir: Path | None) -> Path:
    if gemini_dir is not None:
        return gemini_dir.expanduser().resolve()
    if (config_dir.parent / "GEMINI.md").is_file() or config_dir.parent.name == ".gemini":
        return config_dir.parent
    return (Path.home() / ".gemini").resolve()


def run_doctor(
    config_dir: Path,
    *,
    check_installed: bool = False,
    gemini_dir: Path | None = None,
    telemetry_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if sys.version_info < (3, 10):
        errors.append(f"Python 3.10+ required (found {sys.version.split()[0]})")
    if not shutil.which("git"):
        warnings.append("git not found on PATH")

    # 1. Hook & MCP manifests
    _check_hooks_manifest(config_dir / "hooks.json.portable", config_dir, errors, warnings, check_installed_cmds=False)
    gen_hooks = config_dir / "hooks.json"
    if gen_hooks.is_file():
        _check_hooks_manifest(gen_hooks, config_dir, errors, warnings, check_installed_cmds=True)
    elif check_installed:
        errors.append("Generated hooks.json missing; run bootstrap.sh or bootstrap.ps1")

    _check_mcp_manifest(config_dir / "mcp_config.portable.json", errors, required=True, check_placeholders=False)
    _check_mcp_manifest(config_dir / "mcp_config.json", errors, required=check_installed, check_placeholders=True)

    pol_path = config_dir / "policy.json"
    if pol_path.is_file():
        try:
            pol_obj = json.loads(pol_path.read_text(encoding="utf-8"))
            if not isinstance(pol_obj, dict):
                errors.append("policy.json: must be a JSON object")
            else:
                hygiene = pol_obj.get("deliverable_hygiene")
                if hygiene is not None and not isinstance(hygiene, list):
                    errors.append("policy.json: deliverable_hygiene must be a list")
                for p_idx, prof in enumerate(hygiene if isinstance(hygiene, list) else []):
                    if not isinstance(prof, dict):
                        errors.append(f"policy.json: deliverable_hygiene[{p_idx}] must be an object")
                        continue
                    cp = prof.get("context_pattern")
                    if cp:
                        try:
                            re.compile(str(cp))
                        except re.error as exc:
                            errors.append(f"policy.json: invalid context_pattern in deliverable_hygiene[{p_idx}]: {exc}")
                    rules = prof.get("rules")
                    if rules is not None and not isinstance(rules, list):
                        errors.append(f"policy.json: deliverable_hygiene[{p_idx}].rules must be a list")
                    for r_idx, rule in enumerate(rules if isinstance(rules, list) else []):
                        if isinstance(rule, dict) and rule.get("pattern"):
                            try:
                                re.compile(str(rule["pattern"]))
                            except re.error as exc:
                                errors.append(f"policy.json: invalid regex in deliverable_hygiene[{p_idx}].rules[{r_idx}]: {exc}")
        except (OSError, ValueError) as exc:
            errors.append(f"Invalid JSON in policy.json: {exc}")

    # 2. Constitution parity
    global_src = config_dir / "GEMINI.global.md"
    if not global_src.is_file():
        errors.append("Missing GEMINI.global.md")
    elif check_installed:
        target_gemini_dir = _resolve_gemini_dir(config_dir, gemini_dir)
        installed_gemini = target_gemini_dir / "GEMINI.md"
        if not installed_gemini.is_file():
            errors.append(f"Installed GEMINI.md missing at {installed_gemini}")
        elif installed_gemini.read_text(encoding="utf-8") != global_src.read_text(encoding="utf-8"):
            warnings.append("Installed GEMINI.md drifted from GEMINI.global.md; re-run bootstrap --force")

    # 3. Python scripts syntax, core hook presence & reachability
    py_count = _check_python_scripts_and_imports(config_dir, errors)
    dead_scripts = _check_script_reachability(config_dir, errors)

    # 4. Skills hygiene & broken local references
    skills = _check_skills(config_dir, errors, warnings)

    # 5. Telemetry summary
    telemetry = summarize_telemetry(telemetry_path)

    return {
        "ok": len(errors) == 0,
        "config_dir": str(config_dir),
        "python_version": sys.version.split()[0],
        "python_files_checked": py_count,
        "unreachable_scripts": dead_scripts,
        "skills": skills,
        "telemetry": telemetry,
        "errors": errors,
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Antigravity Config Machine Doctor")
    p.add_argument("--config-dir", type=Path, default=SCRIPTS_DIR.parent)
    p.add_argument("--gemini-dir", type=Path, default=None, help="Override ~/.gemini directory for installed GEMINI.md check")
    p.add_argument("--check-installed", action="store_true", help="Also verify installed GEMINI.md, hooks.json, and mcp_config.json")
    p.add_argument("--strict", action="store_true", help="Treat warnings as failures (exit 1)")
    p.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON output")
    args = p.parse_args(argv)

    report = run_doctor(
        args.config_dir.expanduser().resolve(),
        check_installed=args.check_installed,
        gemini_dir=args.gemini_dir,
    )
    passed = report["ok"] and (not args.strict or not report["warnings"])

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        status = "HEALTHY" if passed else "UNHEALTHY"
        print(f"Machine Doctor: {status} (Python {report['python_version']}, {report['python_files_checked']} scripts, {len(report['skills'])} skills)")
        for s in report["skills"]:
            print(f"  - skill: {s['name']} ({s['lines']} lines)")
        tel = report["telemetry"]
        if tel["exists"]:
            print(f"  - telemetry: {tel['events']} events, p50={tel['p50_ms']}ms, p95={tel['p95_ms']}ms, top_blocks={tel['top_blocks']}")
        else:
            print("  - telemetry: no events recorded yet")
        for w in report["warnings"]:
            print(f"  WARN: {w}")
        for e in report["errors"]:
            print(f"  ERROR: {e}")

    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
