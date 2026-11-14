import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus from "element-plus";
import { beforeEach, expect, it, vi } from "vitest";
import Page from "@/views/module_system/ticket/meeting.vue";
import MeetingAPI from "@/api/module_system/meeting-tasks";

const mocks = vi.hoisted(() => ({
  user: { info: { is_superuser: false }, prems: ["module_ai:chat:query"] },
  push: vi.fn(),
}));
vi.mock("@stores", () => ({ useUserStore: () => mocks.user }));
vi.mock("vue-router", () => ({ useRouter: () => ({ push: mocks.push }) }));
vi.mock("@/api/module_system/meeting-tasks", () => ({
  default: { extract: vi.fn(), confirm: vi.fn(), get: vi.fn() },
}));
vi.mock("@/api/module_system/ticket", () => ({
  default: { assignees: vi.fn().mockResolvedValue({ data: { data: [] } }) },
}));
const render = () => mount(Page, { global: { plugins: [ElementPlus] } });
beforeEach(() => {
  vi.clearAllMocks();
  mocks.user.prems = ["module_ai:chat:query"];
});

it("opens as a standalone page and creates tasks only after explicit review", async () => {
  vi.mocked(MeetingAPI.extract).mockResolvedValue({
    data: {
      data: {
        id: "draft-1",
        confirmed: false,
        warnings: [],
        tasks: [
          {
            title: "整理项目材料",
            description: "汇总会议结论",
            assigned_id: null,
            due_date: null,
            priority: 1,
            evidence: "整理项目材料",
            warnings: [],
          },
        ],
      },
    },
  } as never);
  vi.mocked(MeetingAPI.confirm).mockResolvedValue({ data: { data: { task_ids: [42] } } } as never);
  const wrapper = render();
  await flushPromises();
  expect(wrapper.get("h1").text()).toBe("会议纪要");
  expect(wrapper.find("[role=dialog]").exists()).toBe(false);
  await wrapper.get("textarea").setValue("会议决定：整理项目材料并汇总会议结论。");
  await wrapper.get(".meeting-footer button").trigger("click");
  await flushPromises();
  expect(MeetingAPI.extract).toHaveBeenCalledOnce();
  expect(MeetingAPI.confirm).not.toHaveBeenCalled();
  const confirm = wrapper
    .findAll(".meeting-footer button")
    .find((b) => b.text().startsWith("确认创建"))!;
  expect(confirm.attributes("disabled")).toBeDefined();
  await wrapper.get(".meeting-confirmation input[type=checkbox]").setValue(true);
  await confirm.trigger("click");
  await flushPromises();
  expect(MeetingAPI.confirm).toHaveBeenCalledWith("draft-1", [
    expect.objectContaining({ title: "整理项目材料" }),
  ]);
  expect(wrapper.text()).toContain("已创建 1 项任务");
  await wrapper
    .findAll("button")
    .find((b) => b.text() === "查看任务 #42")!
    .trigger("click");
  expect(mocks.push).toHaveBeenCalledWith({ path: "/system/ticket", query: { task_id: 42 } });
  wrapper.unmount();
});

it("keeps extraction unavailable without AI access", async () => {
  mocks.user.prems = [];
  const wrapper = render();
  await wrapper.get("textarea").setValue("会议决定：整理项目材料并汇总会议结论。");
  expect(wrapper.get(".meeting-footer button").attributes("disabled")).toBeDefined();
  expect(wrapper.text()).toContain("需要 AI 助手访问权限");
  expect(MeetingAPI.extract).not.toHaveBeenCalled();
  wrapper.unmount();
});
