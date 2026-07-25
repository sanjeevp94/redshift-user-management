from typing import Set, Tuple, Dict, Any, List


def build_cluster_yaml_block(
    target_info: Dict[str, Any],
    live_users: Set[str],
    live_roles: Set[str],
    live_user_roles: Set[Tuple[str, str]],
    live_role_grants: Set[Tuple[str, str, str, str]],
) -> Dict[str, Any]:
    # Strip rum_ prefixes for the YAML representations
    def strip_prefix(name: str, prefix: str) -> str:
        if name.startswith(prefix):
            return name[len(prefix) :]
        return name

    cluster_block = {"target": target_info, "users": {}, "roles": {}, "permissions": {}}

    # Process Users and Assigned Roles
    user_roles_map: Dict[str, List[str]] = {}
    for user, role in live_user_roles:
        clean_user = strip_prefix(user, "rum_user_")
        clean_role = strip_prefix(role, "rum_role_")
        if clean_user not in user_roles_map:
            user_roles_map[clean_user] = []
        user_roles_map[clean_user].append(clean_role)

    for user in live_users:
        clean_user = strip_prefix(user, "rum_user_")
        cluster_block["users"][clean_user] = {}
        if clean_user in user_roles_map:
            cluster_block["users"][clean_user]["roles"] = sorted(user_roles_map[clean_user])

    # To rebuild permissions efficiently, we need to group grants by (resource_type, privileges, entities)
    # But because privileges and entities can be grouped in YAML, we will generate a unique permission name
    # based on the resource type and the entity name to group privileges effectively.

    # Map: (resource_type, entity) -> Set[privilege]
    entity_privs_map: Dict[Tuple[str, str], Set[str]] = {}

    # Map: role -> Set[(resource_type, entity)]
    role_entity_map: Dict[str, Set[Tuple[str, str]]] = {}

    for role, resource_type, entity, privilege in live_role_grants:
        clean_role = strip_prefix(role, "rum_role_")

        if (resource_type, entity) not in entity_privs_map:
            entity_privs_map[(resource_type, entity)] = set()
        entity_privs_map[(resource_type, entity)].add(privilege)

        if clean_role not in role_entity_map:
            role_entity_map[clean_role] = set()
        role_entity_map[clean_role].add((resource_type, entity))

    # Build Permissions Dictionary
    # We will name permissions like: <resource_type>_<safe_entity_name>
    perm_name_mapping: Dict[Tuple[str, str], str] = {}

    for (resource_type, entity), privileges in entity_privs_map.items():
        safe_entity = entity.replace(".", "_").replace("*", "all")
        perm_name = f"{resource_type}_{safe_entity}"

        cluster_block["permissions"][perm_name] = {
            "resource_type": resource_type,
            "privileges": sorted(list(privileges)),
            "entities": [entity],
        }
        perm_name_mapping[(resource_type, entity)] = perm_name

    # Build Roles Dictionary
    for role in live_roles:
        clean_role = strip_prefix(role, "rum_role_")
        cluster_block["roles"][clean_role] = {}

        if clean_role in role_entity_map:
            perm_list = []
            for res_ent in role_entity_map[clean_role]:
                perm_list.append(perm_name_mapping[res_ent])
            cluster_block["roles"][clean_role]["permissions"] = sorted(perm_list)

    # Cleanup empty blocks for cleaner YAML output
    if not cluster_block["users"]:
        del cluster_block["users"]
    if not cluster_block["roles"]:
        del cluster_block["roles"]
    if not cluster_block["permissions"]:
        del cluster_block["permissions"]

    return cluster_block
