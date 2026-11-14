import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus, { ElTree } from "element-plus";
import { expect, it, vi } from "vitest";
import MenuTree from "@/components/navigation/argus-menu-tree-table/index.vue";

vi.mock("@/components/navigation/argus-menu-route-icon/index.vue", () => ({
  default: { template: "<span />" },
}));
const menuTree = [
  {
    id: 177,
    name: "知识库",
    type: 2,
    children: [
      { id: 178, name: "全局维护", type: 3 },
      { id: 179, name: "本部门维护", type: 3 },
    ],
  },
];
const render = (checkedIds: number[]) =>
  mount(MenuTree, {
    props: { menuTree, checkedIds },
    global: { plugins: [ElementPlus], stubs: { SwitchIcon: true } },
  });

it("loading view-only permissions preserves the menu without granting maintenance", async () => {
  const wrapper = render([177]);
  await flushPromises();
  expect(wrapper.vm.getCheckedIds()).toEqual([177]);
  const tree = wrapper.findComponent(ElTree);
  expect(tree.vm.getNode(178).checked).toBe(false);
  expect(tree.vm.getNode(179).checked).toBe(false);
  wrapper.unmount();
});

it("checking the knowledge menu does not automatically check maintenance permissions", async () => {
  const wrapper = render([]);
  await flushPromises();
  await wrapper.get('.el-tree input[type="checkbox"]').setValue(true);
  expect(wrapper.vm.getCheckedIds()).toEqual([177]);
  wrapper.unmount();
});

it("restores an explicitly granted department permission without selecting global maintenance", async () => {
  const wrapper = render([177, 179]);
  await flushPromises();
  expect(wrapper.vm.getCheckedIds().sort()).toEqual([177, 179]);
  expect(wrapper.findComponent(ElTree).vm.getNode(178).checked).toBe(false);
  wrapper.unmount();
});
