import { flushPromises, mount } from "@vue/test-utils";
import ElementPlus, { ElMessage, ElSelect } from "element-plus";
import { beforeEach, expect, it, vi } from "vitest";
import Page from "@/views/module_task/storage/browse/index.vue";
import StorageAPI from "@/api/module_storage/browse";

vi.mock("@stores", () => ({ useUserStore: () => ({ info: { id: 1 } }) }));
vi.mock("@/api/module_storage/browse", () => ({
  default: {
    sources: vi.fn(),
    listFiles: vi.fn(),
    uploadFile: vi.fn(),
    mkdir: vi.fn(),
    setVisibility: vi.fn(),
    copyFile: vi.fn(),
    renameFile: vi.fn(),
    deleteFile: vi.fn(),
    downloadFile: vi.fn(),
    downloadDir: vi.fn(),
  },
}));
const result = (data: unknown) => ({ data: { code: 0, data } }) as never;
const render = () =>
  mount(Page, {
    global: {
      plugins: [ElementPlus],
      directives: { hasPerm: {} },
      stubs: {
        ElDialog: {
          props: ["modelValue"],
          template: '<section v-if="modelValue"><slot/><slot name="footer"/></section>',
        },
        ArgusTable: {
          props: ["data"],
          template:
            '<div><article v-for="row in data"><slot name="name" :row="row"/><slot name="visibility" :row="row"/><slot name="operation" :row="row"/></article></div>',
        },
        ElDropdown: { template: '<div><slot/><slot name="dropdown"/></div>' },
        ElDropdownMenu: { template: "<div><slot/></div>" },
        ElDropdownItem: { template: "<span><slot/></span>" },
      },
    },
  });
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(StorageAPI.sources).mockResolvedValue(
    result([{ id: 1, name: "私有档案", protocol: "local", is_default: true }])
  );
  vi.mocked(StorageAPI.listFiles).mockResolvedValue(result([]));
  vi.mocked(StorageAPI.uploadFile).mockResolvedValue(result({}));
});

it("uploads with an explicit root visibility and does not show owner actions for others", async () => {
  vi.mocked(StorageAPI.listFiles).mockResolvedValue(
    result([
      { name: "员工手册.txt", key: "员工手册.txt", visibility: "company", can_manage: false },
    ])
  );
  const wrapper = render();
  await flushPromises();
  expect(wrapper.text()).toContain("全公司可见");
  expect(wrapper.text()).not.toContain("重命名");
  expect(wrapper.text()).not.toContain("删除");
  const scope = wrapper
    .findAllComponents(ElSelect)
    .find((c) => c.props("modelValue") === "private")!;
  scope.vm.$emit("update:modelValue", "department");
  const input = wrapper.get('input[type="file"]');
  Object.defineProperty(input.element, "files", { value: [new File(["hello"], "资料.txt")] });
  await input.trigger("change");
  await flushPromises();
  const payload = vi.mocked(StorageAPI.uploadFile).mock.calls[0]![0];
  expect(payload.get("visibility")).toBe("department");
  expect(payload.get("remote_path")).toBe("资料.txt");
  wrapper.unmount();
});

it("shows inherited scope inside folders and never reports a failed upload as success", async () => {
  vi.mocked(StorageAPI.listFiles).mockResolvedValueOnce(
    result([
      {
        name: "部门资料",
        key: "部门资料",
        is_dir: true,
        visibility: "department",
        can_manage: true,
      },
    ])
  );
  const success = vi.spyOn(ElMessage, "success");
  const wrapper = render();
  await flushPromises();
  await wrapper.get(".file-name").trigger("click");
  await flushPromises();
  expect(wrapper.text()).toContain("新文件继承顶层文件夹的共享范围");
  expect(wrapper.find('[aria-label="上传文件可见范围"]').exists()).toBe(false);
  vi.mocked(StorageAPI.uploadFile).mockResolvedValue({ data: { code: 1 } } as never);
  const input = wrapper.get('input[type="file"]');
  Object.defineProperty(input.element, "files", { value: [new File(["hello"], "资料.txt")] });
  await input.trigger("change");
  await flushPromises();
  expect(vi.mocked(StorageAPI.uploadFile).mock.calls[0]![0].get("remote_path")).toBe("部门资料/");
  expect(wrapper.text()).toContain("操作未完成");
  expect(success).not.toHaveBeenCalled();
  success.mockRestore();
  wrapper.unmount();
});

it("previews images through the authenticated download API and releases the object URL", async () => {
  const create = vi.fn().mockReturnValue("blob:archive-image");
  const revoke = vi.fn();
  vi.stubGlobal(
    "URL",
    class extends URL {
      static override createObjectURL = create;
      static override revokeObjectURL = revoke;
    }
  );
  vi.mocked(StorageAPI.listFiles).mockResolvedValue(
    result([{ name: "curry.jpg", key: "curry.jpg", size: 20 }])
  );
  vi.mocked(StorageAPI.downloadFile).mockResolvedValue({
    data: new Blob(["image"], { type: "application/octet-stream" }),
  } as never);
  const wrapper = render();
  await flushPromises();
  await wrapper.get(".file-name").trigger("click");
  await flushPromises();
  expect(StorageAPI.downloadFile).toHaveBeenCalledWith({ source_id: 1, remote_path: "curry.jpg" });
  expect(wrapper.get(".preview-image").attributes("src")).toBe("blob:archive-image");
  expect(create.mock.calls[0]![0].type).toBe("image/jpeg");
  wrapper.unmount();
  expect(revoke).toHaveBeenCalledWith("blob:archive-image");
  vi.unstubAllGlobals();
});

it("renders text as plain content and shows preview failures", async () => {
  vi.mocked(StorageAPI.listFiles).mockResolvedValue(
    result([{ name: "notes.md", key: "notes.md", size: 20 }])
  );
  vi.mocked(StorageAPI.downloadFile).mockResolvedValue({
    data: { size: 20, text: async () => "<script>alert(1)</script>" },
  } as never);
  const wrapper = render();
  await flushPromises();
  await wrapper.get(".file-name").trigger("click");
  await flushPromises();
  expect(wrapper.get(".preview-text").text()).toBe("<script>alert(1)</script>");
  expect(wrapper.find("script").exists()).toBe(false);
  vi.mocked(StorageAPI.downloadFile).mockRejectedValueOnce(new Error("forbidden"));
  await wrapper.get(".file-name").trigger("click");
  await flushPromises();
  expect(wrapper.text()).toContain("预览加载失败");
  expect(wrapper.find(".preview-text").exists()).toBe(false);
  wrapper.unmount();
});

it("explains unsupported formats without downloading them for preview", async () => {
  vi.mocked(StorageAPI.listFiles).mockResolvedValue(
    result([{ name: "archive.zip", key: "archive.zip" }])
  );
  const wrapper = render();
  await flushPromises();
  await wrapper.get(".file-name").trigger("click");
  await flushPromises();
  expect(wrapper.text()).toContain("暂不支持此格式在线预览");
  expect(StorageAPI.downloadFile).not.toHaveBeenCalled();
  wrapper.unmount();
});
