from __future__ import annotations

from framework.ui import NavNode, PageAction, get_nav_nodes, register_nav_node


class TestNavRegistry:
    def test_registers_nav_node_once(self) -> None:
        node = NavNode(label="Current Affairs", href="/current-affairs/")

        register_nav_node(node)
        register_nav_node(node)

        assert list(get_nav_nodes()) == [node]

    def test_returns_copy_of_registered_nodes(self) -> None:
        node = NavNode(label="Current Affairs", href="/current-affairs/")
        register_nav_node(node)

        nodes = list(get_nav_nodes())
        nodes.append(NavNode(label="Journal", href="/journal/"))

        assert list(get_nav_nodes()) == [node]


class TestUiDataclasses:
    def test_page_action_defaults(self) -> None:
        action = PageAction(label="Save", href="/save")

        assert action.style == "secondary"
        assert action.method == "get"
