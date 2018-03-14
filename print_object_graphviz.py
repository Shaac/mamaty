#!/usr/bin/env python3
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
"""Parse One Hour One Life tech tree"""

import sys

from mamaty import load_databank_graph, Graph, SubGraph


def graphviz(graph: Graph, object_: int) -> str:
    """Print graphviz leading to object"""
    subgraph = SubGraph(graph)
    subgraph.leading_to_obj(object_)
    return subgraph.to_graphviz()


if __name__ == '__main__':
    print(graphviz(load_databank_graph(sys.argv[1]), int(sys.argv[2])))
