from __future__ import annotations

import logging
import os
import shutil
import threading
import time
from pathlib import Path
from typing import Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from config import PROTECTED_NAMES, log_path
from i18n import normalize_lang, translator

LogFn = Callable[[str, str], None]


def setup_file_logging() -> None:
    log_file = log_path()
    root = logging.getLogger("porzadek")
    if root.handlers:
        return
    root.setLevel(logging.INFO)
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S")
    )
    root.addHandler(handler)


def unique_path(directory: Path, name: str) -> Path:
    target = directory / name
    if not target.exists():
        return target
    stem = Path(name).stem
    suffix = Path(name).suffix
    n = 1
    while True:
        candidate = directory / f"{stem} ({n}){suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def is_incomplete(path: Path, ignore_exts: set[str]) -> bool:
    name = path.name
    if name.startswith("~$") or name.startswith(".~"):
        return True
    if name.lower() in {"desktop.ini", "thumbs.db"}:
        return True
    return path.suffix.lower() in ignore_exts


def wait_until_ready(path: Path, timeout: float = 8.0) -> bool:
    if not path.exists():
        return False
    if path.is_dir():
        return True
    deadline = time.time() + timeout
    last_size = -1
    stable = 0
    while time.time() < deadline:
        try:
            size = path.stat().st_size
            with path.open("rb"):
                pass
        except OSError:
            time.sleep(0.35)
            continue
        if size == last_size:
            stable += 1
            if stable >= 2:
                return True
        else:
            stable = 0
            last_size = size
        time.sleep(0.35)
    return path.exists()


class FileSorter:
    def __init__(self, cfg: dict, on_log: LogFn | None = None) -> None:
        self.cfg = cfg
        self.on_log = on_log
        self._observer: Observer | None = None
        self._lock = threading.Lock()
        self._busy: set[str] = set()
        self.logger = logging.getLogger("porzadek")
        setup_file_logging()

    @property
    def source(self) -> Path:
        return Path(self.cfg["source"])

    @property
    def destination(self) -> Path:
        return Path(self.cfg["destination"])

    @property
    def running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()

    def _t(self, key: str, **kwargs: object) -> str:
        return translator(normalize_lang(self.cfg.get("language")))(key, **kwargs)

    def _emit(self, level: str, message: str) -> None:
        if level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        else:
            self.logger.info(message)
        if self.on_log:
            self.on_log(level, message)

    def _target_dir_for_file(self, path: Path) -> Path:
        ext = path.suffix.lower()
        folder = self.cfg["mappings"].get(ext, self.cfg["other_folder"])
        return self.destination / folder

    def _is_protected_dir(self, name: str) -> bool:
        key = name.strip().lower()
        if key in PROTECTED_NAMES:
            return True
        extra = {self.cfg["other_folder"].lower(), self.cfg["folders_folder"].lower()}
        extra.update(str(v).lower() for v in self.cfg["mappings"].values())
        return key in extra

    def move_item(self, item_path: str | Path) -> bool:
        path = Path(item_path)
        key = str(path.resolve()) if path.exists() else str(path)
        with self._lock:
            if key in self._busy:
                return False
            self._busy.add(key)
        try:
            return self._move_item(path)
        finally:
            with self._lock:
                self._busy.discard(key)

    def _move_item(self, path: Path) -> bool:
        if not path.exists():
            return False
        try:
            resolved = path.resolve()
            dest = self.destination.resolve()
            src = self.source.resolve()
            try:
                resolved.relative_to(dest)
                if resolved.parent != src:
                    return False
            except ValueError:
                pass
        except OSError:
            pass

        name = path.name
        if path.is_dir():
            if self._is_protected_dir(name):
                return False
            dest_dir = self.destination / self.cfg["folders_folder"]
            dest_dir.mkdir(parents=True, exist_ok=True)
            target = unique_path(dest_dir, name)
            try:
                shutil.move(str(path), str(target))
                self._emit(
                    "info",
                    self._t("log_folder_moved", name=name, folder=dest_dir.name),
                )
                return True
            except OSError as exc:
                self._emit(
                    "error",
                    self._t("log_move_folder_error", name=name, detail=exc),
                )
                return False

        ignore = {e.lower() for e in self.cfg.get("ignore_extensions", [])}
        if is_incomplete(path, ignore):
            return False
        if not wait_until_ready(path):
            self._emit("warning", self._t("log_busy_file", name=name))
            return False
        if is_incomplete(path, ignore):
            return False

        dest_dir = self._target_dir_for_file(path)
        dest_dir.mkdir(parents=True, exist_ok=True)
        target = unique_path(dest_dir, name)
        try:
            shutil.move(str(path), str(target))
            label = dest_dir.name
            if target.name != name:
                self._emit(
                    "info",
                    self._t(
                        "log_file_moved_renamed",
                        name=name,
                        folder=label,
                        new_name=target.name,
                    ),
                )
            else:
                self._emit("info", self._t("log_file_moved", name=name, folder=label))
            return True
        except OSError as exc:
            self._emit("error", self._t("log_move_file_error", name=name, detail=exc))
            return False

    def clean_now(self) -> int:
        source = self.source
        if not source.exists():
            self._emit("warning", self._t("log_no_source", path=source))
            return 0
        moved = 0
        for name in list(os.listdir(source)):
            if self.move_item(source / name):
                moved += 1
        self._emit("info", self._t("log_cleaned", count=moved))
        return moved

    def start(self, clean_first: bool = True) -> None:
        if self.running:
            return
        source = self.source
        if not source.exists():
            raise FileNotFoundError(self._t("error_folder_not_found", path=source))
        if source.resolve() == self.destination.resolve():
            raise ValueError(self._t("error_same_folders"))
        self.destination.mkdir(parents=True, exist_ok=True)
        if clean_first:
            self.clean_now()
        handler = _WatchHandler(self)
        observer = Observer()
        observer.schedule(handler, str(source), recursive=False)
        observer.start()
        self._observer = observer
        self._emit("info", self._t("log_watching", path=source))

    def stop(self) -> None:
        if not self._observer:
            return
        self._observer.stop()
        self._observer.join(timeout=5)
        self._observer = None
        self._emit("info", self._t("log_stopped"))


class _WatchHandler(FileSystemEventHandler):
    def __init__(self, sorter: FileSorter) -> None:
        super().__init__()
        self.sorter = sorter

    def _handle(self, src_path: str, is_directory: bool) -> None:
        def worker() -> None:
            delay = float(self.sorter.cfg.get("delay_seconds", 1.0))
            time.sleep(max(0.2, delay))
            path = Path(src_path)
            if is_directory or path.exists():
                self.sorter.move_item(path)

        threading.Thread(target=worker, daemon=True).start()

    def on_created(self, event) -> None:
        if event.is_directory:
            self._handle(event.src_path, True)
        else:
            self._handle(event.src_path, False)

    def on_modified(self, event) -> None:
        if event.is_directory:
            return
        self._handle(event.src_path, False)

    def on_moved(self, event) -> None:
        dest = getattr(event, "dest_path", None)
        if dest:
            self._handle(dest, event.is_directory)
