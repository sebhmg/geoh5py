from __future__ import annotations

import inspect
import uuid
import weakref
from contextlib import contextmanager
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)
from weakref import ReferenceType

import h5py
import numpy as np

from geoh5io import data, groups, objects
from geoh5io.data import Data
from geoh5io.groups import CustomGroup, Group, PropertyGroup
from geoh5io.io import H5Reader, H5Writer
from geoh5io.objects import Cell, ObjectBase
from geoh5io.shared import Coord3D, weakref_utils
from geoh5io.shared.entity import Entity

from .root_group import RootGroup

if TYPE_CHECKING:
    from geoh5io.groups import group
    from geoh5io.objects import object_base
    from geoh5io.shared import entity_type


class Workspace:

    _active_ref: ClassVar[ReferenceType[Workspace]] = type(None)  # type: ignore

    attribute_map = {
        "Contributors": "contributors",
        "Distance unit": "distance_unit",
        "GA Version": "ga_version",
        "Version": "version",
    }

    def __init__(self, h5file: str = "Analyst.geoh5", root: RootGroup = None):

        self._contributors = np.asarray(
            ["UserName"], dtype=h5py.special_dtype(vlen=str)
        )
        self._distance_unit = "meter"
        self._ga_version = "1"
        self._version = 1.0

        self._name = "GEOSCIENCE"

        self._types: Dict[uuid.UUID, ReferenceType[entity_type.EntityType]] = {}
        self._groups: Dict[uuid.UUID, ReferenceType[group.Group]] = {}
        self._objects: Dict[uuid.UUID, ReferenceType[object_base.ObjectBase]] = {}
        self._data: Dict[uuid.UUID, ReferenceType[data.Data]] = {}
        self._update_h5 = False
        self._h5file = h5file

        # Create a root, either from file or from scratch
        try:
            open(self.h5file)

            proj_attributes = H5Reader.fetch_project_attributes(self.h5file)

            for key, attr in proj_attributes.items():
                setattr(self, self.attribute_map[key], attr)

            # Get the Root attributes
            attributes, type_attributes = H5Reader.fetch_attributes(
                self.h5file, self.name, uuid.uuid4(), "Root"
            )
            self._root = self.create_entity(
                RootGroup,
                "Workspace",
                uuid.UUID(attributes["ID"]),
                attributes=attributes,
                type_attributes=type_attributes,
            )

            # Get all objects in the file
            self.fetch_children(self._root, recursively=True)
        #
        except FileNotFoundError:
            self._root = root if root is not None else RootGroup(self)
            H5Writer.create_geoh5(self)

    @property
    def ga_version(self):
        """
        ga_version

        Returns
        -------
        ga_version: str="Unknown"
            Geoscience Analyst version
        """
        return self._ga_version

    @ga_version.setter
    def ga_version(self, value: str):
        self._ga_version = value

    @property
    def version(self):
        """
        version

        Returns
        -------
        version: float=1.0
            Project version
        """
        return self._version

    @version.setter
    def version(self, value: float):
        self._version = value

    @property
    def distance_unit(self):
        """
        distance_unit

        Returns
        -------
        distance_unit: str="meter"
            Distance unit used by the project
        """
        return self._distance_unit

    @distance_unit.setter
    def distance_unit(self, value: str):
        self._distance_unit = value

    @property
    def contributors(self):
        """
        contributors

        Returns
        -------
        contributors: List[str]
            List of project contributors name
        """
        return self._contributors

    @contributors.setter
    def contributors(self, value: List[str]):
        self._contributors = np.asarray(value, dtype="object")

    @property
    def name(self):
        """
        name

        Returns
        -------
        name: str='GEOSCIENCE'
            Name of the project
        """
        return self._name

    @property
    def list_groups_name(self):
        """
        list_groups_name

        Returns
        -------
        groups: List[str]
            Names of all groups registered in the workspace
        """
        groups_name = {}
        for key, val in self._groups.items():
            groups_name[key] = val.__call__().name
        return groups_name

    @property
    def list_objects_name(self):
        """
        list_objects_name

        Returns
        -------
        objects: List[str]
            Names of all objects registered in the workspace
        """
        objects_name = {}
        for key, val in self._objects.items():
            objects_name[key] = val.__call__().name
        return objects_name

    @property
    def list_data_name(self):
        """
        list_data_name

        Returns
        -------
        data: List[str]
            Names of all data registered in the workspace
        """
        data_name = {}
        for key, val in self._data.items():
            data_name[key] = val.__call__().name
        return data_name

    @property
    def list_entities_name(self):
        """
        list_entities_name

        Returns
        -------
        data: List[str]
            Names of all entities registered in the workspace
        """
        entities_name = self.list_groups_name
        entities_name.update(self.list_objects_name)
        entities_name.update(self.list_data_name)
        return entities_name

    @property
    def root(self) -> "group.Group":
        """
        root

        Returns
        -------
        root: geoh5io.Group
            Group entity corresponding to the root (Workspace)
        """

        return self._root

    @property
    def h5file(self) -> str:
        """
        h5file

        Returns
        -------
        h5file: str
            File name with path to the target geoh5 database
        """

        return self._h5file

    @property
    def update_h5(self) -> bool:
        return self._update_h5

    @update_h5.setter
    def update_h5(self, value: bool):
        self._update_h5 = value

    @property
    def workspace(self):
        return self

    @staticmethod
    def active() -> Workspace:
        """ Get the active workspace. """
        active_one = Workspace._active_ref()
        if active_one is None:
            raise RuntimeError("No active workspace.")

        # so that type check does not complain of possible returned None
        return cast(Workspace, active_one)

    def save_entity(
        self,
        entity: Entity,
        parent=None,
        close_file: bool = True,
        add_children: bool = True,
    ):
        """
        save_entity

        Parameters
        ----------
        entity: geoh5io.Entity
            Entity to be written to the project geoh5 file

        parent: geoh5io.Entity
            Parent Entity or [None] to be added under in the workspace

        close_file: bool=True
            Close the geoh5 database after writing is completed

        add_children: bool=True
            Add children objects to the geoh5
        """
        # Check if entity if in current workspace
        if self.get_entity(entity.uid)[0] is None:

            if parent is None:
                # If a data entity, then add parent object without data
                if isinstance(entity, Data):
                    parent = entity.parent
                    if self.get_entity(parent.uid)[0] is None:
                        self.save_entity(entity.parent, add_children=False)
                        parent = self.get_entity(parent.uid)[0]
                else:
                    parent = self.root

        H5Writer.save_entity(
            entity,
            parent=parent,
            file=self.h5file,
            close_file=close_file,
            add_children=add_children,
        )

        self.finalize()

    def finalize(self):
        """ Finalize the geoh5 file by checking for updated entities and re-building the Root"""

        for entity in self.all_objects() + self.all_groups() + self.all_data():
            if len(entity.update_h5) > 0:
                self.save_entity(entity)

        H5Writer.finalize(self)

    def get_entity(self, name: Union[str, uuid.UUID]) -> List[Optional[Entity]]:
        """
        get_entity(name)

        Retrieve an entity from one of its identifier, either by name or uuid

        Parameters
        ----------
        name: str | uuid.UUID
            Object identifier, either name or uuid

        Returns
        -------
        object_list: List[Entity]
            List of entities with the same given name
        """

        if isinstance(name, uuid.UUID):
            list_entity_uid = [name]

        else:  # Extract all objects uuid with matching name
            list_entity_uid = [
                key for key, val in self.list_entities_name.items() if val == name
            ]

        entity_list: List[Optional[Entity]] = []
        for uid in list_entity_uid:
            entity_list.append(self.find_entity(uid))

        return entity_list

    def create_entity(
        self, entity_class, name: str, uid: uuid.UUID = uuid.uuid4(), **kwargs
    ):
        """
        create_entity(entity_class, name, uuid, type_uuid)

        Function to create and register a new entity and its entity_type.

        Parameters
        ----------
        entity_class: Entity
            Type of entity to be created
        name: str
            Name of the entity displayed in the project tree
        uid: uuid.UUID
            Unique identifier of the entity

        Returns
        -------
        entity: Entity
            New entity created
        """

        created_entity: Optional[Entity] = None

        if entity_class is RootGroup:
            created_entity = RootGroup(self, uid=uid)

        else:
            if "entity_type_uid" in kwargs:
                entity_type_uid = kwargs["entity_type_uid"]
            # Assume that entity is being created from its class
            elif hasattr(entity_class, "default_type_uid"):
                entity_type_uid = entity_class.default_type_uid()
                entity_class = entity_class.__bases__
            else:
                raise RuntimeError(
                    f"An entity_type_uid must be provided for {entity_class}."
                )

            if entity_class is not Data:
                for _, member in inspect.getmembers(groups) + inspect.getmembers(
                    objects
                ):
                    if (
                        inspect.isclass(member)
                        and issubclass(member, entity_class)
                        and member is not entity_class
                        and hasattr(member, "default_type_uid")
                        and not member == CustomGroup
                        and member.default_type_uid() == entity_type_uid
                    ):
                        known_type = member.find_or_create_type(self)
                        created_entity = member(known_type, name, uid)
                        break

                # Special case for CustomGroup without uuid
                if (created_entity is None) and entity_class == Group:
                    custom = groups.custom_group.CustomGroup
                    unknown_type = custom.find_or_create_type(
                        self, type_uid=entity_type_uid
                    )
                    created_entity = custom(unknown_type, name, uid)

            else:
                for key in kwargs["type_attributes"].keys():
                    if "primitive" in key.lower():
                        primitive_type = getattr(
                            data.primitive_type_enum.PrimitiveTypeEnum,
                            kwargs["type_attributes"][key].upper(),
                        )

                data_type = data.data_type.DataType.find_or_create(
                    self, entity_type_uid, primitive_type
                )
                data_type.name = name

                for key in kwargs["attributes"].keys():
                    if "association" in key.lower():
                        association = getattr(
                            data.data_association_enum.DataAssociationEnum,
                            kwargs["attributes"][key].upper(),
                        )

                for _, member in inspect.getmembers(data):

                    if (
                        inspect.isclass(member)
                        and issubclass(member, entity_class)
                        and member is not entity_class
                        and hasattr(member, "primitive_type")
                        and inspect.ismethod(member.primitive_type)
                        and data_type.primitive_type is member.primitive_type()
                    ):
                        created_entity = member(data_type, association, name, uid)
                        break

        if created_entity is not None:

            if "attributes" in kwargs.keys():
                for attr, item in kwargs["attributes"].items():
                    try:
                        if attr == "PropertyGroups":
                            item = self.fetch_property_groups(uid)

                        if attr in created_entity.attribute_map.keys():
                            attr = created_entity.attribute_map[attr]

                        setattr(created_entity, attr, item)
                    except AttributeError:
                        continue  # print(f"Could not set attribute {attr}")

            if "type_attributes" in kwargs.keys():
                for attr, item in kwargs["type_attributes"].items():

                    if attr in created_entity.entity_type.attribute_map.keys():
                        attr = created_entity.entity_type.attribute_map[attr]

                    try:
                        setattr(created_entity.entity_type, attr, item)
                    except AttributeError:
                        continue

        return created_entity

    def fetch_children(self, entity: Entity, recursively=False):
        """
        fetch_children(entity, recursively=False)

        Recover and register children entities from the geoh5 file

        Parameters
        ----------
        entity: Entity
            Parental entity
        recursively: bool=False
            Recover all children down the project tree
        """

        base_classes = {"group": Group, "object": ObjectBase, "data": Data}

        if isinstance(entity, Group):
            entity_type = "group"
        elif isinstance(entity, ObjectBase):
            entity_type = "object"
        else:
            entity_type = "data"

        children_list = H5Reader.fetch_children(
            self.h5file, self.name, entity.uid, entity_type
        )

        for uid, child_type in children_list.items():
            attributes, type_attributes = H5Reader.fetch_attributes(
                self.h5file, self.name, uid, child_type
            )

            recovered_object = self.create_entity(
                base_classes[child_type],
                attributes["Name"],
                uid=uid,
                entity_type_uid=uuid.UUID(type_attributes["ID"]),
                attributes=attributes,
                type_attributes=type_attributes,
            )

            if recovered_object is not None:
                # Assumes the object was pulled from h5
                recovered_object.existing_h5_entity = True

                # Add parent-child relationship
                recovered_object.parent = entity

                if recursively:
                    self.fetch_children(recovered_object, recursively=True)

    def fetch_values(self, uid: uuid.UUID) -> Optional[float]:
        """
        fetch_values(uid)

        Fetch the data values from the source h5 file

        Parameters
        ----------
        uid: uuid.UUID
            Unique identifier of target data object

        Returns
        -------
        value: numpy.array
            Array of values
        """
        return H5Reader.fetch_values(self.h5file, self.name, uid)

    def fetch_vertices(self, uid: uuid.UUID) -> Coord3D:
        """
        Get the vertices of an object from the source h5 file

        Parameters
        ----------
        uid: uuid.UUID
            Unique identifier of target entity

        Returns
        -------
        coordinates: Coord3D
            Coordinate entity with locations
        """
        return H5Reader.fetch_vertices(self.h5file, self.name, uid)

    def fetch_cells(self, uid: uuid.UUID) -> Cell:
        """
        Get the cells of an object from the source h5 file

        Parameters
        ----------
        uid: uuid.UUID
            Unique identifier of target entity

        Returns
        -------
        cells: geoh5io.Cell
            Cell object with vertices index
        """
        return H5Reader.fetch_cells(self.h5file, self.name, uid)

    def fetch_octree_cells(self, uid: uuid.UUID) -> np.ndarray:
        """
        Get the octree cells ordering from the source h5 file

        Parameters
        ----------
        uid: uuid.UUID
            Unique identifier of target entity

        Returns
        -------
        value: numpy.ndarray(int)
            Array of [i, j, k, dimension] defining the octree mesh
        """
        return H5Reader.fetch_octree_cells(self.h5file, self.name, uid)

    def fetch_delimiters(
        self, uid: uuid.UUID
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        fetch_delimiters(uid)

        Fetch the delimiter attributes from the source h5 file

        Parameters
        ----------
        uid: uuid.UUID
            Unique identifier of target data object

        Returns
        -------
        u_delimiters: numpy.array
            Array of u_delimiters

        v_delimiters: numpy.array
            Array of v_delimiters

        z_delimiters: numpy.array
            Array of z_delimiters
        """
        return H5Reader.fetch_delimiters(self.h5file, self.name, uid)

    def fetch_property_groups(self, uid: uuid.UUID) -> List[PropertyGroup]:
        """
        Get the octree cells ordering from the source h5 file

        Parameters
        ----------
        uid: uuid.UUID
            Unique identifier of target entity

        Returns
        -------
        value: numpy.ndarray(int)
            Array of [i, j, k, dimension] defining the octree mesh
        """

        group_dict = H5Reader.fetch_property_groups(self.h5file, self.name, uid)

        property_groups = []
        for pg_id, attrs in group_dict.items():

            group = PropertyGroup(uid=uuid.UUID(pg_id))

            for attr, val in attrs.items():

                try:
                    setattr(group, group.attribute_map[attr], val)
                except AttributeError:
                    continue

            property_groups.append(group)

        return property_groups

    def activate(self):
        """ Makes this workspace the active one.

            In case the workspace gets deleted, Workspace.active() safely returns None.
        """
        if Workspace._active_ref() is not self:
            Workspace._active_ref = weakref.ref(self)

    def deactivate(self):
        """ Deactivate this workspace if it was the active one, else does nothing.
        """
        if Workspace._active_ref() is self:
            Workspace._active_ref = type(None)

    def _register_type(self, entity_type: "entity_type.EntityType"):
        weakref_utils.insert_once(self._types, entity_type.uid, entity_type)

    def _register_group(self, group: "group.Group"):
        weakref_utils.insert_once(self._groups, group.uid, group)

    def _register_data(self, data_obj: "data.Data"):
        weakref_utils.insert_once(self._data, data_obj.uid, data_obj)

    def _register_object(self, obj: "object_base.ObjectBase"):
        weakref_utils.insert_once(self._objects, obj.uid, obj)

    def find_type(
        self, type_uid: uuid.UUID, type_class: Type["entity_type.EntityType"]
    ) -> Optional["entity_type.EntityType"]:
        found_type = weakref_utils.get_clean_ref(self._types, type_uid)
        return found_type if isinstance(found_type, type_class) else None

    def all_groups(self) -> List["group.Group"]:
        weakref_utils.remove_none_referents(self._groups)
        return [cast("group.Group", v()) for v in self._groups.values()]

    def find_group(self, group_uid: uuid.UUID) -> Optional["group.Group"]:
        return weakref_utils.get_clean_ref(self._groups, group_uid)

    def all_objects(self) -> List["object_base.ObjectBase"]:
        weakref_utils.remove_none_referents(self._objects)
        return [cast("object_base.ObjectBase", v()) for v in self._objects.values()]

    def find_object(self, object_uid: uuid.UUID) -> Optional["object_base.ObjectBase"]:
        return weakref_utils.get_clean_ref(self._objects, object_uid)

    def all_data(self) -> List["data.Data"]:
        weakref_utils.remove_none_referents(self._data)
        return [cast("data.Data", v()) for v in self._data.values()]

    def find_data(self, data_uid: uuid.UUID) -> Optional["data.Data"]:
        return weakref_utils.get_clean_ref(self._data, data_uid)

    def find_entity(self, entity_uid: uuid.UUID) -> Optional["Entity"]:
        return (
            self.find_group(entity_uid)
            or self.find_data(entity_uid)
            or self.find_object(entity_uid)
        )


@contextmanager
def active_workspace(workspace: Workspace):
    previous_active_ref = Workspace._active_ref  # pylint: disable=protected-access
    workspace.activate()
    yield workspace

    workspace.deactivate()
    # restore previous active workspace when leaving the context
    previous_active = previous_active_ref()
    if previous_active is not None:
        previous_active.activate()  # pylint: disable=no-member
