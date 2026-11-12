"""启动时检测重复路由，防止接口被静默覆盖。"""

import re
from fastapi import FastAPI

_PATH_PARAM_RE = re.compile(r"\{[^}]*\}")


def check_route_conflicts(app: FastAPI) -> None:
    """启动期检测路由冲突：同一路径被注册两次时，先注册的会静默屏蔽后注册的。

    FastAPI 按注册顺序首次匹配，冲突不会报错，只会让部分接口永远不可达——
    通常来自插件自带 prefix 与内置模块撞车，或同一 router 被重复挂载。
    """
    seen: dict[tuple[str, str], str] = {}
    conflicts: list[str] = []
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        # 参数名不参与匹配语义，/user/{id} 与 /user/{uid} 属于冲突
        normalized = _PATH_PARAM_RE.sub("{}", path)
        for method in sorted(methods):
            key = (method, normalized)
            endpoint = getattr(route, "name", None) or str(path)
            if key in seen:
                conflicts.append(f"{method} {path}（{endpoint}）已被 {seen[key]} 占用")
            else:
                seen[key] = endpoint

    if conflicts:
        raise RuntimeError(
            f"检测到 {len(conflicts)} 处路由冲突，已中止启动（后注册者将永远不可达）：\n   "
            + "\n   ".join(conflicts)
        )
