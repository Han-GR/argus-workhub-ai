import { request } from "@utils";
export interface MeetingTaskItem {
  title: string;
  description: string;
  assigned_id: number | null;
  due_date: string | null;
  priority: number;
}
export interface MeetingDraftItem extends MeetingTaskItem {
  owner_name?: string | null;
  due_text?: string | null;
  evidence: string;
  warnings: string[];
}
export interface MeetingDraft {
  id: string;
  source_text: string;
  reference_date: string;
  tasks: MeetingDraftItem[];
  warnings: string[];
  confirmed: boolean;
  created_task_ids: number[] | null;
}
export interface MeetingReceipt {
  task_ids: number[];
  replayed: boolean;
}
const base = "/system/ticket/meeting-drafts";
export default {
  extract: (data: { source_text: string; reference_date: string; draft_id?: string }) =>
    request<ApiResponse<MeetingDraft>>({ url: `${base}/extract`, method: "post", data }),
  get: (id: string) => request<ApiResponse<MeetingDraft>>({ url: `${base}/${id}`, method: "get" }),
  confirm: (id: string, tasks: MeetingTaskItem[]) =>
    request<ApiResponse<MeetingReceipt>>({
      url: `${base}/${id}/confirm`,
      method: "post",
      data: { confirmed: true, tasks },
    }),
};
