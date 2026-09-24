"""`grymbl` command line: setup, the watcher, and the entry points hooks call."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable, Sequence
from importlib import resources
from pathlib import Path

from grymbl.config import Settings, find_repo_root
from grymbl.sensors import developer_name
from grymbl.sensors.files import FileSensor
from grymbl.sensors.git import (
    capture_commit,
    capture_push,
    git_toplevel,
    install_hooks,
    is_git_repo,
)
from grymbl.sensors.terminal import capture_command
from grymbl.sensors.tests import UnsupportedRunnerError, run_and_capture
from grymbl.store import Store
from grymbl.watch import watch

_Capture = Callable[[Store, Path], object]

SHELLS = {"bash": "grymbl.bash", "zsh": "grymbl.zsh", "powershell": "grymbl.ps1"}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    handler: int = args.handler(args)
    return handler


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="grymbl", description=__doc__)
    commands = parser.add_subparsers(required=True, metavar="command")

    init = commands.add_parser("init", help="start watching a repository")
    init.add_argument("path", nargs="?", default=".", type=Path)
    init.set_defaults(handler=_init)

    run = commands.add_parser("watch", help="run the watcher (foreground)")
    run.add_argument("path", nargs="?", default=".", type=Path)
    run.set_defaults(handler=_watch)

    status = commands.add_parser("status", help="show recent episodes")
    status.add_argument("-n", type=int, default=10, help="number of episodes")
    status.set_defaults(handler=_status)

    hook = commands.add_parser("shell-hook", help="print the terminal hook for a shell")
    hook.add_argument("shell", choices=sorted(SHELLS))
    hook.set_defaults(handler=_shell_hook)

    test = commands.add_parser(
        "test", help="run tests and record the result: grymbl test -- pytest"
    )
    test.add_argument("command", nargs=argparse.REMAINDER)
    test.set_defaults(handler=_test)

    command = commands.add_parser("capture-command", help=argparse.SUPPRESS)
    command.add_argument("--exit-code", type=int, required=True)
    command.set_defaults(handler=_capture_command)

    git = commands.add_parser("capture-git", help=argparse.SUPPRESS)
    git.add_argument("hook", choices=("post-commit", "pre-push"))
    git.add_argument("hook_args", nargs="*")
    git.set_defaults(handler=_capture_git)
    return parser


def _init(args: argparse.Namespace) -> int:
    root = args.path.resolve()
    if is_git_repo(root):
        root = git_toplevel(root)
    settings = Settings(root)
    settings.data_dir.mkdir(exist_ok=True)
    (settings.data_dir / ".gitignore").write_text("*\n", encoding="utf-8")

    with Store(settings.db_path) as store:
        developer = developer_name(store, root)
        baseline = FileSensor(store, settings, developer).resync()
    print(f"Initialized {settings.data_dir} for {developer} ({baseline} files in baseline)")

    if is_git_repo(root):
        for note in install_hooks(root):
            print(f"git hooks: {note}")
    print(
        "\nNext:\n"
        "  1. Load the terminal hook in your shell profile:\n"
        '       bash (~/.bashrc):  eval "$(grymbl shell-hook bash)"\n'
        '       zsh  (~/.zshrc):   eval "$(grymbl shell-hook zsh)"\n'
        "       PowerShell ($PROFILE):\n"
        "         grymbl shell-hook powershell | Out-String | Invoke-Expression\n"
        "  2. Run tests through Grymbl:  grymbl test -- pytest\n"
        "  3. Start the watcher:  grymbl watch"
    )
    return 0


def _watch(args: argparse.Namespace) -> int:
    root = find_repo_root(args.path)
    if root is None:
        print("Not a Grymbl-watched repository. Run `grymbl init` first.", file=sys.stderr)
        return 1
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    watch(Settings(root))
    return 0


def _status(args: argparse.Namespace) -> int:
    root = find_repo_root(Path.cwd())
    if root is None:
        print("Not a Grymbl-watched repository. Run `grymbl init` first.", file=sys.stderr)
        return 1
    with Store(Settings(root).db_path) as store:
        episodes = store.recent_episodes(args.n)
    if not episodes:
        print("No episodes yet.")
    for episode in episodes:
        flag = "ESCALATED" if episode.escalated else "routine"
        print(
            f"{episode.timestamp_start:%Y-%m-%d %H:%M}  {episode.episode_id}  "
            f"{episode.status:<6}  {flag:<9}  {', '.join(episode.files) or '-'}"
        )
        if episode.summary:
            print(f"    {episode.summary}")
    return 0


def _shell_hook(args: argparse.Namespace) -> int:
    script = resources.files("grymbl").joinpath("hooks", SHELLS[args.shell])
    sys.stdout.write(script.read_text(encoding="utf-8"))
    return 0


def _test(args: argparse.Namespace) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("Usage: grymbl test -- <test command>", file=sys.stderr)
        return 2
    cwd = Path.cwd()
    root = find_repo_root(cwd)
    if root is None:
        print("Not a Grymbl-watched repository. Run `grymbl init` first.", file=sys.stderr)
        return 2
    with Store(Settings(root).db_path) as store:
        try:
            return run_and_capture(command, store, developer_name(store, root), root, cwd)
        except UnsupportedRunnerError as error:
            print(f"grymbl: {error}", file=sys.stderr)
            return 2


def _capture_command(args: argparse.Namespace) -> int:
    # Read bytes: shells differ in stdin encoding, and every hook writes UTF-8.
    raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    return _quietly(
        lambda store, root: capture_command(store, developer_name(store, root), raw, args.exit_code)
    )


def _capture_git(args: argparse.Namespace) -> int:
    if args.hook == "post-commit":
        return _quietly(
            lambda store, root: capture_commit(store, developer_name(store, root), root)
        )
    remote = args.hook_args[0] if args.hook_args else "unknown"
    lines = sys.stdin.read().splitlines()
    return _quietly(
        lambda store, root: capture_push(store, developer_name(store, root), remote, lines)
    )


def _quietly(capture: _Capture) -> int:
    """Run a hook-triggered capture without ever disturbing the developer's shell or git.

    Outside a watched repo this is a no-op. Failures go to the repo's log file, never the
    terminal, and the exit code is always 0.
    """
    root = find_repo_root(Path.cwd())
    if root is None:
        return 0
    settings = Settings(root)
    logging.basicConfig(
        filename=settings.log_path, level=logging.INFO, format="%(asctime)s %(message)s"
    )
    try:
        with Store(settings.db_path) as store:
            capture(store, root)
    except Exception:  # A hook must never break the shell or block a commit.
        logging.getLogger(__name__).exception("capture failed")
    return 0
