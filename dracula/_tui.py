from typing import List, Union

import rich
from pygments.lexer import Lexer
from rich.columns import Columns
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text
from textual import events
from textual.app import App
from textual.keys import Keys
from textual.reactive import Reactive
from textual.widget import Widget
from textual.widgets import Footer, Header, ScrollView
from textual_inputs import TextInput

from ._utils import cycle, previous


class ReactiveColumns(Widget):
    """Rich columns that is reactive to changes to it's renderables"""

    renderables = Reactive(default=False)

    def __init__(self, renderables, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_renderables = renderables
        self.renderables = renderables

    def render(self) -> Columns:
        return Columns(self.renderables)

    def search(self, query: str) -> None:
        """Search for panels with a specific title and update the columns to only show those columns

        Parameters
        ----------
        query : str
            The title of the panel to search for
        """
        self.renderables = [i for i in self.original_renderables if query in i.title]


class ReactiveSyntax(Widget):

    code = Reactive(default=False)
    lexer = Reactive(default=False)

    def __init__(self, code, lexer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.code = code
        self.lexer = lexer

    def render(self) -> Panel:
        return Panel(
            Syntax(self.code, self.lexer, line_numbers=True, indent_guides=True, theme="dracula"),
            title=self.lexer.name,
            expand=False,
        )

    def change_code(self, new_code: str, new_lexer: Union[Lexer, str]) -> None:
        """Change the underlying code and lexer for the syntax

        Parameters
        ----------
        new_code : str
            THe new code to show
        new_lexer : Union[Lexer, str]
            The new lexer to use
        """
        self.code = new_code
        self.lexer = new_lexer


class DraculaColumnsApp(App):
    def __init__(self, columns: Columns, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.columns = ReactiveColumns(columns.renderables)

    async def on_load(self, event: events.Load):
        await self.bind("q", "quit")
        await self.bind("r", "reset")

    async def on_mount(self, event: events.Mount) -> None:
        """Create a grid with auto-arranging cells."""
        self.scroll_view = ScrollView(self.columns)
        self.text_input = TextInput(
            name="code",
            title="Search",
        )
        self.text_input.on_change_handler_name = "handle_on_search_text_change"

        grid = await self.view.dock_grid(edge="left", name="left")

        grid.add_column(fraction=1, name="center")

        grid.add_row(fraction=1, name="top", min_size=3)
        grid.add_row(fraction=10, name="middle")

        grid.add_areas(
            text_view="center,top",
            scroll_view="center,middle",
        )

        grid.place(
            text_view=self.text_input,
            scroll_view=self.scroll_view,
        )

    def handle_on_search_text_change(self, text):
        self.columns.search(text.sender.value)
        self.scroll_view.home()

    def action_reset(self):
        self.columns.search("")
        self.scroll_view.home()


class DraculaDemoApp(App):
    def __init__(self, syntaxes: List[Syntax], *args, **kwargs):
        super().__init__(*args, **kwargs)
        syntax = syntaxes[0]
        self.syntax = ReactiveSyntax(syntax.code, syntax.lexer)
        # It's a cycle since we want to reset to the first one if the list is exhausted
        self.syntaxes = cycle(syntaxes)

    async def on_load(self, event: events.Load):
        await self.bind("q", "quit", "Quit application")
        await self.bind("left", "left", "Previous language")
        await self.bind("right", "right", "Next language")
        await self.bind("up", "up", "Scroll Up")
        await self.bind("down", "down", "Scroll Down")
        await self.bind("pageup", "page_up")
        await self.bind("pagedown", "page_down")

    async def on_mount(self, event: events.Mount) -> None:
        """Create a grid with auto-arranging cells."""
        self.body = ScrollView(gutter=1)

        # Header / footer / dock
        await self.view.dock(Header(style="white on #44475a"), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        # Dock the body in the remaining space
        await self.view.dock(self.body)

        await self.body.update(self.syntax)

    def action_left(self):
        # Change the syntax to the previous one
        previous_syntax = previous(self.syntaxes)
        self.syntax.code, self.syntax.lexer = previous_syntax.code, previous_syntax.lexer
        # Reset the scrollview to avoid visual glitches
        self.body.home()

    def action_right(self):
        # Change the syntax to the next one
        next_syntax = next(self.syntaxes)
        self.syntax.code, self.syntax.lexer = next_syntax.code, next_syntax.lexer
        # Reset the scrollview to avoid visual glitches
        self.body.home()

    def action_up(self):
        # Scroll down means the text will go down, meaning it will show the things that are up
        self.body.scroll_down()

    def action_down(self):
        # Scroll up means the text will go up, meaning it will show the things that are down
        self.body.scroll_up()

    def action_page_up(self):
        self.body.page_up()

    def action_page_down(self):
        self.body.page_down()
