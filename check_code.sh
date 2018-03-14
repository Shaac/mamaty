#!/usr/bin/env bash

yapf --recursive -d mamaty/ print_object_graphviz.py
mypy --strict mamaty print_object_graphviz.py
pylint mamaty print_object_graphviz.py
