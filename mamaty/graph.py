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
"""Graph representing transitions between objects"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Iterator, Optional, Set, Tuple

from mamaty.databank import Object, Transition, TransitionType, load_databank


class GraphNode(ABC):
    """Graph node"""

    DEFAULT_COMPLEXITY = 9999999999

    def __init__(self) -> None:
        self.complexity = self.DEFAULT_COMPLEXITY

    @abstractmethod
    def update_complexity(self, incoming_complexity: int) -> bool:
        """Update the complexity, return True if should propagate"""
        pass

    @abstractmethod
    def graphviz_decl(self) -> str:
        """How to declare the node to graphviz"""
        pass

    @abstractmethod
    def graphviz_name(self) -> str:
        """How to use the node in graphviz"""
        pass


class NodeObject(GraphNode):
    """Graph node representing an object"""

    def __init__(self, obj: Object) -> None:
        super().__init__()
        self.obj = obj
        if obj.is_natural:
            self.complexity = 0
        assert self.obj.identifier < self.DEFAULT_COMPLEXITY

    def update_complexity(self, incoming_complexity: int) -> bool:
        assert incoming_complexity < self.DEFAULT_COMPLEXITY
        if self.complexity > incoming_complexity:
            self.complexity = incoming_complexity
            return True
        return False

    def graphviz_decl(self) -> str:
        color = ",color=green" if self.complexity == 0 else ""
        return '{} [label="{}"{}]'.format(self.obj.identifier, self.obj.name,
                                          color)

    def graphviz_name(self) -> str:
        return '{}'.format(self.obj.identifier)

    def __str__(self) -> str:
        return "{} ({})".format(self.obj.name, self.complexity)


class NodeTransition(GraphNode):
    """Graph node serving as an intermediate to a transition"""

    def __init__(self, transition: Transition) -> None:
        super().__init__()
        self.transition = transition
        self.complexity = -1

    def update_complexity(self, incoming_complexity: int) -> bool:
        assert incoming_complexity < self.DEFAULT_COMPLEXITY
        if self.complexity == -1:
            self.complexity = incoming_complexity
            return len(list(self.transition.get_input_objects())) == 1
        self.complexity = max(self.complexity, incoming_complexity)
        return True  # Now the distance is computed

    def graphviz_decl(self) -> str:
        return '{} [label="+"{}]'.format(
            self.graphviz_name(),
            ",shape=record,width=.05,height=.05,fontsize=6")

    @staticmethod
    def _format_object(obj: int) -> str:
        return str(obj) if obj >= 0 else "m{}".format(-obj)

    def graphviz_name(self) -> str:
        return 't{}p{}{}{}'.format(
            self._format_object(self.transition.actor),
            self._format_object(self.transition.target), "LA"
            if self.transition.last_use_actor else "", "LT"
            if self.transition.last_use_target else "")


def _get_node_through_proxy(node: int, proxy: Dict[int, int]) -> int:
    if node in proxy:
        return proxy[node]
    return node


class EdgeType(Enum):
    """Clasification for an edge (part of a transition)"""
    NATURAL = 0
    BARE_HANDS = 1
    INTERACT = 2
    DROP = 3
    CONSUME = 4
    TOOL = 5
    TRANSITION = 6
    CATEGORY = 7
    OTHER = 8


class Edge():
    """Graph edge"""

    def __init__(self, from_node: int, to_node: int, category: EdgeType,
                 transition: Optional[Transition]) -> None:
        self.from_node = from_node
        self.to_node = to_node
        self.category = category
        self.transition = transition
        self.looping = False

    def format_time(self) -> str:
        """Format a transition time into a readable string"""
        if self.transition is None:
            return ""
        time = self.transition.auto_decay_seconds
        if time == 0:
            return ""
        if time < 0:
            return "{} epoch".format(-time)
        if time % 60 == 0:
            return "{} min".format(time // 60)
        return "{} s".format(time)

    def graphviz(self, nodes: List[GraphNode],
                 proxy_nodes: Dict[int, int]) -> str:
        """Graphviz representation of the edge"""
        edge = "{} -> {}".format(nodes[_get_node_through_proxy(
            self.from_node,
            proxy_nodes)].graphviz_name(), nodes[_get_node_through_proxy(
                self.to_node, proxy_nodes)].graphviz_name())
        edge += ' [label="{}"'.format(self.format_time())
        if self.category == EdgeType.NATURAL:
            edge += ',color="green"'
        elif self.category == EdgeType.BARE_HANDS:
            edge += ',color="blue"'
        elif self.category == EdgeType.INTERACT:
            edge += ',color="purple"'
        elif self.category == EdgeType.DROP:
            edge += ',color="brown"'
        elif self.category == EdgeType.CONSUME:
            edge += ',color="red"'
        elif self.category == EdgeType.TOOL:
            edge += ',color="black"'
        elif self.category == EdgeType.TRANSITION:
            edge += ',color="grey"'
        elif self.category == EdgeType.CATEGORY:
            edge += ',color="yellow"'
        edge += "]"
        return edge

    def cost(self) -> int:
        """Return the cost of the edge in the graph"""
        if self.category in (EdgeType.NATURAL, EdgeType.TRANSITION):
            return 0
        return 1


def _transition_type_to_edge_type(transition_type: TransitionType) -> EdgeType:
    edge_type = EdgeType.OTHER
    if transition_type == TransitionType.NATURAL:
        edge_type = EdgeType.NATURAL
    elif transition_type == TransitionType.BARE_HANDS:
        edge_type = EdgeType.BARE_HANDS
    elif transition_type == TransitionType.INTERACT:
        edge_type = EdgeType.INTERACT
    elif transition_type == TransitionType.DROP:
        edge_type = EdgeType.DROP
    elif transition_type == TransitionType.CRAFT:
        edge_type = EdgeType.CONSUME  # maybe TOOL, only caller knows
    assert edge_type != EdgeType.OTHER
    return edge_type


class Graph:
    """Representation of a graph"""

    def __init__(self, objects: Dict[int, Object],
                 transitions: List[Transition]) -> None:
        self._nodes = []  # type: List[GraphNode]
        self._edges = []  # type: List[Edge]
        self._incoming_edges = []  # type: List[List[int]]
        self._out_edges = []  # type: List[List[int]]
        self.obj_to_node = {}  # type: Dict[int, int]

        self._create(objects, transitions)
        self._finish_computation()

    def _create(self, objects: Dict[int, Object],
                transitions: List[Transition]) -> None:
        """Make graph for objects"""
        # Create nodes:
        for obj in objects.values():
            if obj.identifier > 0:
                self.obj_to_node[obj.identifier] = len(self._nodes)
                self._nodes.append(NodeObject(obj))
        # Add category edges
        for obj in objects.values():
            for contains in obj.category_contains:
                self._edges.append(
                    Edge(self.obj_to_node[contains.identifier],
                         self.obj_to_node[obj.identifier], EdgeType.CATEGORY,
                         None))
        # Add transition edges
        for transition in transitions:
            node = len(self._nodes)
            self._nodes.append(NodeTransition(transition))
            outputs = list(transition.get_output_objects())
            inputs = list(transition.get_input_objects())
            for output in outputs:
                if output not in inputs:
                    self._edges.append(
                        Edge(node, self.obj_to_node[output],
                             EdgeType.TRANSITION, None))
            for input_ in inputs:
                edge_type = _transition_type_to_edge_type(transition.type)
                if edge_type == EdgeType.CONSUME and input_ in outputs:
                    edge_type = EdgeType.TOOL
                self._edges.append(
                    Edge(self.obj_to_node[input_], node, edge_type,
                         transition))

    def _finish_computation(self) -> None:
        """To be called after adding nodes and/or edges"""

        # Update the incoming and out edges of each node
        self._incoming_edges = [[] for _ in range(len(self._nodes))]
        self._out_edges = [[] for _ in range(len(self._nodes))]
        for i, edge in enumerate(self._edges):
            self._out_edges[edge.from_node].append(i)
            self._incoming_edges[edge.to_node].append(i)

        self.__propagate_complexity()

        scc = self.__tarjan()
        self.__remove_loops(scc)

    def __propagate_complexity(self) -> None:
        to_visit = set(
            i for i, node in enumerate(self._nodes) if node.complexity == 0)
        while to_visit:
            current = to_visit.pop()
            current_node = self._nodes[current]
            distance = current_node.complexity
            for edge_n in self._out_edges[current]:
                edge = self._edges[edge_n]
                if self._nodes[edge.to_node].update_complexity(
                        distance + edge.cost()):
                    to_visit.add(edge.to_node)
        for i in self._nodes:
            if i.complexity == i.DEFAULT_COMPLEXITY:
                print("// WARNING: Object {} is unreachable".format(i))

    def __tarjan(self) -> List[int]:
        # Tarjan's strongly connected components algorithm
        index = 0
        indexes = [-1 for _ in range(len(self._nodes))]
        low_link = [-1 for _ in range(len(self._nodes))]
        on_stack = [False for _ in range(len(self._nodes))]
        stack = []
        scc = [-1 for _ in range(len(self._nodes))]
        scc_index = 0

        def __strongconnect(node: int) -> None:
            nonlocal index
            nonlocal indexes
            nonlocal low_link
            nonlocal on_stack
            nonlocal stack
            nonlocal scc
            nonlocal scc_index
            indexes[node] = index
            low_link[node] = index
            index += 1
            stack.append(node)
            on_stack[node] = True
            for edge_n in self._out_edges[node]:
                other_node = self._edges[edge_n].to_node
                if indexes[other_node] == -1:
                    __strongconnect(other_node)
                    low_link[node] = min(low_link[node], low_link[other_node])
                elif on_stack[other_node]:
                    low_link[node] = min(low_link[node], indexes[other_node])
            if low_link[node] == indexes[node]:
                other_node = -1
                while other_node != node:
                    other_node = stack.pop()
                    on_stack[other_node] = False
                    scc[other_node] = scc_index
                scc_index += 1

        for node in range(len(self._nodes)):
            if indexes[node] == -1:
                __strongconnect(node)
        assert -1 not in scc
        return scc

    def __remove_loops(self, scc: List[int]) -> None:
        possible_from = []  # type: List[int]
        possible_to = []  # type: List[int]
        possible_edge = []  # type: List[int]
        for i in range(len(self._nodes)):
            in_edges = [self._edges[j] for j in self._incoming_edges[i]]
            parents = ((e.from_node, e) for e in in_edges
                       if scc[e.from_node] == scc[i])
            for parent, edge in parents:
                if edge.category in (EdgeType.BARE_HANDS, EdgeType.INTERACT,
                                     EdgeType.NATURAL, EdgeType.DROP,
                                     EdgeType.CONSUME):
                    distance = self._nodes[parent].complexity
                    children = ((c, e) for c, e in self.get_out(i)
                                if scc[c] == scc[i]
                                and self._nodes[c].complexity < distance)
                    for child, edge_child in children:
                        possible_from.append(parent)
                        possible_to.append(child)
                        possible_edge.append(edge_child)
        delete_edges = []  # type: List[int]
        for from_node, to_node, edg in zip(possible_from, possible_to,
                                           possible_edge):
            # If we are here, this means that we want to remove the connection
            # from from_node to to_node, because from one we can make the
            # other, and vice versa. Also from_node is more complex than
            # to_node. Problem is, Straw is more complex than a Basket (that
            # can be made simply with Reed), and we want to keep the connection
            # from Straw to Basket.
            distances = [(-1) for _ in range(len(self._nodes))]
            distances[to_node] = 0
            to_visit = {to_node}
            while to_visit:
                current = to_visit.pop()
                current_distance = distances[current]
                for child, child_edge in self.get_out(current):
                    if scc[child] != scc[to_node]:
                        continue
                    new_dist = current_distance + self._edges[child_edge].cost(
                    )
                    if distances[child] == -1 or distances[child] > new_dist:
                        distances[child] = new_dist
                        to_visit.add(child)

            diff = self._nodes[from_node].complexity - \
                    self._nodes[to_node].complexity
            if distances[from_node] <= diff:
                delete_edges.append(edg)

        for delete in delete_edges:
            self._edges[delete].looping = True

    def _is_edge_valid(self, edge_id: int, ignored_nodes: Set[int],
                       ignored_edges: Set[int],
                       proxy_nodes: Dict[int, int]) -> bool:
        if edge_id in ignored_edges:
            return False
        edge = self._edges[edge_id]
        from_node = _get_node_through_proxy(edge.from_node, proxy_nodes)
        to_node = _get_node_through_proxy(edge.to_node, proxy_nodes)
        if from_node == to_node:
            return False
        return not any(i in ignored_nodes for i in (from_node, to_node))

    def to_graphviz(self,
                    ignored_nodes: Optional[Set[int]] = None,
                    ignored_edges: Optional[Set[int]] = None,
                    proxy_nodes: Optional[Dict[int, int]] = None) -> str:
        """Make a graphviz"""
        if ignored_nodes is None:
            ignored_nodes = set()
        if ignored_edges is None:
            ignored_edges = set()
        if proxy_nodes is None:
            proxy_nodes = {}
        graph = "digraph G {\n"
        for i, node in enumerate(self._nodes):
            if i not in ignored_nodes and i not in proxy_nodes:
                graph += '    {};\n'.format(node.graphviz_decl())
        for i, edge in enumerate(self._edges):
            if self._is_edge_valid(i, ignored_nodes, ignored_edges,
                                   proxy_nodes):
                graph += '    {};\n'.format(
                    edge.graphviz(self._nodes, proxy_nodes))
        graph += '}'
        return graph

    def get_out(self, node: int) -> Iterator[Tuple[int, int]]:
        """Get children nodes and its edge, if still in the graph"""
        for edge_n in self._out_edges[node]:
            yield (self._edges[edge_n].to_node, edge_n)


def load_databank_graph(root_folder: str) -> Graph:
    """Get full graph of all transitions in the databank"""
    databank = load_databank(root_folder)
    return Graph(databank[0], databank[1])
