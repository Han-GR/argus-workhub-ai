import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { beforeEach, expect, it, vi } from "vitest";
import Page from "@/views/module_ai/knowledge/question.vue";
import { KnowledgeAPI } from "@/api/module_ai/knowledge";

vi.mock("@/api/module_ai/knowledge", () => ({ KnowledgeAPI: { ask: vi.fn(), list: vi.fn() } }));
const render = () => mount(Page, { global: { plugins: [ElementPlus] } });
beforeEach(() => vi.resetAllMocks());

it("shows a standalone question page without upload controls or document fetching", async () => {
  const wrapper = render();
  expect(wrapper.text()).toContain("知识问答");
  expect(wrapper.text()).not.toContain("上传文档");
  expect(KnowledgeAPI.list).not.toHaveBeenCalled();
  await wrapper.get("textarea").setValue("   ");
  await wrapper.get("button").trigger("click");
  expect(KnowledgeAPI.ask).not.toHaveBeenCalled();
  wrapper.unmount();
});

it("renders authorized citations safely and clears previous answers when a request fails", async () => {
  vi.mocked(KnowledgeAPI.ask).mockResolvedValueOnce({
    data: {
      code: 0,
      data: {
        answer: "年假五天 [1]",
        sources: [
          {
            number: 1,
            document_id: "doc",
            name: "员工手册",
            text: "<script>alert(1)</script>",
            score: 0.9,
          },
        ],
      },
    },
  } as never);
  const wrapper = render();
  await wrapper.get("textarea").setValue(" 年假多少天？ ");
  await wrapper.get("button").trigger("click");
  await flushPromises();
  expect(KnowledgeAPI.ask).toHaveBeenCalledWith("年假多少天？");
  expect(wrapper.text()).toContain("年假五天 [1]");
  expect(wrapper.text()).toContain("<script>alert(1)</script>");
  expect(wrapper.find("script").exists()).toBe(false);
  vi.mocked(KnowledgeAPI.ask).mockRejectedValueOnce(new Error("offline"));
  await wrapper.get("button").trigger("click");
  await flushPromises();
  expect(wrapper.text()).not.toContain("年假五天 [1]");
  expect(wrapper.text()).toContain("提问失败");
  wrapper.unmount();
});
