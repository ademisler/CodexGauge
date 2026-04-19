from __future__ import annotations

import ctypes
import os
import queue
import sys
import tkinter as tk
import tkinter.font as tkfont
from dataclasses import dataclass
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from tkinter import messagebox, ttk
from typing import Any, Callable
from uuid import UUID

from PIL import Image, ImageDraw, ImageTk
import pystray

from .account_manager import CodexAccountManager, CodexAccountManagerError, ManagedLoginProcess
from .brand_icon import build_orbit_dial_icon
from .codex_api import AuthBackedIdentity
from .codex_api import fetch_snapshot
from .codex_desktop import CodexDesktopControlError, restart_codex_desktop
from .models import AccountRuntimeState, AccountUsageSnapshot, StoredAccount, StoredAccountSource, normalize_identifier, utc_now
from .stores import AccountStore, SnapshotStore


@dataclass(slots=True)
class RoundedButtonTheme:
    bg: str
    fg: str
    hover: str
    border: str
    disabled_bg: str
    disabled_fg: str


class RoundedButton(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        theme: RoundedButtonTheme,
        font: tuple[str, int] | tuple[str, int, str],
        icon: str | None,
        icon_font: tuple[str, int] | tuple[str, int, str] | None,
        radius: int,
        pad_x: int,
        pad_y: int,
    ) -> None:
        super().__init__(
            parent,
            highlightthickness=0,
            bd=0,
            relief="flat",
            bg=parent.cget("bg"),
            cursor="hand2",
            takefocus=0,
        )
        self.text = text
        self.command = command
        self.theme = theme
        self.font = font
        self.icon = icon
        self.icon_font = icon_font
        self.radius = radius
        self.pad_x = pad_x
        self.pad_y = pad_y
        self.enabled = True
        self._hovering = False

        self.bind("<Configure>", self._redraw)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

        width, height = self._measure()
        self.configure(width=width, height=height)
        self._redraw()

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = enabled
        self.configure(cursor="hand2" if enabled else "arrow")
        self._redraw()

    def set_text(self, text: str) -> None:
        self.text = text
        width, height = self._measure()
        self.configure(width=width, height=height)
        self._redraw()

    def set_theme(self, theme: RoundedButtonTheme) -> None:
        self.theme = theme
        self._redraw()

    def set_icon(self, icon: str | None) -> None:
        self.icon = icon
        width, height = self._measure()
        self.configure(width=width, height=height)
        self._redraw()

    def _on_enter(self, _: tk.Event[Any]) -> None:
        self._hovering = True
        self._redraw()

    def _on_leave(self, _: tk.Event[Any]) -> None:
        self._hovering = False
        self._redraw()

    def _on_click(self, _: tk.Event[Any]) -> None:
        if self.enabled:
            self.command()

    def _redraw(self, _: tk.Event[Any] | None = None) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())

        if self.enabled:
            fill = self.theme.hover if self._hovering else self.theme.bg
            fg = self.theme.fg
            border = self.theme.border
        else:
            fill = self.theme.disabled_bg
            fg = self.theme.disabled_fg
            border = self.theme.border

        self._rounded_rect(0, 0, width - 1, height - 1, self.radius, fill, border)
        text_font = tkfont.Font(font=self.font)
        text_width = text_font.measure(self.text)
        icon_width = 0
        if self.icon and self.icon_font:
            icon_font = tkfont.Font(font=self.icon_font)
            icon_width = icon_font.measure(self.icon) + 8

        total_width = text_width + icon_width
        start_x = (width - total_width) / 2

        if self.icon and self.icon_font:
            icon_font = tkfont.Font(font=self.icon_font)
            icon_text_width = icon_font.measure(self.icon)
            self.create_text(
                start_x + (icon_text_width / 2),
                height // 2,
                text=self.icon,
                fill=fg,
                font=self.icon_font,
            )
            start_x += icon_text_width + 8

        self.create_text(
            start_x + (text_width / 2),
            height // 2,
            text=self.text,
            fill=fg,
            font=self.font,
        )

    def _measure(self) -> tuple[int, int]:
        text_font = tkfont.Font(font=self.font)
        text_width = text_font.measure(self.text)
        text_height = text_font.metrics("linespace")
        icon_width = 0
        icon_height = 0
        if self.icon and self.icon_font:
            icon_font = tkfont.Font(font=self.icon_font)
            icon_width = icon_font.measure(self.icon) + 8
            icon_height = icon_font.metrics("linespace")

        width = text_width + icon_width + (self.pad_x * 2)
        height = max(text_height, icon_height) + (self.pad_y * 2)
        return width, height

    def _rounded_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, fill: str, outline: str) -> None:
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        self.create_polygon(points, smooth=True, fill=fill, outline=outline)


class DarkScrollbar(tk.Canvas):
    def __init__(
        self,
        parent: tk.Widget,
        command: Callable[..., Any],
        palette: dict[str, str],
        width: int = 11,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            highlightthickness=0,
            bd=0,
            relief="flat",
            bg=palette["shell"],
            cursor="hand2",
            takefocus=0,
        )
        self.command = command
        self.palette = palette
        self.bar_width = width
        self.first = 0.0
        self.last = 1.0
        self.thumb_top = 0
        self.thumb_bottom = 0
        self.drag_offset = 0
        self.dragging = False

        self.bind("<Configure>", self._redraw)
        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)

        self._redraw()

    def set(self, first: str | float, last: str | float) -> None:
        self.first = max(0.0, min(1.0, float(first)))
        self.last = max(self.first, min(1.0, float(last)))
        self._redraw()

    def _on_press(self, event: tk.Event[Any]) -> None:
        if self.thumb_top <= event.y <= self.thumb_bottom:
            self.dragging = True
            self.drag_offset = event.y - self.thumb_top
            return

        self._jump_to(event.y)

    def _on_drag(self, event: tk.Event[Any]) -> None:
        if not self.dragging:
            return

        height = max(1, self.winfo_height())
        thumb_size = max(24, self.thumb_bottom - self.thumb_top)
        track = max(1, height - thumb_size)
        top = min(max(0, event.y - self.drag_offset), track)
        first = top / track if track else 0.0
        self.command("moveto", str(first))

    def _on_release(self, _: tk.Event[Any]) -> None:
        self.dragging = False

    def _jump_to(self, y: int) -> None:
        height = max(1, self.winfo_height())
        visible = max(0.05, self.last - self.first)
        thumb_size = max(24, int(height * visible))
        track = max(1, height - thumb_size)
        target = min(max(0, y - (thumb_size // 2)), track)
        first = target / track if track else 0.0
        self.command("moveto", str(first))

    def _redraw(self, _: tk.Event[Any] | None = None) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())

        self.create_rectangle(
            2,
            0,
            width - 2,
            height,
            fill=self.palette["panel_alt"],
            outline=self.palette["hairline"],
        )

        visible = max(0.05, self.last - self.first)
        thumb_size = max(24, int(height * visible))
        track = max(1, height - thumb_size)
        top = int(track * self.first)
        bottom = top + thumb_size
        self.thumb_top = top
        self.thumb_bottom = bottom

        self.create_rectangle(
            3,
            top + 2,
            width - 3,
            bottom - 2,
            fill="#596779",
            outline="#66778b",
        )


class CodexControlWindowsApp:
    AUTO_REFRESH_MS = 5 * 60 * 1000
    QUEUE_POLL_MS = 150

    def __init__(self, start_hidden: bool = False) -> None:
        self.account_store = AccountStore()
        self.snapshot_store = SnapshotStore()
        self.account_manager = CodexAccountManager()
        self.executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="codexcontrol")
        self.events: queue.Queue[tuple[Any, ...]] = queue.Queue()

        self.accounts: list[StoredAccount] = []
        self.runtime_states: dict[UUID, AccountRuntimeState] = {}
        self.nickname_drafts: dict[UUID, str] = {}
        self.selected_account_id: UUID | None = None
        self.active_identity: AuthBackedIdentity | None = None
        self.status_message: str | None = None
        self.is_refreshing_all = False
        self.is_adding_account = False
        self.reauthenticating_account_id: UUID | None = None
        self._group_refresh_pending = 0
        self._add_handle: ManagedLoginProcess | None = None
        self._reauth_handle: ManagedLoginProcess | None = None
        self._quitting = False
        self._resize_job: str | None = None
        self._last_render_width = 0
        self.start_hidden = start_hidden

        self.palette = {
            "bg": "#0a0f14",
            "shell": "#0f151c",
            "panel": "#151c24",
            "panel_alt": "#1b2430",
            "selected": "#122129",
            "text": "#edf2f7",
            "muted": "#93a0ae",
            "hairline": "#27313c",
            "accent": "#4fd1c5",
            "accent_soft": "#13373a",
            "accent_line": "#235155",
            "success": "#38d39f",
            "warning": "#f0b35b",
            "danger": "#ef7d72",
            "neutral": "#8090a1",
            "dark_icon": "#0c1218",
            "track": "#26323f",
        }

        self.root = tk.Tk()
        self.root.title("CodexControl")
        self.root.geometry("438x616")
        self.root.minsize(410, 500)
        self.root.configure(bg=self.palette["bg"])
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        self.search_var = tk.StringVar(master=self.root)
        self.root.bind("<Configure>", self._on_root_configure)

        self._configure_fonts()

        self.window_icon_images: list[ImageTk.PhotoImage] = []
        self.brand_icon_image: ImageTk.PhotoImage | None = None
        self._set_window_icon()

        self._configure_styles()
        self._build_ui()
        self.root.update_idletasks()
        self._apply_dark_title_bar()
        self._setup_tray_icon()
        self._load_initial_state()
        self._render()
        if self.start_hidden:
            self.hide_window()

        self.search_var.trace_add("write", lambda *_: self._render())
        self.root.after(self.QUEUE_POLL_MS, self._process_event_queue)
        self.root.after(800, self.refresh_all)
        self.root.after(self.AUTO_REFRESH_MS, self._auto_refresh_tick)

    def run(self) -> None:
        self.root.mainloop()

    def quit(self) -> None:
        self._quitting = True
        if self.tray_icon is not None:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()

    def show_window(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def hide_window(self) -> None:
        self.root.withdraw()

    def refresh_all(self) -> None:
        if not self.accounts or self.is_refreshing_all:
            return

        self.is_refreshing_all = True
        self._group_refresh_pending = len(self.accounts)
        for account in self.accounts:
            state = self.runtime_states.setdefault(account.id, AccountRuntimeState())
            state.is_loading = True
            self.runtime_states[account.id] = state
            self._submit_future(
                self.executor.submit(fetch_snapshot, account),
                "refresh_result",
                account.id,
                True,
            )
        self._render()

    def refresh_account(self, account: StoredAccount) -> None:
        state = self.runtime_states.setdefault(account.id, AccountRuntimeState())
        if state.is_loading:
            return

        state.is_loading = True
        self.runtime_states[account.id] = state
        self._submit_future(
            self.executor.submit(fetch_snapshot, account),
            "refresh_result",
            account.id,
            False,
        )
        self._render()

    def start_or_cancel_add_account(self) -> None:
        if self.is_adding_account:
            self.cancel_add_account()
        else:
            self.start_add_account()

    def start_add_account(self) -> None:
        if self.is_adding_account:
            return

        self.is_adding_account = True
        self.status_message = "Complete or cancel the Codex sign-in flow in your browser."
        self._add_handle = ManagedLoginProcess()
        self._submit_future(
            self.executor.submit(self.account_manager.add_managed_account, self._add_handle),
            "add_account_result",
        )
        self._render()

    def cancel_add_account(self) -> None:
        if not self.is_adding_account or self._add_handle is None:
            return

        self.status_message = "Cancelling account setup."
        self._add_handle.cancel()
        self._render()

    def reauthenticate(self, account: StoredAccount) -> None:
        if self.reauthenticating_account_id is not None:
            return

        self.reauthenticating_account_id = account.id
        self.status_message = f"Waiting for {account.display_name} to sign in again."
        self._reauth_handle = ManagedLoginProcess()
        self._submit_future(
            self.executor.submit(self.account_manager.reauthenticate, account, self._reauth_handle),
            "reauth_result",
            account.id,
        )
        self._render()

    def update_nickname(self, account_id: UUID) -> None:
        account = next((candidate for candidate in self.accounts if candidate.id == account_id), None)
        if account is None:
            return

        draft = self.nickname_drafts.get(account_id, "").strip()
        account.nickname = draft or None
        self.nickname_drafts[account_id] = draft
        account.updated_at = utc_now()
        self._persist_accounts_silently()
        self._render()

    def remove_account(self, account: StoredAccount) -> None:
        if not account.source.owns_files:
            self.status_message = "System accounts are auto-discovered and cannot be removed here."
            self._render()
            return

        confirmed = messagebox.askyesno(
            "Remove Account",
            f"{account.display_name} will be removed from CodexControl.",
            parent=self.root,
        )
        if not confirmed:
            return

        self.accounts = [candidate for candidate in self.accounts if candidate.id != account.id]
        self.runtime_states.pop(account.id, None)
        self.nickname_drafts.pop(account.id, None)
        try:
            self.account_manager.remove_managed_files_if_owned(account)
            self.account_store.save_accounts(self.accounts)
            self._ensure_selection()
            self.status_message = f"{account.display_name} removed."
        except CodexAccountManagerError as error:
            self.status_message = str(error)
        self._render()

    def switch_account(self, account: StoredAccount) -> None:
        if self._is_active_account(account):
            self.status_message = f"{account.display_name} is already the active Codex account."
            self._render()
            return

        try:
            result = self.account_manager.switch_active_account(account, self.accounts)
            if result.materialized_account is not None:
                self._replace_or_append_account(result.materialized_account)
            self._refresh_active_identity()
            self._load_initial_state()
            self.status_message = (
                f"Active account switched to {account.display_name}. "
                "Restarting Codex Desktop to apply the new session."
            )
            self._render()
            self.root.after(250, self._restart_codex_desktop)
        except CodexAccountManagerError as error:
            self.status_message = str(error)
            self._render()

    def _restart_codex_desktop(self) -> None:
        try:
            restart_codex_desktop()
        except CodexDesktopControlError as error:
            self.status_message = str(error)
            self._render()

    def open_folder(self, account: StoredAccount) -> None:
        os.startfile(account.codex_home_path)

    def _configure_styles(self) -> None:
        style = ttk.Style()
        if "clam" in style.theme_names():
            style.theme_use("clam")

    def _configure_fonts(self) -> None:
        families = {name.casefold(): name for name in tkfont.families(self.root)}

        def pick(candidates: list[str], fallback: str) -> str:
            for candidate in candidates:
                match = families.get(candidate.casefold())
                if match:
                    return match
            return fallback

        self.font_family_display = pick(
            [
                "Aptos Display",
                "Segoe UI Variable Display Semib",
                "Segoe UI Variable Display",
                "Bahnschrift SemiBold",
                "Segoe UI Semibold",
                "Segoe UI",
            ],
            "Segoe UI",
        )
        self.font_family_text = pick(
            [
                "Aptos",
                "Segoe UI Variable Text",
                "Segoe UI Variable Small",
                "Segoe UI",
            ],
            "Segoe UI",
        )
        self.font_family_mono = pick(
            [
                "Cascadia Code",
                "Consolas",
            ],
            "Consolas",
        )
        self.font_family_icon = pick(
            [
                "Segoe Fluent Icons",
                "Segoe MDL2 Assets",
            ],
            self.font_family_text,
        )

        self.fonts = {
            "title": (self.font_family_display, 15, "bold"),
            "headline": (self.font_family_display, 12, "bold"),
            "body": (self.font_family_text, 10),
            "body_small": (self.font_family_text, 9),
            "caption": (self.font_family_text, 8),
            "label": (self.font_family_text, 8, "bold"),
            "button": (self.font_family_text, 9, "bold"),
            "button_small": (self.font_family_text, 8, "bold"),
            "metric": (self.font_family_display, 12, "bold"),
            "mono": (self.font_family_mono, 8),
            "icon": (self.font_family_icon, 10),
            "icon_small": (self.font_family_icon, 9),
        }

        self.icons = {
            "search": "\ue721" if self.font_family_icon != self.font_family_text else "⌕",
            "add": "\ue710" if self.font_family_icon != self.font_family_text else "+",
            "refresh": "\ue72c" if self.font_family_icon != self.font_family_text else "↻",
            "folder": "\ue838" if self.font_family_icon != self.font_family_text else "⌂",
            "trash": "\ue74d" if self.font_family_icon != self.font_family_text else "×",
            "save": "\ue74e" if self.font_family_icon != self.font_family_text else "•",
            "spark": "\ue945" if self.font_family_icon != self.font_family_text else "•",
        }
        if self.font_family_icon == self.font_family_text:
            self.icons["search"] = "\u2315"
            self.icons["refresh"] = "\u21bb"
            self.icons["folder"] = "\u25a3"
            self.icons["trash"] = "\u2715"
            self.icons["save"] = "\u25cf"
            self.icons["spark"] = "\u2736"
        self.icons["metric_accounts"] = "\u25a6"
        self.icons["metric_live"] = "\u25c9"
        self.icons["metric_critical"] = "\u26a0"

    def _build_ui(self) -> None:
        outer = tk.Frame(self.root, bg=self.palette["bg"])
        outer.pack(fill="both", expand=True, padx=10, pady=10)

        self.shell = tk.Frame(
            outer,
            bg=self.palette["shell"],
            highlightthickness=1,
            highlightbackground=self.palette["hairline"],
            padx=10,
            pady=10,
        )
        self.shell.pack(fill="both", expand=True)

        header = tk.Frame(self.shell, bg=self.palette["shell"])
        header.pack(fill="x")

        header_top = tk.Frame(header, bg=self.palette["shell"])
        header_top.pack(fill="x")

        brand = tk.Frame(header_top, bg=self.palette["shell"])
        brand.pack(side="left", fill="x", expand=True)

        self.brand_icon_image = ImageTk.PhotoImage(self._create_icon_image("neutral", 26))
        brand_icon = tk.Label(
            brand,
            image=self.brand_icon_image,
            bg=self.palette["shell"],
            bd=0,
        )
        brand_icon.pack(side="left")

        brand_text = tk.Frame(brand, bg=self.palette["shell"])
        brand_text.pack(side="left", padx=(10, 0))

        title_row = tk.Frame(brand_text, bg=self.palette["shell"])
        title_row.pack(anchor="w")

        self.title_label = tk.Label(
            title_row,
            text="CodexControl",
            bg=self.palette["shell"],
            fg=self.palette["text"],
            font=self.fonts["title"],
        )
        self.title_label.pack(side="left")

        controls = tk.Frame(header_top, bg=self.palette["shell"])
        controls.pack(side="right")

        self.add_button = self._make_button(
            controls,
            text="Add",
            command=self.start_or_cancel_add_account,
            kind="surface",
            icon=self.icons["add"],
        )
        self.add_button.pack(side="left", padx=(0, 6))

        self.refresh_button = self._make_button(
            controls,
            text="Refresh",
            command=self.refresh_all,
            kind="surface",
            icon=self.icons["refresh"],
        )
        self.refresh_button.pack(side="left")

        self.subtitle_label = tk.Label(
            header,
            text="",
            bg=self.palette["shell"],
            fg=self.palette["muted"],
            font=self.fonts["body_small"],
            justify="left",
            anchor="w",
        )
        self.subtitle_label.pack(fill="x", pady=(8, 0))

        self.search_shell = tk.Frame(
            self.shell,
            bg=self.palette["panel"],
            highlightthickness=1,
            highlightbackground=self.palette["hairline"],
            padx=10,
            pady=8,
        )
        self.search_shell.pack(fill="x", pady=(12, 10))

        search_icon = tk.Label(
            self.search_shell,
            text=self.icons["search"],
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=self.fonts["icon"],
        )
        search_icon.pack(side="left", padx=(0, 8))

        self.search_entry = tk.Entry(
            self.search_shell,
            textvariable=self.search_var,
            relief="flat",
            bg=self.palette["panel"],
            fg=self.palette["text"],
            insertbackground=self.palette["text"],
            font=self.fonts["body"],
        )
        self.search_entry.pack(side="left", fill="x", expand=True)

        self.metrics_frame = tk.Frame(self.shell, bg=self.palette["shell"])
        self.metrics_frame.pack(fill="x", pady=(0, 8))

        list_shell = tk.Frame(self.shell, bg=self.palette["shell"])
        list_shell.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(
            list_shell,
            bg=self.palette["shell"],
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(side="left", fill="both", expand=True)

        scrollbar = DarkScrollbar(
            list_shell,
            command=self.canvas.yview,
            palette=self.palette,
            width=11,
        )
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.scrollbar = scrollbar

        self.cards_frame = tk.Frame(self.canvas, bg=self.palette["shell"])
        self.cards_window = self.canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")
        self.cards_frame.bind("<Configure>", self._on_cards_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _setup_tray_icon(self) -> None:
        self.tray_icon: pystray.Icon | None = None
        menu = pystray.Menu(
            pystray.MenuItem(
                lambda _: "Hide Window" if self.root.state() != "withdrawn" else "Show Window",
                lambda icon, item: self.root.after(0, self._toggle_window),
            ),
            pystray.MenuItem("Refresh All", lambda icon, item: self.root.after(0, self.refresh_all)),
            pystray.MenuItem("Add Account", lambda icon, item: self.root.after(0, self.start_add_account)),
            pystray.MenuItem("Quit", lambda icon, item: self.root.after(0, self.quit)),
        )
        self.tray_icon = pystray.Icon(
            "CodexControl",
            self._create_icon_image("neutral", 64),
            "CodexControl",
            menu,
        )
        self.tray_icon.run_detached()

    def _set_window_icon(self) -> None:
        self.window_icon_images = [
            ImageTk.PhotoImage(self._create_icon_image("neutral", size))
            for size in (16, 24, 32, 48, 64)
        ]
        self.root.iconphoto(True, *self.window_icon_images)

    def _toggle_window(self) -> None:
        if self.root.state() == "withdrawn":
            self.show_window()
        else:
            self.hide_window()

    def _load_initial_state(self) -> None:
        try:
            loaded_accounts = self.account_store.load_accounts()
            stored_accounts = [account for account in loaded_accounts if account.source is not StoredAccountSource.AMBIENT]
            discovered_accounts = self.account_manager.discover_managed_accounts(loaded_accounts)
            ambient_account = self.account_manager.discover_ambient_account(loaded_accounts)
            incoming_accounts = list(discovered_accounts)
            if ambient_account is not None:
                incoming_accounts.insert(0, ambient_account)

            self.accounts = self.account_store.merge(stored_accounts, incoming_accounts)
            if self.accounts != loaded_accounts:
                self.account_store.save_accounts(self.accounts)
        except Exception as error:
            self.status_message = str(error)
            self.accounts = []

        try:
            persisted = self.snapshot_store.load()
            valid_ids = {account.id for account in self.accounts}
            self.runtime_states = {
                account_id: AccountRuntimeState(snapshot=snapshot)
                for account_id, snapshot in persisted.items()
                if account_id in valid_ids
            }
        except Exception as error:
            self.status_message = str(error)
            self.runtime_states = {}

        for account in self.accounts:
            self.nickname_drafts[account.id] = account.nickname or ""

        self._ensure_selection()
        self._refresh_active_identity()

    def _submit_future(self, future: Future[Any], event_name: str, *metadata: Any) -> None:
        def callback(completed: Future[Any]) -> None:
            try:
                result = completed.result()
                self.events.put((event_name, *metadata, result, None))
            except Exception as error:
                self.events.put((event_name, *metadata, None, error))

        future.add_done_callback(callback)

    def _process_event_queue(self) -> None:
        processed = 0
        while processed < 100:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break

            processed += 1
            name = event[0]
            if name == "refresh_result":
                _, account_id, from_group, snapshot, error = event
                self._apply_refresh_result(account_id, from_group, snapshot, error)
            elif name == "add_account_result":
                _, account, error = event
                self._apply_add_account_result(account, error)
            elif name == "reauth_result":
                _, account_id, account, error = event
                self._apply_reauth_result(account_id, account, error)

        if not self._quitting:
            self.root.after(self.QUEUE_POLL_MS, self._process_event_queue)

    def _apply_refresh_result(
        self,
        account_id: UUID,
        from_group: bool,
        snapshot: AccountUsageSnapshot | None,
        error: Exception | None,
    ) -> None:
        state = self.runtime_states.setdefault(account_id, AccountRuntimeState())
        state.is_loading = False

        if snapshot is not None:
            state.snapshot = snapshot
            state.error_message = None
            self.runtime_states[account_id] = state
            self._update_account_metadata(account_id, snapshot)
        else:
            state.snapshot = None
            state.error_message = str(error) if error else "Unknown refresh error."
            self.runtime_states[account_id] = state

        if from_group:
            self._group_refresh_pending = max(0, self._group_refresh_pending - 1)
            if self._group_refresh_pending == 0:
                self.is_refreshing_all = False

        self._persist_snapshots_silently()
        self._render()

    def _apply_add_account_result(self, account: StoredAccount | None, error: Exception | None) -> None:
        self.is_adding_account = False
        self._add_handle = None

        if account is not None:
            self.accounts = self.account_store.merge(self.accounts, [account])
            self.account_store.save_accounts(self.accounts)
            matched = next((candidate for candidate in self.accounts if candidate.matches(account)), account)
            self.selected_account_id = matched.id
            self.nickname_drafts[matched.id] = matched.nickname or ""
            self.status_message = f"{matched.display_name} added."
            self.refresh_account(matched)
        else:
            self.status_message = str(error) if error else "Account setup failed."
            self._render()

    def _apply_reauth_result(
        self,
        original_account_id: UUID,
        account: StoredAccount | None,
        error: Exception | None,
    ) -> None:
        self.reauthenticating_account_id = None
        self._reauth_handle = None

        if account is not None:
            self.accounts = self.account_store.merge(self.accounts, [account])
            self.account_store.save_accounts(self.accounts)
            self.status_message = f"{account.display_name} reauthenticated."
            refreshed = next((candidate for candidate in self.accounts if candidate.id == original_account_id), None)
            if refreshed is not None:
                self.refresh_account(refreshed)
            else:
                self._render()
            return

        self.status_message = str(error) if error else "Reauthentication failed."
        self._render()

    def _update_account_metadata(self, account_id: UUID, snapshot: AccountUsageSnapshot) -> None:
        account = next((candidate for candidate in self.accounts if candidate.id == account_id), None)
        if account is None:
            return

        did_change = False
        normalized_email = snapshot.email.strip().lower() if snapshot.email else None
        if normalized_email and account.email_hint != normalized_email:
            account.email_hint = normalized_email
            did_change = True

        if snapshot.provider_account_id and account.provider_account_id != snapshot.provider_account_id:
            account.provider_account_id = snapshot.provider_account_id
            did_change = True

        if did_change:
            self._persist_accounts_silently()

    def _persist_accounts_silently(self) -> None:
        try:
            self.account_store.save_accounts(self.accounts)
        except Exception as error:
            self.status_message = str(error)

    def _persist_snapshots_silently(self) -> None:
        snapshots = {
            account_id: state.snapshot
            for account_id, state in self.runtime_states.items()
            if state.snapshot is not None
        }
        try:
            self.snapshot_store.save(snapshots)
        except Exception as error:
            self.status_message = str(error)

    def _ensure_selection(self) -> None:
        valid_ids = {account.id for account in self.accounts}
        if self.selected_account_id in valid_ids:
            return
        self.selected_account_id = self.filtered_accounts[0].id if self.filtered_accounts else None

    def _refresh_active_identity(self) -> None:
        self.active_identity = self.account_manager.load_active_identity()

    def _replace_or_append_account(self, account: StoredAccount) -> None:
        replaced = False
        for index, existing in enumerate(self.accounts):
            if existing.id == account.id or existing.matches(account):
                self.accounts[index] = account
                replaced = True
                break
        if not replaced:
            self.accounts.append(account)
        self._persist_accounts_silently()

    def _is_active_account(self, account: StoredAccount) -> bool:
        identity = self.active_identity
        if identity is None:
            return False

        account_subject = normalize_identifier(account.auth_subject)
        identity_subject = normalize_identifier(identity.auth_subject)
        if account_subject and identity_subject and account_subject == identity_subject:
            return True

        account_email = normalize_identifier(account.email_hint)
        identity_email = normalize_identifier(identity.email)
        if account_email and identity_email and account_email == identity_email:
            return True

        account_provider = normalize_identifier(account.provider_account_id)
        identity_provider = normalize_identifier(identity.provider_account_id)
        if account_provider and identity_provider and account_provider == identity_provider:
            return True

        return False

    def _can_switch_account(self, account: StoredAccount) -> bool:
        if self._is_active_account(account):
            return False
        return (Path(account.codex_home_path) / "auth.json").exists()

    def _auto_refresh_tick(self) -> None:
        if not self._quitting:
            self.refresh_all()
            self.root.after(self.AUTO_REFRESH_MS, self._auto_refresh_tick)

    @property
    def filtered_accounts(self) -> list[StoredAccount]:
        query = self.search_var.get().strip().lower()
        accounts = self.accounts
        if query:
            accounts = [
                account
                for account in self.accounts
                if any(
                    query in candidate.lower()
                    for candidate in (
                        account.display_name,
                        account.email_hint or "",
                        account.auth_subject or "",
                        account.provider_account_id or "",
                        account.codex_home_path,
                    )
                )
            ]

        def key(account: StoredAccount):
            snapshot = self.runtime_states.get(account.id, AccountRuntimeState()).snapshot
            priority = snapshot.sort_priority if snapshot else 2
            usable = 0 if snapshot and snapshot.has_usable_quota_now else 1
            remaining = -(snapshot.lowest_remaining_percent if snapshot else -1)
            reset_at = snapshot.next_reset_at.timestamp() if snapshot and snapshot.next_reset_at else float("inf")
            name = account.display_name.casefold()
            return priority, usable, remaining, reset_at, name

        return sorted(accounts, key=key)

    @property
    def account_count(self) -> int:
        return len(self.accounts)

    @property
    def low_quota_count(self) -> int:
        total = 0
        for account in self.accounts:
            snapshot = self.runtime_states.get(account.id, AccountRuntimeState()).snapshot
            if snapshot and snapshot.lowest_remaining_percent <= 20:
                total += 1
        return total

    @property
    def usable_quota_count(self) -> int:
        total = 0
        for account in self.accounts:
            snapshot = self.runtime_states.get(account.id, AccountRuntimeState()).snapshot
            if snapshot and snapshot.has_usable_quota_now:
                total += 1
        return total

    @property
    def menu_bar_quota_state(self) -> str:
        if not self.accounts:
            return "empty"
        if self.usable_quota_count > 0:
            return "available"

        exhausted_count = 0
        for account in self.accounts:
            snapshot = self.runtime_states.get(account.id, AccountRuntimeState()).snapshot
            if snapshot is not None and not snapshot.has_usable_quota_now:
                exhausted_count += 1

        if exhausted_count == self.account_count:
            return "unavailable"
        return "unresolved"

    def _render(self) -> None:
        self.subtitle_label.configure(
            text=self._header_status_text(),
            wraplength=self._header_wrap_width(),
        )
        self.add_button.set_text("Cancel" if self.is_adding_account else "Add")
        self.add_button.set_icon(self.icons["trash"] if self.is_adding_account else self.icons["add"])
        self.add_button.set_theme(self._button_theme("accent" if self.is_adding_account else "surface"))
        self.refresh_button.set_enabled(not self.is_refreshing_all)
        self._render_metrics()
        self._render_cards()
        self._update_tray()

    def _render_metrics(self) -> None:
        for child in self.metrics_frame.winfo_children():
            child.destroy()

        metrics = [
            ("Accounts", str(self.account_count), self.icons["metric_accounts"], self.palette["neutral"]),
            ("Live", str(self.usable_quota_count), self.icons["metric_live"], self.palette["success"]),
            ("Critical", str(self.low_quota_count), self.icons["metric_critical"], self.palette["warning"]),
        ]
        for column in range(3):
            self.metrics_frame.grid_columnconfigure(column, weight=1, uniform="metrics")

        for index, (label, value, icon, tone) in enumerate(metrics):
            tile = self._build_metric_tile(self.metrics_frame, label, value, icon, tone)
            tile.grid(row=0, column=index, sticky="nsew", padx=(0, 6 if index < len(metrics) - 1 else 0))

    def _build_metric_tile(
        self,
        parent: tk.Widget,
        label: str,
        value: str,
        icon: str,
        tone: str,
    ) -> tk.Frame:
        tile = tk.Frame(
            parent,
            bg=self.palette["panel"],
            highlightthickness=1,
            highlightbackground=self.palette["hairline"],
            padx=10,
            pady=9,
        )

        top = tk.Frame(tile, bg=self.palette["panel"])
        top.pack(fill="x")

        badge = tk.Frame(
            top,
            bg=self.palette["panel_alt"],
            highlightthickness=1,
            highlightbackground=self.palette["hairline"],
            width=24,
            height=24,
        )
        badge.pack(side="left")
        badge.pack_propagate(False)

        tk.Label(
            badge,
            text=icon,
            bg=self.palette["panel_alt"],
            fg=tone,
            font=self.fonts["label"],
        ).pack(expand=True)

        tk.Label(
            top,
            text=label,
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        ).pack(side="left", padx=(8, 0))

        tk.Label(
            tile,
            text=value,
            bg=self.palette["panel"],
            fg=self.palette["text"],
            font=self.fonts["metric"],
        ).pack(anchor="w", pady=(8, 0))
        return tile

    def _render_cards(self) -> None:
        for child in self.cards_frame.winfo_children():
            child.destroy()

        accounts = self.filtered_accounts
        if not accounts:
            self._render_empty_state()
            return

        columns = self._cards_column_count()
        pending: list[StoredAccount] = []

        for account in accounts:
            if columns > 1 and self.selected_account_id == account.id:
                if pending:
                    self._render_card_row(pending, span_all=False)
                    pending = []
                self._render_card_row([account], span_all=True)
                continue

            pending.append(account)
            if len(pending) == columns:
                self._render_card_row(pending, span_all=False)
                pending = []

        if pending:
            self._render_card_row(pending, span_all=False)

    def _render_card_row(self, accounts: list[StoredAccount], span_all: bool) -> None:
        row = tk.Frame(self.cards_frame, bg=self.palette["shell"])
        row.pack(fill="x", pady=(0, 8))

        if span_all:
            card = self._build_account_card(
                row,
                accounts[0],
                width_hint=self._card_width(self._cards_column_count()),
            )
            card.pack(fill="x")
            return

        row_gap = self._card_gap()
        row_count = len(accounts)
        for index, account in enumerate(accounts):
            span = self._cards_column_count() if row_count == 1 else 1
            card = self._build_account_card(
                row,
                account,
                width_hint=self._card_width(span),
            )
            card.pack(side="left", fill="both", expand=True)
            if index < row_count - 1:
                tk.Frame(row, bg=self.palette["shell"], width=row_gap).pack(side="left")

    def _render_empty_state(self) -> None:
        panel = tk.Frame(
            self.cards_frame,
            bg=self.palette["panel"],
            highlightthickness=1,
            highlightbackground=self.palette["hairline"],
            padx=14,
            pady=14,
        )
        panel.pack(fill="x")

        title = "No Accounts" if not self.search_var.get().strip() else "No Matches"
        message = (
            "Add a Codex account to start tracking quota."
            if not self.accounts
            else "No accounts match your current search."
        )
        tk.Label(
            panel,
            text=title,
            bg=self.palette["panel"],
            fg=self.palette["text"],
            font=self.fonts["headline"],
        ).pack(anchor="w")
        tk.Label(
            panel,
            text=message,
            bg=self.palette["panel"],
            fg=self.palette["muted"],
            font=self.fonts["body_small"],
            wraplength=self._wrap_width(),
            justify="left",
        ).pack(anchor="w", pady=(6, 0))

    def _build_account_card(self, parent: tk.Widget, account: StoredAccount, width_hint: int) -> tk.Frame:
        state = self.runtime_states.get(account.id, AccountRuntimeState())
        is_selected = self.selected_account_id == account.id
        is_active = self._is_active_account(account)
        is_compact = width_hint <= 430
        card_bg = self.palette["selected"] if is_selected else self.palette["panel"]
        border = self.palette["accent_line"] if is_selected else self.palette["hairline"]
        text_width = max(150, width_hint - 156)

        card = tk.Frame(
            parent,
            bg=card_bg,
            highlightthickness=1,
            highlightbackground=border,
            padx=8,
            pady=8,
        )
        self._bind_click(card, lambda _: self._toggle_selection(account.id))

        header = tk.Frame(card, bg=card_bg)
        header.pack(fill="x")
        self._bind_click(header, lambda _: self._toggle_selection(account.id))

        title_wrap = tk.Frame(header, bg=card_bg)
        title_wrap.pack(side="left", fill="x", expand=True)
        self._bind_click(title_wrap, lambda _: self._toggle_selection(account.id))

        title_row = tk.Frame(title_wrap, bg=card_bg)
        title_row.pack(fill="x")
        self._bind_click(title_row, lambda _: self._toggle_selection(account.id))

        title = tk.Label(
            title_row,
            text=self._ellipsize(account.display_name, self.fonts["headline"], text_width),
            bg=card_bg,
            fg=self.palette["text"],
            font=self.fonts["headline"],
        )
        title.pack(side="left")
        self._bind_click(title, lambda _: self._toggle_selection(account.id))

        if is_active:
            active_chip = self._make_inline_chip(
                title_row,
                "Active",
                self.palette["accent_soft"],
                self.palette["accent"],
            )
            active_chip.pack(side="left", padx=(8, 0))
            self._bind_click(active_chip, lambda _: self._toggle_selection(account.id))

        if account.source is StoredAccountSource.AMBIENT:
            system_chip = self._make_inline_chip(
                title_row,
                "System",
                self.palette["panel_alt"],
                self.palette["muted"],
            )
            system_chip.pack(side="left", padx=(8, 0))
            self._bind_click(system_chip, lambda _: self._toggle_selection(account.id))

        meta_row = tk.Frame(title_wrap, bg=card_bg)
        meta_row.pack(fill="x", pady=(4, 0))
        self._bind_click(meta_row, lambda _: self._toggle_selection(account.id))

        meta = tk.Label(
            meta_row,
            text=self._ellipsize(account.email_hint or account.source.display_name, self.fonts["caption"], text_width),
            bg=card_bg,
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        )
        meta.pack(side="left")
        self._bind_click(meta, lambda _: self._toggle_selection(account.id))

        right = tk.Frame(header, bg=card_bg)
        right.pack(side="right", padx=(8, 0))

        if state.snapshot is not None:
            self._make_inline_chip(
                right,
                state.snapshot.plan_display_name,
                self.palette["panel_alt"],
                self.palette["muted"],
            ).pack(anchor="e")

        status_row = tk.Frame(right, bg=card_bg)
        status_row.pack(anchor="e", pady=(4 if state.snapshot is not None else 0, 0))

        status_dot = tk.Canvas(status_row, width=7, height=7, bg=card_bg, highlightthickness=0)
        status_dot.pack(side="left", padx=(0, 6))
        status_dot.create_oval(0, 0, 7, 7, fill=self._status_color(state), outline="")

        tk.Label(
            status_row,
            text=self._status_value_text(state),
            bg=card_bg,
            fg=self.palette["text"],
            font=self.fonts["headline"],
        ).pack(side="left")

        if not is_active and self._can_switch_account(account):
            quick_actions = tk.Frame(right, bg=card_bg)
            quick_actions.pack(anchor="e", pady=(8, 0))
            self._make_button(
                quick_actions,
                "Switch",
                lambda: self.switch_account(account),
                kind="surface_tiny",
                icon=self.icons["add"],
            ).pack(anchor="e")

        summary = tk.Frame(card, bg=card_bg)
        summary.pack(fill="x", pady=(8, 0))
        self._bind_click(summary, lambda _: self._toggle_selection(account.id))

        if state.snapshot is not None and state.snapshot.has_quota_windows:
            summary_panel = tk.Frame(
                summary,
                bg=self.palette["panel_alt"],
                highlightthickness=1,
                highlightbackground=self.palette["hairline"],
                padx=9,
                pady=8,
            )
            summary_panel.pack(fill="x")
            windows = [candidate for candidate in (state.snapshot.primary_window, state.snapshot.secondary_window) if candidate]
            for index, window in enumerate(windows):
                strip = self._build_window_strip(summary_panel, window, width_hint)
                strip.pack(fill="x")
                self._bind_click(strip, lambda _, account_id=account.id: self._toggle_selection(account_id))
                if index < len(windows) - 1:
                    divider = tk.Frame(summary_panel, bg=self.palette["hairline"], height=1)
                    divider.pack(fill="x", pady=7)
        else:
            summary_panel = tk.Frame(
                summary,
                bg=self.palette["panel_alt"],
                highlightthickness=1,
                highlightbackground=self.palette["hairline"],
                padx=9,
                pady=8,
            )
            summary_panel.pack(fill="x")
            message = tk.Label(
                summary_panel,
                text=self._inline_message(state),
                bg=self.palette["panel_alt"],
                fg=self._status_color(state),
                font=self.fonts["body_small"],
                justify="left",
                wraplength=self._card_wrap_width(width_hint),
            )
            message.pack(anchor="w")
            self._bind_click(message, lambda _: self._toggle_selection(account.id))

        if not is_selected:
            return card

        divider = tk.Frame(card, bg=self.palette["hairline"], height=1)
        divider.pack(fill="x", pady=9)

        actions = tk.Frame(card, bg=card_bg)
        actions.pack(fill="x")

        button_specs: list[tuple[str, Callable[[], None], str, str | None]] = [
            ("Refresh", lambda: self.refresh_account(account), "surface_small", self.icons["refresh"]),
        ]
        if is_active:
            button_specs.append(("Active", lambda: None, "surface_small", self.icons["spark"]))
        elif self._can_switch_account(account):
            button_specs.append(("Switch", lambda: self.switch_account(account), "surface_small", self.icons["add"]))
        button_specs.append(("Reauth", lambda: self.reauthenticate(account), "surface_small", self.icons["spark"]))
        button_specs.append(("Folder", lambda: self.open_folder(account), "surface_small", self.icons["folder"]))
        if account.source.owns_files:
            button_specs.append(("Remove", lambda: self.remove_account(account), "danger_small", self.icons["trash"]))

        self._render_action_buttons(actions, button_specs, width_hint)

        if not account.source.owns_files:
            tk.Label(
                actions,
                text="System account",
                bg=card_bg,
                fg=self.palette["muted"],
                font=self.fonts["body_small"],
            ).pack(anchor="w", pady=(8, 0))

        if state.snapshot is not None:
            actions_meta = tk.Frame(actions, bg=card_bg)
            actions_meta.pack(fill="x", pady=(8, 0))
            tk.Label(
                actions_meta,
                text=state.snapshot.updated_at.astimezone().strftime("Updated %H:%M"),
                bg=card_bg,
                fg=self.palette["muted"],
                font=self.fonts["caption"],
            ).pack(anchor="e")

        label_row = tk.Frame(card, bg=card_bg)
        label_row.pack(fill="x", pady=(9, 0))

        draft_var = tk.StringVar(value=self.nickname_drafts.get(account.id, account.nickname or ""))

        def sync_draft(*_: Any) -> None:
            self.nickname_drafts[account.id] = draft_var.get()

        draft_var.trace_add("write", sync_draft)

        label_shell = tk.Frame(
            label_row,
            bg=self.palette["panel"],
            highlightthickness=1,
            highlightbackground=self.palette["hairline"],
            padx=8,
            pady=5,
        )
        if is_compact:
            label_shell.pack(fill="x")
        else:
            label_shell.pack(side="left", fill="x", expand=True)

        label_entry = tk.Entry(
            label_shell,
            textvariable=draft_var,
            relief="flat",
            bg=self.palette["panel"],
            fg=self.palette["text"],
            insertbackground=self.palette["text"],
            font=self.fonts["body_small"],
        )
        label_entry.pack(fill="x")

        save_button = self._make_button(
            label_row,
            "Save",
            lambda: self.update_nickname(account.id),
            kind="surface_small",
            icon=self.icons["save"],
        )
        if is_compact:
            save_button.pack(anchor="e", pady=(8, 0))
        else:
            save_button.pack(side="left", padx=(8, 0))

        footer = tk.Frame(card, bg=card_bg)
        footer.pack(fill="x", pady=(9, 0))

        tk.Label(
            footer,
            text=self._ellipsize(self._short_path(account.codex_home_path), self.fonts["mono"], self._card_wrap_width(width_hint)),
            bg=card_bg,
            fg=self.palette["muted"],
            font=self.fonts["mono"],
        ).pack(anchor="w")

        if state.snapshot is not None and state.snapshot.next_reset_at is not None:
            tk.Label(
                footer,
                text=f"Next reset {state.snapshot.next_reset_at.astimezone().strftime('%b %d %H:%M')}",
                bg=card_bg,
                fg=self.palette["muted"],
                font=self.fonts["caption"],
            ).pack(anchor="w", pady=(4, 0))

        return card

    def _render_action_buttons(
        self,
        parent: tk.Widget,
        button_specs: list[tuple[str, Callable[[], None], str, str | None]],
        width_hint: int,
    ) -> None:
        max_per_row = 2 if width_hint < 370 else 3 if width_hint < 560 else 5
        for start in range(0, len(button_specs), max_per_row):
            row = tk.Frame(parent, bg=parent.cget("bg"))
            row.pack(fill="x", pady=(0, 6 if start + max_per_row < len(button_specs) else 0))
            current = button_specs[start:start + max_per_row]
            for index, (text, command, kind, icon) in enumerate(current):
                button = self._make_button(row, text, command, kind, icon=icon)
                button.pack(side="left")
                if index < len(current) - 1:
                    tk.Frame(row, bg=parent.cget("bg"), width=6).pack(side="left")

    def _build_window_strip(self, parent: tk.Widget, window: Any, width_hint: int) -> tk.Frame:
        strip = tk.Frame(parent, bg=self.palette["panel_alt"])

        header = tk.Frame(strip, bg=self.palette["panel_alt"])
        header.pack(fill="x")
        tk.Label(
            header,
            text=window.short_label.upper(),
            bg=self.palette["panel_alt"],
            fg=self._quota_color(window.remaining_percent),
            font=self.fonts["label"],
        ).pack(side="left")
        tk.Label(
            header,
            text=window.display_name,
            bg=self.palette["panel_alt"],
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            header,
            text=f"{window.remaining_percent:.0f}%",
            bg=self.palette["panel_alt"],
            fg=self.palette["text"],
            font=self.fonts["headline"],
        ).pack(side="right")

        bar = tk.Canvas(strip, height=5, bg=self.palette["panel_alt"], highlightthickness=0, bd=0)
        bar.pack(fill="x", pady=(8, 6))
        bar_width = self._card_progress_width(width_hint)
        bar.create_rectangle(0, 0, bar_width, 5, fill=self.palette["track"], outline="")
        fill_width = max(0, min(bar_width, int(bar_width * (window.remaining_percent / 100.0))))
        bar.create_rectangle(0, 0, fill_width, 5, fill=self._quota_color(window.remaining_percent), outline="")

        footer = tk.Frame(strip, bg=self.palette["panel_alt"])
        footer.pack(fill="x")
        tk.Label(
            footer,
            text=f"Used {window.used_percent:.0f}%",
            bg=self.palette["panel_alt"],
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        ).pack(side="left")
        tk.Label(
            footer,
            text=window.compact_reset_at_display or "Reset unknown",
            bg=self.palette["panel_alt"],
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        ).pack(side="right")
        return strip

    def _build_window_tile(self, parent: tk.Widget, card_bg: str, window: Any) -> tk.Frame:
        tile = tk.Frame(
            parent,
            bg=self.palette["panel_alt"],
            highlightthickness=1,
            highlightbackground=self.palette["hairline"],
            padx=10,
            pady=8,
        )

        header = tk.Frame(tile, bg=self.palette["panel_alt"])
        header.pack(fill="x")
        tk.Label(
            header,
            text=window.short_label.upper(),
            bg=self.palette["panel_alt"],
            fg=self._quota_color(window.remaining_percent),
            font=self.fonts["label"],
        ).pack(side="left")
        tk.Label(
            header,
            text=window.display_name,
            bg=self.palette["panel_alt"],
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        ).pack(side="left", padx=(8, 0))
        tk.Label(
            header,
            text=f"{window.remaining_percent:.0f}%",
            bg=self.palette["panel_alt"],
            fg=self.palette["text"],
            font=self.fonts["headline"],
        ).pack(side="right")

        bar = tk.Canvas(tile, height=6, bg=self.palette["panel_alt"], highlightthickness=0, bd=0)
        bar.pack(fill="x", pady=(8, 7))
        bar_width = self._progress_width()
        bar.create_rectangle(0, 0, bar_width, 6, fill=self.palette["track"], outline="")
        fill_width = max(0, min(bar_width, int(bar_width * (window.remaining_percent / 100.0))))
        bar.create_rectangle(0, 0, fill_width, 6, fill=self._quota_color(window.remaining_percent), outline="")

        footer = tk.Frame(tile, bg=self.palette["panel_alt"])
        footer.pack(fill="x")
        tk.Label(
            footer,
            text=f"Used {window.used_percent:.0f}%",
            bg=self.palette["panel_alt"],
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        ).pack(side="left")
        reset_text = window.compact_reset_at_display or "Reset unknown"
        tk.Label(
            footer,
            text=reset_text,
            bg=self.palette["panel_alt"],
            fg=self.palette["muted"],
            font=self.fonts["caption"],
        ).pack(side="right")
        return tile

    def _toggle_selection(self, account_id: UUID) -> None:
        self.selected_account_id = None if self.selected_account_id == account_id else account_id
        self._render()

    def _header_status_text(self) -> str:
        if self.status_message:
            return self.status_message
        if self.low_quota_count > 0:
            return f"{self.account_count} accounts, {self.low_quota_count} critical"
        return f"{self.account_count} accounts"

    def _status_text(self, state: AccountRuntimeState) -> str:
        if state.is_loading:
            return "Syncing"
        if state.error_message:
            return "Attention"
        if state.snapshot is None:
            return "Pending"
        if state.snapshot.has_usable_quota_now:
            return "Available"
        if state.snapshot.is_quota_blocked:
            return "Blocked"
        return "Limited"

    def _status_value_text(self, state: AccountRuntimeState) -> str:
        if state.snapshot is not None:
            return f"{state.snapshot.lowest_remaining_percent:.0f}%"
        if state.is_loading:
            return "..."
        return "--"

    def _inline_message(self, state: AccountRuntimeState) -> str:
        if state.is_loading:
            return "Refreshing live quota data..."
        if state.error_message:
            return state.error_message
        if state.snapshot is None:
            return "Waiting for data."
        if state.snapshot.is_quota_blocked:
            return "Quota reached."
        return "No quota data."

    def _status_color(self, state: AccountRuntimeState) -> str:
        if state.error_message:
            return self.palette["warning"]
        if state.is_loading:
            return self.palette["neutral"]
        if state.snapshot is None:
            return self.palette["neutral"]
        return self._quota_color(state.snapshot.lowest_remaining_percent)

    def _quota_color(self, remaining: float) -> str:
        if remaining <= 10:
            return self.palette["danger"]
        if remaining <= 20:
            return self.palette["warning"]
        return self.palette["success"]

    def _make_button(
        self,
        parent: tk.Widget,
        text: str,
        command: Callable[[], None],
        kind: str,
        icon: str | None = None,
    ) -> RoundedButton:
        button = RoundedButton(
            parent,
            text=text,
            command=command,
            theme=self._button_theme(kind),
            font=self._button_font(kind),
            icon=icon,
            icon_font=self.fonts["icon_small"],
            radius=self._button_radius(kind),
            pad_x=self._button_pad(kind)[0],
            pad_y=self._button_pad(kind)[1],
        )
        return button

    def _button_theme(self, kind: str) -> RoundedButtonTheme:
        if kind == "accent":
            return RoundedButtonTheme(
                bg=self.palette["accent_soft"],
                fg=self.palette["accent"],
                hover="#184247",
                border=self.palette["accent_line"],
                disabled_bg=self.palette["panel_alt"],
                disabled_fg=self.palette["neutral"],
            )
        if kind == "danger_small":
            return RoundedButtonTheme(
                bg="#351d21",
                fg=self.palette["danger"],
                hover="#46262c",
                border="#5a3338",
                disabled_bg=self.palette["panel_alt"],
                disabled_fg=self.palette["neutral"],
            )
        return RoundedButtonTheme(
            bg=self.palette["panel_alt"],
            fg=self.palette["text"],
            hover="#232d39",
            border=self.palette["hairline"],
            disabled_bg=self.palette["panel_alt"],
            disabled_fg=self.palette["neutral"],
        )

    def _button_font(self, kind: str) -> tuple[str, int] | tuple[str, int, str]:
        if kind in {"surface_small", "danger_small", "surface_tiny"}:
            return self.fonts["button_small"]
        return self.fonts["button"]

    def _button_radius(self, kind: str) -> int:
        if kind == "surface_tiny":
            return 9
        if kind in {"surface_small", "danger_small"}:
            return 10
        return 11

    def _button_pad(self, kind: str) -> tuple[int, int]:
        if kind == "surface_tiny":
            return 8, 5
        if kind in {"surface_small", "danger_small"}:
            return 10, 6
        return 12, 7

    def _make_inline_chip(self, parent: tk.Widget, text: str, bg: str, fg: str) -> tk.Frame:
        chip = tk.Frame(parent, bg=bg, padx=7, pady=3)
        label = tk.Label(chip, text=text, bg=bg, fg=fg, font=self.fonts["label"])
        label.pack()
        return chip

    def _update_tray(self) -> None:
        if self.tray_icon is None:
            return

        state = self.menu_bar_quota_state
        self.tray_icon.icon = self._create_icon_image(state, 64)
        self.tray_icon.title = self._header_status_text()
        try:
            self.tray_icon.update_menu()
        except Exception:
            pass

    def _create_icon_image(self, state: str, size: int) -> Image.Image:
        color_map = {
            "available": self.palette["success"],
            "unavailable": self.palette["danger"],
            "unresolved": self.palette["neutral"],
            "empty": self.palette["neutral"],
            "neutral": self.palette["accent"],
        }
        accent = color_map.get(state, self.palette["accent"])
        return build_orbit_dial_icon(
            size,
            accent=accent,
            core="#ff4a4a",
            panel_fill=self.palette["panel"],
            panel_fill_end=self.palette["bg"],
            dark=self.palette["dark_icon"],
            border=self.palette["hairline"],
        )

    def _short_path(self, path: str) -> str:
        if len(path) <= 34:
            return path
        return f"...{path[-31:]}"

    def _header_wrap_width(self) -> int:
        return max(220, self.shell.winfo_width() - 24)

    def _cards_available_width(self) -> int:
        return max(320, self.canvas.winfo_width() - 4)

    def _card_gap(self) -> int:
        return 10

    def _cards_column_count(self) -> int:
        return 2 if self._cards_available_width() >= 860 else 1

    def _card_width(self, span: int = 1) -> int:
        columns = self._cards_column_count()
        available = self._cards_available_width()
        if span >= columns:
            return available
        total_gap = self._card_gap() * (columns - 1)
        column_width = max(240, int((available - total_gap) / columns))
        return column_width

    def _card_wrap_width(self, width_hint: int) -> int:
        return max(180, width_hint - 58)

    def _card_progress_width(self, width_hint: int) -> int:
        return max(132, width_hint - 74)

    def _wrap_width(self) -> int:
        return self._card_wrap_width(self._cards_available_width())

    def _progress_width(self) -> int:
        return self._card_progress_width(self._cards_available_width())

    def _is_compact_card_layout(self) -> bool:
        return self.canvas.winfo_width() <= 420

    def _ellipsize(
        self,
        text: str,
        font_spec: tuple[str, int] | tuple[str, int, str],
        max_width: int,
    ) -> str:
        font = tkfont.Font(font=font_spec)
        if font.measure(text) <= max_width:
            return text

        ellipsis = "..."
        truncated = text
        while truncated and font.measure(truncated + ellipsis) > max_width:
            truncated = truncated[:-1]
        return (truncated or text[:1]) + ellipsis

    def _on_root_configure(self, event: tk.Event[Any]) -> None:
        if event.widget is not self.root:
            return

        if event.width == self._last_render_width:
            return

        self._last_render_width = event.width
        if self._resize_job is not None:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(90, self._render_after_resize)

    def _render_after_resize(self) -> None:
        self._resize_job = None
        self._render()

    def _apply_dark_title_bar(self) -> None:
        if os.name != "nt":
            return

        try:
            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            if not hwnd:
                hwnd = self.root.winfo_id()
            value = ctypes.c_int(1)
            for attribute in (20, 19):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd,
                    attribute,
                    ctypes.byref(value),
                    ctypes.sizeof(value),
                )
        except Exception:
            pass

    def _on_cards_configure(self, event: tk.Event[tk.Widget]) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event: tk.Event[tk.Widget]) -> None:
        self.canvas.itemconfigure(self.cards_window, width=event.width)

    def _on_mousewheel(self, event: tk.Event[tk.Widget]) -> None:
        if event.delta:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _bind_click(self, widget: tk.Widget, callback: Callable[[tk.Event[Any]], None]) -> None:
        widget.bind("<Button-1>", callback)


def main(argv: list[str] | None = None) -> None:
    arguments = list(sys.argv[1:] if argv is None else argv)
    start_hidden = any(argument.lower() in {"--hidden", "/hidden"} for argument in arguments)
    app = CodexControlWindowsApp(start_hidden=start_hidden)
    app.run()
