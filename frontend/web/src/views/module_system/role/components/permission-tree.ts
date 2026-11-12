import type { MenuTable } from "@/api/module_system/menu";

/** 保留启用的管理端分支；隐藏配置页仍可能承载业务所需的按钮权限。 */
export function selectGrantableMenus(nodes: MenuTable[], scope = "web"): MenuTable[] {
  return nodes.flatMap((node) => {
    const effectiveScope = node.scope ?? scope;
    if (effectiveScope !== "web" || node.status !== 0) return [];
    return [{ ...node, children: selectGrantableMenus(node.children ?? [], effectiveScope) }];
  });
}

/** 仅替换当前可见树的授权，补全祖先并保留树外的历史授权。 */
export function mergePermissionSelection(
  checkedIds: number[],
  roots: MenuTable[],
  savedIds: number[]
): number[] {
  const parentById = new Map<number, number | undefined>();
  const walk = (nodes: MenuTable[], parent?: number) => {
    for (const node of nodes) {
      if (node.id === undefined) continue;
      parentById.set(node.id, parent);
      walk(node.children ?? [], node.id);
    }
  };
  walk(roots);
  const out = new Set(savedIds.filter((id) => !parentById.has(id)));
  for (const id of checkedIds) {
    if (!parentById.has(id)) continue;
    let current: number | undefined = id;
    while (current !== undefined) {
      out.add(current);
      current = parentById.get(current);
    }
  }
  return [...out];
}
