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

from copy import deepcopy
from typing import Any, cast
from uuid import UUID

from geoh5py.groups import PropertyGroup
from geoh5py.shared import Entity
from geoh5py.shared.exceptions import RequiredValidationError
from geoh5py.shared.validators import (
    AssociationValidator,
    AtLeastOneValidator,
    BaseValidator,
    OptionalValidator,
    PropertyGroupValidator,
    RequiredValidator,
    ShapeValidator,
    TypeValidator,
    UUIDValidator,
    ValueValidator,
)
from geoh5py.ui_json.utils import optional_type
from geoh5py.workspace import Workspace


class InputValidation:
    """
    Validations on dictionary of parameters.

    Attributes
    ----------
    validations : Validations dictionary with matching set of input parameter keys.
    workspace (optional) : Workspace instance needed to validate uuid types.
    ignore_requirements (optional): Omit raising error on 'required' validator.

    Methods
    -------
    validate_data(data)
        Validates data of params and contents/type/shape/keys/reqs of values.
    """

    def __init__(
        self,
        validators: dict[str, BaseValidator] = None,
        validations: dict[str, Any] | None = None,
        workspace: Workspace = None,
        ui_json: dict[str, Any] | None = None,
        validation_options: dict[str, Any] | None = None,
    ):
        self.validations = self.infer_validations(ui_json, validations=validations)
        self.validators: dict[str, BaseValidator] = validators
        self.workspace: Workspace | None = workspace

        if validation_options is None:
            validation_options = {}

        self.ignore_list: tuple = validation_options.get("ignore_list", ())
        self.ignore_requirements: bool = validation_options.get(
            "ignore_requirements", False
        )

    @property
    def validations(self):
        return self._validations

    @validations.setter
    def validations(self, val: dict[str, Any]):
        self._validations = val

    @property
    def validators(self):
        return self._validators

    @validators.setter
    def validators(self, val: dict[str, BaseValidator]):
        if val is None:
            val = {}
        elif not all(isinstance(v, BaseValidator) for v in val.values()):
            raise TypeError("Validators should be subclass of BaseValidator.")

        if self.validations is not None:
            required_validators = InputValidation._required_validators(self.validations)
            val = dict(required_validators, **val)

        self._validators = val

    @property
    def workspace(self):
        return self._workspace

    @workspace.setter
    def workspace(self, value: Workspace | None):
        if value is not None:
            TypeValidator.validate("workspace", value, Workspace)
        self._workspace = value

    @staticmethod
    def _unique_validators(validations: dict[str, Any]) -> list[str]:
        """Return names of validators required by a validations dictionary."""
        return list({key for item in validations.values() for key in item})

    @staticmethod
    def _required_validators(validations):
        """Returns dictionary of validators required by validations."""
        unique_validators = InputValidation._unique_validators(validations)
        all_validators = {k.validator_type: k() for k in BaseValidator.__subclasses__()}
        val = {}
        for k in unique_validators:
            if k not in all_validators:
                raise ValueError(f"No validator implemented for argument '{k}'.")
            val[k] = all_validators[k]
        return val

    @staticmethod
    def _validations_from_uijson(ui_json: dict[str, Any]) -> dict[str, dict]:
        """Determine base set of validations from ui.json structure."""
        validations: dict[str, dict] = {}
        for key, item in ui_json.items():
            if not isinstance(item, dict):
                check_type = cast(Any, type(item))
                validations[key] = {
                    "types": [check_type],
                }
                continue

            if "isValue" in item:
                validations[key] = {
                    "types": [str, UUID, int, float, Entity],
                }
                validations[key]["association"] = item["parent"]
                validations[key]["uuid"] = None

            elif "choiceList" in item:
                validations[key] = {
                    "types": [str],
                    "values": item["choiceList"],
                }
            elif "fileType" in item:
                validations[key] = {
                    "types": [str],
                }
            elif "meshType" in item:
                validations[key] = {
                    "types": [str, UUID, Entity],
                    "association": "geoh5",
                    "uuid": None,
                }
            elif "parent" in item:
                validations[key] = {
                    "types": [str, UUID, Entity],
                    "association": item["parent"],
                    "uuid": None,
                }
                if "dataGroupType" in item:
                    validations[key]["property_group_type"] = item["dataGroupType"]
                    validations[key]["types"] = [str, UUID, PropertyGroup]
            elif "value" in item:
                if item["value"] is None:
                    check_type = str
                else:
                    check_type = cast(Any, type(item["value"]))

                validations[key] = {
                    "types": [check_type],
                }
                if check_type is UUID:
                    validations[key]["types"].append(Entity)

            validations[key].update({"optional": optional_type(ui_json, key)})

            if optional_type(ui_json, key) and "types" in validations[key]:
                validations[key]["types"].append(type(None))

        return validations

    @staticmethod
    def infer_validations(
        ui_json: dict[str, Any] | None, validations: dict[str, dict] | None = None
    ) -> dict:
        """Infer necessary validations from ui json structure."""

        inferred_validations = (
            {} if ui_json is None else InputValidation._validations_from_uijson(ui_json)
        )

        if validations is not None:
            inferred_validations = InputValidation._merge_validations(
                inferred_validations, validations
            )

        return inferred_validations

    @staticmethod
    def _merge_validations(
        validations_a: dict[str, dict], validations_b: dict[str, dict]
    ):
        """Merge validations_b into validations_a."""
        out = deepcopy(validations_a)
        if validations_b is not None:
            for key, val in validations_b.items():
                if key not in out:
                    out[key] = val
                else:
                    out[key].update(val)
        return out

    def validate(self, name: str, value: Any, validations: dict[str, Any] = None):
        """
        Run validations on a given key and value.

        :param name: Parameter identifier.
        :param value: Input parameter value.
        :param validations: [Optional] Validations provided on runtime
        """
        if validations is None:
            if name not in self.validations:
                raise KeyError(f"{name} is missing from the known validations.")

            validations = self.validations[name]

        for validator in [
            RequiredValidator,
            AtLeastOneValidator,
            OptionalValidator,
            UUIDValidator,
            TypeValidator,
            AssociationValidator,
            PropertyGroupValidator,
            ValueValidator,
            ShapeValidator,
        ]:
            val = str(validator.validator_type)
            if (
                val not in validations
                or (val == "required" and self.ignore_requirements)
                or name in self.ignore_list
            ):
                continue

            self.validators[val](name, value, validations[val])

    def validate_data(self, data: dict[str, Any]) -> None:
        """
        Calls validate method on individual key/value pairs in input.

        :param data: Input data with known validations.
        """

        one_of_validations: dict[str, Any] = {}
        local_validations = self.validations.copy()
        for param, validations in local_validations.items():

            if param not in data.keys():
                if "required" in validations and not self.ignore_requirements:
                    raise RequiredValidationError(param)

                continue

            if "one_of" in validations:
                one_of_group = validations.pop("one_of")
                val = {param: data[param] is not None}
                if one_of_group in one_of_validations:
                    one_of_validations[one_of_group].update(val)
                else:
                    one_of_validations[one_of_group] = val

            if "association" in validations and validations["association"] in data:
                validations["association"] = data[validations["association"]]
                self.validate(param, data[param], validations)
            else:
                self.validate(param, data.get(param, None), validations)

        for name, val in one_of_validations.items():
            self.validate(name, val, {"one_of": None})

    def __call__(self, data, *args):
        if isinstance(data, dict):
            self.validate_data(data)
        elif isinstance(data, str) and args is not None:
            self.validate(data, args)
        else:
            raise ValueError(
                "InputValidators can only be called with dictionary of data or "
                "(key, value) pair."
            )