"""Atomic JSON files, OS-owned cross-process locks, and explicit data locations."""

import copy
import hashlib
import json
import os
import tempfile
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .errors import MakeSoundError, require


def canonical_json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "invalid_json", "Duplicate JSON keys are not permitted.")
        result[key] = value
    return result


def read_json(path):
    try:
        require(path.stat().st_size <= 8 * 1024 * 1024, "file_too_large", "JSON input exceeds 8 MiB.")
        return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except MakeSoundError:
        raise
    except FileNotFoundError:
        raise MakeSoundError("not_found", "Requested local data does not exist.") from None
    except (ValueError, UnicodeError):
        raise MakeSoundError("invalid_json", "Input is not valid UTF-8 JSON.") from None
    except OSError:
        raise MakeSoundError("io_error", "Local data could not be read.") from None


def reject_links(path):
    for part in (path, *path.parents):
        is_junction = getattr(part, "is_junction", lambda: False)
        require(not part.is_symlink() and not is_junction(), "unsafe_path", "Symlinks and junctions are not allowed for managed data.")


def project_root(value):
    require(value is not None, "project_required", "An explicit trusted project root is required.")
    path = Path(value)
    require(path.is_absolute(), "unsafe_project", "Project root must be absolute.")
    reject_links(path)
    path = path.resolve()
    require(path.is_dir() and path != Path(path.anchor) and path != Path.home().resolve(),
            "unsafe_project", "Project root is not a valid explicit project directory.")
    system = Path(os.environ.get("WINDIR", "C:/Windows")) / "System32"
    require(path != system.resolve(), "unsafe_project", "System directories cannot be project roots.")
    reject_links(path / ".makesound" / "preset.json")
    return path


def project_id(path):
    return "project_" + hashlib.sha256(os.path.normcase(str(path.resolve())).encode("utf-8")).hexdigest()[:24]


@dataclass(frozen=True)
class Locations:
    data_dir: Path
    global_config: Path
    minimax_config: Path

    @classmethod
    def default(cls):
        data = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share")) / "makesound"
        return cls(data, Path.home() / ".config/makesound/presets.json",
                   Path.home() / ".config/minimax/config.json")


@contextmanager
def file_lock(path, timeout=5.0):
    """Lock release is owned by the OS, including after a process crashes."""
    reject_links(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + timeout
        while True:
            try:
                stream.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise MakeSoundError("lock_timeout", "Another process is updating local data.") from None
                time.sleep(0.02)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_UN)


def atomic_write(path, value):
    reject_links(path)
    payload = (canonical_json(value) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    require(path.parent.stat().st_mode & 0o222, "read_only", "Managed directory is read-only.")
    if path.exists():
        require(path.stat().st_mode & 0o222, "read_only", "Managed file is read-only.")
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix=".makesound-", suffix=".tmp", dir=path.parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except OSError:
        raise MakeSoundError("write_failed", "Atomic update failed; previous committed data was retained.") from None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


class JsonStore:
    def __init__(self, path, initial, validate):
        self.path = path
        self.initial = initial
        self.validate = validate

    def read(self):
        reject_links(self.path)
        value = read_json(self.path) if self.path.exists() else copy.deepcopy(self.initial)
        self.validate(value)
        return value

    def update(self, change, expected_revision=None):
        with file_lock(self.path.with_suffix(self.path.suffix + ".lock")):
            value = self.read()
            if expected_revision is not None:
                require(type(expected_revision) is int and expected_revision >= 0, message="Revision must be a non-negative integer.")
                require(value["revision"] == expected_revision, "revision_conflict", "Configuration changed; reload and confirm again.")
            result = change(value)
            value["revision"] += 1
            self.validate(value)
            atomic_write(self.path, value)
            return value, result
