# Copyright 2018 Sacha Delanoue
#
# This file is part of MamaTY, a helper for the game 'One Hour One Life'.
#
# MamaTY is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# MamaTY is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with MamaTY.  If not, see <http://www.gnu.org/licenses/>.
"""Graph partial representation of transitions between objects"""

from enum import Enum
from typing import Dict, Iterator, Set

from mamaty.graph import Graph, NodeObject


class IgnoreMode(Enum):
    """Different ways to ignore parents of a node"""
    NO_PARENTS = 0
    LEAST_COMPLEX_PARENT = 1
    ONLY_EXISTING_PARENTS = 2
    ALL_PARENTS = 3


class SubGraph():  # pylint: disable=protected-access
    """Graph with some edges and nodes ignored"""

    def __init__(self, graph: Graph) -> None:
        self.graph = graph
        self.ignored_nodes = set()  # type: Set[int]
        self.ignored_edges = set()  # type: Set[int]
        for i, edge in enumerate(self.graph._edges):
            if edge.looping:
                self.ignored_edges.add(i)

        self.max_distance = 50
        self.ignore_categories = IgnoreMode.ONLY_EXISTING_PARENTS
        self.ignore_natural = IgnoreMode.NO_PARENTS
        self.ignore_others = IgnoreMode.LEAST_COMPLEX_PARENT

    def _compute_proxy(self) -> Dict[int, int]:
        proxy = {}  # type Dict[int, int]
        for i, node in enumerate(self.graph._nodes):
            if not isinstance(node, NodeObject):
                if len(list(self._get_parents(i))) == 1:
                    children = list(self._get_children(i))
                    if len(children) == 1:
                        proxy[i] = children[0]
        return proxy

    def to_graphviz(self) -> str:
        """Make a graphviz"""
        return self.graph.to_graphviz(self.ignored_nodes, self.ignored_edges,
                                      self._compute_proxy())

    def leading_to_obj(self, obj: int) -> None:
        """Simplify graph: only have nodes and edges leading to obj node"""
        self.ignored_edges.union(self._edges_ignored_by_no_parent_nodes())

        start = self.graph.obj_to_node[obj]
        visited = {start}
        distances = [0 for _ in range(len(self.graph._nodes))]
        to_visit = {start}
        while to_visit:
            current = to_visit.pop()
            distance = distances[current] if self.max_distance > 0 else -1
            if distance > self.max_distance:
                continue
            for parent in self._get_parents(current):
                if parent not in visited:
                    distances[parent] = distance + 1
                    visited.add(parent)
                    to_visit.add(parent)
                elif distances[parent] < distance + 1:
                    distances[parent] = distance + 1
                    to_visit.add(parent)

        for i in range(len(self.graph._nodes)):
            if i not in visited:
                self.ignored_nodes.add(i)

    def _get_ignore_type(self, node_index: int) -> IgnoreMode:
        """Get ignore mode of node"""
        node = self.graph._nodes[node_index]
        if not isinstance(node, NodeObject):
            return IgnoreMode.ALL_PARENTS
        if node.complexity == 0:
            return self.ignore_natural
        if node.obj.is_category:
            return self.ignore_categories
        return self.ignore_others

    def _get_children(self, node: int) -> Iterator[int]:
        """Get children nodes in the subgraph"""
        for edge_n in self.graph._out_edges[node]:
            if edge_n in self.ignored_edges:
                continue
            child = self.graph._edges[edge_n].to_node
            if child not in self.ignored_nodes:
                if node in self._get_parents(child):
                    yield child

    def _get_all_parents(self, node: int) -> Iterator[int]:
        """Get parents nodes in the subgraph, even if ignored by the node"""
        for edge_n in self.graph._incoming_edges[node]:
            if edge_n in self.ignored_edges:
                continue
            parent = self.graph._edges[edge_n].from_node
            if parent not in self.ignored_nodes:
                yield parent

    def _get_parents(self, node: int) -> Iterator[int]:
        """Get parents nodes in the subgraph"""
        mode = self._get_ignore_type(node)
        if mode in (IgnoreMode.NO_PARENTS, IgnoreMode.ONLY_EXISTING_PARENTS):
            pass
        elif mode == IgnoreMode.ALL_PARENTS:
            for i in self._get_all_parents(node):
                yield i
        else:
            assert mode == IgnoreMode.LEAST_COMPLEX_PARENT
            parents = list(self._get_all_parents(node))
            chosen = parents[0]
            complexity = self.graph._nodes[chosen].complexity
            for parent in parents:
                if self.graph._nodes[parent].complexity < complexity:
                    chosen = parent
                    complexity = self.graph._nodes[chosen].complexity
            yield chosen

    def _edges_ignored_by_no_parent_nodes(self) -> Set[int]:
        ignored_edges = set()  # type: Set[int]
        for i in range(len(self.graph._nodes)):
            if self._get_ignore_type(i) == IgnoreMode.NO_PARENTS:
                for edge in self.graph._incoming_edges[i]:
                    ignored_edges.add(edge)
        return ignored_edges
