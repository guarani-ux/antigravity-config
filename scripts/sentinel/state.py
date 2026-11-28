"""Transactional, content-hashed Finite State Machine persistence for Sentinel lifecycle hooks."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterator, TypeVar

STATE_SCHEMA_VERSION = 2
STATE_FILENAME = "sentinel-state.json"
LOCK_FILENAME = "sentinel-state.lock"
STATE_PROTECTED_BASENAMES = frozenset(
    {
        STATE_FILENAME,
        LOCK_FILENAME,
        "operator-router-seen.json",
        "hook-events.jsonl",
        "reliability-events.jsonl",
    }
)

_MAX_HASH_BYTES = 8 * 1024 * 1024
_PROCESS_LOCKS_GUARD = threading.Lock()
_PROCESS_LOCKS: dict[str, threading.Lock] = {}

T = TypeVar("T")


@dataclass
class EvidenceRecord:
    state_digest: str = ""
    outcome: str = ""  # PASS | FAIL | VACUOUS | UNKNOWN
    channel: str = "absent"  # captured | absent
    runner: str = ""
    scope: str = ""  # tests | crucible_strict | gate
    discharged: bool = False
    detail: str = ""


@dataclass
class SentinelState:
    schema_version: int = STATE_SCHEMA_VERSION
    oriented: bool = False
    repair_strikes: int = 0
    consecutive_tool_errors: int = 0
    mutation_epoch: int = 0
    obligations: dict[str, str] = field(default_factory=dict)  # abs_path -> digest
    verified_files: dict[str, str] = field(default_factory=dict)  # abs_path -> verified digest
    shell_dirty: bool = False
    edited_since_last_fail: bool = False
    edited_domain_dirs: list[str] = field(default_factory=list)
    last_evidence: EvidenceRecord | None = None
    corrupt: bool = False

    @property
    def has_open_obligations(self) -> bool:
        return bool(self.obligations) or self.shell_dirty


def file_digest(abs_path: str) -> str:
    """Compute a fast, deterministic content identity for a workspace file."""
    try:
        st = os.stat(abs_path)
    except OSError:
        return "absent"
    if not os.path.isfile(abs_path):
        return "absent"
    if st.st_size > _MAX_HASH_BYTES:
        return f"stat:{st.st_size}:{st.st_mtime_ns}"
    h = hashlib.sha256()
    try:
        with open(abs_path, "rb") as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return f"sha256:{h.hexdigest()}"
    except OSError:
        return "unreadable"


def compute_state_digest(mutation_epoch: int, file_hashes: dict[str, str], shell_dirty: bool) -> str:
    """Bind verification evidence to the exact observed workspace state."""
    canonical = json.dumps(
        {"e": mutation_epoch, "f": sorted(file_hashes.items()), "s": bool(shell_dirty)},
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]


def state_path(payload: dict[str, Any]) -> Path | None:
    art_dir = payload.get("artifactDirectoryPath")
    if isinstance(art_dir, str) and art_dir.strip():
        return Path(art_dir.strip()) / STATE_FILENAME
    tpath = payload.get("transcriptPath")
    if isinstance(tpath, str) and tpath.strip():
        return Path(tpath.strip()).resolve().parent / STATE_FILENAME
    return None


def _thread_lock_for(lock_path: Path) -> threading.Lock:
    key = os.path.normcase(str(lock_path.resolve()))
    with _PROCESS_LOCKS_GUARD:
        lk = _PROCESS_LOCKS.get(key)
        if lk is None:
            lk = threading.Lock()
            _PROCESS_LOCKS[key] = lk
        return lk


@contextmanager
def _acquire_state_lock(sp: Path) -> Iterator[None]:
    """Acquire an in-process thread lock plus cross-process OS advisory lock on sidecar lockfile."""
    lp = sp.with_name(LOCK_FILENAME)
    lp.parent.mkdir(parents=True, exist_ok=True)
    tlk = _thread_lock_for(lp)
    with tlk:
        fd: int | None = None
        locked = False
        try:
            fd = os.open(str(lp), os.O_CREAT | os.O_RDWR, 0o600)
            if os.name == "nt":
                import msvcrt

                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                deadline = time.monotonic() + 2.0
                while True:
                    try:
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                        locked = True
                        break
                    except OSError:
                        if time.monotonic() >= deadline:
                            break
                        time.sleep(0.005)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX)
                locked = True
            yield
        finally:
            if fd is not None:
                if locked:
                    try:
                        if os.name == "nt":
                            import msvcrt

                            os.lseek(fd, 0, os.SEEK_SET)
                            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl

                            fcntl.flock(fd, fcntl.LOCK_UN)
                    except OSError:
                        pass
                try:
                    os.close(fd)
                except OSError:
                    pass


def _parse_evidence(raw: Any) -> EvidenceRecord | None:
    if not isinstance(raw, dict):
        return None
    return EvidenceRecord(
        state_digest=str(raw.get("state_digest") or ""),
        outcome=str(raw.get("outcome") or ""),
        channel=str(raw.get("channel") or "absent"),
        runner=str(raw.get("runner") or ""),
        scope=str(raw.get("scope") or ""),
        discharged=bool(raw.get("discharged", False)),
        detail=str(raw.get("detail") or ""),
    )


def _load_state_unlocked(sp: Path) -> SentinelState:
    if not sp.is_file():
        return SentinelState()
    try:
        raw = json.loads(sp.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return SentinelState(corrupt=True)
        # Fail closed on malformed v2 schema instead of silently resetting via v1 fallback
        if "obligations" in raw or raw.get("schema_version") == STATE_SCHEMA_VERSION:
            raw_obls = raw.get("obligations")
            if not isinstance(raw_obls, dict):
                return SentinelState(corrupt=True)
            obligations = {str(k): str(v) for k, v in raw_obls.items() if isinstance(k, str)}
            shell_dirty = bool(raw.get("shell_dirty", False))
        else:
            legacy_files = [str(x) for x in (raw.get("edited_code_files") or []) if isinstance(x, str)]
            obligations = {p: file_digest(p) for p in legacy_files}
            shell_dirty = bool(raw.get("unverified_code_edits", False)) and not obligations
        verified_raw = raw.get("verified_files")
        if verified_raw is not None and not isinstance(verified_raw, dict):
            return SentinelState(corrupt=True)
        verified_files = (
            {str(k): str(v) for k, v in verified_raw.items() if isinstance(k, str)}
            if isinstance(verified_raw, dict)
            else {}
        )
        return SentinelState(
            schema_version=STATE_SCHEMA_VERSION,
            oriented=bool(raw.get("oriented", False)),
            repair_strikes=int(raw.get("repair_strikes", 0)),
            consecutive_tool_errors=int(raw.get("consecutive_tool_errors", 0)),
            mutation_epoch=int(raw.get("mutation_epoch", 0)),
            obligations=obligations,
            verified_files=verified_files,
            shell_dirty=shell_dirty,
            edited_since_last_fail=bool(raw.get("edited_since_last_fail", False)),
            edited_domain_dirs=[str(x) for x in (raw.get("edited_domain_dirs") or []) if isinstance(x, str)],
            last_evidence=_parse_evidence(raw.get("last_evidence")),
            corrupt=bool(raw.get("corrupt", False)),
        )
    except (OSError, ValueError, TypeError) as exc:
        print(f"sentinel state load error: {type(exc).__name__}", file=sys.stderr)
        return SentinelState(corrupt=True)


def load_state(payload: dict[str, Any]) -> SentinelState:
    sp = state_path(payload)
    if sp is None or not sp.is_file():
        return SentinelState()
    with _acquire_state_lock(sp):
        return _load_state_unlocked(sp)


def _save_state_unlocked(sp: Path, state: SentinelState) -> None:
    tmp = sp.with_name(f".{sp.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        sp.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(asdict(state), ensure_ascii=False) + "\n", encoding="utf-8")
        for attempt in range(5):
            try:
                os.replace(tmp, sp)
                return
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.01 * (attempt + 1))
    except OSError as exc:
        print(f"sentinel state save error: {type(exc).__name__}", file=sys.stderr)
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def save_state(payload: dict[str, Any], state: SentinelState) -> None:
    sp = state_path(payload)
    if sp is None:
        return
    with _acquire_state_lock(sp):
        _save_state_unlocked(sp, state)


def update_state(payload: dict[str, Any], mutator: Callable[[SentinelState], T]) -> T | None:
    """Atomically load, mutate, and persist SentinelState under a cross-process/thread lock."""
    sp = state_path(payload)
    if sp is None:
        return None
    with _acquire_state_lock(sp):
        st = _load_state_unlocked(sp)
        res = mutator(st)
        _save_state_unlocked(sp, st)
        return res
