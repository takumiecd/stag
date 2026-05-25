"""Textual widget: scrollable, clickable flowchart view."""

from __future__ import annotations

from textual.message import Message
from textual.widget import Widget
from textual.events import Click, MouseDown, MouseMove, MouseUp

from stag.tui.flowchart import ClickRegion, render_flowchart


class FlowchartItemClicked(Message):
    """Posted when the user clicks a node or transition in the flowchart."""

    def __init__(self, kind: str, raw_id: str) -> None:
        super().__init__()
        self.kind = kind
        self.raw_id = raw_id


# Mouse-movement threshold (in chars) below which a press-release is treated as a click.
_DRAG_THRESHOLD = 2


class FlowchartView(Widget, can_focus=True):
    """Scrollable, clickable, drag-pannable flowchart widget.

    - mouse wheel / arrow keys: scroll
    - left-button drag: pan
    - left-button click (no drag): post FlowchartItemClicked on the hit region
    """

    DEFAULT_CSS = """
    FlowchartView {
        overflow: auto auto;
        background: $surface;
    }
    """

    BINDINGS = [
        ("up", "scroll_up", "Scroll up"),
        ("down", "scroll_down", "Scroll down"),
        ("left", "scroll_left", "Scroll left"),
        ("right", "scroll_right", "Scroll right"),
        ("pageup", "page_up", "Page up"),
        ("pagedown", "page_down", "Page down"),
        ("home", "scroll_home", "Top"),
        ("end", "scroll_end", "Bottom"),
    ]

    _depth: int = 2
    _handle = None
    _center_node_id: str | None = None
    _selected: tuple[str, str] | None = None
    _drag_origin: tuple[int, int] | None = None
    _drag_scroll_start: tuple[float, float] | None = None
    _drag_moved: bool = False
    _lines: list[str] = []
    _click_map: list[ClickRegion] = []

    def show(self, handle, center_node_id: str, depth: int | None = None) -> None:
        self._handle = handle
        self._center_node_id = center_node_id
        self._selected = None
        if depth is not None:
            self._depth = depth
        else:
            self._depth = self._auto_depth()
        self._refresh_lines()

    def set_selected(self, kind: str | None, raw_id: str | None) -> None:
        if kind is None or raw_id is None:
            self._selected = None
        else:
            self._selected = (kind, raw_id)
        self._refresh_lines()

    def _auto_depth(self) -> int:
        h = self.size.height or 24
        from stag.tui.flowchart import BAND_H
        return max(1, min(4, (h // BAND_H) - 1))

    def _refresh_lines(self) -> None:
        if self._handle is None or self._center_node_id is None:
            return
        lines, regions = render_flowchart(
            self._handle, self._center_node_id, self._depth, selected=self._selected
        )
        self._lines = lines
        self._click_map = regions
        self.refresh()

    def render(self) -> str:
        return "\n".join(self._lines) if self._lines else " "

    def adjust_depth(self, delta: int) -> None:
        self._depth = max(1, min(6, self._depth + delta))
        self._refresh_lines()

    def recenter(self) -> None:
        self.scroll_home(animate=False)

    # ------------------------------------------------------------------
    # Mouse: drag-pan + click (mutually exclusive based on movement)
    # ------------------------------------------------------------------

    def on_mouse_down(self, event: MouseDown) -> None:
        if event.button != 1:
            return
        self._drag_origin = (event.screen_x, event.screen_y)
        self._drag_scroll_start = (self.scroll_x, self.scroll_y)
        self._drag_moved = False
        self.capture_mouse()
        self.focus()

    def on_mouse_move(self, event: MouseMove) -> None:
        if self._drag_origin is None:
            return
        dx = self._drag_origin[0] - event.screen_x
        dy = self._drag_origin[1] - event.screen_y
        if not self._drag_moved and abs(dx) + abs(dy) < _DRAG_THRESHOLD:
            return
        self._drag_moved = True
        sx, sy = self._drag_scroll_start or (0, 0)
        self.scroll_to(sx + dx, sy + dy, animate=False)

    def on_mouse_up(self, _event: MouseUp) -> None:
        self.release_mouse()
        self._drag_origin = None
        self._drag_scroll_start = None
        # _drag_moved cleared on next mouse_down; on_click checks it.

    def on_click(self, event: Click) -> None:
        # If the user dragged, suppress the click so we don't navigate accidentally.
        if self._drag_moved:
            self._drag_moved = False
            event.stop()
            return
        content_x = event.x + int(self.scroll_x)
        content_y = event.y + int(self.scroll_y)
        for region in self._click_map:
            if region.row == content_y and region.col_start <= content_x <= region.col_end:
                self.post_message(FlowchartItemClicked(region.kind, region.raw_id))
                event.stop()
                return

    # ------------------------------------------------------------------
    # Keyboard scrolling
    # ------------------------------------------------------------------

    def action_scroll_up(self) -> None:
        self.scroll_relative(y=-2, animate=False)

    def action_scroll_down(self) -> None:
        self.scroll_relative(y=2, animate=False)

    def action_scroll_left(self) -> None:
        self.scroll_relative(x=-4, animate=False)

    def action_scroll_right(self) -> None:
        self.scroll_relative(x=4, animate=False)

    def action_page_up(self) -> None:
        self.scroll_relative(y=-(self.size.height or 10), animate=False)

    def action_page_down(self) -> None:
        self.scroll_relative(y=(self.size.height or 10), animate=False)

    def action_scroll_home(self) -> None:
        self.scroll_home(animate=False)

    def action_scroll_end(self) -> None:
        self.scroll_end(animate=False)
