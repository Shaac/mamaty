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
"""Utils to load and use the game data bank"""

import os
from enum import Enum
from typing import Dict, Iterator, List, Tuple, Type, TypeVar

_T_OBJECT = TypeVar('_T_OBJECT', bound='Object')
_T_TRANSITION = TypeVar('_T_TRANSITION', bound='Transition')


class Object:
    """An in game object"""

    def __init__(self: _T_OBJECT, identifier: int, name: str,
                 natural: bool) -> None:
        self.identifier = identifier
        self.name = name
        self.is_natural = natural
        self.is_category = False
        self.transitions_from = []  # type: List[Transition]
        self.transitions_to = []  # type: List[Transition]
        self.transitions_through = []  # type: List[Transition]
        self.category_contains = []  # type: List[_T_OBJECT]

    def __repr__(self: _T_OBJECT) -> str:
        return self.name

    def set_category(self: _T_OBJECT, content: List[_T_OBJECT]) -> None:
        """Set this object as a category and list of contained objects"""
        assert content
        assert self.name[0] == '@'
        self.is_category = True
        self.category_contains = content

    @classmethod
    def from_file(cls: Type[_T_OBJECT], filename: str) -> _T_OBJECT:
        """Parse an object file"""
        with open(filename, 'r') as in_file:
            object_id = int(in_file.readline()[3:].strip())
            name = in_file.readline().strip()
            natural = False
            for line in in_file:
                split = line.split("=")
                if split[0] == 'mapChance':
                    natural = natural or float(split[1].split('#')[0]) != 0
                    if natural:
                        break
                elif split[0] == 'deathMarker':
                    natural = natural or int(split[1].strip()) != 0
                    if natural:
                        break
            return cls(object_id, name, natural)

    @classmethod
    def parse_all(cls: Type[_T_OBJECT],
                  object_folder: str) -> Dict[int, _T_OBJECT]:
        """Parse all objects from objects folder"""
        next_object = 0
        try:
            with open(object_folder + "/nextObjectNumber.txt", 'r') as in_file:
                next_object = int(in_file.read())
        except (FileNotFoundError, ValueError):
            return {}
        dic = {}  # type: Dict[int, _T_OBJECT]
        for i in range(next_object):
            try:
                obj = cls.from_file("{}/{}.txt".format(object_folder, i))
                assert i == obj.identifier
                dic[i] = obj
            except (FileNotFoundError, ValueError):
                continue
        assert 0 not in dic
        dic[0] = cls(0, "Bare Hands", True)
        return dic


class TransitionType(Enum):
    """Classification of transitions"""
    NATURAL = 0
    BARE_HANDS = 1
    INTERACT = 2
    DROP = 3
    CRAFT = 4


class Transition:
    """A recipe: transition from objects to others"""

    def __init__(self: _T_TRANSITION,
                 actor: int,
                 target: int,
                 new_actor: int,
                 new_target: int,
                 last_use_actor: bool = False,
                 last_use_target: bool = False,
                 auto_decay_seconds: int = 0,
                 actor_min_use_fraction: float = 0.,
                 target_min_use_fraction: float = 0.,
                 reverse_use_actor_flag: int = 0,
                 reverse_use_target_flag: int = 0,
                 move: int = 0,
                 desired_move_dist: int = 0) -> None:
        # Object hold in hand before the transition
        self.actor = actor
        # Object on the ground before the transition
        self.target = target
        # Object hold in hand after the transition
        self.new_actor = new_actor
        # Object on the ground after the transition
        self.new_target = new_target
        # Automaticly occurs after this number in seconds, and is epocs if < 0
        self.auto_decay_seconds = auto_decay_seconds
        # This transition consumes the last use of the actor
        self.last_use_actor = last_use_actor
        # This transition consumes the last use of the target
        self.last_use_target = last_use_target
        # ?
        self.move = move
        # ?
        self.desired_move_dist = desired_move_dist
        # The transitions gives one use back to the actor
        self.reverse_use_actor_flag = reverse_use_actor_flag == 1
        # The transitions gives one use back to the target
        self.reverse_use_target_flag = reverse_use_target_flag == 1
        self.actor_min_use_fraction = actor_min_use_fraction
        self.target_min_use_fraction = target_min_use_fraction

        self.type = TransitionType.CRAFT
        if actor == -1:
            self.type = TransitionType.NATURAL
            assert target > 0
        elif actor == 0:
            self.type = TransitionType.BARE_HANDS
            assert target > 0
        elif actor == -2:
            self.type = TransitionType.INTERACT
            assert target > 0
        elif target == -1:
            self.type = TransitionType.DROP
            assert actor > 0
        assert (self.type == TransitionType.NATURAL) == (auto_decay_seconds !=
                                                         0)

    def add_to_objects(self: _T_TRANSITION,
                       objects: Dict[int, _T_OBJECT]) -> None:
        """Add transition to objects presents in it"""
        for object_from in self.get_input_objects():
            if object_from in self.get_output_objects():
                objects[object_from].transitions_through.append(self)
            else:
                objects[object_from].transitions_from.append(self)
        for object_to in self.get_output_objects():
            if object_to not in self.get_input_objects():
                objects[object_to].transitions_to.append(self)

    def get_input_objects(self: _T_TRANSITION) -> Iterator[int]:
        """Give identifier of input objects if there are real objects"""
        if self.actor > 0:
            yield self.actor
        if self.target > 0:
            yield self.target

    def get_output_objects(self: _T_TRANSITION) -> Iterator[int]:
        """Give identifier of output objects if there are real objects"""
        if self.new_actor > 0:
            yield self.new_actor
        if self.new_target > 0:
            yield self.new_target

    @classmethod
    def from_file(cls: Type[_T_TRANSITION], folder: str,
                  filename: str) -> _T_TRANSITION:
        """Parse a transition file"""
        args = filename[:-4].split('_')
        actor = int(args[0])
        target = int(args[1])
        last_use_actor = 'LA' in args
        last_use_target = 'LT' in args or 'L' in args
        line = ''
        with open(folder + "/" + filename, 'r') as in_file:
            line = in_file.readline().strip()
        args = line.split()
        new_actor = int(args[0])
        new_target = int(args[1])
        auto_decay_seconds = int(args[2]) if len(args) > 2 else 0
        actor_min_use_fraction = float(args[3]) if len(args) > 3 else 0.
        target_min_use_fraction = float(args[4]) if len(args) > 4 else 0.
        reverse_use_actor_flag = int(args[5]) if len(args) > 5 else 0
        reverse_use_target_flag = int(args[6]) if len(args) > 6 else 0
        move = int(args[7]) if len(args) > 7 else 0
        desired_move_dist = int(args[8]) if len(args) > 8 else 0
        return cls(actor, target, new_actor, new_target, last_use_actor,
                   last_use_target, auto_decay_seconds, actor_min_use_fraction,
                   target_min_use_fraction, reverse_use_actor_flag,
                   reverse_use_target_flag, move, desired_move_dist)

    @classmethod
    def parse_all(cls: Type[_T_TRANSITION],
                  transition_folder: str) -> Iterator[_T_TRANSITION]:
        """Parse all transitions from transitions folder"""
        for filename in os.listdir(transition_folder):
            if filename.endswith(".txt"):
                yield cls.from_file(transition_folder, filename)


def _parse_all_categories(categories_folder: str,
                          objects: Dict[int, _T_OBJECT]) -> None:
    """Parse all categories from categories folder"""
    for filename in os.listdir(categories_folder):
        if filename.endswith(".txt"):
            with open(categories_folder + "/" + filename, 'r') as in_file:
                parent_id = int(in_file.readline().strip().split("=")[1])
                num_objs = int(in_file.readline().strip().split("=")[1])
                objects[parent_id].set_category([
                    objects[int(in_file.readline().strip())]
                    for _ in range(num_objs)
                ])


def load_databank(
        root_folder: str) -> Tuple[Dict[int, Object], List[Transition]]:
    """Read all objects and load them with transitions and categories.
    Returns both the object list and the transition list
    """
    objects = Object.parse_all(root_folder + '/objects')
    transitions = list(Transition.parse_all(root_folder + '/transitions'))
    for transition in transitions:
        transition.add_to_objects(objects)
    _parse_all_categories(root_folder + '/categories', objects)
    return objects, transitions
