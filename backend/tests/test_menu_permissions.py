"""菜单权限种子与公共文件权限回归测试。"""

import json
from pathlib import Path

MENU_SEED = Path(__file__).resolve().parents[1] / "sql" / "sys_menu.json"


def _walk(nodes):
    for node in nodes:
        yield node
        yield from _walk(node.get("children") or [])


def test_common_file_permissions_are_assignable() -> None:
    permissions = {n.get("permission") for n in _walk(json.loads(MENU_SEED.read_text(encoding="utf-8")))}
    assert "module_common:file:upload" in permissions
    assert "module_common:file:download" in permissions


def test_detail_permissions_exist() -> None:
    permissions = {n.get("permission") for n in _walk(json.loads(MENU_SEED.read_text(encoding="utf-8")))}
    assert "module_system:log:detail" in permissions
    assert "module_system:ticket:detail" in permissions




def test_seed_menus_pass_runtime_schema_validation() -> None:
    """登录返回菜单时复用此校验，目录缺少 redirect 会使整个用户信息请求失败。"""
    from app.modules.system.menu.schema import MenuCreateSchema

    for node in _walk(json.loads(MENU_SEED.read_text(encoding="utf-8"))):
        MenuCreateSchema.model_validate(node)
