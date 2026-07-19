import yaml
from typing import Set, Tuple, Dict, Any, List


class Compiler:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def compile(self) -> List[Dict[str, Any]]:
        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f) or {}

        cluster_configs = []

        # Support both the new `clusters` block and the old format as a fallback (treating it as 1 cluster)
        clusters = config.get("clusters", [])
        if not clusters:
            # Fallback wrapper
            clusters = [config]

        for cluster_block in clusters:
            # Handle old `targets` list or `target` dict if mixed, but prefer `target` per new spec
            target_info = cluster_block.get("target", {})
            if not target_info and "targets" in cluster_block and cluster_block["targets"]:
                target_info = cluster_block["targets"][0]

            desired_users: Set[str] = set()
            desired_roles: Set[str] = set()
            desired_user_roles: Set[Tuple[str, str]] = set()
            desired_role_grants: Set[Tuple[str, str, str, str]] = set()

            # Parse Permissions
            raw_permissions = cluster_block.get("permissions", {})

            # Parse Roles
            raw_roles = cluster_block.get("roles", {})
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
            raw_users = cluster_block.get("users", {})
            for user_name, user_data in raw_users.items():
                full_user_name = f"rum_user_{user_name}"
                desired_users.add(full_user_name)

                for role_name in user_data.get("roles", []):
                    full_role_name = f"rum_role_{role_name}"
                    desired_user_roles.add((full_user_name, full_role_name))

            cluster_configs.append(
                {
                    "target_info": target_info,
                    "desired_users": desired_users,
                    "desired_roles": desired_roles,
                    "desired_user_roles": desired_user_roles,
                    "desired_role_grants": desired_role_grants,
                }
            )

        return cluster_configs


def compile_state(config_path: str) -> List[Dict[str, Any]]:
    compiler = Compiler(config_path)
    return compiler.compile()
