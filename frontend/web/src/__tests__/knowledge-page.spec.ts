import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { beforeEach, expect, it, vi } from "vitest";
import Page from "@/views/module_ai/knowledge/index.vue";
import { KnowledgeAPI } from "@/api/module_ai/knowledge";
vi.mock("@/api/module_ai/knowledge", () => ({ KnowledgeAPI: { workspace: vi.fn() } }));
vi.mock("@/views/module_ai/knowledge/components/KnowledgeDocuments.vue", () => ({
  default: {
    props: ["departmentName"],
    template: '<div data-testid="documents">{{ departmentName }}</div>',
  },
}));
vi.mock("@/views/module_ai/knowledge/components/EmbeddingConfig.vue", () => ({
  default: { template: "<div>企业向量配置</div>" },
}));
const ok = (can_configure = false) => ({
  data: { code: 0, data: { can_configure, department: { id: 20, name: "人力资源部门" } } },
});
const render = () =>
  mount(Page, {
    global: { plugins: [ElementPlus], stubs: { ArgusDrawer: { template: "<div><slot /></div>" } } },
  });
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(KnowledgeAPI.workspace).mockResolvedValue(ok() as never);
});
it("opens the shared document workspace for ordinary members without admin controls", async () => {
  const wrapper = render();
  await flushPromises();
  expect(wrapper.get('[data-testid="documents"]').text()).toBe("人力资源部门");
  expect(wrapper.get("h1").text()).toBe("文档管理");
  expect(wrapper.text()).not.toContain("向量模型配置");
  expect(wrapper.text()).not.toContain("新建知识库");
  wrapper.unmount();
});
it("keeps shared embedding configuration available only to administrators", async () => {
  vi.mocked(KnowledgeAPI.workspace).mockResolvedValue(ok(true) as never);
  const wrapper = render();
  await flushPromises();
  expect(wrapper.text()).toContain("向量模型配置");
  wrapper.unmount();
});
it("offers retry when loading workspace permissions fails", async () => {
  vi.mocked(KnowledgeAPI.workspace).mockRejectedValueOnce(new Error("offline"));
  const wrapper = render();
  await flushPromises();
  expect(wrapper.text()).toContain("知识库加载失败");
  await wrapper
    .findAll("button")
    .find((b) => b.text() === "重试")!
    .trigger("click");
  await flushPromises();
  expect(wrapper.find('[data-testid="documents"]').exists()).toBe(true);
  wrapper.unmount();
});
