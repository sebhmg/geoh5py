#  Copyright (c) 2022 Mira Geoscience Ltd.
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

from abc import ABC
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable
from uuid import UUID

import h5py
import numpy as np

if TYPE_CHECKING:
    from ..workspace import Workspace
    from .entity import Entity


@contextmanager
def fetch_h5_handle(file: str | h5py.File | Path, mode: str = "r") -> h5py.File:
    """
    Open in read+ mode a geoh5 file from string.
    If receiving a file instead of a string, merely return the given file.

    :param file: Name or handle to a geoh5 file.
    :param mode: Set the h5 read/write mode

    :return h5py.File: Handle to an opened h5py file.
    """
    if isinstance(file, h5py.File):
        try:
            yield file
        finally:
            pass
    else:
        if Path(file).suffix != ".geoh5":
            raise ValueError("Input h5 file must have a 'geoh5' extension.")

        h5file = h5py.File(file, mode)

        try:
            yield h5file
        finally:
            h5file.close()


def match_values(vec_a, vec_b, collocation_distance=1e-4) -> np.ndarray:
    """
    Find indices of matching values between two arrays, within collocation_distance.

    :param: vec_a, list or numpy.ndarray
        Input sorted values

    :param: vec_b, list or numpy.ndarray
        Query values

    :return: indices, numpy.ndarray
        Pairs of indices for matching values between the two arrays such
        that vec_a[ind[:, 0]] == vec_b[ind[:, 1]].
    """
    ind_sort = np.argsort(vec_a)
    ind = np.minimum(
        np.searchsorted(vec_a[ind_sort], vec_b, side="right"), vec_a.shape[0] - 1
    )
    nearests = np.c_[ind, ind - 1]
    match = np.where(
        np.abs(vec_a[ind_sort][nearests] - vec_b[:, None]) < collocation_distance
    )
    indices = np.c_[ind_sort[nearests[match[0], match[1]]], match[0]]
    return indices


def merge_arrays(
    head,
    tail,
    replace="A->B",
    mapping=None,
    collocation_distance=1e-4,
    return_mapping=False,
) -> np.ndarray:
    """
    Given two numpy.arrays of different length, find the matching values and append both arrays.

    :param: head, numpy.array of float
        First vector of shape(M,) to be appended.
    :param: tail, numpy.array of float
        Second vector of shape(N,) to be appended
    :param: mapping=None, numpy.ndarray of int
        Optional array where values from the head are replaced by the tail.
    :param: collocation_distance=1e-4, float
        Tolerance between matching values.

    :return: numpy.array shape(O,)
        Unique values from head to tail without repeats, within collocation_distance.
    """

    if mapping is None:
        mapping = match_values(head, tail, collocation_distance=collocation_distance)

    if mapping.shape[0] > 0:
        if replace == "B->A":
            head[mapping[:, 0]] = tail[mapping[:, 1]]
        else:
            tail[mapping[:, 1]] = head[mapping[:, 0]]

        tail = np.delete(tail, mapping[:, 1])

    if return_mapping:
        return np.r_[head, tail], mapping

    return np.r_[head, tail]


def compare_entities(
    object_a, object_b, ignore: list | None = None, decimal: int = 6
) -> None:

    ignore_list = ["_workspace", "_children"]
    if ignore is not None:
        for item in ignore:
            ignore_list.append(item)

    for attr in object_a.__dict__.keys():
        if attr in ignore_list:
            continue
        if isinstance(getattr(object_a, attr[1:]), ABC):
            compare_entities(
                getattr(object_a, attr[1:]), getattr(object_b, attr[1:]), ignore=ignore
            )
        else:
            if isinstance(getattr(object_a, attr[1:]), np.ndarray):
                np.testing.assert_array_almost_equal(
                    getattr(object_a, attr[1:]).tolist(),
                    getattr(object_b, attr[1:]).tolist(),
                    decimal=decimal,
                    err_msg=f"Error comparing attribute '{attr}'.",
                )
            else:
                assert np.all(
                    getattr(object_a, attr[1:]) == getattr(object_b, attr[1:])
                ), f"Output attribute '{attr[1:]}' for {object_a} do not match input {object_b}"


def iterable(value: Any, checklen: bool = False) -> bool:
    """
    Checks if object is iterable.

    Parameters
    ----------
    value : Object to check for iterableness.
    checklen : Restrict objects with __iter__ method to len > 1.

    Returns
    -------
    True if object has __iter__ attribute but is not string or dict type.
    """
    only_array_like = (not isinstance(value, str)) & (not isinstance(value, dict))
    if (hasattr(value, "__iter__")) & only_array_like:
        return not (checklen and (len(value) == 1))

    return False


def iterable_message(valid: list[Any] | None) -> str:
    """Append possibly iterable valid: "Must be (one of): {valid}."."""
    if valid is None:
        msg = ""
    elif iterable(valid, checklen=True):
        vstr = "'" + "', '".join(str(k) for k in valid) + "'"
        msg = f" Must be one of: {vstr}."
    else:
        msg = f" Must be: '{valid[0]}'."

    return msg


KEY_MAP = {
    "values": "Data",
    "cells": "Cells",
    "surveys": "Surveys",
    "trace": "Trace",
    "trace_depth": "TraceDepth",
    "vertices": "Vertices",
    "octree_cells": "Octree Cells",
    "property_groups": "PropertyGroups",
    "u_cell_delimiters": "U cell delimiters",
    "v_cell_delimiters": "V cell delimiters",
    "z_cell_delimiters": "Z cell delimiters",
    "color_map": "Color map",
    "metadata": "Metadata",
    "options": "options",
    "concatenated_object_ids": "Concatenated object IDs",
    "concatenated_attributes": "Attributes",
    "property_group_ids": "Property Group IDs",
}


def is_uuid(value: str) -> bool:
    """Check if a string is UUID compliant."""
    try:
        UUID(str(value))
        return True
    except ValueError:
        return False


def entity2uuid(value: Any) -> UUID | Any:
    """Convert an entity to its UUID."""
    if hasattr(value, "uid"):
        return value.uid
    return value


def uuid2entity(value: UUID, workspace: Workspace) -> Entity | Any:
    """Convert UUID to a known entity."""
    if isinstance(value, UUID):
        if value in workspace.list_entities_name:
            return workspace.get_entity(value)[0]

        # Search for property groups
        for obj in workspace.objects:
            if getattr(obj, "property_groups", None) is not None:
                prop_group = [
                    prop_group
                    for prop_group in getattr(obj, "property_groups")
                    if prop_group.uid == value
                ]

                if prop_group:
                    return prop_group[0]

        return None

    return value


def str2uuid(value: Any) -> UUID | Any:
    """Convert string to UUID"""
    if is_uuid(value):
        # TODO insert validation
        return UUID(str(value))
    return value


def as_str_if_uuid(value: UUID | Any) -> str | Any:
    """Convert :obj:`UUID` to string used in geoh5."""
    if isinstance(value, UUID):
        return "{" + str(value) + "}"
    return value


def bool_value(value: np.int8) -> bool:
    """Convert logical int8 to bool."""
    return bool(value)


def as_str_if_utf8_bytes(value) -> str:
    """Convert bytes to string"""
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return value


def dict_mapper(
    val, string_funcs: list[Callable], *args, omit: dict | None = None
) -> dict:
    """
    Recursion through nested dictionaries and applies mapping functions to values.

    :param val: Value (could be another dictionary) to apply transform functions.
    :param string_funcs: Functions to apply on values within the input dictionary.
    :param omit: Dictionary of functions to omit.

    :return val: Transformed values
    """
    if omit is None:
        omit = {}
    if isinstance(val, dict):
        for key, values in val.items():
            val[key] = dict_mapper(
                values,
                [fun for fun in string_funcs if fun not in omit.get(key, [])],
            )

    for fun in string_funcs:
        val = fun(val, *args)
    return val
