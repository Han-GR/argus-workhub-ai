"""精简后的接口边界与真实登录/菜单回归。"""


def test_only_retained_domains_are_registered(test_client):
    paths = test_client.app.openapi()["paths"]
    for prefix in ["/ops", "/generator", "/example", "/task/cronjob", "/task/storage/workflow", "/system/notice", "/system/version", "/monitor/cache", "/monitor/server", "/system/auth/wx-", "/system/auth/oauth/"]:
        assert not any(path.startswith(prefix) for path in paths), prefix
    for prefix in ["/system/auth/login", "/system/user", "/system/role", "/system/ticket", "/task/storage/browse", "/task/storage/node", "/task/storage/transfer", "/ai", "/monitor/health", "/monitor/online/current"]:
        assert any(path.startswith(prefix) for path in paths), prefix


def test_login_user_menu_and_permission_tree(test_client, auth_headers):
    current = test_client.get("/system/user/current/info", headers=auth_headers)
    assert current.status_code == 200, current.text
    menus = current.json()["data"]["menus"]
    assert menus
    tree = test_client.get("/system/menu/tree", headers=auth_headers)
    assert tree.status_code == 200, tree.text
    def walk(nodes):
        for node in nodes:
            yield node
            yield from walk(node.get("children") or [])
    nodes = list(walk(tree.json()["data"]))
    assert any(n.get("permission") == "module_common:file:upload" for n in nodes)
    assert not any(n.get("scope") == "app" for n in nodes)
    assert not any(n.get("route_name") in ["Ops", "Generator", "Monitor", "Cronjob", "WorkflowFlow"] for n in nodes)


def test_menu_seed_components_exist_and_transfer_permissions_remain():
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    menus = json.loads((root / "backend/sql/sys_menu.json").read_text())
    permissions = set()

    def check(nodes):
        for node in nodes:
            component = node.get("component_path")
            if component:
                assert (root / "frontend/web/src/views" / f"{component}.vue").is_file(), component
            if node.get("permission"):
                permissions.add(node["permission"])
            check(node.get("children") or [])

    check(menus)
    for action in ["query", "create", "update", "delete"]:
        assert f"module_task:storage:transfer:{action}" in permissions
