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

import warnings
from typing import Any, Callable

import numpy as np

from geoh5py.groups import ContainerGroup
from geoh5py.workspace import Workspace


def dict_mapper(
    val, string_funcs: list[Callable], *args, omit: dict | None = None
) -> dict:
    """
    Recurses through nested dictionary and applies mapping funcs to all values

    Parameters
    ----------
    val :
        Dictionary val (could be another dictionary).
    string_funcs:
        Function to apply to values within dictionary.
    omit: Dictionary of functions to omit.
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
        if args is None:
            val = fun(val)
        else:
            val = fun(val, *args)
    return val


def flatten(ui_json: dict[str, dict]) -> dict[str, Any]:
    """Flattens ui.json format to simple key/value pair."""
    data: dict[str, Any] = {}
    for name, value in ui_json.items():
        if isinstance(value, dict):
            if is_uijson({name: value}):
                field = "value" if truth(ui_json, name, "isValue") else "property"
                if not truth(ui_json, name, "enabled"):
                    data[name] = None
                else:
                    data[name] = value[field]
        else:
            data[name] = value

    return data


def collect(ui_json: dict[str, dict], member: str, value: Any = None) -> dict[str, Any]:
    """Collects ui parameters with common field and optional value."""

    parameters = {}
    for name, form in ui_json.items():
        if is_form(form) and member in form:
            if value is None or form[member] == value:
                parameters[name] = form

    return parameters


def find_all(ui_json: dict[str, dict], member: str, value: Any = None) -> list[str]:
    """Returns names of all collected paramters."""
    parameters = collect(ui_json, member, value)
    return list(parameters.keys())


def group_optional(ui_json: dict[str, dict], group_name: str):
    """Returns groupOptional bool for group name."""
    group = collect(ui_json, "group", group_name)
    parameters = find_all(group, "groupOptional")
    return group[parameters[0]]["groupOptional"] if parameters else False


def optional_type(ui_json: dict[str, dict], parameter: str):
    """
    Check if a ui.json parameter is optional or groupOptional

    :param ui_json: UI.json dictionary
    :param name: Name of parameter to check type.
    """
    is_optional = False
    if is_form(ui_json[parameter]):
        is_optional |= ui_json[parameter].get("optional", False)
        if "group" in ui_json[parameter]:
            is_optional |= group_optional(ui_json, ui_json[parameter]["group"])

    return is_optional


def group_enabled(group: dict[str, dict]) -> bool:
    """Return true if groupOptional and enabled are both true."""
    parameters = find_all(group, "groupOptional")
    if not parameters:
        raise ValueError(
            "Provided group does not contain a parameter with groupOptional member."
        )
    return group[parameters[0]].get("enabled", True)


def set_enabled(ui_json: dict, parameter: str, value: bool):
    """
    Set enabled status for an optional or groupOptional parameter.

    :param ui_json: UI.json dictionary
    :param parameter: Name of the parameter to check optional on.
    :param value: Set enable True or False.
    """

    ui_json[parameter]["enabled"] = value
    if "group" in ui_json[parameter]:
        group = collect(ui_json, "group", ui_json[parameter]["group"])
        parameters = find_all(group, "groupOptional")

    if parameters:
        if group[parameters[0]]["enabled"] and value is False:
            warnings.warn(
                f"The ui.json group {ui_json[parameter]['group']} was disabled "
                f"due to parameter '{parameter}'."
            )
        ui_json[parameters[0]]["enabled"] = value


def truth(var: dict[str, Any], name: str, field: str) -> bool:
    default_states = {
        "enabled": True,
        "optional": False,
        "groupOptional": False,
        "main": False,
        "isValue": True,
    }
    if field in var[name]:
        return var[name][field]

    if field in default_states:
        return default_states[field]

    raise ValueError(
        f"Field: {field} was not provided in ui.json and does not have a default state."
    )


def is_uijson(var):
    uijson_keys = [
        "title",
        "monitoring_directory",
        "run_command",
        "conda_environment",
        "geoh5",
        "workspace_geoh5",
    ]
    uijson = True
    if len(var.keys()) > 1:
        for k in uijson_keys:
            if k not in var.keys():
                uijson = False

    for value in var.values():
        if isinstance(value, dict):
            for name in ["label", "value"]:
                if name not in value.keys():
                    uijson = False

    return uijson


def is_form(var: Any) -> bool:
    """Return true if dictionary 'var' contains both 'label' and 'value' members."""
    is_a_form = False
    if isinstance(var, dict):
        if all(k in var.keys() for k in ["label", "value"]):
            is_a_form = True

    return is_a_form


def list2str(value):
    if isinstance(value, list):  # & (key not in exclude):
        return str(value)[1:-1]
    return value


def none2str(value):
    if value is None:
        return ""
    return value


def inf2str(value):  # map np.inf to "inf"
    if not isinstance(value, (int, float)):
        return value
    return str(value) if not np.isfinite(value) else value


def str2list(value):  # map "[...]" to [...]
    if isinstance(value, str):
        if value in ["inf", "-inf", ""]:
            return value
        try:
            return [float(n) for n in value.split(",") if n != ""]
        except ValueError:
            return value

    return value


def str2none(value):
    if value == "":
        return None
    return value


def str2inf(value):
    if value in ["inf", "-inf"]:
        return float(value)
    return value


def workspace2path(value):
    if isinstance(value, Workspace):
        return value.h5file
    return value


def path2workspace(value):
    if isinstance(value, str) and ".geoh5" in value:
        return Workspace(value)
    return value


def container_group2name(value):
    if isinstance(value, ContainerGroup):
        return value.name
    return value
