from __future__ import annotations

from typing import Callable

Locale = str

STRINGS: dict[Locale, dict[str, str]] = {
    "en": {
        "title_main": "Tidy",
        "title_sub": "File organizer",
        "window_title": "Tidy",
        "tagline": "Watch any folder on your PC and sort new files into categories you choose.",
        "status_stopped": "Stopped",
        "status_running": "Running",
        "source_label": "Watch folder (source)",
        "dest_label": "Sort into (destination)",
        "browse": "Browse…",
        "clean_on_start": "Sort existing files when starting",
        "startup_windows": "Launch with Windows (minimized)",
        "logs_hint": "Logs:",
        "activity": "Activity",
        "btn_start": "Start",
        "btn_stop": "Stop",
        "btn_clean": "Clean now",
        "btn_logs": "Open logs",
        "lang_label": "Language",
        "paths_card": "Folders",
        "options_card": "Options",
        "confirm_close_title": "Tidy",
        "confirm_close": "Stop watching and close the app?",
        "error_title": "Tidy",
        "error_startup": "Could not set startup shortcut:\n{detail}",
        "error_start": "Could not start:\n{detail}",
        "started_autostart": "Started from Windows autostart",
        "log_folder_moved": "Folder: {name} → {folder}",
        "log_file_moved": "File: {name} → {folder}",
        "log_file_moved_renamed": "File: {name} → {folder} (as {new_name})",
        "log_move_folder_error": "Could not move folder {name}: {detail}",
        "log_move_file_error": "Could not move {name}: {detail}",
        "log_busy_file": "File still in use, skipped: {name}",
        "log_no_source": "Source folder missing: {path}",
        "log_cleaned": "Cleaned {count} item(s)",
        "log_watching": "Watching: {path}",
        "log_stopped": "Stopped watching",
        "error_folder_not_found": "Folder not found: {path}",
        "error_same_folders": "Source and destination cannot be the same",
    },
    "pl": {
        "title_main": "Tidy",
        "title_sub": "Organizer plików",
        "window_title": "Tidy",
        "tagline": "Obserwuje wybrany folder i sortuje pliki do kategorii. Źródło i cel ustawiasz sam.",
        "status_stopped": "Zatrzymane",
        "status_running": "Działa",
        "source_label": "Folder do obserwacji (źródło)",
        "dest_label": "Sortuj do (cel)",
        "browse": "Wybierz…",
        "clean_on_start": "Posprzątaj istniejące pliki przy starcie",
        "startup_windows": "Uruchom wraz z Windows (w tle)",
        "logs_hint": "Logi:",
        "activity": "Aktywność",
        "btn_start": "Start",
        "btn_stop": "Stop",
        "btn_clean": "Posprzątaj teraz",
        "btn_logs": "Otwórz logi",
        "lang_label": "Język",
        "paths_card": "Foldery",
        "options_card": "Opcje",
        "confirm_close_title": "Tidy",
        "confirm_close": "Zatrzymać nasłuchiwanie i zamknąć aplikację?",
        "error_title": "Tidy",
        "error_startup": "Nie udało się ustawić autostartu:\n{detail}",
        "error_start": "Nie udało się uruchomić:\n{detail}",
        "started_autostart": "Uruchomiono z autostartu Windows",
        "log_folder_moved": "Folder: {name} → {folder}",
        "log_file_moved": "Plik: {name} → {folder}",
        "log_file_moved_renamed": "Plik: {name} → {folder} (jako {new_name})",
        "log_move_folder_error": "Nie udało się przenieść folderu {name}: {detail}",
        "log_move_file_error": "Nie udało się przenieść {name}: {detail}",
        "log_busy_file": "Plik nadal zajęty, pominięto: {name}",
        "log_no_source": "Brak folderu źródłowego: {path}",
        "log_cleaned": "Posprzątano {count} elementów",
        "log_watching": "Nasłuchiwanie: {path}",
        "log_stopped": "Zatrzymano nasłuchiwanie",
        "error_folder_not_found": "Nie znaleziono folderu: {path}",
        "error_same_folders": "Folder źródłowy i docelowy nie mogą być takie same",
    },
}

LANG_LABELS = {"en": "English", "pl": "Polski"}


def normalize_lang(code: str | None) -> Locale:
    if code and code.lower().startswith("pl"):
        return "pl"
    return "en"


def translator(lang: Locale) -> Callable[..., str]:
    lang = normalize_lang(lang)
    table = STRINGS[lang]

    def t(key: str, **kwargs: object) -> str:
        text = table.get(key) or STRINGS["en"].get(key, key)
        return text.format(**kwargs) if kwargs else text

    return t
