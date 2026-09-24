"""Terminal sensor: the shell hooks pipe each finished command here (plan §5).

The raw command only ever exists in this process's memory. It is redacted before it
is stored, and nothing is sent over the network.
"""

from __future__ import annotations

from grymbl.events import Event, EventKind, utcnow
from grymbl.redact import redact
from grymbl.store import Store

# Our own plumbing is not developer activity.
_SELF_COMMANDS = ("grymbl capture-", "grymbl status", "grymbl shell-hook")


def is_self_command(command: str) -> bool:
    return command.startswith(_SELF_COMMANDS)


def capture_command(store: Store, developer: str, raw_command: str, exit_code: int) -> Event | None:
    command = raw_command.strip()
    if not command or is_self_command(command):
        return None
    return store.add_event(
        Event(
            EventKind.COMMAND,
            utcnow(),
            developer,
            payload={"command": redact(command), "exit_code": exit_code},
        )
    )
