#!/usr/bin/env bash

./print_object_graphviz.py $1 $2 | dot -Tpng -o$3
