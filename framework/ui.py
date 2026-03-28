from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class NavNode:
    label: str
    href: str | None = None  # None = current page
    icon: str | None = None  # Optional, for future use


@dataclass
class PageAction:
    label: str
    href: str
    style: str = "secondary"  # primary | secondary | destructive
    method: str = "get"  # get | post


_nav_nodes: list[NavNode] = []


def register_nav_node(node: NavNode) -> None:
    if node in _nav_nodes:
        return
    _nav_nodes.append(node)


def get_nav_nodes() -> Sequence[NavNode]:
    return _nav_nodes.copy()
