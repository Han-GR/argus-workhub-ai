import { DOMWrapper, flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ElementPlus, { ElMessageBox, ElSelect } from "element-plus";
import Workspace from "@/views/module_ai/knowledge/components/KnowledgeDocuments.vue";
import { KnowledgeAPI } from "@/api/module_ai/knowledge";

vi.mock("@/api/module_ai/knowledge", () => ({
  KnowledgeAPI: {
    list: vi.fn(),
    upload: vi.fn(),
    reindex: vi.fn(),
    remove: vi.fn(),
    update: vi.fn(),
    ask: vi.fn(),
  },
}));

const document = {
  id: "doc-1",
  name: "员工手册.md",
  chunk_count: 3,
  needs_reindex: false,
  created_time: "2026-11-13T08:00:00Z",
  visibility: "company",
  dept_id: null,
  dept_name: null,
  uploaded_by: 2,
  uploader_name: "陈悦",
  can_edit: true,
  can_query: true,
};
const ok = (data: unknown) => ({ data: { code: 0, data } });
const render = () =>
  mount(Workspace, {
    attachTo: globalThis.document.body,
    props: { departmentName: "人力资源部门" },
    global: { plugins: [ElementPlus], stubs: {} },
  });

async function click(wrapper: ReturnType<typeof render>, text: string) {
  const button =
    wrapper.findAll("button").find((item) => item.text() === text) ??
    new DOMWrapper(globalThis.document.body).findAll("button").find((item) => item.text() === text);
  expect(button, `button ${text}`).toBeDefined();
  await button!.trigger("click");
  await flushPromises();
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(KnowledgeAPI.list).mockResolvedValue(ok([document]) as never);
  vi.mocked(KnowledgeAPI.upload).mockResolvedValue(ok(document) as never);
  vi.mocked(KnowledgeAPI.reindex).mockResolvedValue(ok(document) as never);
  vi.mocked(KnowledgeAPI.update).mockResolvedValue(ok(document) as never);
  vi.mocked(KnowledgeAPI.remove).mockResolvedValue(ok(null) as never);
});

describe("knowledge workspace", () => {
  it("lets readers ask while hiding all document maintenance actions", async () => {
    vi.mocked(KnowledgeAPI.list).mockResolvedValue(ok([{ ...document, can_edit: false }]) as never);
    const wrapper = render();
    await flushPromises();
    const buttons = wrapper.findAll("button").map((button) => button.text());
    expect(buttons).toContain("上传文档");
    expect(buttons).not.toContain("重建索引");
    expect(buttons).not.toContain("删除");
    expect(buttons).toContain("提问");
    wrapper.unmount();
  });

  it("allows rebuilding a current-model document after Redis index loss", async () => {
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("可检索");
    await click(wrapper, "重建索引");
    expect(KnowledgeAPI.reindex).toHaveBeenCalledWith(document.id);
    wrapper.unmount();
  });

  it("shows stale index status and offers retry when listing fails", async () => {
    vi.mocked(KnowledgeAPI.list).mockRejectedValueOnce(new Error("offline"));
    const wrapper = render();
    await flushPromises();
    expect(wrapper.text()).toContain("文档列表加载失败");
    vi.mocked(KnowledgeAPI.list).mockResolvedValue(
      ok([{ ...document, needs_reindex: true }]) as never
    );
    await click(wrapper, "重试");
    expect(wrapper.text()).toContain("需要重建");
    expect(wrapper.text()).toContain(document.name);
    wrapper.unmount();
  });

  it("rejects unsupported and oversize files, then uploads a valid file", async () => {
    const wrapper = render();
    await flushPromises();
    await click(wrapper, "上传文档");
    const input = new DOMWrapper(globalThis.document.body).get('input[type="file"]');
    for (const file of [
      new File(["x"], "a.exe"),
      new File([new Uint8Array(2 * 1024 * 1024 + 1)], "a.txt"),
    ]) {
      Object.defineProperty(input.element, "files", { value: [file], configurable: true });
      await input.trigger("change");
      await flushPromises();
    }
    expect(KnowledgeAPI.upload).not.toHaveBeenCalled();
    const file = new File(["资料"], "a.md");
    Object.defineProperty(input.element, "files", { value: [file], configurable: true });
    await input.trigger("change");
    await flushPromises();
    await click(wrapper, "上传");
    expect(KnowledgeAPI.upload).toHaveBeenCalledWith(file, "department");
    expect(KnowledgeAPI.list).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("trims questions, renders source text safely and clears old answers on failure", async () => {
    vi.mocked(KnowledgeAPI.ask).mockResolvedValueOnce(
      ok({
        answer: "年假为五天 [1]",
        sources: [
          {
            number: 1,
            document_id: "doc-1",
            name: document.name,
            text: "<script>alert(1)</script>",
            score: 0.9,
          },
        ],
      }) as never
    );
    const wrapper = render();
    await flushPromises();
    await wrapper.get("textarea").setValue("   ");
    await click(wrapper, "提问");
    expect(KnowledgeAPI.ask).not.toHaveBeenCalled();
    await wrapper.get("textarea").setValue(" 年假多少天？ ");
    await click(wrapper, "提问");
    expect(KnowledgeAPI.ask).toHaveBeenCalledWith("年假多少天？");
    expect(wrapper.text()).toContain("年假为五天 [1]");
    expect(wrapper.text()).toContain("<script>alert(1)</script>");
    expect(wrapper.find("script").exists()).toBe(false);
    vi.mocked(KnowledgeAPI.ask).mockRejectedValueOnce(new Error("offline"));
    await click(wrapper, "提问");
    expect(wrapper.text()).not.toContain("年假为五天 [1]");
    expect(wrapper.text()).toContain("提问失败");
    wrapper.unmount();
  });

  it("reindexes stale documents and only deletes after confirmation", async () => {
    vi.mocked(KnowledgeAPI.list).mockResolvedValue(
      ok([{ ...document, needs_reindex: true }]) as never
    );
    const confirm = vi.spyOn(ElMessageBox, "confirm").mockRejectedValueOnce("cancel");
    const wrapper = render();
    await flushPromises();
    await click(wrapper, "重建索引");
    expect(KnowledgeAPI.reindex).toHaveBeenCalledWith(document.id);
    await click(wrapper, "删除");
    expect(KnowledgeAPI.remove).not.toHaveBeenCalled();
    confirm.mockResolvedValueOnce("confirm" as never);
    await click(wrapper, "删除");
    expect(KnowledgeAPI.remove).toHaveBeenCalledWith(document.id);
    wrapper.unmount();
    confirm.mockRestore();
  });
  it("lets an owner edit the name and visibility without replacing the file", async () => {
    const wrapper = render();
    await flushPromises();
    await click(wrapper, "编辑");
    await new DOMWrapper(globalThis.document.body)
      .get('input[aria-label="文档名称"]')
      .setValue("  新制度  ");
    wrapper.findComponent(ElSelect).vm.$emit("update:modelValue", "department");
    await click(wrapper, "保存");
    expect(KnowledgeAPI.update).toHaveBeenCalledWith(
      document.id,
      "新制度",
      "department",
      undefined
    );
    wrapper.unmount();
  });
  it("requests the selected document view from the backend", async () => {
    const wrapper = render();
    await flushPromises();
    const tab = wrapper.findAll('[role="tab"]').find((item) => item.text() === "我上传的");
    await tab!.trigger("click");
    await flushPromises();
    expect(KnowledgeAPI.list).toHaveBeenLastCalledWith("mine");
    wrapper.unmount();
  });
});
