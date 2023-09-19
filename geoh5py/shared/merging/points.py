#  Copyright (c) 2023 Mira Geoscience Ltd.
#
#  This file is part of geoh5py.
#
#  geoh5py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Lesser General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  geoh5py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with geoh5py.  If not, see <https://www.gnu.org/licenses/>.
from __future__ import annotations

import numpy as np

from ...objects import ObjectBase, Points
from ...workspace import Workspace
from .base import BaseMerger


class PointsMerger(BaseMerger):
    _type = Points

    @classmethod
    def validate_type(cls, input_entity):
        # want to make sure that the input entities are Points, no subclasses
        if type(input_entity) is not cls._type:  # pylint: disable=unidiomatic-typecheck
            raise TypeError("The input entities must be a list of geoh5py Points.")

    @classmethod
    def create_object(
        cls, workspace: Workspace, input_entities: list[ObjectBase], **kwargs
    ) -> Points:
        # create the vertices
        vertices = np.vstack([input_entity.vertices for input_entity in input_entities])

        # create an object of type
        output = cls._type.create(workspace, vertices=vertices, **kwargs)

        return output
