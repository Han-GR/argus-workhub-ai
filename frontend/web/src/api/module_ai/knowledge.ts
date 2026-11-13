import { request } from "@utils";

export interface KnowledgeDocument {
  id: string;
  name: string;
  chunk_count: number;
  created_time: string;
  needs_reindex: boolean;
}

export interface KnowledgeAnswer {
  answer: string;
  sources: { number: number; document_id: string; name: string; text: string; score: number }[];
}

const url = "/ai/knowledge";
export interface KnowledgeBase {
  id: string;
  name: string;
  dept_id: number | null;
  dept_name: string | null;
  can_manage: boolean;
}
export interface KnowledgeCatalog {
  bases: KnowledgeBase[];
  departments: { id: number; name: string }[];
  can_create: boolean;
  can_create_company: boolean;
  can_configure: boolean;
}

export const KnowledgeAPI = {
  catalog() {
    return request<ApiResponse<KnowledgeCatalog>>({ url: `${url}/bases`, method: "get" });
  },
  createBase(data: { name: string; dept_id: number | null }) {
    return request<ApiResponse<{ id: string }>>({ url: `${url}/bases`, method: "post", data });
  },
  deleteBase(id: string) {
    return request<ApiResponse<null>>({
      url: `${url}/bases/${encodeURIComponent(id)}`,
      method: "delete",
    });
  },
  list(baseId: string) {
    return request<ApiResponse<KnowledgeDocument[]>>({
      url: `${url}/bases/${encodeURIComponent(baseId)}/documents`,
      method: "get",
    });
  },
  upload(baseId: string, file: File) {
    const data = new FormData();
    data.append("file", file);
    return request<ApiResponse<KnowledgeDocument>>({
      url: `${url}/bases/${encodeURIComponent(baseId)}/documents`,
      method: "post",
      data,
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 200000,
    });
  },
  reindex(baseId: string, id: string) {
    return request<ApiResponse<KnowledgeDocument>>({
      url: `${url}/bases/${encodeURIComponent(baseId)}/documents/${encodeURIComponent(id)}/reindex`,
      method: "post",
      timeout: 200000,
    });
  },
  remove(baseId: string, id: string) {
    return request<ApiResponse<null>>({
      url: `${url}/bases/${encodeURIComponent(baseId)}/documents/${encodeURIComponent(id)}`,
      method: "delete",
      timeout: 40000,
    });
  },
  ask(baseId: string, question: string) {
    return request<ApiResponse<KnowledgeAnswer>>({
      url: `${url}/bases/${encodeURIComponent(baseId)}/ask`,
      method: "post",
      data: { question },
      timeout: 160000,
    });
  },
};
