from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

from i18n import normalize_lang

DOWNLOADS_GUID = "374DE290-123F-4565-9164-39C4925E467B"
DESKTOP_GUID = "B4BFCC3A-DB2C-424C-B029-7FE99A87C641"

MAPPINGS_EN = {
    ".pdf": "Documents",
    ".doc": "Documents",
    ".docx": "Documents",
    ".txt": "Documents",
    ".rtf": "Documents",
    ".odt": "Documents",
    ".xls": "Documents",
    ".xlsx": "Documents",
    ".csv": "Documents",
    ".ppt": "Documents",
    ".pptx": "Documents",
    ".jpg": "Photos",
    ".jpeg": "Photos",
    ".png": "Photos",
    ".jfif": "Photos",
    ".gif": "Photos",
    ".webp": "Photos",
    ".bmp": "Photos",
    ".svg": "Photos",
    ".heic": "Photos",
    ".tif": "Photos",
    ".tiff": "Photos",
    ".mp4": "Video",
    ".mkv": "Video",
    ".avi": "Video",
    ".mov": "Video",
    ".wmv": "Video",
    ".webm": "Video",
    ".mp3": "Music",
    ".wav": "Music",
    ".flac": "Music",
    ".aac": "Music",
    ".ogg": "Music",
    ".m4a": "Music",
    ".zip": "Archives",
    ".rar": "Archives",
    ".7z": "Archives",
    ".tar": "Archives",
    ".gz": "Archives",
    ".exe": "Installers",
    ".msi": "Installers",
    ".msix": "Installers",
    ".iso": "Disk_images",
    ".img": "Disk_images",
}

IGNORE_EXTENSIONS = [
    ".crdownload",
    ".part",
    ".partial",
    ".tmp",
    ".temp",
    ".download",
    ".opdownload",
    ".filepart",
]

PROTECTED_NAMES = {
    "dokumenty",
    "zdjecia",
    "wideo",
    "muzyka",
    "archiwa",
    "instalatory",
    "obrazy_dyskow",
    "inne",
    "foldery_z_pobranych",
    "documents",
    "photos",
    "video",
    "music",
    "archives",
    "installers",
    "disk_images",
    "other",
    "other files",
    "folders_from_downloads",
    "folders_from_downloads",
    "foldery_z_pobranych",
}

APP_NAME = "Tidy"
LEGACY_APP_NAME = "Porzadek"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def data_dir() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        path = base / APP_NAME
    else:
        path = Path.home() / ".config" / APP_NAME.lower()
    path.mkdir(parents=True, exist_ok=True)
    return path


def config_path() -> Path:
    return data_dir() / "config.json"


def log_path() -> Path:
    return data_dir() / "sort.log"


def _known_folder(guid: str) -> Path | None:
    if os.name != "nt":
        return None
    try:
        import ctypes
        from uuid import UUID

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", ctypes.c_ulong),
                ("Data2", ctypes.c_ushort),
                ("Data3", ctypes.c_ushort),
                ("Data4", ctypes.c_ubyte * 8),
            ]

            def __init__(self, uuid_str: str) -> None:
                uuid_ = UUID(uuid_str)
                super().__init__()
                self.Data1 = uuid_.time_low
                self.Data2 = uuid_.time_mid
                self.Data3 = uuid_.time_hi_version
                self.Data4[:] = uuid_.bytes[8:]

        path_ptr = ctypes.c_wchar_p()
        folder_id = GUID(guid)
        result = ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(folder_id), 0, None, ctypes.byref(path_ptr)
        )
        if result != 0 or not path_ptr.value:
            return None
        path = Path(path_ptr.value)
        ctypes.windll.ole32.CoTaskMemFree(path_ptr)
        return path if path.exists() else None
    except Exception:
        return None


def detect_downloads() -> Path:
    known = _known_folder(DOWNLOADS_GUID)
    if known:
        return known
    home = Path.home()
    for name in ("Downloads", "Pobrane"):
        candidate = home / name
        if candidate.exists():
            return candidate
    return home / "Downloads"


def detect_desktop() -> Path:
    known = _known_folder(DESKTOP_GUID)
    if known:
        return known
    home = Path.home()
    for name in ("Desktop", "Pulpit"):
        candidate = home / name
        if candidate.exists():
            return candidate
    return home / "Desktop"


def default_folders_for_lang(_lang: str | None = None) -> tuple[dict, str, str]:
    return dict(MAPPINGS_EN), "Other", "Folders_from_downloads"


def default_config() -> dict:
    lang = "en"
    mappings, other, folders = default_folders_for_lang(lang)
    return {
        "language": lang,
        "source": str(detect_downloads()),
        "destination": str(detect_desktop()),
        "delay_seconds": 1.0,
        "clean_on_start": True,
        "start_with_windows": False,
        "other_folder": other,
        "folders_folder": folders,
        "mappings": mappings,
        "ignore_extensions": list(IGNORE_EXTENSIONS),
    }


def legacy_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / LEGACY_APP_NAME / "config.json"
    return Path.home() / ".config" / LEGACY_APP_NAME.lower() / "config.json"


def load_config() -> dict:
    path = config_path()
    legacy = legacy_config_path()
    if not path.exists() and legacy.exists():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(legacy, path)
        except OSError:
            pass

    cfg = default_config()
    if path.exists():
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                mappings = saved.pop("mappings", None)
                ignore = saved.pop("ignore_extensions", None)
                cfg.update(saved)
                cfg["language"] = normalize_lang(cfg.get("language"))
                if isinstance(mappings, dict) and mappings:
                    cfg["mappings"] = {
                        str(k).lower() if str(k).startswith(".") else f".{k}".lower(): v
                        for k, v in mappings.items()
                    }
                if isinstance(ignore, list) and ignore:
                    cfg["ignore_extensions"] = [
                        e.lower() if str(e).startswith(".") else f".{e}".lower()
                        for e in ignore
                    ]
        except (OSError, json.JSONDecodeError):
            pass
    elif normalize_lang(os.environ.get("LANG", "")) == "pl":
        cfg["language"] = "pl"
    return cfg


def save_config(cfg: dict) -> None:
    cfg["language"] = normalize_lang(cfg.get("language"))
    path = config_path()
    path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
