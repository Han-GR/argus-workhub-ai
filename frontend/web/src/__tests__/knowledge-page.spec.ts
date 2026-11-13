import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { beforeEach, expect, it, vi } from "vitest";
import Page from "@/views/module_ai/knowledge/index.vue";
import { KnowledgeAPI, type KnowledgeCatalog } from "@/api/module_ai/knowledge";

vi.mock("@/api/module_ai/knowledge", () => ({
  KnowledgeAPI: { catalog: vi.fn(), createBase: vi.fn(), deleteBase: vi.fn() },
}));
vi.mock("@/views/module_ai/knowledge/components/KnowledgeDocuments.vue", () => ({
  default: {
    props: ["baseId", "canManage"],
    template: '<div data-testid="documents">{{ baseId }} / {{ canManage }}</div>',
  },
}));
vi.mock("@/views/module_ai/knowledge/components/EmbeddingConfig.vue", () => ({
  default: { template: "<div>企业向量配置</div>" },
}));

const catalog: KnowledgeCatalog = {
  bases: [
    { id: "company", name: "公司制度", dept_id: null, dept_name: null, can_manage: false },
    { id: "dev", name: "研发资料", dept_id: 10, dept_name: "研发部", can_manage: true },
  ],
  departments: [{ id: 10, name: "研发部" }],
  can_create: true,
  can_create_company: false,
  can_configure: false,
};
const render = () =>
  mount(Page, {
    global: { plugins: [ElementPlus], stubs: { ArgusDrawer: { template: "<div><slot /></div>" } } },
  });
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(KnowledgeAPI.catalog).mockResolvedValue({
    data: { code: 0, data: structuredClone(catalog) },
  } as never);
});

it("switches knowledge bases and uses each base's server-provided maintenance permission", async () => {
  const wrapper = render();
  await flushPromises();
  expect(wrapper.get('[data-testid="documents"]').text()).toBe("company / false");
  await wrapper
    .findAll("button")
    .find((b) => b.text().includes("研发资料"))!
    .trigger("click");
  expect(wrapper.get('[data-testid="documents"]').text()).toBe("dev / true");
  expect(wrapper.text()).not.toContain("向量模型配置");
  wrapper.unmount();
});

it("limits department maintainers to department creation and submits that department", async () => {
  vi.mocked(KnowledgeAPI.createBase).mockResolvedValue({
    data: { code: 0, data: { id: "new" } },
  } as never);
  const wrapper = render();
  await flushPromises();
  await wrapper
    .findAll("button")
    .find((b) => b.text() === "新建知识库")!
    .trigger("click");
  await flushPromises();
  const dialog = document.body.querySelector('[role="dialog"]')!;
  expect(dialog).toBeTruthy();
  expect(dialog.textContent).not.toContain("全公司");
  const input = dialog.querySelector("input[placeholder='请输入知识库名称']") as HTMLInputElement;
  input.value = "研发规范";
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await flushPromises();
  (
    Array.from(dialog.querySelectorAll("button")).find(
      (b) => b.textContent?.trim() === "创建"
    ) as HTMLButtonElement
  ).click();
  await flushPromises();
  expect(KnowledgeAPI.createBase).toHaveBeenCalledWith({ name: "研发规范", dept_id: 10 });
  wrapper.unmount();
});

it("shows retry after catalog failure and hides creation from readers", async () => {
  vi.mocked(KnowledgeAPI.catalog).mockRejectedValueOnce(new Error("offline"));
  const wrapper = render();
  await flushPromises();
  expect(wrapper.text()).toContain("知识库加载失败");
  vi.mocked(KnowledgeAPI.catalog).mockResolvedValue({
    data: { code: 0, data: { ...catalog, can_create: false } },
  } as never);
  await wrapper
    .findAll("button")
    .find((b) => b.text() === "重试")!
    .trigger("click");
  await flushPromises();
  expect(wrapper.text()).not.toContain("新建知识库");
  expect(wrapper.text()).toContain("公司制度");
  wrapper.unmount();
});
