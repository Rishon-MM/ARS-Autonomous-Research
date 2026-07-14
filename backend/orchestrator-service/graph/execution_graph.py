"""
graph/execution_graph.py — DAG construction and traversal.

Builds the execution graph from a TaskState and supports:
- Topological ordering
- Dynamic node insertion (parallel research sub-tasks)
- Ready-node detection for parallel execution
"""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from .node import GraphNode
from models.task_state import NodeStatus

if TYPE_CHECKING:
    pass


class ExecutionGraph:
    """
    A directed acyclic graph of worker nodes.

    The graph is built once at the start of a task and can be
    extended dynamically (e.g., planner spawns N research nodes).
    """

    def __init__(self) -> None:
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[tuple[str, str]] = []  # (from_id, to_id)

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node
        for dep in node.dependencies:
            self.edges.append((dep, node.node_id))

    def add_dynamic_node(self, node: GraphNode, after: str) -> None:
        """
        Insert a node dynamically after a given node.

        Used when the planner produces N sub-tasks that each
        need their own research node.
        """
        node.dependencies.append(after)
        self.add_node(node)

    def get_ready_nodes(self, completed: set[str]) -> list[GraphNode]:
        """
        Return all nodes whose dependencies are met and that
        haven't started yet.  These can run in parallel.
        """
        ready = []
        for node in self.nodes.values():
            if (
                node.status == NodeStatus.PENDING
                and node.dependencies_met(completed)
            ):
                ready.append(node)
        return ready

    def topological_order(self) -> list[GraphNode]:
        """
        Return nodes in a valid topological order.

        Uses Kahn's algorithm for deterministic ordering.
        """
        in_degree: dict[str, int] = defaultdict(int)
        adjacency: dict[str, list[str]] = defaultdict(list)

        for node_id in self.nodes:
            in_degree.setdefault(node_id, 0)

        for from_id, to_id in self.edges:
            adjacency[from_id].append(to_id)
            in_degree[to_id] += 1

        # Start with nodes that have no incoming edges
        queue = [
            nid for nid, deg in in_degree.items()
            if deg == 0 and nid in self.nodes
        ]
        queue.sort()  # deterministic ordering

        result = []
        while queue:
            nid = queue.pop(0)
            result.append(self.nodes[nid])
            for neighbor in sorted(adjacency.get(nid, [])):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(result) != len(self.nodes):
            missing = set(self.nodes.keys()) - {n.node_id for n in result}
            raise RuntimeError(
                f"Graph has a cycle involving nodes: {missing}"
            )

        return result

    def get_node(self, node_id: str) -> GraphNode:
        """Get a node by ID."""
        if node_id not in self.nodes:
            raise KeyError(f"Node {node_id!r} not found in graph")
        return self.nodes[node_id]

    def __len__(self) -> int:
        return len(self.nodes)

    def __repr__(self) -> str:
        lines = ["ExecutionGraph:"]
        for node in self.topological_order():
            deps = ", ".join(node.dependencies) or "none"
            lines.append(f"  {node.node_id} (deps: {deps}) [{node.status.value}]")
        return "\n".join(lines)
