from __future__ import annotations

import calendar
import sys
import tkinter as tk
from datetime import date, datetime, timedelta
from pathlib import Path
from tkinter import messagebox

from .storage import MAX_HABITS, Habit, Store
from .theme import DISPLAY_FONT, THEMES, UI_FONT, Theme
from .widgets import (
    HabitCard,
    HeatmapCanvas,
    PillButton,
    PreferenceHabitRow,
    SlimScrollbar,
    ThemeChip,
    rounded_rect,
)


def main() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "span.habits.desktop"
            )
        except (AttributeError, OSError):
            pass
    app = SpanApp()
    try:
        app.run()
    finally:
        app.close()


def resource_path(relative: str) -> Path:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return root / relative


class SpanApp:
    MIN_WIDTH = 920
    MIN_HEIGHT = 640
    TITLEBAR_HEIGHT = 42

    def __init__(self, store: Store | None = None) -> None:
        self.store = store or Store()
        self._closing = False
        theme_key = self.store.get_setting("theme")
        self.theme = (
            THEMES.get(theme_key, THEMES["forest"])
            if isinstance(theme_key, str)
            else THEMES["forest"]
        )
        self.root = tk.Tk()
        self.root.title("span")
        self._set_window_icon()
        self.root.geometry("1120x760")
        self.root.minsize(self.MIN_WIDTH, self.MIN_HEIGHT)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.overrideredirect(True)
        self.selected_day = date.today()
        self.view = "year"
        self._maximized = False
        self._restore_geometry = "1120x760"
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._resize_origin: tuple[str, int, int, int, int, int, int] | None = None
        self._habits: list[Habit] = []
        self._habit_cards: dict[int, HabitCard] = {}
        self._habit_total = 0
        self._habit_count = 0
        self._completion_panel: tk.Frame | None = None
        self._completion_animation_id: str | None = None
        self._active_heatmap: HeatmapCanvas | None = None
        self._redraw_jobs: dict[tk.Misc, str] = {}
        self._root_jobs: set[str] = set()
        self._configure_root()
        self._build_window_chrome()
        self._build_resize_grips()
        self._after_root(20, self._restore_taskbar_presence)

    def _after_root(self, delay: int, callback) -> str:
        """Schedule a root-level callback that is cancelled cleanly on close."""

        def run() -> None:
            self._root_jobs.discard(job)
            if not self._closing:
                callback()

        job = self.root.after(delay, run)
        self._root_jobs.add(job)
        return job

    def _set_window_icon(self) -> None:
        try:
            self._icon_image = tk.PhotoImage(file=str(resource_path("assets/span.png")))
            self.root.iconphoto(True, self._icon_image)
            if sys.platform == "win32":
                self.root.iconbitmap(default=str(resource_path("assets/span.ico")))
        except (OSError, tk.TclError):
            self._icon_image = None

    def _configure_root(self) -> None:
        self.root.configure(bg=self.theme.background)
        self.root.option_add("*Font", (UI_FONT, 10))
        self.root.option_add("*Entry.Background", self.theme.surface_high)
        self.root.option_add("*Entry.Foreground", self.theme.text)
        self.root.option_add("*Entry.InsertBackground", self.theme.text)
        self.root.option_add("*Entry.Relief", "flat")
        if hasattr(self, "titlebar"):
            self._style_window_chrome()

    def _build_window_chrome(self) -> None:
        self.window_border = tk.Frame(
            self.root,
            bg=self.theme.border,
            padx=1,
            pady=1,
        )
        self.window_border.pack(fill="both", expand=True)
        self.titlebar = tk.Frame(
            self.window_border,
            bg=self.theme.surface,
            height=self.TITLEBAR_HEIGHT,
        )
        self.titlebar.pack(fill="x")
        self.titlebar.pack_propagate(False)
        self.titlebar.bind("<ButtonPress-1>", self._start_window_drag)
        self.titlebar.bind("<B1-Motion>", self._drag_window)
        self.titlebar.bind("<ButtonRelease-1>", lambda _: self._end_window_action())
        self.titlebar.bind("<Double-Button-1>", lambda _: self._toggle_maximize())

        self.title_mark = tk.Canvas(
            self.titlebar,
            width=24,
            height=24,
            bg=self.theme.surface,
            highlightthickness=0,
        )
        self.title_mark.pack(side="left", padx=(14, 8))
        rounded_rect(self.title_mark, 1, 1, 23, 23, 7, fill=self.theme.text, outline="")
        self.title_mark.create_text(
            12,
            11,
            text="s",
            fill=self.theme.background,
            font=(DISPLAY_FONT, 12, "bold"),
        )
        self.title_mark.bind("<ButtonPress-1>", self._start_window_drag)
        self.title_mark.bind("<B1-Motion>", self._drag_window)
        self.title_mark.bind("<ButtonRelease-1>", lambda _: self._end_window_action())

        self.window_title = self.label(
            self.titlebar,
            "span",
            size=10,
            weight="bold",
            bg=self.theme.surface,
        )
        self.window_title.pack(side="left")
        self.window_title.bind("<ButtonPress-1>", self._start_window_drag)
        self.window_title.bind("<B1-Motion>", self._drag_window)
        self.window_title.bind("<ButtonRelease-1>", lambda _: self._end_window_action())
        self.window_title.bind("<Double-Button-1>", lambda _: self._toggle_maximize())

        self.close_button = self._window_button("close", self.close)
        self.close_button.pack(side="right", fill="y")
        self.max_button = self._window_button("maximize", self._toggle_maximize)
        self.max_button.pack(side="right", fill="y")
        self.min_button = self._window_button("minimize", self._minimize)
        self.min_button.pack(side="right", fill="y")

        self.content = tk.Frame(self.window_border, bg=self.theme.background)
        self.content.pack(fill="both", expand=True)

    def _build_resize_grips(self) -> None:
        specs = {
            "n": ("sb_v_double_arrow", {"x": 6, "y": 0, "relwidth": 1, "width": -12, "height": 5}),
            "s": ("sb_v_double_arrow", {"x": 6, "rely": 1, "y": -5, "relwidth": 1, "width": -12, "height": 5}),
            "w": ("sb_h_double_arrow", {"x": 0, "y": 6, "width": 5, "relheight": 1, "height": -12}),
            "e": ("sb_h_double_arrow", {"relx": 1, "x": -5, "y": 6, "width": 5, "relheight": 1, "height": -12}),
            "nw": ("size_nw_se", {"x": 0, "y": 0, "width": 7, "height": 7}),
            "ne": ("size_ne_sw", {"relx": 1, "x": -7, "y": 0, "width": 7, "height": 7}),
            "sw": ("size_ne_sw", {"x": 0, "rely": 1, "y": -7, "width": 7, "height": 7}),
            "se": ("size_nw_se", {"relx": 1, "x": -7, "rely": 1, "y": -7, "width": 7, "height": 7}),
        }
        self.resize_grips = []
        for edge, (cursor, placement) in specs.items():
            grip = tk.Frame(self.root, bg=self.theme.border, cursor=cursor)
            grip.place(**placement)
            grip.bind(
                "<ButtonPress-1>",
                lambda event, selected=edge: self._start_resize(event, selected),
            )
            grip.bind("<B1-Motion>", self._resize_window)
            grip.bind("<ButtonRelease-1>", lambda _: self._end_window_action())
            grip.lift()
            self.resize_grips.append((grip, placement))

    def _window_button(self, kind: str, command) -> tk.Canvas:
        button = tk.Canvas(
            self.titlebar,
            width=46,
            height=self.TITLEBAR_HEIGHT,
            bg=self.theme.surface,
            highlightthickness=0,
            cursor="hand2",
        )

        def draw(hover=False, pressed=False) -> None:
            button.delete("all")
            if kind == "close" and hover:
                fill = "#c42b1c"
            elif hover:
                fill = self.theme.surface_high
            else:
                fill = self.theme.surface
            button.configure(bg=fill)
            color = "#ffffff" if kind == "close" and hover else self.theme.text
            offset = 1 if pressed else 0
            if kind == "minimize":
                button.create_line(17, 21 + offset, 29, 21 + offset, fill=color, width=1.4)
            elif kind == "maximize":
                if self._maximized:
                    button.create_rectangle(17, 15 + offset, 27, 25 + offset, outline=color, width=1.2)
                    button.create_line(19, 13 + offset, 29, 13 + offset, 29, 23 + offset, fill=color, width=1.2)
                else:
                    button.create_rectangle(17, 14 + offset, 29, 26 + offset, outline=color, width=1.2)
            else:
                button.create_line(18, 15 + offset, 28, 25 + offset, fill=color, width=1.4)
                button.create_line(28, 15 + offset, 18, 25 + offset, fill=color, width=1.4)

        def release(event) -> None:
            draw(True)
            if 0 <= event.x <= button.winfo_width() and 0 <= event.y <= button.winfo_height():
                command()

        button.bind("<Enter>", lambda _: draw(True))
        button.bind("<Leave>", lambda _: draw())
        button.bind("<ButtonPress-1>", lambda _: draw(True, True))
        button.bind("<ButtonRelease-1>", release)
        button.draw_control = draw
        draw()
        return button

    def _style_window_chrome(self) -> None:
        self.window_border.configure(bg=self.theme.border)
        self.titlebar.configure(bg=self.theme.surface)
        self.title_mark.configure(bg=self.theme.surface)
        self.title_mark.delete("all")
        rounded_rect(self.title_mark, 1, 1, 23, 23, 7, fill=self.theme.text, outline="")
        self.title_mark.create_text(
            12,
            11,
            text="s",
            fill=self.theme.background,
            font=(DISPLAY_FONT, 12, "bold"),
        )
        self.content.configure(bg=self.theme.background)
        self.window_title.configure(bg=self.theme.surface, fg=self.theme.text)
        for button in (self.min_button, self.max_button, self.close_button):
            button.draw_control()
        for grip, _placement in self.resize_grips:
            grip.configure(bg=self.theme.border)

    def _start_window_drag(self, event) -> None:
        if self._maximized:
            pointer_ratio = event.x_root / max(1, self.root.winfo_screenwidth())
            self._toggle_maximize()
            self.root.update_idletasks()
            x = round(event.x_root - self.root.winfo_width() * pointer_ratio)
            y = max(0, event.y_root - self.TITLEBAR_HEIGHT // 2)
            self.root.geometry(f"+{x}+{y}")
        self._drag_origin = (
            event.x_root,
            event.y_root,
            self.root.winfo_x(),
            self.root.winfo_y(),
        )

    def _drag_window(self, event) -> None:
        if self._drag_origin is None:
            return
        start_x, start_y, window_x, window_y = self._drag_origin
        self.root.geometry(
            f"+{window_x + event.x_root - start_x}+{window_y + event.y_root - start_y}"
        )

    def _start_resize(self, event, edge: str) -> None:
        if self._maximized:
            return
        self._resize_origin = (
            edge,
            event.x_root,
            event.y_root,
            self.root.winfo_x(),
            self.root.winfo_y(),
            self.root.winfo_width(),
            self.root.winfo_height(),
        )

    def _resize_window(self, event) -> None:
        if self._resize_origin is None or self._maximized:
            return
        edge, start_x, start_y, x, y, width, height = self._resize_origin
        dx = event.x_root - start_x
        dy = event.y_root - start_y
        new_x, new_y, new_width, new_height = x, y, width, height
        if "e" in edge:
            new_width = max(self.MIN_WIDTH, width + dx)
        if "s" in edge:
            new_height = max(self.MIN_HEIGHT, height + dy)
        if "w" in edge:
            new_width = max(self.MIN_WIDTH, width - dx)
            new_x = x + width - new_width
        if "n" in edge:
            new_height = max(self.MIN_HEIGHT, height - dy)
            new_y = y + height - new_height
        self.root.geometry(f"{new_width}x{new_height}+{new_x}+{new_y}")

    def _end_window_action(self) -> None:
        self._drag_origin = None
        self._resize_origin = None

    def _set_resize_grips_visible(self, visible: bool) -> None:
        for grip, placement in self.resize_grips:
            if visible:
                grip.place(**placement)
                grip.lift()
            else:
                grip.place_forget()

    def _toggle_maximize(self) -> None:
        if self._maximized:
            self.root.geometry(self._restore_geometry)
            self._maximized = False
            self._set_resize_grips_visible(True)
        else:
            self._restore_geometry = self.root.geometry()
            x, y, width, height = self._work_area()
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            self._maximized = True
            self._set_resize_grips_visible(False)
        self.max_button.draw_control()

    def _work_area(self) -> tuple[int, int, int, int]:
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                rect = wintypes.RECT()
                ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(rect), 0)
                return (
                    rect.left,
                    rect.top,
                    rect.right - rect.left,
                    rect.bottom - rect.top,
                )
            except (AttributeError, OSError):
                pass
        return (0, 0, self.root.winfo_screenwidth(), self.root.winfo_screenheight())

    def _minimize(self) -> None:
        if sys.platform == "win32":
            try:
                import ctypes

                hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
                ctypes.windll.user32.ShowWindow(hwnd, 6)
                return
            except (AttributeError, OSError):
                pass
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.bind("<Map>", self._restore_custom_chrome, add="+")

    def _restore_custom_chrome(self, _event=None) -> None:
        if self.root.state() == "normal":
            self.root.unbind("<Map>")
            self.root.overrideredirect(True)
            self._after_root(10, self._restore_taskbar_presence)

    def _restore_taskbar_presence(self) -> None:
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = ctypes.windll.user32.GetParent(self.root.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            style = (style & ~0x00000080) | 0x00040000
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, style)
            ctypes.windll.user32.SetWindowPos(
                hwnd,
                0,
                0,
                0,
                0,
                0,
                0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020,
            )
        except (AttributeError, OSError, tk.TclError):
            pass

    def run(self) -> None:
        self.render()
        self.root.mainloop()

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        for job in list(self._root_jobs):
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._root_jobs.clear()
        for job in self._redraw_jobs.values():
            try:
                self.root.after_cancel(job)
            except tk.TclError:
                pass
        self._redraw_jobs.clear()
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        finally:
            self.store.close()

    def clear(self) -> None:
        for child in self.content.winfo_children():
            child.destroy()

    def render(self) -> None:
        self.clear()
        # Fetch the habit list once per render; every sub-view below reuses it
        # instead of issuing the same query four times.
        self._habits = self.store.habits()
        if not self._habits:
            self.render_onboarding()
        else:
            self.render_main()

    def label(self, parent, text: str, *, size=10, color=None, weight="normal", **kwargs):
        return tk.Label(
            parent,
            text=text,
            bg=kwargs.pop("bg", self.theme.background),
            fg=color or self.theme.text,
            font=(DISPLAY_FONT if size >= 17 else UI_FONT, size, weight),
            **kwargs,
        )

    def panel(self, parent, *, background=None, **kwargs) -> tk.Frame:
        return tk.Frame(
            parent,
            bg=background or self.theme.surface,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme.border,
            **kwargs,
        )

    def _focusable_entry(
        self,
        parent,
        *,
        value: str = "",
        variable: tk.StringVar | None = None,
        size: int = 11,
    ) -> tuple[tk.Frame, tk.Entry]:
        shell = tk.Frame(
            parent,
            bg=self.theme.surface_high,
            bd=0,
            highlightthickness=1,
            highlightbackground=self.theme.border,
        )
        entry = tk.Entry(
            shell,
            textvariable=variable,
            bg=self.theme.surface_high,
            fg=self.theme.text,
            insertbackground=self.theme.accent,
            selectbackground=self.theme.accent_soft,
            selectforeground=self.theme.text,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(UI_FONT, size),
        )
        if value:
            entry.insert(0, value)
        entry.pack(fill="x", expand=True, ipady=10, padx=13)
        entry.bind(
            "<FocusIn>",
            lambda _: shell.configure(highlightbackground=self.theme.accent),
        )
        entry.bind(
            "<FocusOut>",
            lambda _: shell.configure(highlightbackground=self.theme.border),
        )
        return shell, entry

    def render_onboarding(self) -> None:
        shell = tk.Frame(self.content, bg=self.theme.background)
        # Fits inside the minimum window height (640px) without clipping the
        # privacy note at the bottom.
        shell.place(relx=0.5, rely=0.5, anchor="center", width=620, height=590)

        mark = tk.Canvas(
            shell, width=54, height=54, bg=self.theme.background, highlightthickness=0
        )
        mark.pack(pady=(8, 10))
        rounded_rect(mark, 1, 1, 53, 53, 16, fill=self.theme.text, outline="")
        mark.create_text(
            27,
            26,
            text="s",
            fill=self.theme.background,
            font=(DISPLAY_FONT, 24, "bold"),
        )
        self.label(shell, "Build your span.", size=26, weight="bold").pack()
        self.label(
            shell,
            "Choose the few things worth showing up for each day.",
            size=11,
            color=self.theme.muted,
        ).pack(pady=(6, 18))

        card = self.panel(shell, padx=24, pady=18)
        card.pack(fill="x")
        self.label(
            card,
            "YOUR HABITS",
            size=9,
            color=self.theme.muted,
            weight="bold",
            bg=self.theme.surface,
        ).pack(anchor="w", pady=(0, 12))

        suggestions = [
            "Move for 30 minutes",
            "Read 10 pages",
            "Practice my craft",
            "Eat with intention",
            "Wind down on time",
        ]
        entries: list[tk.Entry] = []
        for index, suggestion in enumerate(suggestions):
            row = tk.Frame(card, bg=self.theme.surface)
            row.pack(fill="x", pady=4)
            number = self.label(
                row,
                str(index + 1).zfill(2),
                size=9,
                color=self.theme.muted,
                bg=self.theme.surface,
                width=3,
            )
            number.pack(side="left")
            entry_shell, entry = self._focusable_entry(row, value=suggestion)
            entry_shell.pack(side="left", fill="x", expand=True, padx=(8, 0))
            entries.append(entry)

        def begin() -> None:
            names = []
            for entry in entries:
                name = entry.get().strip()
                if name:
                    names.append(name)
            if not 3 <= len(names) <= 5:
                messagebox.showinfo("Choose your habits", "Start with 3 to 5 habits.")
                return
            self.store.replace_habits(names)
            self.render()

        PillButton(
            shell,
            "Start tracking",
            begin,
            self.theme,
            primary=True,
            width=160,
            height=44,
        ).pack(pady=16)
        self.label(
            shell,
            "Private by default · stored only on this device",
            size=9,
            color=self.theme.muted,
        ).pack()

    def render_main(self) -> None:
        sidebar = tk.Frame(
            self.content,
            bg=self.theme.surface,
            width=220,
            highlightthickness=1,
            highlightbackground=self.theme.border,
            bd=0,
        )
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        content = tk.Frame(self.content, bg=self.theme.background)
        content.pack(side="left", fill="both", expand=True)

        self._render_sidebar(sidebar)
        self._render_content(content)

    def _render_sidebar(self, parent) -> None:
        self._nav_items: dict[str, tuple[tk.Frame, tk.Frame, tk.Button]] = {}
        brand = tk.Frame(parent, bg=self.theme.surface)
        brand.pack(fill="x", padx=24, pady=(26, 34))
        logo = tk.Canvas(
            brand, width=32, height=32, bg=self.theme.surface, highlightthickness=0
        )
        logo.pack(side="left")
        rounded_rect(logo, 0, 0, 32, 32, 10, fill=self.theme.text, outline="")
        logo.create_text(
            16,
            15,
            text="s",
            fill=self.theme.background,
            font=(DISPLAY_FONT, 16, "bold"),
        )
        self.label(
            brand, "span", size=17, weight="bold", bg=self.theme.surface
        ).pack(side="left", padx=10)

        self.label(
            parent,
            "VIEWS",
            size=8,
            weight="bold",
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(anchor="w", padx=26, pady=(0, 8))

        for key, title in (("month", "Month"), ("year", "Year"), ("lifetime", "Lifetime")):
            self._nav_item(parent, key, title)

        spacer = tk.Frame(parent, bg=self.theme.surface)
        spacer.pack(fill="both", expand=True)

        streak = self.store.streak()
        stat = self.panel(
            parent,
            background=self.theme.surface_high,
            padx=16,
            pady=14,
        )
        stat.pack(fill="x", padx=16, pady=(0, 14))
        self.label(
            stat,
            "STREAK",
            size=7,
            weight="bold",
            color=self.theme.accent,
            bg=self.theme.surface_high,
        ).pack(anchor="w", pady=(0, 5))
        self._streak_value_label = self.label(
            stat,
            f"{streak} day{'s' if streak != 1 else ''}",
            size=14,
            weight="bold",
            bg=self.theme.surface_high,
        )
        self._streak_value_label.pack(anchor="w")
        self.label(
            stat,
            "current perfect streak",
            size=8,
            color=self.theme.muted,
            bg=self.theme.surface_high,
        ).pack(anchor="w", pady=(3, 0))

        settings = tk.Button(
            parent,
            text="Preferences",
            command=self.render_settings,
            bg=self.theme.surface,
            fg=self.theme.muted,
            activebackground=self.theme.surface_high,
            activeforeground=self.theme.text,
            relief="flat",
            bd=0,
            anchor="w",
            padx=26,
            pady=14,
            cursor="hand2",
        )
        settings.pack(fill="x", pady=(0, 10))
        settings.bind(
            "<Enter>",
            lambda _: settings.configure(
                bg=self.theme.surface_high,
                fg=self.theme.text,
            ),
        )
        settings.bind(
            "<Leave>",
            lambda _: settings.configure(
                bg=self.theme.surface,
                fg=self.theme.muted,
            ),
        )

    def _nav_item(self, parent, key: str, title: str) -> None:
        active = self.view == key
        background = self.theme.surface_high if active else self.theme.surface
        foreground = self.theme.text if active else self.theme.muted
        row = tk.Frame(parent, bg=background, height=42)
        row.pack(fill="x", padx=10, pady=3)
        row.pack_propagate(False)
        indicator = tk.Frame(
            row,
            bg=self.theme.accent if active else background,
            width=3,
        )
        indicator.pack(side="left", fill="y", pady=8)
        button = tk.Button(
            row,
            text=title,
            command=lambda: self.set_view(key),
            bg=background,
            fg=foreground,
            activebackground=self.theme.surface_high,
            activeforeground=self.theme.text,
            relief="flat",
            bd=0,
            anchor="w",
            padx=14,
            pady=12,
            cursor="hand2",
            font=(UI_FONT, 10, "bold" if active else "normal"),
        )
        button.pack(side="left", fill="both", expand=True)
        self._nav_items[key] = (row, indicator, button)
        button.bind("<Enter>", lambda _, selected=key: self._hover_nav(selected, True))
        button.bind("<Leave>", lambda _, selected=key: self._hover_nav(selected, False))

    def _hover_nav(self, key: str, hover: bool) -> None:
        if key == self.view:
            return
        row, indicator, button = self._nav_items[key]
        background = self.theme.surface_high if hover else self.theme.surface
        foreground = self.theme.text if hover else self.theme.muted
        row.configure(bg=background)
        indicator.configure(bg=background)
        button.configure(bg=background, fg=foreground)

    def _update_nav_state(self) -> None:
        for key, (row, indicator, button) in self._nav_items.items():
            if not button.winfo_exists():
                continue
            active = key == self.view
            background = self.theme.surface_high if active else self.theme.surface
            row.configure(bg=background)
            indicator.configure(
                bg=self.theme.accent if active else background
            )
            button.configure(
                bg=background,
                fg=self.theme.text if active else self.theme.muted,
                font=(UI_FONT, 10, "bold" if active else "normal"),
            )

    def set_view(self, view: str) -> None:
        if view == self.view or view not in ("month", "year", "lifetime"):
            return
        if not getattr(self, "_heat_panel", None) or not self._heat_panel.winfo_exists():
            return
        self.view = view
        self._update_nav_state()
        self._active_heatmap = None
        for child in self._heat_panel.winfo_children():
            child.destroy()
        self._render_heatmap(self._heat_panel)

    def _render_content(self, parent) -> None:
        shell = tk.Frame(parent, bg=self.theme.background)
        shell.pack(fill="both", expand=True, padx=38, pady=30)

        header = tk.Frame(shell, bg=self.theme.background)
        header.pack(fill="x", pady=(0, 22))
        heading = "Today" if self.selected_day == date.today() else self.selected_day.strftime("%A")
        self.label(
            header,
            "DAILY CHECK-IN",
            size=8,
            weight="bold",
            color=self.theme.accent,
        ).pack(anchor="w", pady=(0, 6))
        self.label(header, heading, size=26, weight="bold").pack(anchor="w")
        self.label(
            header,
            self.selected_day.strftime("%B %d, %Y"),
            size=10,
            color=self.theme.muted,
        ).pack(anchor="w", pady=(4, 0))

        if self.selected_day != date.today():
            PillButton(
                header,
                "Back to today",
                self.select_today,
                self.theme,
                width=120,
                height=36,
            ).place(relx=1, rely=0, anchor="ne")

        body = tk.Frame(shell, bg=self.theme.background)
        body.pack(fill="both", expand=True)
        body.grid_columnconfigure(0, weight=5, uniform="main-content")
        body.grid_columnconfigure(1, weight=7, uniform="main-content")
        body.grid_rowconfigure(0, weight=1)

        habits_panel = tk.Frame(body, bg=self.theme.background)
        habits_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        heat_panel = self.panel(body)
        heat_panel.grid(row=0, column=1, sticky="nsew", padx=(12, 0))
        self._heat_panel = heat_panel

        self._render_habits(habits_panel)
        self._render_heatmap(heat_panel)

    def select_today(self) -> None:
        if self.selected_day == date.today():
            return
        self.selected_day = date.today()
        self.render()

    def select_day(self, selected: date) -> None:
        if selected == self.selected_day:
            return
        start = self._start_date()
        if start <= selected <= date.today():
            self.selected_day = selected
            self.render()

    def _start_date(self) -> date:
        try:
            return date.fromisoformat(self.store.get_setting("start_date"))
        except (TypeError, ValueError):
            return date.today()

    def _render_habits(self, parent) -> None:
        habits = self._habits
        # Archived habits keep their history, but a completion for a habit that
        # is no longer shown must not inflate today's count past the total.
        completed = self.store.completed_ids(self.selected_day) & {
            habit.id for habit in habits
        }
        count = len(completed)
        self._habit_total = len(habits)
        self._habit_count = count
        self._habit_cards = {}
        self._habits_parent = parent
        self._completion_panel = None
        self._completion_animation_id = None
        top = tk.Frame(parent, bg=self.theme.background)
        top.pack(fill="x", pady=(0, 12))
        self.label(top, "Daily habits", size=13, weight="bold").pack(side="left")
        self._habit_count_label = self.label(
            top,
            f"{count}/{len(habits)}",
            size=10,
            color=self.theme.accent,
            weight="bold",
        )
        self._habit_count_label.pack(side="right")

        progress = tk.Canvas(
            parent, height=5, bg=self.theme.background, highlightthickness=0
        )
        progress.pack(fill="x", pady=(0, 13))
        self._habit_progress = progress
        self._habit_progress_fraction = count / len(habits) if habits else 0.0
        self._progress_animation_id: str | None = None

        def cancel_progress(event) -> None:
            if event.widget is not progress:
                return
            job = self._progress_animation_id
            if job is not None:
                try:
                    progress.after_cancel(job)
                except tk.TclError:
                    pass
                self._progress_animation_id = None

        progress.bind("<Destroy>", cancel_progress)

        def draw_progress(event=None, fraction=None) -> None:
            progress.delete("all")
            width = progress.winfo_width()
            rounded_rect(progress, 0, 0, width, 5, 2, fill=self.theme.surface_high, outline="")
            if habits:
                filled = width * (
                    self._habit_progress_fraction if fraction is None else fraction
                )
                rounded_rect(progress, 0, 0, filled, 5, 2, fill=self.theme.accent, outline="")

        progress.bind("<Configure>", draw_progress)
        self._draw_habit_progress = draw_progress

        for habit in habits:
            card = HabitCard(
                parent,
                habit.name,
                habit.id in completed,
                self.theme,
                lambda habit_id=habit.id: self.toggle_habit(habit_id),
            )
            card.pack(fill="x", pady=4)
            self._habit_cards[habit.id] = card

        if count == len(habits):
            self._show_completion(animate=False)

    def _show_completion(self, animate: bool = True) -> None:
        if self._completion_panel is not None:
            return
        complete = self.panel(
            self._habits_parent,
            background=self.theme.accent_soft,
            padx=16,
            pady=13,
        )
        complete.pack(fill="x", pady=(14, 0))
        self._completion_panel = complete
        title = self.label(
            complete,
            "Day complete",
            size=10,
            weight="bold",
            color=self.theme.accent,
            bg=self.theme.accent_soft,
        )
        title.pack(anchor="w")
        subtitle = self.label(
            complete,
            "You kept every promise today.",
            size=9,
            color=self.theme.muted,
            bg=self.theme.accent_soft,
        )
        subtitle.pack(anchor="w", pady=(3, 0))
        if animate:
            complete.pack_configure(padx=12)

            def settle(frame: int) -> None:
                self._completion_animation_id = None
                if not complete.winfo_exists():
                    return
                inset = max(0, 12 - frame * 3)
                complete.pack_configure(padx=inset)
                if frame < 4:
                    self._completion_animation_id = complete.after(
                        24, settle, frame + 1
                    )

            def cancel_settle(event) -> None:
                if event.widget is not complete:
                    return
                job = self._completion_animation_id
                if job is not None:
                    try:
                        complete.after_cancel(job)
                    except tk.TclError:
                        pass
                    self._completion_animation_id = None

            complete.bind("<Destroy>", cancel_settle)
            settle(0)

    def _hide_completion(self) -> None:
        panel = self._completion_panel
        if panel is not None:
            if self._completion_animation_id is not None:
                try:
                    panel.after_cancel(self._completion_animation_id)
                except tk.TclError:
                    pass
                self._completion_animation_id = None
            panel.destroy()
            self._completion_panel = None

    def _animate_habit_progress(self, target: float) -> None:
        progress = self._habit_progress
        draw = self._draw_habit_progress
        if self._progress_animation_id is not None:
            try:
                progress.after_cancel(self._progress_animation_id)
            except tk.TclError:
                pass
            self._progress_animation_id = None
        start = self._habit_progress_fraction
        frames = 6

        def step(frame: int) -> None:
            if not progress.winfo_exists():
                self._progress_animation_id = None
                return
            amount = frame / frames
            eased = 1 - (1 - amount) ** 3
            value = start + (target - start) * eased
            self._habit_progress_fraction = value
            draw(fraction=value)
            if frame < frames:
                self._progress_animation_id = progress.after(20, step, frame + 1)
            else:
                self._progress_animation_id = None

        step(1)

    def toggle_habit(self, habit_id: int) -> None:
        if self._closing or self.selected_day > date.today():
            return
        card = self._habit_cards.get(habit_id)
        if card is None or not card.winfo_exists():
            return
        checked = self.store.toggle(habit_id, self.selected_day)
        card.set_checked(checked)

        delta = 1 if checked else -1
        self._habit_count = max(0, min(self._habit_total, self._habit_count + delta))
        self._habit_count_label.configure(
            text=f"{self._habit_count}/{self._habit_total}"
        )
        target = self._habit_count / max(1, self._habit_total)
        self._animate_habit_progress(target)

        if self._habit_count == self._habit_total:
            self._show_completion()
        else:
            self._hide_completion()

        streak = self.store.streak()
        if self._streak_value_label.winfo_exists():
            self._streak_value_label.configure(
                text=f"{streak} day{'s' if streak != 1 else ''}"
            )

        if self._active_heatmap is not None and self._active_heatmap.winfo_exists():
            self._active_heatmap.update_day(
                self.selected_day,
                self._habit_count,
                self._habit_total,
            )

    def _render_heatmap(self, parent) -> None:
        header = tk.Frame(parent, bg=self.theme.surface)
        header.pack(fill="x", padx=22, pady=(20, 10))
        title = {"month": "This month", "year": "This year", "lifetime": "Your span"}[self.view]
        self.label(
            header, title, size=13, weight="bold", bg=self.theme.surface
        ).pack(side="left")
        self.label(
            header,
            "Click a past day to review",
            size=8,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(side="right")

        if self.view == "lifetime":
            self._render_lifetime(parent)
            return

        if self.view == "year":
            wrapper = tk.Frame(parent, bg=self.theme.surface)
            wrapper.pack(fill="both", expand=True, padx=18, pady=(4, 18))
            scrollbar = self._heatmap_scrollbar(wrapper)
            canvas = HeatmapCanvas(wrapper, self.theme, self.select_day)
            self._active_heatmap = canvas
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.set_command(canvas.yview)
            canvas.pack(side="left", fill="both", expand=True)
            canvas.bind(
                "<MouseWheel>",
                lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
            )
            canvas.bind("<Button-4>", lambda _: canvas.yview_scroll(-1, "units"))
            canvas.bind("<Button-5>", lambda _: canvas.yview_scroll(1, "units"))
            canvas.bind(
                "<Configure>",
                lambda _: self._schedule_heatmap_draw(canvas, self._draw_year),
            )
            return

        canvas = HeatmapCanvas(parent, self.theme, self.select_day)
        self._active_heatmap = canvas
        canvas.pack(fill="both", expand=True, padx=18, pady=(4, 18))
        canvas.bind(
            "<Configure>",
            lambda _: self._schedule_heatmap_draw(canvas, self._draw_month),
        )

    def _schedule_heatmap_draw(self, canvas: HeatmapCanvas, draw) -> None:
        """Coalesce resize events into a single redraw.

        A redraw can create thousands of canvas items; doing that for every
        pixel of a window drag makes resizing feel broken.
        """
        pending = self._redraw_jobs.pop(canvas, None)
        if pending is not None:
            try:
                self.root.after_cancel(pending)
            except tk.TclError:
                pass
        self._redraw_jobs[canvas] = self.root.after(
            40, self._run_heatmap_draw, canvas, draw
        )

    def _run_heatmap_draw(self, canvas: HeatmapCanvas, draw) -> None:
        self._redraw_jobs.pop(canvas, None)
        if not self._closing and canvas.winfo_exists():
            draw(canvas)

    def _draw_month(self, canvas: HeatmapCanvas) -> None:
        canvas.reset()
        canvas.total_habits = max(1, len(self._habits))
        today = date.today()
        first = date(today.year, today.month, 1)
        last = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        counts, targets = self.store.daily_summary(first, last)
        width = max(canvas.winfo_width(), 1)
        height = max(canvas.winfo_height(), 1)
        start_offset = first.weekday()
        rows = (start_offset + last.day + 6) // 7
        outer_x = 14
        outer_y = 14
        label_height = 28
        gap = max(6, min(14, width // 55))
        width_cell = (width - outer_x * 2 - gap * 6) // 7
        height_cell = (
            height - outer_y * 2 - label_height - gap * (rows - 1)
        ) // rows
        cell = max(18, min(width_cell, height_cell))
        total = cell * 7 + gap * 6
        grid_height = cell * rows + gap * (rows - 1)
        left = max(outer_x, (width - total) // 2)
        top = label_height + max(
            outer_y,
            (height - label_height - grid_height) // 2,
        )
        label_size = max(8, min(10, cell // 7))
        number_size = max(8, min(12, cell // 7))
        for index, name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            canvas.create_text(
                left + index * (cell + gap) + cell / 2,
                top - 17,
                text=name,
                fill=self.theme.muted,
                font=(UI_FONT, label_size),
            )
        for day_number in range(1, last.day + 1):
            current = date(today.year, today.month, day_number)
            position = start_offset + day_number - 1
            row, column = divmod(position, 7)
            x = left + column * (cell + gap)
            y = top + row * (cell + gap)
            canvas.add_cell(
                current,
                x,
                y,
                cell,
                counts.get(current, 0),
                total=targets.get(current, canvas.total_habits),
                future=current > today,
                radius=max(6, min(14, cell // 5)),
            )
            canvas.create_text(
                x + max(8, cell // 7),
                y + max(8, cell // 7),
                text=str(day_number),
                anchor="nw",
                fill=self.theme.muted if current != self.selected_day else self.theme.text,
                font=(
                    UI_FONT,
                    number_size,
                    "bold" if current == self.selected_day else "normal",
                ),
            )
            if current == self.selected_day:
                canvas.create_oval(
                    x + cell - 13,
                    y + 8,
                    x + cell - 7,
                    y + 14,
                    fill=self.theme.accent,
                    outline="",
                )

    def _draw_year(self, canvas: HeatmapCanvas) -> None:
        canvas.reset()
        canvas.total_habits = max(1, len(self._habits))
        today = date.today()
        first = date(today.year, 1, 1)
        last = date(today.year, 12, 31)
        counts, targets = self.store.daily_summary(first, last)
        width = max(canvas.winfo_width(), 1)
        top = 18
        column_gap = 24
        gap = 4
        preferred_month_width = 150
        columns = max(
            2,
            min(
                4,
                (width - 36 + column_gap)
                // (preferred_month_width + column_gap),
            ),
        )
        available_per_month = max(
            87,
            (width - column_gap * (columns - 1) - 36) // columns,
        )
        cell = max(9, min(18, (available_per_month - gap * 6) // 7))
        step = cell + gap
        month_width = cell * 7 + gap * 6
        grid_width = month_width * columns + column_gap * (columns - 1)
        outer_x = max(18, (width - grid_width) // 2)
        title_height = 28
        month_height = title_height + step * 6
        row_gap = 24
        row_count = (12 + columns - 1) // columns

        for month in range(1, 13):
            grid_row, grid_column = divmod(month - 1, columns)
            block_x = outer_x + grid_column * (month_width + column_gap)
            block_y = top + grid_row * (month_height + row_gap)
            canvas.create_text(
                block_x,
                block_y,
                text=calendar.month_name[month],
                anchor="nw",
                fill=self.theme.text,
                font=(UI_FONT, 10, "bold"),
            )

            month_first = date(today.year, month, 1)
            days_in_month = calendar.monthrange(today.year, month)[1]
            for day_number in range(1, days_in_month + 1):
                current = date(today.year, month, day_number)
                position = month_first.weekday() + day_number - 1
                week, weekday = divmod(position, 7)
                canvas.add_cell(
                    current,
                    block_x + weekday * step,
                    block_y + title_height + week * step,
                    cell,
                    counts.get(current, 0),
                    total=targets.get(current, canvas.total_habits),
                    future=current > today,
                    radius=4,
                )

        footer_y = top + row_count * (month_height + row_gap) + 4
        tracked = max(1, (today - first).days + 1)
        total = sum(counts.values())
        possible = sum(
            targets.get(first + timedelta(days=offset), canvas.total_habits)
            for offset in range(tracked)
        )
        rate = round(total / possible * 100) if possible else 0
        canvas.create_text(
            outer_x,
            footer_y,
            text=f"{total} check-ins  |  {rate}% completion",
            anchor="w",
            fill=self.theme.muted,
            font=(UI_FONT, 9),
        )
        legend_x = max(outer_x + 180, width - 145)
        canvas.create_text(
            legend_x - 8,
            footer_y,
            text="Less",
            anchor="e",
            fill=self.theme.muted,
            font=(UI_FONT, 7),
        )
        for index, color in enumerate(self.theme.heat):
            rounded_rect(
                canvas,
                legend_x + index * 17,
                footer_y - 6,
                legend_x + index * 17 + 11,
                footer_y + 5,
                2,
                fill=color,
                outline="",
            )
        canvas.configure(scrollregion=(0, 0, width, footer_y + 24))

    def _render_lifetime(self, parent) -> None:
        birth = self._birth_date()
        lifespan = self._lifespan()
        end = self._add_years(birth, lifespan)
        start = self._start_date()
        days = max(1, (end - start).days + 1)
        lived = max(0, min(days, (date.today() - start).days + 1))

        summary = tk.Frame(parent, bg=self.theme.surface)
        summary.pack(fill="x", padx=20, pady=(0, 8))
        self.label(
            summary,
            f"{lived:,}",
            size=18,
            weight="bold",
            color=self.theme.accent,
            bg=self.theme.surface,
        ).pack(side="left")
        self.label(
            summary,
            f" days tracked or elapsed  ·  {max(0, days - lived):,} projected days ahead",
            size=9,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(side="left", padx=(8, 0), pady=(5, 0))

        wrapper = tk.Frame(parent, bg=self.theme.surface)
        wrapper.pack(fill="both", expand=True, padx=18, pady=(0, 18))
        scrollbar = self._heatmap_scrollbar(wrapper)
        canvas = HeatmapCanvas(wrapper, self.theme, self.select_day)
        self._active_heatmap = canvas
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.set_command(canvas.yview)
        canvas.pack(side="left", fill="both", expand=True)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(int(-e.delta / 120), "units"))
        canvas.bind("<Button-4>", lambda _: canvas.yview_scroll(-1, "units"))
        canvas.bind("<Button-5>", lambda _: canvas.yview_scroll(1, "units"))
        canvas.bind(
            "<Configure>",
            lambda _: self._schedule_heatmap_draw(
                canvas, lambda target: self._draw_lifetime(target, start, end)
            ),
        )

    def _heatmap_scrollbar(self, parent) -> SlimScrollbar:
        scrollbar = SlimScrollbar(parent, self.theme, width=9)
        scrollbar.pack(side="right", fill="y", padx=(3, 0))
        return scrollbar

    def _draw_lifetime(self, canvas: HeatmapCanvas, start: date, end: date) -> None:
        canvas.reset()
        canvas.total_habits = max(1, len(self._habits))
        today = date.today()
        counts, targets = self.store.daily_summary(start, min(today, end))
        width = max(canvas.winfo_width(), 1)
        cell, gap, label_width = 9, 3, 42
        right_padding = 22
        columns = max(12, (width - label_width - right_padding) // (cell + gap))
        total_days = max(1, (end - start).days + 1)
        rows = (total_days + columns - 1) // columns
        top = 22
        last_year = None

        for index in range(total_days):
            current = start + timedelta(days=index)
            row, column = divmod(index, columns)
            x = label_width + column * (cell + gap)
            y = top + row * (cell + gap)
            if current.year != last_year:
                canvas.create_text(
                    4,
                    y + cell / 2,
                    text=str(current.year),
                    anchor="w",
                    fill=self.theme.muted,
                    font=(UI_FONT, 7),
                )
                last_year = current.year
            canvas.add_cell(
                current,
                x,
                y,
                cell,
                counts.get(current, 0),
                total=targets.get(current, canvas.total_habits),
                future=current > today,
                radius=0,
            )

        height = top + rows * (cell + gap) + 18
        canvas.configure(scrollregion=(0, 0, width, height))
        today_index = max(0, min(total_days - 1, (today - start).days))
        today_row = today_index // columns
        if height > canvas.winfo_height():
            canvas.yview_moveto(max(0, (today_row * (cell + gap) - 80) / height))

    def render_settings(self) -> None:
        self.clear()
        shell = tk.Frame(self.content, bg=self.theme.background)
        shell.pack(fill="both", expand=True, padx=46, pady=34)

        header = tk.Frame(shell, bg=self.theme.background)
        header.pack(fill="x", pady=(0, 24))
        title_group = tk.Frame(header, bg=self.theme.background)
        title_group.pack(side="left")
        self.label(
            title_group,
            "CUSTOMIZE SPAN",
            size=8,
            weight="bold",
            color=self.theme.accent,
        ).pack(anchor="w", pady=(0, 6))
        self.label(title_group, "Preferences", size=26, weight="bold").pack(anchor="w")
        PillButton(
            header, "Back", self.render, self.theme, width=90, height=38
        ).pack(side="right")

        columns = tk.Frame(shell, bg=self.theme.background)
        columns.pack(fill="both", expand=True)
        columns.grid_columnconfigure(0, weight=1)
        columns.grid_columnconfigure(1, weight=1)

        habits_card = self.panel(columns, padx=24, pady=22)
        habits_card.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        profile_card = self.panel(columns, padx=24, pady=22)
        profile_card.grid(row=0, column=1, sticky="nsew", padx=(12, 0))

        self.label(
            habits_card, "Daily habits", size=14, weight="bold", bg=self.theme.surface
        ).pack(anchor="w")
        self.label(
            habits_card,
            "Edit the promises that appear on your daily check-in.",
            size=9,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(anchor="w", pady=(4, 14))

        entries_frame = tk.Frame(habits_card, bg=self.theme.surface)
        entries_frame.pack(fill="x")
        entries: list[tuple[PreferenceHabitRow, int | None]] = []

        def add_entry(value="", habit_id: int | None = None) -> None:
            if len(entries) >= MAX_HABITS:
                return
            def remove() -> None:
                entries[:] = [item for item in entries if item[0] is not row]

            row = PreferenceHabitRow(
                entries_frame,
                value,
                self.theme,
                remove,
                animate=habit_id is None,
            )
            row.pack(fill="x", pady=4)
            entries.append((row, habit_id))

        for habit in self.store.habits():
            add_entry(habit.name, habit.id)

        add_actions = tk.Frame(habits_card, bg=self.theme.surface)
        add_actions.pack(fill="x", pady=(8, 0))
        PillButton(
            add_actions,
            "+ Add habit",
            add_entry,
            self.theme,
            width=118,
            height=38,
        ).pack(side="left")
        self.label(
            add_actions,
            f"Up to {MAX_HABITS}",
            size=8,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(side="right", pady=10)

        self.label(
            profile_card, "Color theme", size=14, weight="bold", bg=self.theme.surface
        ).pack(anchor="w")
        self.label(
            profile_card,
            "Choose the energy of your heatmap and interface.",
            size=9,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(anchor="w", pady=(4, 12))

        theme_var = tk.StringVar(value=self.theme.name)
        swatches = tk.Frame(profile_card, bg=self.theme.surface)
        swatches.pack(fill="x", pady=(0, 22))
        theme_chips: dict[str, ThemeChip] = {}

        def choose_theme(key: str) -> None:
            theme_var.set(key)
            for chip_key, chip in theme_chips.items():
                chip.set_selected(chip_key == key)

        for key, theme in THEMES.items():
            chip = ThemeChip(
                swatches,
                theme.label,
                theme.accent,
                key == theme_var.get(),
                self.theme,
                lambda selected=key: choose_theme(selected),
                width=88,
            )
            index = len(theme_chips)
            chip.grid(
                row=index // 3,
                column=index % 3,
                sticky="w",
                padx=(0, 6),
                pady=(0, 6),
            )
            theme_chips[key] = chip

        divider = tk.Frame(profile_card, bg=self.theme.border, height=1)
        divider.pack(fill="x", pady=(0, 20))

        self.label(
            profile_card, "Lifetime projection", size=14, weight="bold", bg=self.theme.surface
        ).pack(anchor="w")
        self.label(
            profile_card,
            "Used only to draw your projected span.",
            size=9,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(anchor="w", pady=(4, 12))

        birth_var = tk.StringVar(value=self.store.get_setting("birth_date"))
        life_var = tk.StringVar(value=str(self.store.get_setting("lifespan", 85)))
        self._settings_field(profile_card, "Birth date", birth_var, "YYYY-MM-DD")
        self._settings_field(profile_card, "Expected age", life_var, "85")

        save_bar = tk.Frame(profile_card, bg=self.theme.surface)
        save_bar.pack(side="bottom", fill="x", pady=(24, 0))
        self.label(
            save_bar,
            "Changes stay on this device",
            size=8,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(side="left", pady=12)

        def save() -> None:
            habits = []
            for row, habit_id in entries:
                name = row.value()
                if name:
                    habits.append((habit_id, name))
            if not 1 <= len(habits) <= MAX_HABITS:
                messagebox.showinfo(
                    "Habits", f"Keep between 1 and {MAX_HABITS} habits."
                )
                return
            try:
                birth = datetime.strptime(birth_var.get().strip(), "%Y-%m-%d").date()
                lifespan = int(life_var.get())
                if (
                    birth >= date.today()
                    or not 1 <= lifespan <= 150
                    or self._add_years(birth, lifespan) <= date.today()
                ):
                    raise ValueError
            except ValueError:
                messagebox.showinfo(
                    "Lifetime",
                    "Enter a valid birth date and an expected age later than your current age.",
                )
                return
            theme = THEMES.get(theme_var.get(), self.theme)
            with self.store.connection():
                self.store.save_habits(habits)
                self.store.set_settings(
                    {
                        "birth_date": birth.isoformat(),
                        "lifespan": lifespan,
                        "theme": theme.name,
                    }
                )
            self.theme = theme
            self._configure_root()
            self.render()

        PillButton(
            save_bar,
            "Save changes",
            save,
            self.theme,
            primary=True,
            width=136,
            height=42,
        ).pack(side="right")

    def _settings_field(
        self,
        parent,
        title: str,
        variable: tk.StringVar,
        hint: str,
    ) -> None:
        heading = tk.Frame(parent, bg=self.theme.surface)
        heading.pack(fill="x", pady=(10, 5))
        self.label(
            heading,
            title,
            size=8,
            color=self.theme.muted,
            weight="bold",
            bg=self.theme.surface,
        ).pack(side="left")
        self.label(
            heading,
            hint,
            size=8,
            color=self.theme.muted,
            bg=self.theme.surface,
        ).pack(side="right")
        shell, _entry = self._focusable_entry(parent, variable=variable, size=10)
        shell.pack(fill="x")

    def _birth_date(self) -> date:
        try:
            return date.fromisoformat(self.store.get_setting("birth_date"))
        except (TypeError, ValueError):
            return date(date.today().year - 30, 1, 1)

    def _lifespan(self) -> int:
        try:
            return max(1, min(150, int(self.store.get_setting("lifespan", 85))))
        except (TypeError, ValueError):
            return 85

    @staticmethod
    def _add_years(day: date, years: int) -> date:
        target = day.year + years
        if target > date.max.year:
            return date.max
        if target < date.min.year:
            return date.min
        try:
            return day.replace(year=target)
        except ValueError:
            # February 29 in a non-leap year.
            return day.replace(year=target, day=28)
