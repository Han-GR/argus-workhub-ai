"""AI 只读工具注册表（FastHub ``ai_tools`` 的只读子集）。

设计要点：
- **只读**：存储源清单与存储文件列表；不提供写入/删除/执行命令类工具
  （FastHub 的 ``run_host_command`` / 本机终端在多租户 Web 下等于 RCE，明确不移植）；
- **工具签名只允许模型可填的参数**：``auth`` / ``redis`` 通过闭包捕获，绝不放进函数签名，
  否则会被当成「需要模型提供的参数」而诱发无效调用；
- 工具内部异常**不抛给模型**，统一转成 ``{"error": ...}``，避免一次工具失败中断整轮对话；
- 需要数据库的工具自行开短生命周期 session（与传输引擎一致），不依赖请求级 session。
"""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any


from app.core.base_schema import AuthSchema
from app.core.database import async_db_session
from app.core.logger import logger
from app.modules.task.storage.browse.service import StorageFileService
from app.modules.task.storage.core.base import StoragePage
from app.modules.task.storage.node.service import StorageNodeService

# 单次返回的条目上限（防止把大结果塞进上下文）
_MAX_ENTRIES = 200


@dataclass(frozen=True)
class ReadonlyToolSpec:
    """一个只读工具：名字 + 描述 + 可调用对象（供 Agno 注入）。"""

    name: str
    description: str
    func: Callable[..., Awaitable[Any]]


def _error(action: str, exc: BaseException) -> dict[str, Any]:
    logger.warning(f"AI 只读工具[{action}]失败: {type(exc).__name__}: {exc}")
    return {"error": f"{action}失败: {type(exc).__name__}: {exc}"[:300]}


def build_readonly_tools(auth: AuthSchema, redis: Any | None = None) -> list[ReadonlyToolSpec]:
    """构造当前用户可用的只读工具列表（auth/redis 以闭包捕获）。"""

    async def storage_sources() -> list[dict[str, Any]]:
        """列出已配置的存储源（名称、协议、状态；不含地址与凭据）。"""
        try:
            async with async_db_session() as db:
                nodes = await StorageNodeService(auth, db).get_list()
                return [
                    {
                        "id": node.id,
                        "name": node.name,
                        "protocol": node.protocol,
                        "status": node.status,
                        "is_default": node.is_default,
                    }
                    for node in nodes
                ]
        except Exception as exc:
            return [_error("列出存储源", exc)]

    async def storage_files(source_name: str, path: str = "", bucket: str = "") -> dict[str, Any]:
        """列出某个存储源指定目录下的文件与子目录（source_name 必填）。"""
        try:
            async with async_db_session() as db:
                nodes = await StorageNodeService(auth, db).get_list()
                node = next((item for item in nodes if item.name == source_name), None)
                if node is None:
                    names = [item.name for item in nodes][:20]
                    return {"error": f"存储源不存在: {source_name}", "available": names}
                result = await StorageFileService(auth, db).list_files(
                    source_id=node.id,
                    prefix=path or "",
                    bucket=bucket or None,
                    page_size=_MAX_ENTRIES,
                )
            if isinstance(result, StoragePage):
                return {
                    "source": source_name,
                    "path": path,
                    "entries": [
                        {"name": entry.name, "is_dir": entry.is_dir, "size": entry.size}
                        for entry in result.items[:_MAX_ENTRIES]
                    ],
                    "has_next": result.has_next,
                }
            return {
                "source": source_name,
                "path": path,
                "entries": [
                    {"name": entry.name, "is_dir": entry.is_dir, "size": entry.size}
                    for entry in result[:_MAX_ENTRIES]
                ],
                "has_next": False,
            }
        except Exception as exc:
            return _error("列出存储文件", exc)

    tools = [
        ReadonlyToolSpec("storage_sources", "列出已配置的存储源（名称/协议/状态，不含凭据）", storage_sources),
        ReadonlyToolSpec("storage_files", "列出某个存储源指定目录下的文件与子目录", storage_files),
    ]
    _assert_no_injected_params(tools)
    return tools


def _assert_no_injected_params(tools: list[ReadonlyToolSpec]) -> None:
    """守卫：工具签名里不允许出现由闭包捕获的参数（否则模型会试图传它们）。"""
    forbidden = {"auth", "self", "cls", "redis", "db"}
    for spec in tools:
        params = set(inspect.signature(spec.func).parameters)
        leaked = params & forbidden
        if leaked:
            raise RuntimeError(f"AI 工具 {spec.name} 的签名包含闭包参数: {sorted(leaked)}")
