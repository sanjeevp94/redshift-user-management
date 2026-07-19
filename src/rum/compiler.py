import yaml
from typing import Set, Tuple, Dict, Any


class Compiler:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def compile(
        self,
    ) -> Tuple[
        Dict[str, Any], Set[str], Set[str], Set[Tuple[str, str]], Set[Tuple[str, str, str, str]]
    ]:
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f) or {}

        target_info = config.get("target", {})
        desired_users: Set[str] = set()
        desired_roles: Set[str] = set()
        desired_user_roles: Set[Tuple[str, str]] = set()
        desired_role_grants: Set[Tuple[str, str, str, str]] = set()

        # Parse Permissions
        raw_permissions = config.get("permissions", {})

        # Parse Roles
        raw_roles = config.get("roles", {})
        for role_name, role_data in raw_roles.items():
            full_role_name = f"rum_role_{role_name}"
            desired_roles.add(full_role_name)

            for perm_name in role_data.get("permissions", []):
                if perm_name in raw_permissions:
                    perm = raw_permissions[perm_name]
                    resource_type = perm.get("resource_type")
                    for privilege in perm.get("privileges", []):
                        for entity in perm.get("entities", []):
                            desired_role_grants.add(
                                (full_role_name, resource_type, entity, privilege)
                            )

        # Parse Users
        raw_users = config.get("users", {})
        for user_name, user_data in raw_users.items():
            full_user_name = f"rum_user_{user_name}"
            desired_users.add(full_user_name)

            for role_name in user_data.get("roles", []):
                full_role_name = f"rum_role_{role_name}"
                desired_user_roles.add((full_user_name, full_role_name))

        return target_info, desired_users, desired_roles, desired_user_roles, desired_role_grants


def compile_state(
    config_path: str,
) -> Tuple[
    Dict[str, Any], Set[str], Set[str], Set[Tuple[str, str]], Set[Tuple[str, str, str, str]]
]:
    compiler = Compiler(config_path)
    return compiler.compile()
