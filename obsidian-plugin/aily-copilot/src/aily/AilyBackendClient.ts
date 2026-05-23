import { getSettings } from "@/settings/model";
import { requestUrl } from "obsidian";

export interface AilyChatRequest {
  message: string;
  search_query: string;
  project_id?: string;
  limit?: number;
  chat_history?: Array<{ role: string; content: string }>;
  use_llm?: boolean;
}

export interface AilyCitation {
  id?: string;
  title?: string;
  path?: string;
  relative_path?: string;
  score?: number;
}

export interface AilyChatResponse {
  answer: string;
  grounding_status?: string;
  used_llm?: boolean;
  citations?: AilyCitation[];
  search?: {
    results?: Array<{
      title?: string;
      path?: string;
      relative_path?: string;
      score?: number;
    }>;
  };
  suggested_actions?: string[];
}

export interface AilyStatusResponse {
  status: string;
  vault_path?: string;
  features?: Record<string, boolean>;
}

export interface AilySecretStatus {
  configured: boolean;
  preview: string;
}

export interface AilyResolvedRoute {
  workload: string;
  provider: "kimi" | "deepseek";
  model: string;
  base_url: string;
  api_key_configured: boolean;
}

export interface AilyConfigResponse {
  llm_provider: "kimi" | "deepseek";
  llm_base_url: string;
  llm_model: string;
  kimi: {
    model: string;
    vision_model: string;
    api_key: AilySecretStatus;
  };
  deepseek: {
    model: string;
    api_key: AilySecretStatus;
  };
  tavily: {
    search_depth: "basic" | "advanced";
    api_key: AilySecretStatus;
  };
  runtime: {
    timeout_seconds: number;
    max_retries: number;
    max_concurrency: number;
    min_interval_seconds: number;
  };
  routes: {
    copilot_chat: AilyResolvedRoute;
    copilot_dossier: AilyResolvedRoute;
  };
  workload_routes_json: string;
  persistence: "runtime_only" | string;
}

export interface AilyConfigUpdateRequest {
  llm_provider?: "kimi" | "deepseek";
  copilot_chat_provider?: "kimi" | "deepseek";
  copilot_dossier_provider?: "kimi" | "deepseek";
  kimi_api_key?: string;
  kimi_model?: string;
  kimi_vision_model?: string;
  deepseek_api_key?: string;
  deepseek_model?: string;
  tavily_api_key?: string;
  tavily_search_depth?: "basic" | "advanced";
  llm_timeout_seconds?: number;
  llm_max_retries?: number;
  llm_max_concurrency?: number;
  llm_min_interval_seconds?: number;
}

export class AilyBackendClient {
  async status(): Promise<AilyStatusResponse> {
    return this.request<AilyStatusResponse>("/api/copilot/status", "GET");
  }

  async config(): Promise<AilyConfigResponse> {
    return this.request<AilyConfigResponse>("/api/copilot/config", "GET");
  }

  async updateConfig(payload: AilyConfigUpdateRequest): Promise<AilyConfigResponse> {
    return this.request<AilyConfigResponse>("/api/copilot/config", "POST", payload);
  }

  async chat(payload: AilyChatRequest): Promise<AilyChatResponse> {
    return this.request<AilyChatResponse>("/api/copilot/chat", "POST", payload);
  }

  private async request<T>(path: string, method: "GET" | "POST", body?: unknown): Promise<T> {
    const settings = getSettings();
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (method === "POST") {
      headers["Content-Type"] = "application/json";
    }
    if (settings.ailyApiToken) {
      headers.Authorization = `Bearer ${settings.ailyApiToken}`;
    }

    const url = `${settings.ailyApiBaseUrl.replace(/\/$/, "")}${path}`;
    const response = await requestUrl({
      url,
      method,
      headers,
      body: method === "POST" ? JSON.stringify(body ?? {}) : undefined,
      throw: false,
    });

    const parsed = parseJson(response.text);
    if (response.status < 200 || response.status >= 300) {
      const detail =
        typeof parsed.detail === "string" ? parsed.detail : response.text || `HTTP ${response.status}`;
      throw new Error(`Aily API ${response.status}: ${detail}`);
    }
    return parsed as T;
  }
}

function parseJson(text: string): Record<string, unknown> {
  if (!text.trim()) return {};
  try {
    return JSON.parse(text) as Record<string, unknown>;
  } catch {
    return { text };
  }
}
