import { request } from "@utils";

export type DocumentVisibility = "company" | "department";
export type DocumentView = "all" | "company" | "department" | "mine";
export interface KnowledgeDocument {
  id: string;
  name: string;
  chunk_count: number;
  created_time: string;
  needs_reindex: boolean;
  visibility: DocumentVisibility;
  dept_id: number | null;
  dept_name: string | null;
  uploaded_by: number | null;
  uploader_name: string | null;
  can_edit: boolean;
  can_query: boolean;
}
export interface KnowledgeAnswer {
  answer: string;
  sources: { number: number; document_id: string; name: string; text: string; score: number }[];
}
export interface KnowledgeWorkspace {
  can_configure: boolean;
  department: { id: number; name: string } | null;
}
const url = "/ai/knowledge";
export const KnowledgeAPI = {
  workspace() {
    return request<ApiResponse<KnowledgeWorkspace>>({ url: `${url}/workspace`, method: "get" });
  },
  list(view: DocumentView = "all") {
    return request<ApiResponse<KnowledgeDocument[]>>({
      url: `${url}/documents`,
      method: "get",
      params: { view },
    });
  },
  upload(file: File, visibility: DocumentVisibility) {
    const data = new FormData();
    data.append("file", file);
    data.append("visibility", visibility);
    return request<ApiResponse<KnowledgeDocument>>({
      url: `${url}/documents`,
      method: "post",
      data,
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 200000,
    });
  },
  update(id: string, name: string, visibility: DocumentVisibility, file?: File) {
    const data = new FormData();
    data.append("name", name);
    data.append("visibility", visibility);
    if (file) data.append("file", file);
    return request<ApiResponse<KnowledgeDocument>>({
      url: `${url}/documents/${encodeURIComponent(id)}`,
      method: "put",
      data,
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 200000,
    });
  },
  reindex(id: string) {
    return request<ApiResponse<KnowledgeDocument>>({
      url: `${url}/documents/${encodeURIComponent(id)}/reindex`,
      method: "post",
      timeout: 200000,
    });
  },
  remove(id: string) {
    return request<ApiResponse<null>>({
      url: `${url}/documents/${encodeURIComponent(id)}`,
      method: "delete",
      timeout: 40000,
    });
  },
  ask(question: string) {
    return request<ApiResponse<KnowledgeAnswer>>({
      url: `${url}/ask`,
      method: "post",
      data: { question },
      timeout: 160000,
    });
  },
};
