import { request } from "@utils";

export interface TaskNotification {
  id: number;
  ticket_id: number;
  title: string;
  kind: "assigned" | "comment" | "status" | "due_soon" | "overdue";
  message: string;
  is_read: boolean;
  created_time: string;
}
export interface TaskInbox {
  items: TaskNotification[];
  total: number;
  unread: number;
}
const base = "/system/ticket/notifications";
export default {
  count: () => request<ApiResponse<number>>({ url: `${base}/unread-count`, method: "get" }),
  list: (page: number) =>
    request<ApiResponse<TaskInbox>>({
      url: base,
      method: "get",
      params: { page_no: page, page_size: 20 },
    }),
  read: (id: number) => request<ApiResponse>({ url: `${base}/${id}/read`, method: "put" }),
  readAll: () => request<ApiResponse>({ url: `${base}/read-all`, method: "put" }),
};
