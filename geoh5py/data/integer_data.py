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

from ..shared import INTEGER_NDV
from .data import PrimitiveTypeEnum
from .numeric_data import NumericData


class IntegerData(NumericData):
    def check_type(self, values: np.ndarray):
        """
        Check if the type of values is valid
        :param values: numpy array"""
        if not isinstance(values, np.ndarray):
            raise TypeError("Values must be a numpy array")
        if np.sum(values - values.astype(np.int32)) != 0:
            raise TypeError("Values cannot have decimal points.")

        return values.astype(np.int32)

    @classmethod
    def primitive_type(cls) -> PrimitiveTypeEnum:
        return PrimitiveTypeEnum.INTEGER

    @property
    def nan_value(self):
        """
        Nan-Data-Value
        """
        return self.ndv

    @property
    def ndv(self) -> int:
        """
        No-Data-Value
        """
        return INTEGER_NDV
