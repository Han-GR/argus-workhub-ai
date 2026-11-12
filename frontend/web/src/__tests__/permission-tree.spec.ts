import { describe, expect, it } from "vitest";
import {
  selectGrantableMenus,
  mergePermissionSelection,
} from "@/views/module_system/role/components/permission-tree";
import type { MenuTable } from "@/api/module_system/menu";

const menus: MenuTable[] = [
  {
    id: 1,
    scope: "web",
    status: 0,
    children: [
      {
        id: 2,
        status: 0,
        hidden: true,
        children: [{ id: 3, type: 3, status: 0, permission: "module_common:file:upload" }],
      },
      { id: 4, status: 1, children: [{ id: 5, type: 3, status: 0 }] },
    ],
  },
  { id: 6, scope: "app", status: 0 },
  { id: 7, scope: "web", status: 1, children: [{ id: 8, status: 0 }] },
];

describe("角色权限树", () => {
  it("排除停用分支与移动端，保留隐藏页面和必要按钮", () => {
    expect(selectGrantableMenus(menus)).toEqual([
      {
        ...menus[0]!,
        children: [
          {
            ...menus[0]!.children![0],
            children: [{ ...menus[0]!.children![0]!.children![0], children: [] }],
          },
        ],
      },
    ]);
    expect(menus[0]!.children).toHaveLength(2);
  });
  it("保存补全祖先、忽略未知选中ID并保留未展示授权", () => {
    const visible = selectGrantableMenus(menus);
    expect(
      mergePermissionSelection([3, 999], visible, [2, 4, 5, 6, 8]).sort((a, b) => a - b)
    ).toEqual([1, 2, 3, 4, 5, 6, 8]);
    expect(mergePermissionSelection([], visible, [1, 2, 3, 6])).toEqual([6]);
  });
});
