import { request } from "@utils";

export interface EmbeddingConfigInput {
  base_url: string;
  model_id: string;
  dimensions: number;
  api_key: string;
}

export interface EmbeddingConfig extends Omit<EmbeddingConfigInput, "api_key"> {
  configured: boolean;
  has_api_key: boolean;
}

export interface EmbeddingTestResult {
  ok: boolean;
  model_id: string;
  dimensions: number;
  latency_ms: number;
}

export const EmbeddingAPI = {
  getConfig() {
    return request<ApiResponse<EmbeddingConfig>>({ url: "/ai/knowledge/embedding", method: "get" });
  },
  saveConfig(data: EmbeddingConfigInput) {
    return request<ApiResponse<EmbeddingConfig>>({
      url: "/ai/knowledge/embedding",
      method: "put",
      data,
    });
  },
  testConfig(data: EmbeddingConfigInput) {
    return request<ApiResponse<EmbeddingTestResult>>({
      url: "/ai/knowledge/embedding/test",
      method: "post",
      data,
      timeout: 40000,
    });
  },
};
