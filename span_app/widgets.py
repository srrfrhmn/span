from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from functools import lru_cache

from .theme import UI_FONT, Theme


@lru_cache(maxsize=256)
def _rgb(color: str) -> tuple[int, int, int]:
    return tuple(int(color[index : index + 2], 16) for index in (1, 3, 5))


def blend_color(start: str, end: str, amount: float) -> str:
    amount = max(0.0, min(1.0, amount))
    mixed = tuple(
        round(source + (target - source) * amount)
        for source, target in zip(_rgb(start), _rgb(end))
    )
    return "#{:02x}{:02x}{:02x}".format(*mixed)


def rounded_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    **kwargs,
) -> int:
    radius = min(radius, (x2 - x1) / 2, (y2 - y1) / 2)
    if radius <= 0:
        # A plain rectangle is dramatically cheaper for small cells (the
        # lifetime heatmap draws tens of thousands of them).
        return canvas.create_rectangle(x1, y1, x2, y2, **kwargs)
    points = [
        x1 + radius,
        y1,
        x2 - radius,
        y1,
        x2,
        y1,
        x2,
        y1 + radius,
        x2,
        y2 - radius,
        x2,
        y2,
        x2 - radius,
        y2,
        x1 + radius,
        y2,
        x1,
        y2,
        x1,
        y2 - radius,
        x1,
        y1 + radius,
        x1,
        y1,
    ]
    return canvas.create_polygon(
        points,
        smooth=True,
        splinesteps=20 if radius > 6 else 10,
        **kwargs,
    )


class PillButton(tk.Canvas):
    def __init__(
        self,
        parent,
        text: str,
        command: Callable[[], None],
        theme: Theme,
        *,
        primary: bool = False,
        width: int = 110,
        height: int = 38,
    ) -> None:
        try:
            background = parent.cget("bg")
        except tk.TclError:
            background = theme.background
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=background,
            highlightthickness=0,
            cursor="hand2",
        )
        self.text = text
        self.command = command
        self.theme = theme
        self.primary = primary
        self.hover = False
        self.pressed = False
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<ButtonRelease-1>", self._release)
        self.draw()

    def _enter(self, _event) -> None:
        self.hover = True
        self.draw()

    def _leave(self, _event) -> None:
        self.hover = False
        self.pressed = False
        self.draw()

    def _press(self, _event) -> None:
        self.pressed = True
        self.draw()

    def _release(self, event) -> None:
        was_pressed = self.pressed
        self.pressed = False
        self.draw()
        if (
            was_pressed
            and 0 <= event.x <= self.winfo_width()
            and 0 <= event.y <= self.winfo_height()
        ):
            self.command()

    def draw(self) -> None:
        self.delete("all")
        if self.primary:
            border = self.theme.text if self.hover else self.theme.accent
            fill = border
            text = self.theme.background
        else:
            fill = self.theme.surface_high if self.hover else self.theme.surface
            border = self.theme.muted if self.hover else self.theme.border
            text = self.theme.text
        width = int(self["width"])
        height = int(self["height"])
        inset = 2 if self.pressed else 1
        rounded_rect(
            self,
            inset,
            inset,
            width - inset,
            height - inset,
            12,
            fill=border,
            outline="",
        )
        rounded_rect(
            self,
            inset + 1,
            inset + 1,
            width - inset - 1,
            height - inset - 1,
            11,
            fill=fill,
            outline="",
        )
        self.create_text(
            width / 2,
            height / 2 + (1 if self.pressed else 0),
            text=self.text,
            fill=text,
            font=(UI_FONT, 10, "bold"),
        )


class HabitCard(tk.Canvas):
    def __init__(
        self,
        parent,
        name: str,
        checked: bool,
        theme: Theme,
        command: Callable[[], None],
    ) -> None:
        super().__init__(
            parent,
            height=66,
            bg=theme.background,
            highlightthickness=0,
            cursor="hand2",
        )
        self.name = name
        self.checked = checked
        self.theme = theme
        self.command = command
        self.hover = False
        self.pulse = 0.0
        self._animation_id: str | None = None
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Button-1>", lambda _: self.command())
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Destroy>", self._destroyed)

    def _destroyed(self, event) -> None:
        if event.widget is not self:
            return
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

    def _enter(self, _event) -> None:
        self.hover = True
        self.draw()

    def _leave(self, _event) -> None:
        self.hover = False
        self.draw()

    def set_checked(self, checked: bool, animate: bool = True) -> None:
        self.checked = checked
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None
        if not animate:
            self.pulse = 0.0
            self.draw()
            return

        frames = (0.0, 0.75, 1.0, 0.45, 0.0)

        def step(index: int) -> None:
            if not self.winfo_exists():
                return
            self.pulse = frames[index]
            self.draw()
            if index + 1 < len(frames):
                self._animation_id = self.after(28, step, index + 1)
            else:
                self._animation_id = None

        step(0)

    def draw(self) -> None:
        self.delete("all")
        width = max(self.winfo_width(), 300)
        fill = self.theme.surface_high if self.hover else self.theme.surface
        if self.pulse:
            fill = blend_color(fill, self.theme.accent_soft, self.pulse * 0.55)
        border = self.theme.accent_soft if self.hover else self.theme.border
        if self.pulse:
            border = blend_color(border, self.theme.accent, self.pulse)
        rounded_rect(self, 1, 2, width - 1, 64, 16, fill=border, outline="")
        rounded_rect(self, 2, 3, width - 2, 63, 15, fill=fill, outline="")
        circle_fill = self.theme.accent if self.checked else self.theme.surface_high
        circle_outline = self.theme.accent if self.checked else self.theme.border
        growth = self.pulse * 3
        self.create_oval(
            18 - growth,
            20 - growth,
            44 + growth,
            46 + growth,
            fill=circle_fill,
            outline=circle_outline,
            width=1.5,
        )
        if self.checked:
            self.create_line(
                24,
                33,
                30,
                39,
                39,
                27,
                fill=self.theme.background,
                width=2.5,
                capstyle=tk.ROUND,
                joinstyle=tk.ROUND,
            )
        else:
            self.create_oval(24, 26, 38, 40, outline=self.theme.muted, width=1.25)
        self.create_text(
            60,
            33,
            text=self.name,
            anchor="w",
            fill=self.theme.muted if self.checked else self.theme.text,
            font=(UI_FONT, 11, "bold" if not self.checked else "overstrike"),
        )
        self.create_text(
            width - 18,
            33,
            text="DONE" if self.checked else "",
            anchor="e",
            fill=self.theme.accent,
            font=(UI_FONT, 7, "bold"),
        )


class ThemeChip(tk.Canvas):
    def __init__(
        self,
        parent,
        label: str,
        color: str,
        selected: bool,
        theme: Theme,
        command: Callable[[], None],
        width: int = 92,
    ) -> None:
        super().__init__(
            parent,
            width=width,
            height=42,
            bg=theme.surface,
            highlightthickness=0,
            cursor="hand2",
        )
        self.label = label
        self.color = color
        self.selected = selected
        self.theme = theme
        self.command = command
        self.hover = False
        self.pulse = 0.0
        self._animation_id: str | None = None
        self.bind("<Enter>", self._enter)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", lambda _: self.command())
        self.bind("<Destroy>", self._destroyed)
        self.draw()

    def _destroyed(self, event) -> None:
        if event.widget is not self:
            return
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

    def _enter(self, _event) -> None:
        self.hover = True
        self.draw()

    def _leave(self, _event) -> None:
        self.hover = False
        self.draw()

    def set_selected(self, selected: bool) -> None:
        self.selected = selected
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None
        frames = (0.0, 0.8, 1.0, 0.4, 0.0)

        def step(index: int) -> None:
            if not self.winfo_exists():
                return
            self.pulse = frames[index]
            self.draw()
            if index + 1 < len(frames):
                self._animation_id = self.after(24, step, index + 1)
            else:
                self._animation_id = None

        step(0)

    def draw(self) -> None:
        self.delete("all")
        width = int(self["width"])
        border = self.color if self.selected else self.theme.border
        if self.hover:
            border = blend_color(border, self.theme.text, 0.35)
        if self.pulse:
            border = blend_color(border, self.color, self.pulse)
        fill = self.theme.surface_high if self.hover or self.selected else self.theme.surface
        rounded_rect(self, 1, 1, width - 1, 41, 12, fill=border, outline="")
        rounded_rect(self, 2, 2, width - 2, 40, 11, fill=fill, outline="")
        radius = 5 + self.pulse * 2
        self.create_oval(
            13 - radius,
            21 - radius,
            13 + radius,
            21 + radius,
            fill=self.color,
            outline="",
        )
        self.create_text(
            27,
            21,
            text=self.label,
            anchor="w",
            fill=self.theme.text,
            font=(UI_FONT, 9, "bold"),
        )


class PreferenceHabitRow(tk.Frame):
    HEIGHT = 56

    def __init__(
        self,
        parent,
        value: str,
        theme: Theme,
        on_remove: Callable[[], None],
        *,
        animate: bool = False,
    ) -> None:
        super().__init__(
            parent,
            bg=theme.surface_high,
            height=0 if animate else self.HEIGHT,
            bd=0,
            highlightthickness=1,
            highlightbackground=theme.border,
        )
        self.theme = theme
        self.on_remove = on_remove
        self._animation_id: str | None = None
        self._removing = False
        self.pack_propagate(False)
        self.entry = tk.Entry(
            self,
            bg=theme.surface_high,
            fg=theme.text,
            insertbackground=theme.accent,
            selectbackground=theme.accent_soft,
            selectforeground=theme.text,
            relief="flat",
            bd=0,
            highlightthickness=0,
            font=(UI_FONT, 11, "bold"),
        )
        self.entry.insert(0, value)
        self.entry.pack(side="left", fill="both", expand=True, padx=(15, 6), pady=7)
        self.entry.bind(
            "<FocusIn>",
            lambda _: self.configure(highlightbackground=theme.accent),
        )
        self.entry.bind(
            "<FocusOut>",
            lambda _: self.configure(highlightbackground=theme.border),
        )

        self.remove = PillButton(
            self,
            "X",
            self.remove_animated,
            theme,
            width=38,
            height=38,
        )
        self.remove.pack(side="right", padx=(0, 8))
        self.bind("<Destroy>", self._destroyed)
        if animate:
            self._animation_id = self.after_idle(self._animate_in, 0)

    def _destroyed(self, event) -> None:
        if event.widget is not self:
            return
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None

    def value(self) -> str:
        return self.entry.get().strip()

    def _animate_in(self, frame: int) -> None:
        self._animation_id = None
        if not self.winfo_exists():
            return
        frames = 5
        amount = frame / frames
        eased = 1 - (1 - amount) ** 3
        self.configure(height=max(1, round(self.HEIGHT * eased)))
        if frame < frames:
            self._animation_id = self.after(22, self._animate_in, frame + 1)
        else:
            self.entry.focus_set()

    def remove_animated(self) -> None:
        if self._removing:
            return
        self._removing = True
        if self._animation_id is not None:
            try:
                self.after_cancel(self._animation_id)
            except tk.TclError:
                pass
            self._animation_id = None
        start = max(1, self.winfo_height())

        def step(frame: int) -> None:
            self._animation_id = None
            if not self.winfo_exists():
                return
            amount = frame / 5
            self.configure(height=max(1, round(start * (1 - amount))))
            if frame < 5:
                self._animation_id = self.after(20, step, frame + 1)
            else:
                self.on_remove()
                self.destroy()

        step(1)


class SlimScrollbar(tk.Canvas):
    def __init__(self, parent, theme: Theme, width: int = 9) -> None:
        super().__init__(
            parent,
            width=width,
            bg=theme.surface,
            highlightthickness=0,
            cursor="hand2",
        )
        self.theme = theme
        self.command: Callable[..., None] | None = None
        self.first = 0.0
        self.last = 1.0
        self.drag_offset = 0.0
        self.bind("<Configure>", lambda _: self.draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag)

    def set_command(self, command: Callable[..., None]) -> None:
        self.command = command

    def set(self, first: str | float, last: str | float) -> None:
        self.first = float(first)
        self.last = float(last)
        self.draw()

    def _thumb_bounds(self) -> tuple[float, float]:
        height = max(1, self.winfo_height())
        thumb_top = self.first * height
        thumb_bottom = self.last * height
        minimum = min(28, height)
        if thumb_bottom - thumb_top < minimum:
            center = (thumb_top + thumb_bottom) / 2
            thumb_top = max(0, min(height - minimum, center - minimum / 2))
            thumb_bottom = thumb_top + minimum
        return thumb_top, thumb_bottom

    def draw(self) -> None:
        self.delete("all")
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        rounded_rect(
            self,
            1,
            0,
            width - 1,
            height,
            max(1, width / 2),
            fill=self.theme.surface_high,
            outline="",
        )
        if self.last - self.first >= 0.999:
            return
        top, bottom = self._thumb_bounds()
        rounded_rect(
            self,
            1,
            top,
            width - 1,
            bottom,
            max(1, width / 2),
            fill=self.theme.border,
            outline="",
        )

    def _press(self, event) -> None:
        if self.command is None or self.last - self.first >= 0.999:
            return
        top, bottom = self._thumb_bounds()
        if top <= event.y <= bottom:
            self.drag_offset = event.y - top
        else:
            self.command("scroll", -1 if event.y < top else 1, "pages")

    def _drag(self, event) -> None:
        if self.command is None or self.last - self.first >= 0.999:
            return
        height = max(1, self.winfo_height())
        top, bottom = self._thumb_bounds()
        thumb_height = bottom - top
        travel = max(1, height - thumb_height)
        fraction = max(0.0, min(1.0, (event.y - self.drag_offset) / travel))
        visible = self.last - self.first
        self.command("moveto", fraction * max(0.0, 1.0 - visible))


@dataclass
class HeatCell:
    day: date
    x1: int
    y1: int
    x2: int
    y2: int
    count: int
    total: int
    future: bool = False


class HeatmapCanvas(tk.Canvas):
    def __init__(
        self,
        parent,
        theme: Theme,
        on_select: Callable[[date], None],
    ) -> None:
        super().__init__(
            parent,
            bg=theme.surface,
            highlightthickness=0,
            cursor="hand2",
        )
        self.theme = theme
        self.on_select = on_select
        self.cells: list[HeatCell] = []
        self.item_cells: dict[int, HeatCell] = {}
        self.day_items: dict[date, tuple[int, HeatCell]] = {}
        self.day_animations: dict[date, str] = {}
        self.total_habits = 1
        self.tooltip: int | None = None
        self._hovered: HeatCell | None = None
        self.bind("<Motion>", self._motion)
        self.bind("<Leave>", self._leave)
        self.bind("<Button-1>", self._click)
        self.bind("<Destroy>", self._destroyed)

    def _destroyed(self, event) -> None:
        if event.widget is not self:
            return
        for animation in self.day_animations.values():
            try:
                self.after_cancel(animation)
            except tk.TclError:
                pass
        self.day_animations.clear()

    def _leave(self, _event) -> None:
        self._hovered = None
        self._hide_tooltip()

    def reset(self) -> None:
        for animation in self.day_animations.values():
            try:
                self.after_cancel(animation)
            except tk.TclError:
                pass
        self.day_animations.clear()
        self.delete("all")
        self.cells.clear()
        self.item_cells.clear()
        self.day_items.clear()
        self._hovered = None
        self.tooltip = None

    def color_for(self, count: int, total: int, future: bool = False) -> str:
        if future:
            return self.theme.background
        if count <= 0:
            return self.theme.heat[0]
        level = min(4, max(1, round((count / max(1, total)) * 4)))
        return self.theme.heat[level]

    def add_cell(
        self,
        day: date,
        x: int,
        y: int,
        size: int,
        count: int,
        *,
        total: int | None = None,
        future: bool = False,
        radius: int = 3,
    ) -> None:
        total = total or self.total_habits
        item = rounded_rect(
            self,
            x,
            y,
            x + size,
            y + size,
            radius,
            fill=self.color_for(count, total, future),
            outline="",
        )
        cell = HeatCell(day, x, y, x + size, y + size, count, total, future)
        self.cells.append(cell)
        self.item_cells[item] = cell
        self.day_items[day] = (item, cell)

    def update_day(self, day: date, count: int, total: int) -> None:
        match = self.day_items.get(day)
        if match is None:
            return
        animation = self.day_animations.pop(day, None)
        if animation is not None:
            try:
                self.after_cancel(animation)
            except tk.TclError:
                pass
        item, cell = match
        start = self.itemcget(item, "fill")
        target = self.color_for(count, total, cell.future)
        cell.count = count
        cell.total = total

        def step(frame: int) -> None:
            if not self.winfo_exists() or day not in self.day_items:
                self.day_animations.pop(day, None)
                return
            amount = frame / 5
            self.itemconfigure(item, fill=blend_color(start, target, amount))
            if frame < 5:
                self.day_animations[day] = self.after(22, step, frame + 1)
            else:
                self.day_animations.pop(day, None)

        step(1)

    def _cell_at(self, x: int, y: int) -> HeatCell | None:
        canvas_x = self.canvasx(x)
        canvas_y = self.canvasy(y)
        for item in reversed(self.find_overlapping(canvas_x, canvas_y, canvas_x, canvas_y)):
            cell = self.item_cells.get(item)
            if cell is not None:
                return cell
        return None

    def _motion(self, event) -> None:
        cell = self._cell_at(event.x, event.y)
        if cell is self._hovered:
            # Recreating the tooltip on every pixel of movement is expensive
            # and makes it flicker. Only redraw when the hovered day changes.
            return
        self._hovered = cell
        self._hide_tooltip()
        if cell is None:
            return
        status = "Future" if cell.future else f"{cell.count}/{cell.total} complete"
        label = f"{cell.day.strftime('%b %d, %Y')}  ·  {status}"
        font = (UI_FONT, 9)
        text_id = self.create_text(0, 0, text=label, font=font)
        box = self.bbox(text_id)
        self.delete(text_id)
        if box is None:
            return
        width = box[2] - box[0] + 20
        viewport_left = self.canvasx(8)
        viewport_right = self.canvasx(self.winfo_width() - 8)
        viewport_top = self.canvasy(8)
        pointer_x = self.canvasx(event.x)
        pointer_y = self.canvasy(event.y)
        x = min(max(viewport_left, pointer_x + 12), max(viewport_left, viewport_right - width))
        y = max(viewport_top, pointer_y - 38)
        self.tooltip = rounded_rect(
            self,
            x,
            y,
            x + width,
            y + 28,
            8,
            fill=self.theme.text,
            outline="",
            tags="tooltip",
        )
        self.create_text(
            x + 10,
            y + 14,
            text=label,
            anchor="w",
            fill=self.theme.background,
            font=font,
            tags="tooltip",
        )

    def _hide_tooltip(self) -> None:
        self.delete("tooltip")
        self.tooltip = None

    def _click(self, event) -> None:
        cell = self._cell_at(event.x, event.y)
        if cell and not cell.future and cell.day <= date.today():
            self.on_select(cell.day)
