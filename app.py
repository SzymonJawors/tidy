from __future__ import annotations

import argparse
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from config import app_dir, is_frozen, load_config, log_path, save_config
from i18n import LANG_LABELS, normalize_lang, translator
from sorter import FileSorter

# Palette
BG = "#f1f5f9"
SURFACE = "#ffffff"
HEADER = "#1e1b4b"
HEADER_TOP = "#312e81"
HEADER_TEXT = "#c7d2fe"
HEADER_SUB = "#e0e7ff"
ACCENT_BAR = "#6366f1"
TEXT = "#0f172a"
MUTED = "#64748b"
BORDER = "#e2e8f0"
ACCENT = "#4f46e5"
ACCENT_ACTIVE = "#4338ca"
ACCENT_DISABLED = "#a5b4fc"
DANGER = "#ef4444"
DANGER_ACTIVE = "#dc2626"
OK = "#10b981"
OK_BG = "#d1fae5"
STOPPED_BG = "#e2e8f0"
LOG_BG = "#0f172a"
LOG_FG = "#cbd5e1"
LOG_INFO = "#93c5fd"
LOG_WARN = "#fcd34d"
LOG_ERR = "#fca5a5"


def startup_shortcut_path() -> Path:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    return appdata / r"Microsoft\Windows\Start Menu\Programs\Startup" / "Tidy.lnk"


def launch_command() -> tuple[str, str]:
    if is_frozen():
        return str(Path(sys.executable)), "--minimized"
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    if not pythonw.exists():
        pythonw = Path(sys.executable)
    return str(pythonw), f'"{app_dir() / "app.py"}" --minimized'


def set_windows_startup(enabled: bool) -> None:
    shortcut = startup_shortcut_path()
    legacy = shortcut.parent / "Porzadek.lnk"
    if not enabled:
        if shortcut.exists():
            shortcut.unlink()
        if legacy.exists():
            legacy.unlink()
        return
    if legacy.exists():
        legacy.unlink()
    target, args = launch_command()
    workdir = str(app_dir())
    script = (
        "$s = (New-Object -ComObject WScript.Shell).CreateShortcut("
        f"'{shortcut}')\n"
        f"$s.TargetPath = '{target}'\n"
        f"$s.Arguments = '{args}'\n"
        f"$s.WorkingDirectory = '{workdir}'\n"
        "$s.WindowStyle = 7\n"
        "$s.Save()\n"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


class Pill(tk.Frame):
    def __init__(self, master: tk.Misc, **kw) -> None:
        super().__init__(master, bg=STOPPED_BG, **kw)
        self.dot = tk.Label(self, text="●", bg=STOPPED_BG, fg=MUTED, font=("Segoe UI", 8))
        self.dot.pack(side="left", padx=(10, 4))
        self.label = tk.Label(self, bg=STOPPED_BG, fg=TEXT, font=("Segoe UI Semibold", 9))
        self.label.pack(side="left", padx=(0, 12), pady=6)

    def set_state(self, running: bool, text: str) -> None:
        bg = OK_BG if running else STOPPED_BG
        fg = "#065f46" if running else MUTED
        dot = OK if running else MUTED
        self.configure(bg=bg)
        self.dot.configure(bg=bg, fg=dot)
        self.label.configure(bg=bg, fg=fg, text=text)


class FlatButton(tk.Button):
    def __init__(
        self,
        master: tk.Misc,
        *,
        variant: str = "secondary",
        **kw,
    ) -> None:
        self._variant = variant
        defaults = {
            "relief": "flat",
            "borderwidth": 0,
            "padx": 16,
            "pady": 10,
            "cursor": "hand2",
            "font": ("Segoe UI Semibold", 10),
            "activeforeground": "#ffffff",
        }
        defaults.update(kw)
        super().__init__(master, **defaults)
        self._apply(variant)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _colors(self, variant: str, hover: bool = False) -> tuple[str, str]:
        if variant == "primary":
            return (ACCENT_ACTIVE if hover else ACCENT, "#ffffff")
        if variant == "danger":
            return (DANGER_ACTIVE if hover else DANGER, "#ffffff")
        if hover:
            return ("#e2e8f0", TEXT)
        return (SURFACE, TEXT)

    def _apply(self, variant: str, hover: bool = False) -> None:
        bg, fg = self._colors(variant, hover)
        active = self._colors(variant, True)[0]
        self.configure(bg=bg, fg=fg, activebackground=active, highlightthickness=0)

    def _on_enter(self, _event) -> None:
        if str(self.cget("state")) != "disabled":
            self._apply(self._variant, True)

    def _on_leave(self, _event) -> None:
        if str(self.cget("state")) != "disabled":
            self._apply(self._variant, False)

    def set_variant(self, variant: str) -> None:
        self._variant = variant
        self._apply(variant)


class App(tk.Tk):
    def __init__(self, start_minimized: bool = False) -> None:
        super().__init__()
        self.cfg = load_config()
        self.lang = normalize_lang(self.cfg.get("language"))
        self.t = translator(self.lang)
        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.sorter = FileSorter(self.cfg, on_log=self._enqueue_log)

        self.title(self.t("window_title"))
        self.geometry("820x680")
        self.minsize(680, 560)
        self.configure(bg=BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._label_widgets: dict[str, tk.Widget] = {}
        self._build()
        self.after(150, self._drain_logs)

        if start_minimized:
            self.after(200, self.iconify)
            if self.cfg.get("clean_on_start", True):
                self.after(400, lambda: self._start(from_autostart=True))

    def _card(self, parent: tk.Misc, title_key: str) -> tk.Frame:
        shadow = tk.Frame(parent, bg="#cbd5e1")
        shadow.pack(fill="x", pady=(0, 14))
        wrap = tk.Frame(shadow, bg=SURFACE, highlightbackground=BORDER, highlightthickness=1)
        wrap.pack(fill="x", padx=1, pady=1)
        inner = tk.Frame(wrap, bg=SURFACE)
        inner.pack(fill="x", padx=22, pady=18)
        head = tk.Label(
            inner,
            text=self.t(title_key),
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI Semibold", 9),
            anchor="w",
        )
        head.pack(fill="x", pady=(0, 10))
        self._label_widgets[title_key] = head
        body = tk.Frame(inner, bg=SURFACE)
        body.pack(fill="x")
        return body

    def _build(self) -> None:
        self._font_title = tkfont.Font(family="Segoe UI", size=22, weight="bold")
        self._font_sub = tkfont.Font(family="Segoe UI", size=11)
        self._font_tag = tkfont.Font(family="Segoe UI", size=10)

        header_wrap = tk.Frame(self, bg=HEADER_TOP)
        header_wrap.pack(fill="x")
        header = tk.Frame(header_wrap, bg=HEADER_TOP)
        header.pack(fill="x")
        h_inner = tk.Frame(header, bg=HEADER_TOP)
        h_inner.pack(fill="x", padx=28, pady=(20, 18))
        h_inner.columnconfigure(0, weight=1)
        h_inner.columnconfigure(1, weight=0)

        left = tk.Frame(h_inner, bg=HEADER_TOP)
        left.grid(row=0, column=0, sticky="nw")

        title_row = tk.Frame(left, bg=HEADER_TOP)
        title_row.pack(anchor="w")
        self._label_widgets["title_main"] = tk.Label(
            title_row,
            text=self.t("title_main"),
            bg=HEADER_TOP,
            fg="#ffffff",
            font=self._font_title,
            anchor="w",
        )
        self._label_widgets["title_main"].pack(side="left")
        self._label_widgets["title_sub"] = tk.Label(
            title_row,
            text=self.t("title_sub"),
            bg=HEADER_TOP,
            fg=HEADER_SUB,
            font=self._font_sub,
            anchor="w",
        )
        self._label_widgets["title_sub"].pack(side="left", padx=(10, 0), pady=(6, 0))

        self._label_widgets["tagline"] = tk.Label(
            left,
            text=self.t("tagline"),
            bg=HEADER_TOP,
            fg=HEADER_TEXT,
            font=self._font_tag,
            anchor="nw",
            justify="left",
        )
        self._label_widgets["tagline"].pack(anchor="w", pady=(10, 0), fill="x")

        right = tk.Frame(h_inner, bg=HEADER_TOP)
        right.grid(row=0, column=1, sticky="ne", padx=(16, 0))
        lang_row = tk.Frame(right, bg=HEADER_TOP)
        lang_row.pack(anchor="e", pady=(0, 10))
        self._label_widgets["lang_label"] = tk.Label(
            lang_row,
            text=self.t("lang_label"),
            bg=HEADER_TOP,
            fg=HEADER_TEXT,
            font=("Segoe UI", 9),
        )
        self._label_widgets["lang_label"].pack(side="left", padx=(0, 8))
        self.lang_var = tk.StringVar(value=self.lang)
        self.lang_combo = ttk.Combobox(
            lang_row,
            textvariable=self.lang_var,
            values=["en", "pl"],
            state="readonly",
            width=10,
        )
        self.lang_combo.pack(side="left")
        self.lang_combo.bind("<<ComboboxSelected>>", self._on_language)

        self.status_pill = Pill(right)
        self.status_pill.pack(anchor="e")
        self.status_pill.set_state(False, self.t("status_stopped"))

        tk.Frame(header_wrap, bg=ACCENT_BAR, height=3).pack(fill="x")

        self._header_left = left
        self.bind("<Configure>", self._on_window_configure, add="+")
        self.after_idle(self._update_header_wrap)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=24, pady=20)

        paths = self._card(body, "paths_card")

        self.source_var = tk.StringVar(value=self.cfg["source"])
        self.dest_var = tk.StringVar(value=self.cfg["destination"])
        self._path_row(paths, "source_label", self.source_var, 0)
        self._path_row(paths, "dest_label", self.dest_var, 1)

        opts_body = self._card(body, "options_card")

        self.clean_var = tk.BooleanVar(value=bool(self.cfg.get("clean_on_start", True)))
        self.startup_var = tk.BooleanVar(value=bool(self.cfg.get("start_with_windows", False)))

        self._chk_clean = tk.Checkbutton(
            opts_body,
            text=self.t("clean_on_start"),
            variable=self.clean_var,
            bg=SURFACE,
            fg=TEXT,
            activebackground=SURFACE,
            activeforeground=TEXT,
            selectcolor=SURFACE,
            font=("Segoe UI", 10),
            anchor="w",
        )
        self._chk_clean.pack(anchor="w", pady=2)
        self._label_widgets["clean_on_start"] = self._chk_clean

        self._chk_startup = tk.Checkbutton(
            opts_body,
            text=self.t("startup_windows"),
            variable=self.startup_var,
            command=self._toggle_startup,
            bg=SURFACE,
            fg=TEXT,
            activebackground=SURFACE,
            activeforeground=TEXT,
            selectcolor=SURFACE,
            font=("Segoe UI", 10),
            anchor="w",
        )
        self._chk_startup.pack(anchor="w", pady=2)
        self._label_widgets["startup_windows"] = self._chk_startup

        logs_row = tk.Frame(opts_body, bg=SURFACE)
        logs_row.pack(fill="x", pady=(10, 0))
        self._label_widgets["logs_hint"] = tk.Label(
            logs_row,
            text=f"{self.t('logs_hint')} {log_path()}",
            bg=SURFACE,
            fg=MUTED,
            font=("Segoe UI", 8),
            anchor="w",
            wraplength=720,
            justify="left",
        )
        self._label_widgets["logs_hint"].pack(anchor="w")

        btn_row = tk.Frame(body, bg=BG)
        btn_row.pack(fill="x", pady=(0, 14))
        self.start_btn = FlatButton(btn_row, text=self.t("btn_start"), variant="primary", command=self._start)
        self.start_btn.pack(side="left")
        self._label_widgets["btn_start"] = self.start_btn

        self.stop_btn = FlatButton(
            btn_row,
            text=self.t("btn_stop"),
            variant="danger",
            command=self._stop,
            state="disabled",
        )
        self.stop_btn.pack(side="left", padx=(10, 0))
        self._label_widgets["btn_stop"] = self.stop_btn

        self.clean_btn = FlatButton(btn_row, text=self.t("btn_clean"), command=self._clean_now)
        self.clean_btn.pack(side="left", padx=(10, 0))
        self._label_widgets["btn_clean"] = self.clean_btn

        self.logs_btn = FlatButton(btn_row, text=self.t("btn_logs"), command=self._open_logs)
        self.logs_btn.pack(side="right")
        self._label_widgets["btn_logs"] = self.logs_btn

        self._label_widgets["activity"] = tk.Label(
            body,
            text=self.t("activity"),
            bg=BG,
            fg=TEXT,
            font=("Segoe UI Semibold", 11),
            anchor="w",
        )
        self._label_widgets["activity"].pack(anchor="w")

        log_outer = tk.Frame(body, bg=BORDER, padx=1, pady=1)
        log_outer.pack(fill="both", expand=True, pady=(8, 0))
        log_wrap = tk.Frame(log_outer, bg=LOG_BG)
        log_wrap.pack(fill="both", expand=True)
        self.log_box = tk.Text(
            log_wrap,
            height=12,
            wrap="word",
            bg=LOG_BG,
            fg=LOG_FG,
            insertbackground=LOG_FG,
            relief="flat",
            font=("Cascadia Mono", 9) if os.name == "nt" else ("Consolas", 9),
            padx=14,
            pady=12,
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(log_wrap, command=self.log_box.yview)
        self.log_box.configure(yscrollcommand=scroll.set, state="disabled")
        self.log_box.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.log_box.tag_configure("info", foreground=LOG_INFO)
        self.log_box.tag_configure("warning", foreground=LOG_WARN)
        self.log_box.tag_configure("error", foreground=LOG_ERR)

        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            style.theme_use("clam")
        style.configure("TCombobox", padding=4)
        style.configure("Header.TCombobox", padding=4)

        self._refresh_lang_combo_display()

    def _on_window_configure(self, event) -> None:
        if event.widget is self:
            self._update_header_wrap()

    def _update_header_wrap(self) -> None:
        tag = self._label_widgets.get("tagline")
        if not tag or not hasattr(self, "_header_left"):
            return
        try:
            right_reserve = 220
            width = max(self.winfo_width(), 680)
            wrap = max(320, width - right_reserve - 56)
            tag.configure(wraplength=wrap)
        except tk.TclError:
            pass

    def _refresh_lang_combo_display(self) -> None:
        self.lang_combo["values"] = [f"{LANG_LABELS['en']} (en)", f"{LANG_LABELS['pl']} (pl)"]
        idx = 0 if self.lang == "en" else 1
        self.lang_combo.current(idx)

    def _path_row(self, parent: tk.Frame, label_key: str, var: tk.StringVar, row: int) -> None:
        row_f = tk.Frame(parent, bg=SURFACE)
        row_f.pack(fill="x", pady=8)
        row_f.columnconfigure(1, weight=1)
        lbl = tk.Label(
            row_f,
            text=self.t(label_key),
            bg=SURFACE,
            fg=TEXT,
            font=("Segoe UI", 10),
            anchor="nw",
            justify="left",
            wraplength=200,
        )
        lbl.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        self._label_widgets[label_key] = lbl
        entry = tk.Entry(
            row_f,
            textvariable=var,
            font=("Segoe UI", 10),
            bg="#f8fafc",
            fg=TEXT,
            relief="flat",
            highlightthickness=1,
            highlightbackground=BORDER,
            highlightcolor=ACCENT,
        )
        entry.grid(row=0, column=1, sticky="ew", ipady=7)
        btn = FlatButton(row_f, text=self.t("browse"), command=lambda: self._browse(var))
        btn.configure(padx=12, pady=6, font=("Segoe UI", 9))
        btn.set_variant("secondary")
        btn.grid(row=0, column=2, sticky="e", padx=(10, 0))
        self._label_widgets[f"browse_{label_key}"] = btn

    def _on_language(self, _event=None) -> None:
        self.lang = "pl" if self.lang_combo.current() == 1 else "en"
        self.cfg["language"] = self.lang
        self.t = translator(self.lang)
        self.sorter.cfg = self.cfg
        save_config(self.cfg)
        self._apply_language()
        self.after_idle(self._update_header_wrap)

    def _apply_language(self) -> None:
        self.title(self.t("window_title"))
        mapping = {
            "title_main": self.t("title_main"),
            "title_sub": self.t("title_sub"),
            "tagline": self.t("tagline"),
            "lang_label": self.t("lang_label"),
            "paths_card": self.t("paths_card"),
            "options_card": self.t("options_card"),
            "browse": self.t("browse"),
            "source_label": self.t("source_label"),
            "dest_label": self.t("dest_label"),
            "clean_on_start": self.t("clean_on_start"),
            "startup_windows": self.t("startup_windows"),
            "activity": self.t("activity"),
        }
        for key, text in mapping.items():
            w = self._label_widgets.get(key)
            if w is None:
                continue
            if isinstance(w, tk.Checkbutton):
                w.configure(text=text)
            else:
                w.configure(text=text)
        self._label_widgets["logs_hint"].configure(text=f"{self.t('logs_hint')} {log_path()}")
        self.start_btn.configure(text=self.t("btn_start"))
        self.stop_btn.configure(text=self.t("btn_stop"))
        self.clean_btn.configure(text=self.t("btn_clean"))
        self.logs_btn.configure(text=self.t("btn_logs"))
        if "browse_source_label" in self._label_widgets:
            self._label_widgets["browse_source_label"].configure(text=self.t("browse"))
        if "browse_dest_label" in self._label_widgets:
            self._label_widgets["browse_dest_label"].configure(text=self.t("browse"))
        running = self.sorter.running
        self.status_pill.set_state(
            running,
            self.t("status_running") if running else self.t("status_stopped"),
        )
        self._refresh_lang_combo_display()
        self.after_idle(self._update_header_wrap)

    def _browse(self, var: tk.StringVar) -> None:
        chosen = filedialog.askdirectory(initialdir=var.get() or str(Path.home()))
        if chosen:
            var.set(chosen)

    def _enqueue_log(self, level: str, message: str) -> None:
        self.log_queue.put((level, message))

    def _drain_logs(self) -> None:
        while True:
            try:
                level, message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self.log_box.configure(state="normal")
            self.log_box.insert("end", message + "\n", level)
            self.log_box.see("end")
            self.log_box.configure(state="disabled")
        self.after(150, self._drain_logs)

    def _persist(self) -> None:
        self.cfg["source"] = self.source_var.get().strip()
        self.cfg["destination"] = self.dest_var.get().strip()
        self.cfg["clean_on_start"] = bool(self.clean_var.get())
        self.cfg["start_with_windows"] = bool(self.startup_var.get())
        self.cfg["language"] = self.lang
        save_config(self.cfg)
        self.sorter.cfg = self.cfg

    def _toggle_startup(self) -> None:
        self._persist()
        try:
            set_windows_startup(self.startup_var.get())
        except OSError as exc:
            messagebox.showerror(self.t("error_title"), self.t("error_startup", detail=exc))

    def _set_running(self, running: bool) -> None:
        self.status_pill.set_state(
            running,
            self.t("status_running") if running else self.t("status_stopped"),
        )
        if running:
            self.start_btn.configure(state="disabled", bg=ACCENT_DISABLED)
            self.stop_btn.configure(state="normal")
            self.stop_btn._apply("danger")
        else:
            self.start_btn.configure(state="normal")
            self.start_btn._apply("primary")
            self.stop_btn.configure(state="disabled", bg="#fca5a5")

    def _start(self, from_autostart: bool = False) -> None:
        self._persist()
        if self.sorter.running:
            return
        try:
            self.sorter.start(clean_first=self.clean_var.get())
        except (FileNotFoundError, ValueError) as exc:
            messagebox.showerror(self.t("error_title"), self.t("error_start", detail=exc))
            return
        except Exception as exc:
            messagebox.showerror(self.t("error_title"), self.t("error_start", detail=exc))
            return
        self._set_running(True)
        if from_autostart:
            self._enqueue_log("info", self.t("started_autostart"))

    def _stop(self) -> None:
        if self.sorter.running:
            threading.Thread(target=self.sorter.stop, daemon=True).start()
        self._set_running(False)

    def _clean_now(self) -> None:
        self._persist()
        threading.Thread(target=self.sorter.clean_now, daemon=True).start()

    def _open_logs(self) -> None:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch(exist_ok=True)
        os.startfile(path)  # noqa: S606

    def _on_close(self) -> None:
        if self.sorter.running:
            if not messagebox.askokcancel(self.t("confirm_close_title"), self.t("confirm_close")):
                return
            self.sorter.stop()
        self._persist()
        self.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description="Tidy")
    parser.add_argument("--minimized", action="store_true")
    args, _ = parser.parse_known_args()
    app = App(start_minimized=args.minimized)
    app.mainloop()


if __name__ == "__main__":
    main()
