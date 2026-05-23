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

export class AilyBackendClient {
  async status(): Promise<AilyStatusResponse> {
    return this.request<AilyStatusResponse>("/api/copilot/status", "GET");
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
