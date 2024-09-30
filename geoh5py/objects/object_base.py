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

# pylint: disable=R0904

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING, Any
from uuid import UUID

import numpy as np

from ..data import (
    CommentsData,
    Data,
    DataAssociationEnum,
    VisualParameters,
)
from ..groups.property_group import GroupTypeEnum, PropertyGroup
from ..shared import Entity
from ..shared.conversion import BaseConversion
from ..shared.entity_container import EntityContainer
from ..shared.utils import (
    box_intersect,
    clear_array_attributes,
    mask_by_extent,
    str2uuid,
)
from .object_type import ObjectType


if TYPE_CHECKING:  # pragma: no cover
    from ..workspace import Workspace


class ObjectBase(EntityContainer):
    """
    Object base class.

    :param last_focus: Object visible in camera on start.
    """

    _attribute_map: dict = EntityContainer._attribute_map.copy()
    _attribute_map.update(
        {"Last focus": "last_focus", "PropertyGroups": "property_groups"}
    )
    _converter: type[BaseConversion] | None = None

    def __init__(self, last_focus: str = "None", **kwargs):
        self._property_groups: list[PropertyGroup] | None = None
        self._visual_parameters: VisualParameters | None = None
        self._comments: CommentsData | None = None

        self.last_focus = last_focus

        super().__init__(**kwargs)

    def add_children(self, children: list[Entity | PropertyGroup]):
        """
        :param children: a list of entity to add as children.
        """
        property_groups = self._property_groups or []

        prop_group_uids = {prop_group.uid: prop_group for prop_group in property_groups}
        children_uids = {child.uid: child for child in self._children}

        for child in children:
            if child.uid not in children_uids and isinstance(
                child, (Data, PropertyGroup)
            ):
                self._children.append(child)
                if (
                    isinstance(child, PropertyGroup)
                    and child.uid not in prop_group_uids
                ):
                    property_groups.append(child)
            else:
                warnings.warn(f"Child {child} is not valid or already exists.")

        if property_groups:
            self._property_groups = property_groups

    def add_data(
        self,
        data: dict,
        property_group: str | PropertyGroup | None = None,
        compression: int = 5,
        **kwargs,
    ) -> Data | list[Data]:
        """
        Create a Data from dictionary of name and arguments.
        The provided arguments can be any property of the target Data class.

        :param data: Dictionary of data to be added to the object, e.g.
        :param property_group: Name or :obj:`~geoh5py.groups.property_group.PropertyGroup`.
        :param compression: Compression level for data.

        .. code-block:: python

            data = {
                "data_A": {
                    'values': [v_1, v_2, ...],
                    'association': 'VERTEX'
                    },
                "data_B": {
                    'values': [v_1, v_2, ...],
                    'association': 'CELLS'
                    },
            }

        :return: List of new Data objects.
        """
        data_objects = []

        if not isinstance(data, dict):
            raise TypeError(
                f"Input 'data' must be of type {dict}. Got {type(data)} instead."
            )

        for name, attr in data.items():
            if not isinstance(attr, dict):
                raise TypeError(
                    f"Given value to data {name} should of type {dict}. "
                    f"Type {type(attr)} given instead."
                )

            attr["name"] = name

            attr, validate_property_group = self.validate_association(
                attr, property_group=property_group, **kwargs
            )

            entity_type = self.workspace.validate_data_type(attr, attr.get("values"))

            kwargs = {"parent": self}
            for key, val in attr.items():
                if key not in ["parent", "entity_type", "type"]:
                    kwargs[key] = val

            data_object = self.workspace.create_entity(
                Data,  # type: ignore
                entity=kwargs,
                entity_type=entity_type,
                compression=compression,
            )

            if validate_property_group is not None:
                self.add_data_to_group(data_object, validate_property_group)

            data_objects.append(data_object)

        # TODO: Legacy re-sorting for old drillhole format
        self.post_processing()

        if len(data_objects) == 1:
            return data_objects[0]

        return data_objects

    def add_data_to_group(
        self,
        data: list[Data | UUID | str] | Data | UUID | str,
        property_group: str | PropertyGroup,
    ) -> PropertyGroup:
        """
        Append data children to a :obj:`~geoh5py.groups.property_group.PropertyGroup`
        All given data must be children of the parent object.

        :param data: The name, the uid or the object to add itself, pass as a list or single object.
        :param property_group: The name or the object of the property group;
            a new one will be created if not found.

        :return: The target property group.
        """
        if isinstance(property_group, str):
            property_group = self.fetch_property_group(
                name=property_group, properties=data
            )

        if isinstance(property_group, PropertyGroup):
            property_group.add_properties(data)
            return property_group

        raise TypeError(
            "Property group must be of type PropertyGroup or str; "
            f"got {type(property_group)} instead."
        )

    def add_default_visual_parameters(self):
        """
        Create a default visual parameters to the object.
        """
        if self.visual_parameters is not None:
            raise UserWarning("Visual parameters already exist.")

        self._visual_parameters = self.workspace.create_entity(
            Data,  # type: ignore
            save_on_creation=True,
            entity={
                "name": "Visual Parameters",
                "parent": self,
                "association": "OBJECT",
            },
            entity_type={"name": "XmlData", "primitive_type": "TEXT"},
        )

        return self._visual_parameters

    @property
    def cells(self) -> np.ndarray:
        """
        :obj:`numpy.array` of :obj:`int`: Array of indices
        defining the connection between
        :obj:`~geoh5py.objects.object_base.ObjectBase.vertices`.
        """
        raise AttributeError(
            f"Object {self.__class__.__name__} does not have the attribute 'cells'."
        )

    @property
    def converter(self) -> Any:
        """
        :return: The converter for the object.
        """
        return self._converter

    def copy(
        self,
        parent=None,
        copy_children: bool = True,
        clear_cache: bool = False,
        mask: np.ndarray | None = None,
        **kwargs,
    ):
        """
        Function to copy an entity to a different parent entity.

        :param parent: New parent for the copied object.
        :param copy_children: Copy children entities.
        :param clear_cache: Clear cache of data values.
        :param mask: Array of indices to sub-sample the input entity.
        :param kwargs: Additional keyword arguments.

        :return: New copy of the input entity.
        """

        if parent is None:
            parent = self.parent

        new_object = self.workspace.copy_to_parent(
            self,
            parent,
            clear_cache=clear_cache,
            **kwargs,
        )

        if copy_children:
            children_map = {}
            for child in self.children:
                if isinstance(child, PropertyGroup):
                    continue
                if isinstance(child, Data) and child.association in (
                    DataAssociationEnum.VERTEX,
                    DataAssociationEnum.CELL,
                ):
                    child_copy = child.copy(
                        parent=new_object,
                        clear_cache=clear_cache,
                        mask=mask,
                    )
                else:
                    child_copy = self.workspace.copy_to_parent(
                        child, new_object, clear_cache=clear_cache
                    )
                children_map[child.uid] = child_copy.uid

            if self.property_groups:
                self.workspace.copy_property_groups(
                    new_object, self.property_groups, children_map
                )
                new_object.workspace.update_attribute(new_object, "property_groups")

        return new_object

    def create_property_group(
        self,
        name=None,
        property_group_type: GroupTypeEnum | str = GroupTypeEnum.MULTI,
        **kwargs,
    ) -> PropertyGroup:
        """
        Create a new :obj:`~geoh5py.groups.property_group.PropertyGroup`.

        :param name: Name of the new property group.
        :param property_group_type: Type of property group.
        :param kwargs: Any arguments taken by the
            :obj:`~geoh5py.groups.property_group.PropertyGroup` class.

        :return: A new :obj:`~geoh5py.groups.property_group.PropertyGroup`
        """
        if self._property_groups is not None and name in [
            pg.name for pg in self._property_groups
        ]:
            raise KeyError(f"A Property Group with name '{name}' already exists.")

        prop_group = PropertyGroup(
            self, name=name, property_group_type=property_group_type, **kwargs
        )

        return prop_group

    @property
    def entity_type(self) -> ObjectType:
        """
        :obj:`~geoh5py.shared.entity_type.EntityType`: Object type.
        """
        return self._entity_type

    @property
    def extent(self) -> np.ndarray | None:
        """
        Geography bounding box of the object.

        :return: Bounding box defined by the bottom South-West and
            top North-East coordinates,  shape(2, 3).
        """
        if self.locations is None:
            return None

        return np.c_[self.locations.min(axis=0), self.locations.max(axis=0)].T

    @property
    def faces(self) -> np.ndarray:
        """Object faces."""
        raise AttributeError(
            f"Object {self.__class__.__name__} does not have the attribute 'faces'."
        )

    def fetch_property_group(self, name=None, uid=None, **kwargs) -> PropertyGroup:
        """
        Find or create a PropertyGroup from given name and properties.

        :param name: Name of the property group.
        :param uid: Unique identifier for the property group.
        :param kwargs: Any arguments taken by the
            :obj:`~geoh5py.groups.property_group.PropertyGroup` class.

        :return: A new or existing :obj:`~geoh5py.groups.property_group.PropertyGroup`
        """
        prop_group = None
        if name is not None or uid is not None:
            prop_group = self.get_property_group(uid or name)[0]

        if prop_group is None:
            prop_group = self.create_property_group(name=name, uid=uid, **kwargs)

        return prop_group

    def find_or_create_property_group(
        self, name=None, uid=None, **kwargs
    ) -> PropertyGroup:
        """
        Find or create a PropertyGroup from given name and properties.
        """
        warnings.warn(
            "The 'find_and_create_property_group' will be deprecated. "
            "Use fetch_property_group instead.",
            DeprecationWarning,
        )
        return self.fetch_property_group(name=name, uid=uid, **kwargs)

    @classmethod
    def find_or_create_type(cls, workspace: Workspace, **kwargs) -> ObjectType:
        """
        Find or create a type instance for a given object class.

        :param workspace: Target workspace.
        :param kwargs: Keyword arguments for the ObjectType.

        :return: The ObjectType instance for the given object class.
        """
        kwargs["entity_class"] = cls
        return ObjectType.find_or_create(workspace, **kwargs)

    def get_property_group(self, name: UUID | str) -> list[PropertyGroup] | list[None]:
        """
        Get a child PropertyGroup by name.

        :param name: the reference of the property group to get.

        :return: A list of children Data objects
        """
        if self._property_groups is None:
            return [None]

        entities = []
        for child in self._property_groups:
            if (isinstance(name, UUID) and child.uid == name) or child.name == name:
                entities.append(child)

        if len(entities) == 0:
            return [None]

        return entities

    def get_data(self, name: str | UUID) -> list[Data]:
        """
        Get the children associated with a given name.

        :param name: Name or UUID of the target child data

        :return: A list of children Data objects
        """
        return [child for child in self.get_entity(name) if isinstance(child, Data)]

    def get_data_list(self, attribute: str = "name") -> list[Any]:
        """
        Get a list of a specific attribute of the data children.

        :param attribute: The attribute to return from the data objects.

        :return: List of names of data associated with the object.
        """
        return sorted(
            [
                getattr(child, attribute)
                for child in self.children
                if isinstance(child, Data)
            ]
        )

    @property
    def last_focus(self) -> str:
        """
        The name of the object visible in the camera on start.
        """
        return self._last_focus

    @last_focus.setter
    def last_focus(self, value: str):
        if not isinstance(value, str):
            raise TypeError("Attribute 'last_focus' must be a string")

        self._last_focus = value

    @property
    def locations(self) -> np.ndarray | None:
        """
        Exposes the vertices or centroids of the object.
        """
        out = None
        if hasattr(self, "vertices"):
            out = self.vertices
        if hasattr(self, "centroids"):
            out = self.centroids

        return out

    def mask_by_extent(
        self, extent: np.ndarray, inverse: bool = False
    ) -> np.ndarray | None:
        if self.extent is None or not box_intersect(self.extent, extent):
            return None

        return mask_by_extent(self.locations, extent, inverse=inverse)

    @property
    def n_cells(self) -> int:
        """
        The number of cells.
        """
        raise AttributeError(
            f"Object {self.__class__.__name__} does not have the attribute 'n_cells'."
        )

    @property
    def n_vertices(self) -> int:
        """
        The number of vertices
        """
        raise AttributeError(
            f"Object {self.__class__.__name__} does not have the attribute 'n_vertices'."
        )

    def post_processing(self):
        """
        Post-processing function to be called after adding data.
        """

    @property
    def property_groups(self) -> list[PropertyGroup] | None:
        """
        List of the property groups associated with the object.
        """
        return self._property_groups

    def reference_to_data(self, data: str | Data | UUID) -> Data:
        """
        Convert a reference to a Data object.

        :param data: The data to convert.
            It can be the name, the uuid or the data itself.

        :return: The data object.
        """
        data = str2uuid(data)

        if isinstance(data, Data):
            if self != data.parent:
                raise ValueError(
                    f"Data '{data.name}' parent ({data.parent}) "
                    f"does not match group parent ({self})."
                )

        if isinstance(data, (str, UUID)):
            data_: list = self.get_data(data)
            if len(data_) == 0 and isinstance(data, UUID):
                data_temp = self.workspace.load_entity(data, "data", self)
                data_ = [] if data_temp is None else [data_temp]
            if len(data_) == 0:
                raise ValueError(f"Data '{data}' not found in parent {self}")
            if len(data_) > 1:
                raise ValueError(f"Multiple data '{data}' found in parent {self}")
            data = data_[0]

        if not isinstance(data, Data):
            raise TypeError(
                f"Data must be of type Data, UUID or str. Provided {type(data)}"
            )

        return data

    def remove_children(self, children: list[Entity | PropertyGroup]):
        """
        Remove children from the list of children entities.

        :param children: List of entities

        .. warning::
            Removing a child entity without re-assigning it to a different
            parent may cause it to become inactive. Inactive entities are removed
            from the workspace by
            :func:`~geoh5py.shared.weakref_utils.remove_none_referents`.
        """
        if not isinstance(children, list):
            children = [children]

        for child in children:
            if child not in self._children:
                warnings.warn(f"Child {child} not found in parent {self}.")
                continue
            if isinstance(child, PropertyGroup) and self._property_groups:
                self.remove_property_group(child)
            elif isinstance(child, Data):
                self.remove_data_from_groups(child)

            self._children.remove(child)

        self.workspace.remove_children(self, children)

    @staticmethod
    def remove_children_values(
        indices: list[int] | np.ndarray,
        children: list[Data],
        clear_cache: bool = False,
    ):
        """
        Remove values from children data objects.

        :param indices: The indices to remove.
        :param children: The children data objects.
        :param clear_cache: Clear the cache of the children.
        """
        if isinstance(indices, list):
            indices = np.array(indices)

        if not isinstance(indices, np.ndarray):
            raise TypeError("Indices must be a list or numpy array.")

        for child in children:
            if not isinstance(child.values, np.ndarray):
                continue

            child.values = np.delete(child.values, indices, axis=0)

            if child.values.size == 0:
                child.values = None

            if clear_cache:
                clear_array_attributes(child)

    def remove_property_group(self, property_group: PropertyGroup):
        """
        Remove a property group from the object.

        :param property_group: The property group to remove.
        """
        if (
            self._property_groups is not None
            and property_group in self._property_groups
        ):
            self._property_groups.remove(property_group)
            # todo: this should suppress the property group too?

    def validate_association(self, attributes, property_group=None, **_):
        """
        Get a dictionary of attributes and validate the data 'association' keyword.

        :param attributes: Dictionary of attributes provided for the data.
        :param property_group: Property group to associate the data with.
        """
        if attributes.get("association") is not None:
            return attributes, property_group

        if (
            getattr(self, "n_cells", None) is not None
            and attributes["values"].ravel().shape[0] == self.n_cells
        ):
            attributes["association"] = "CELL"
        elif (
            getattr(self, "n_vertices", None) is not None
            and attributes["values"].ravel().shape[0] == self.n_vertices
        ):
            attributes["association"] = "VERTEX"
        else:
            attributes["association"] = "OBJECT"

        return attributes, property_group

    @property
    def vertices(self) -> np.ndarray:
        """
        x, y, z coordinates of points in 3D space.
        """
        raise AttributeError(
            f"Object {type(self)} does not have the attribute 'vertices'."
        )

    def remove_data_from_groups(
        self, data: list[Data | UUID | str] | Data | UUID | str
    ):
        """
        Remove data children to all
        :obj:`~geoh5py.groups.property_group.PropertyGroup` of the object.

        :param data: The name, the uid or the object to remove itself,
            pass as a list or single object.
        """
        if not isinstance(data, list):
            data = [data]

        if not self._property_groups:
            return

        for property_group in self._property_groups:
            property_group.remove_properties(data)

    def validate_entity_type(self, entity_type: ObjectType | None) -> ObjectType:
        """
        Validate the entity type.
        """
        if not isinstance(entity_type, ObjectType):
            raise TypeError(
                f"Input 'entity_type' must be of type {ObjectType}, not {type(entity_type)}"
            )

        if entity_type.name == "Entity":
            entity_type.name = self.name
            entity_type.description = self.name

        return entity_type

    @property
    def visual_parameters(self) -> VisualParameters | None:
        """
        The visual parameters of the object.
        """
        if self._visual_parameters is None:
            for child in self.children:
                # todo: so  an object can have several Visual Parameters?
                if isinstance(child, VisualParameters):
                    self._visual_parameters = child
                    break

        return self._visual_parameters
