MamaTY
======

Software to help with One Hour One Life tech tree.

Currently it can output graph of how to make an object.

## Dependencies

- Python >= 3.5
- graphviz

## Usage

    ./create_png_graph.sh <game-data-folder> <object-id> <output-image.png>

For exemple if you want to know how to make a Clay Bowl:

    ./create_png_graph.sh ../FolderContainingOneLifeApp/ 235 bowl.png
