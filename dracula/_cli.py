import datetime as dt
import math
import os
import os.path
from typing import List, Optional

import click
import humanize
import questionary
import rich
import typer
from pygments.lexers import ClassNotFound, guess_lexer_for_filename
from prompt_toolkit.shortcuts.prompt import CompleteStyle
from questionary import Style
from requests_cache import CachedSession
from rich.align import Align
from rich.box import HEAVY_EDGE
from rich.columns import Columns
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.progress import Progress, track
from rich.rule import Rule
from rich.syntax import Syntax
from rich.text import Text
from rich.traceback import install
from rich.tree import Tree

from ._colors import format_language
from ._typer import Typer
from ._utils import get_closest_clock_emoji, datetime_from_utc_to_local
from ._downloader import download_files


def _get_github_readme(repo: str) -> Optional[str]:
    """Get the github readme contents for a particular repository"""
    # Get the readme path from github since the readme file and extension is case insensitive
    readme = session.get(f"https://api.github.com/repos/{repo}/readme").json()
    if readme.get("message") == "Not Found":
        return
    # Get the contents of the readme file
    content = session.get(f"https://raw.githubusercontent.com/{repo}/master/{readme['path']}")
    if content.status_code == 200:
        return content.text
    return


def _get_install_guide(repo: str) -> Optional[str]:
    """Get the install guide for a particular dracula supported app"""
    # Since each repo has a INSTALL.md file with instructions, we can safely get the contents of the INSTALL.md file
    content = session.get(f"https://raw.githubusercontent.com/{repo}/master/INSTALL.md")
    if content.status_code == 200:
        return content.text
    return


def _generate_formatted_time(iso_8601_time: Optional[str], title: str, delta_first: bool = True) -> str:
    """Convert a datetime object to a human readable time"""
    # Parse the time given to us
    if iso_8601_time:
        time = dt.datetime.strptime(iso_8601_time, "%Y-%m-%dT%H:%M:%SZ")
    else:
        time = dt.datetime.fromtimestamp(0)
    # Get the clock emoji that most closely matches the time given
    closest_clock_emoji = get_closest_clock_emoji(time)
    # Calculate the amount of time that has passed since the time given
    delta = dt.datetime.now() - time
    # Depending on the use case, the delta may need to be shown before the absolute time
    if delta_first:
        return f"{closest_clock_emoji} {title}:" \
               f" {humanize.naturaldelta(delta)} ago ({humanize.naturaldate(datetime_from_utc_to_local(time))})\n"
    else:
        return f"{closest_clock_emoji} {title}:" \
               f"{humanize.naturaldate(datetime_from_utc_to_local(time))} ({humanize.naturaldelta(delta)})\n"


def _generate_contributors_data(url: str) -> str:
    """Get the contributors of a repository given it's api url"""
    response = session.get(url)
    if response.status_code != 200:
        try:
            response_json = response.json()
        except Exception:
            message = None
        else:
            message = response_json.get("message", None)
        return f"Could not get contributors, Error {response.status_code}{f': {message}' if message else ''}"
    response_json = response.json()
    # SOrt the list by the amount of contributions
    contributors = sorted(response_json, key=lambda d: d["contributions"])
    # Remove bot accounts from contributors
    contributors = filter(lambda u: u["login"] not in ["ImgBotApp"], contributors)
    # Return the list of contributors with rich formatting
    return ":grinning: Contributors: " + "[#ff5555],[/] ".join(
        f"[#ffb86c link={i.get('html_url')}]{i['login']}[/]" for i in contributors
    )


def _get_org_repo_count(org_name: str) -> int:
    """Get how many apps are supported by dracula"""
    url = f"https://api.github.com/orgs/{org_name}"
    response = session.get(url)
    if response.status_code != 200:
        # 300 is a fallback since it should be less than 300 for a couple of months
        return 300
    response_json = response.json()
    return response_json.get("public_repos", 300)


def _render_tree(repo:str, file_list, path: str =".") -> Tree:
    """Render a git repo's files in a tree"""
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    response = session.get(url)
    response_json = response.json()
    if response.status_code != 200 and isinstance(response_json, dict) and response_json.get("message"):
        # If there was a error and then stop attemping to download the files
        print(url, response_json.get("message"))
        raise typer.Exit()
    tree = Tree("", highlight=True, hide_root=True)
    for element in response_json:
        label = Text(element.get("name"))
        if element.get("type") == "dir":
            label.stylize("bold #bd93f9")
            icon = "📁"
            folder = tree.add(Text(f"{icon} ", no_wrap=True, overflow="ellipsis") + label)
            folder.add(_render_tree(repo, file_list, element.get("path")))
        if element.get("type") == "file":
            label.stylize("bold #50fa7b")
            icon = "📄"
            label.highlight_regex(r"\..*$", "not bold #50fa7b")
            tree.add(Text(f"{icon} ", no_wrap=True, overflow="ellipsis") + label)
            file_list.append(element.get("path"))
    return tree


# A folder called requests in a folder called cache inside the install directory
cache_path = os.path.join(os.path.dirname(__file__), "cache", "requests")

# Autocompletion is mostly unnecessary in this case
app = Typer(add_completion=False)
console = Console()
session = CachedSession(
    cache_path,
    backend="sqlite",
    urls_expire_after={
        "https://api.github.com/repo": 21_600,  # 6 hours
        "https://api.github.com/orgs": 10_800,  # 3 hours
        "https://api.github.com/contributors": 86_400,  # 24 hours
        "https://raw.githubusercontent.com/dracula/template/master/sample": 7_890_000,  # 3 months
        "https://raw.githubusercontent.com/dracula/*": 86_400,  # 24 hours
    },
    headers={"User-Agent": "wasi_master/dracula-cli"},
)
install()  # Install rich traceback


@app.callback()
def main(
    token: str = typer.Option(
        None,
        envvar="GITHUB_TOKEN",
        help="Github access token for less ratelimits, Can be also set via the environment variable GITHUB_TOKEN",
    ),
):
    if token:
        session.headers.update({"Authorization": f"Token {token}"})


@app.command()
def all(
    sort: str = typer.Option(
        "stars",
        help="What to use when sorting repos, valid options are name,stars,forks,size,watchers,language,issues,created_at,updated_at,pushed_at",
    ),
    pager: bool = typer.Option(False, help="Whether to use pagination or not"),
    tui: bool = typer.Option(False, help="Whether to use a textual use interface or not. Close by pressir Ctrl+C or q"),
):
    """
    View all dracula supported apps

    The output can sometimes be too big to be shown at once in some terminals,
    to make sure this doesn't happen you can use the --pager flag or if you want the best of the best, use the --tui flag.
    The --sort option can be used to sort the list of apps based on specific criterias
    """
    url = "https://api.github.com/orgs/dracula/repos"

    with console.status("Getting app amount information"):
        # Since the github API can only return 100 results per page.
        # This gets the number of repositories that we need to retrieve
        maximum = _get_org_repo_count("dracula")
        per_page = 100

    with Progress(transient=True) as progress:
        apps = []
        loading_task = progress.add_task("[#ff5555]Loading...", total=maximum)
        # ceil the number of repositories divided by the number of repositories per page
        # to get the number of api calls that we would need to make
        for page in range(1, math.ceil(maximum / per_page)+1):
            response = session.get(url, params={"per_page": per_page, "page": page})
            if response.status_code != 200:
                try:
                    response_json = response.json()
                except Exception:
                    message = None
                else:
                    message = response_json.get("message", None)
                console.print(
                    Panel(
                        f"Error {response.status_code}{f': {message}' if message else ''}",
                        title="Could not load",
                        border_style="#ff5555",
                        title_align="left",
                    )
                )
                raise typer.Exit()
            response_json = response.json()
            apps.extend(response_json)
            progress.update(loading_task, advance=per_page)

    columns = Columns()
    # These apps are not in the official dracula website.
    # FIXME: Switch to parsing paths.js (https://github.com/dracula/draculatheme.com/blob/site/lib/paths.js)
    not_app = {
        "dracula-theme",
        "atom-ui",
        "chrome-devtools",
        "draculatheme.com",
        "jetbrains-legacy",
        "liteide-archived",
        "template",
        "spec",
        "jupyterlab_dracula",
        "racket",
        "react-devtools",
        "putty",
        "slate",
    }

    # Mapping of sorting method to api response keys. If the sorting method is not
    # in this list then the sorting method is used as the key
    sort_aliases = {
        "stars": "stargazers_count",
        "star": "stargazers_count",
        "watcher": "watchers",
        "fork": "forks",
        "issues": "open_issues",
        "issue": "open_issues",
    }
    #fmt: off
    apps = sorted(
        apps,
        # Available values: name, stars, forks, size, watchers, language, issues,
        #                   created_at, updated_at, pushed_at
        key=lambda d: d[sort_aliases.get(sort, sort)],
        # Only do reversed sort for names since people usually want A-Z.
        # for other things such as stars, people usually want highest to lowest
        reverse=sort != "name",
    )
    #fmt: on

    for repo in apps:
        # If the repo does not exist in draculatheme.com then we don't show it
        if repo["name"] in not_app:
            continue
        columns.add_renderable(
            Panel(
                (
                    f":pinching_hand: Size: {humanize.naturalsize(repo.get('size', 0))}\n"
                    f":star: Stars: {repo.get('stargazers_count', 0):,}\n"
                    f":fork_and_knife: Forks: {repo.get('forks_count', 0):,}\n"
                    f":eyes: Watchers: {repo.get('watchers_count', 0):,}\n"
                    f":abc: Language: {format_language(repo.get('language', 'N/A'))}\n"
                    f":bug: Issues Open: {repo.get('open_issues_count', 'N/A')}\n"
                    f":scroll: License: {repo['license']['name'] if repo['license'] else 'Not Specified'}\n"
                    + _generate_formatted_time(repo.get("created_at"), title="Created At", delta_first=False)
                    + _generate_formatted_time(repo.get("updated_at"), title="Last updated")
                    + _generate_formatted_time(repo.get("pushed_at"), title="Last pushed")
                ),
                title=f"[link=https://draculatheme.com/{repo.get('name')}]{repo.get('name')}[/]",
            )
        )
    if pager and tui:
        raise click.UsageError("You cannot use both a pager and a tui")
    if pager:
        with console.pager():
            console.print(Rule(title=f"{len(apps)} Apps"))
            console.print(columns)
    elif tui:
        from ._tui import DraculaColumnsApp

        DraculaColumnsApp.run(title="All Apps", columns=columns)
    else:
        console.print(Rule(title=f"{len(apps)} Apps"))
        console.print(columns)


@app.command()
def show(
    app: str = typer.Argument(..., help="The name of the app to view"),
    readme: bool = typer.Option(False, help="Whether to show the github readme page or not"),
    installation: bool = typer.Option(True, help="Whether to show the installation guide or not"),
):
    """
    View the documentation for the dracula theme for a specific app

    By default only the app git repository metadata and the installation instructions are shown. You can optionally
    also ask for the readme.md file by using the --readme flag.
    """
    url = f"https://api.github.com/repos/dracula/{app}"

    response = session.get(url)
    if response.status_code != 200:
        try:
            response_json = response.json()
        except Exception:
            message = None
        else:
            message = response_json.get("message", None)
        console.print(
            Panel(
                f"Error {response.status_code}{f': {message}' if message else ''}",
                title=f"Could not get [#50fa7b]{app}[/]",
                border_style="#ff5555",
                title_align="left",
            )
        )
        raise typer.Exit()
    response_json = response.json()

    console.print(
        Align(
            Panel(
                (
                    f":pinching_hand: Size: {humanize.naturalsize(response_json.get('size', 0))}\n"
                    f":star: Stars: {response_json.get('stargazers_count', 0):,}\n"
                    f":fork_and_knife: Forks: {response_json.get('forks_count', 0):,}\n"
                    f":eyes: Watchers: {response_json.get('watchers_count', 0):,}\n"
                    f":abc: Language: {format_language(response_json.get('language', 'N/A'))}\n"
                    f":bug: Issues Open: {response_json.get('open_issues_count', 'N/A')}\n"
                    f":scroll: License: {response_json['license']['name'] if response_json['license'] else 'Not Specified'}\n"
                    + _generate_formatted_time(
                        response_json.get("created_at", dt.datetime.fromtimestamp(0)),
                        title="Created At",
                        delta_first=False,
                    )
                    + _generate_formatted_time(
                        response_json.get("updated_at", dt.datetime.fromtimestamp(0)), title="Last updated"
                    )
                    + _generate_formatted_time(
                        response_json.get("pushed_at", dt.datetime.fromtimestamp(0)), title="Last pushed"
                    )
                    + _generate_contributors_data(response_json.get("contributors_url"))
                ),
                title=response_json.get("description", "").replace("🧛🏻‍♂️", ":vampire:"),
                border_style="#8be9fd",
                expand=False,
                subtitle=f"https://draculatheme.com/{app}",
            ),
            "center",
        )
    )
    # console.print(Rule(title="Installation Guide", characters="━"))
    if installation:
        with console.status("Getting installation guide"):
            installation_guide = _get_install_guide(f"dracula/{app}")
        console.print(
            Panel(
                Markdown(installation_guide, code_theme="dracula"),
                title="[b u]Installation Guide[/]",
                border_style="#50fa7b",
                box=HEAVY_EDGE,
            )
        )
    if readme:
        with console.status("Getting github readme"):
            github_readme = _get_github_readme(f"dracula/{app}")
        console.print(
            Panel(
                Markdown(github_readme, code_theme="dracula"),
                title="[b u]Readme[/]",
                border_style="#ff79c6",
                box=HEAVY_EDGE,
            )
        )
    # If both readme and installation are false then there's nothing to show for detailed information.
    # This may not be intentional, so it just informs the user
    if (installation, readme) == (False, False):
        console.print(Align("[bold #ff5555]You disabled both installation and readme.[/]", "center"))


@app.command()
def demo():
    """
    View an approximate demonstration of the dracula theme

    The code shown here is same as the dracula template repo. To switch between different programming languages,
    use the arrow keys left and right. To scroll you can use the mouse or the up and down arrow keys, the page-up and page-down keys
    also work. To exit, press q
    """
    from ._tui import DraculaDemoApp

    # fmt: off
    # Generate a list of all available demo files
    urls = [
        f"https://raw.githubusercontent.com/dracula/template/master/sample/dracula.{ext}"
        for ext in ('c', 'c++', 'clj', 'cs', 'css', 'dart', 'ex', 'go', 'html',
                    'java', 'js', 'kt', 'md', 'php', 'py', 'rb', 'rs', 'scala',
                    'sml', 'swift', 'ts')
    ]
    # fmt: on

    syntaxes = []
    for url in track(urls, transient=True, description="Loading code demos"):
        # Get the contents of each of the demo files. This is only done once in 3 months
        response = session.get(url)
        if response.status_code != 200:
            continue
        try:
            lexer = guess_lexer_for_filename("dracula." + url.split(".")[-1], response.text)
        except ClassNotFound:
            continue
        syntaxes.append(Syntax(response.text, lexer))
    DraculaDemoApp.run(title="Theme demo", syntaxes=syntaxes)


@app.command()
def download(app: str = typer.Argument(..., help="The name of the app to view")):
    """
    Download files for a theme to a specific folder

    This is useful for themes where there is some kind of configuration files required
    in order to install the theme. Use `.` if the path is the current working directory
    """

    github_files = []
    # Render a rich tree for better understanding of the directory structure
    tree = _render_tree(f"dracula/{app}", github_files)
    console.print(tree)

    files = questionary.checkbox("Which file(s) do you want to download?", github_files).ask()
    if not files:
        raise typer.Exit()
    # Ask the user for a path to download the files to, this has autocompletion
    download_path = questionary.path(
        "Where to download the file to?", only_directories=True, complete_style=CompleteStyle.MULTI_COLUMN
    ).ask()
    # The default download path is the current working directory
    if download_path is None:
        download_path = "."
    # Ask for confirmation before downloading the file
    confirmed = questionary.confirm(f"Are you sure you want to download {files} to {download_path} ")
    if confirmed:
        file_urls = [f"https://raw.githubusercontent.com/dracula/{app}/master/{lib}" for lib in files]
        download_files(file_urls, dest_dir=download_path)
