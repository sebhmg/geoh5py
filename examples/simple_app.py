#!/usr/bin/env python3

from geoh5io import data_handler, groups_handler, objects_handler, workspace_handler


# TODO: share this code between app and client demo
def simple_demo(workspace_service, objects_service, groups_service, data_service):
    print("API version: " + workspace_service.get_api_version().value)

    workspace_service.open_geoh5("test.geoh5")
    all_objects = objects_service.get_all()
    print(f"Found {len(all_objects)} Objects in workspace.")

    all_groups = groups_service.get_all()
    print(f"found {len(all_groups)} Groups in workspace.")

    all_data = data_service.get_all()
    print(f"found {len(all_data)} Data in workspace.")

    # TODO: some more interesting examples

    workspace_service.close()


def main():

    workspace_service = workspace_handler.WorkspaceHandler()
    objects_service = objects_handler.ObjectsHandler()
    groups_service = groups_handler.GroupsHandler()
    data_service = data_handler.DataHandler()
    simple_demo(workspace_service, objects_service, groups_service, data_service)


if __name__ == "__main__":
    main()