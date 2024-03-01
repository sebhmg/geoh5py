#  Copyright (c) 2024 Mira Geoscience Ltd.
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

import uuid
import weakref
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, TypeVar, cast

from ..shared.utils import ensure_uuid

if TYPE_CHECKING:
    from ..workspace import Workspace

EntityTypeT = TypeVar("EntityTypeT", bound="EntityType")


class EntityType(ABC):
    """
    The base class for all entity types.

    :param workspace: The workspace to associate the entity type with.
    :param uid: The unique identifier of the entity type.
    :param description: The description of the entity type.
    :param name: The name of the entity type.
    """

    _attribute_map = {"Description": "description", "ID": "uid", "Name": "name"}

    def __init__(
        self,
        workspace: Workspace,
        uid: uuid.UUID | None = None,
        description: str | None = "Entity",
        name: str | None = "Entity",
        entity_class: type | None = None,
    ):
        self._on_file: bool = False
        self._uid: uuid.UUID = ensure_uuid(uid) if uid is not None else uuid.uuid4()

        self.description = description
        self.name = name
        self.entity_class = entity_class
        self.workspace = workspace

    @property
    def attribute_map(self) -> dict[str, str]:
        """
        Correspondence map between property names used in geoh5py and
        geoh5.
        """
        return self._attribute_map

    @classmethod
    def convert_kwargs(cls, kwargs: dict[str, Any]) -> dict[str, Any]:
        """
        Convert the kwargs to the geoh5py attribute names.

        :param kwargs: The kwargs to convert.

        :return: The converted kwargs.
        """
        return {
            cls._attribute_map.get(key, key): value for key, value in kwargs.items()
        }

    def copy(self, **kwargs) -> EntityType:
        """
        Copy this entity type to another workspace.
        """

        attributes = {
            prop: getattr(self, prop)
            for prop in dir(self)
            if isinstance(getattr(self.__class__, prop, None), property)
            and getattr(self, prop) is not None
        }

        attributes.update(kwargs)

        if attributes.get("uid") in getattr(
            attributes.get("workspace", self.workspace), "_types"
        ):
            del attributes["uid"]

        return self.__class__(**attributes)

    @property
    def description(self) -> str | None:
        """
        The description of the entity type.
        """
        return self._description

    @description.setter
    def description(self, description: str | None):
        if not isinstance(description, (str, type(None))):
            raise TypeError(
                f"Description must be a string or None, find {type(description)}"
            )

        self._description = description

        if self.workspace:
            self.workspace.update_attribute(self, "attributes")

    @property
    def entity_class(self) -> type | None:
        """
        The class of the entity.
        """
        return self._entity_class

    @entity_class.setter
    def entity_class(self, value: type | None):
        if not isinstance(value, (type, type(None))):
            raise TypeError(f"entity_class must be a type, not {type(value)}")

        self._entity_class = value

        if self.workspace:
            self.workspace.update_attribute(self, "attributes")

    @classmethod
    def find(
        cls: type[EntityTypeT], workspace: Workspace, type_uid: uuid.UUID
    ) -> EntityTypeT | None:
        """
        Finds in the given Workspace the EntityType with the given UUID for
        this specific EntityType implementation class.

        :return: EntityType of None
        """
        return cast(EntityTypeT, workspace.find_type(ensure_uuid(type_uid), cls))

    @classmethod
    @abstractmethod
    def find_or_create(cls, workspace: Workspace, **kwargs) -> EntityType:
        """
        Find or creates an EntityType with given UUID that matches the given
        Entity implementation class.

        :param workspace: An active Workspace class

        :return: EntityType
        """

    @property
    def name(self) -> str | None:
        """
        The name of the entity type.
        """
        return self._name

    @name.setter
    def name(self, name: str | None):
        if not isinstance(name, (str, type(None))):
            raise TypeError(f"name must be a string or None, not {type(name)}")

        self._name = name

        if self.workspace:
            self.workspace.update_attribute(self, "attributes")

    @property
    def on_file(self) -> bool:
        """
        Return True if Entity already present in
        the workspace.
        """
        return self._on_file

    @on_file.setter
    def on_file(self, value: bool):
        if not isinstance(value, bool) and value != 1 and value != 0:
            raise TypeError(f"on_file must be a bool, not {type(value)}")
        self._on_file = bool(value)

    @property
    def uid(self) -> uuid.UUID:
        """
        The unique identifier of an entity, either as stored
        in geoh5 or generated in :func:`~uuid.UUID.uuid4` format.
        """
        return self._uid

    @property
    def workspace(self) -> Workspace:
        """
        The Workspace associated to the object.
        """
        if not hasattr(self, "_workspace"):
            return None  # type: ignore

        _workspace = self._workspace()
        if _workspace is None:
            raise AssertionError("Cannot access the workspace, ensure it is open.")

        return _workspace

    @workspace.setter
    def workspace(self, workspace: Workspace):
        if hasattr(self, "_workspace"):
            raise AssertionError("Cannot change the workspace of an entity type.")
        if not hasattr(workspace, "create_entity"):
            raise TypeError(f"Workspace must be a Workspace, not {type(workspace)}")

        self._workspace = weakref.ref(workspace)
        self.workspace.register(self)
