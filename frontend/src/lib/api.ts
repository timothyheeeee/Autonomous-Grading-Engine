export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "agas_admin_token";
const THREAD_KEY = "agas_thread";
const LEGACY_KEYS = ["agas_token", "agas_user", "agas_admin_token"];

function clearAuth() {
  for (const key of LEGACY_KEYS) localStorage.removeItem(key);
}

export async function getAdminToken(force = false): Promise<string> {
  if (!force) {
    const existing = localStorage.getItem(TOKEN_KEY);
    if (existing && existing !== "undefined") return existing;
  }
  clearAuth();
  const response = await fetch(`${API_URL}/api/auth/bootstrap`);
  if (!response.ok) {
    throw new Error("Could not start a local admin session. Is the backend running on port 8000?");
  }
  const payload = await response.json();
  if (!payload.access_token) {
    throw new Error("Bootstrap did not return a token.");
  }
  localStorage.setItem(TOKEN_KEY, payload.access_token);
  return payload.access_token as string;
}

export function getThreadId(): string | null {
  return localStorage.getItem(THREAD_KEY);
}

export function setThreadId(id: string | null) {
  if (id) localStorage.setItem(THREAD_KEY, id);
  else localStorage.removeItem(THREAD_KEY);
}

async function request<T>(path: string, init: RequestInit, token: string): Promise<Response> {
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${token}`);
  if (!(init.body instanceof FormData) && init.body) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${API_URL}${path}`, { ...init, headers });
}

function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const record = detail as { detail?: unknown; message?: string };
    if (typeof record.detail === "string") return record.detail;
    if (record.detail && typeof record.detail === "object") {
      const nested = record.detail as { message?: string };
      if (nested.message) return nested.message;
    }
    if (record.message) return record.message;
  }
  return fallback;
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  let token = await getAdminToken();
  let response = await request(path, init, token);
  if (response.status === 401) {
    token = await getAdminToken(true);
    response = await request(path, init, token);
  }
  if (!response.ok) {
    const detail = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errorMessage(detail, "Request failed"));
  }
  return response.json() as Promise<T>;
}

export type AuditStep = { step: number; title: string; detail: string; ok: boolean };

export type StudentPercent = {
  student_name: string;
  contribution_percentage: number;
  overall_percentage: number;
  audit: string;
  criteria: Array<{ criterion: string; percentage: number; source_row_ids: number[] }>;
};

export type PipelineState = {
  thread_id: string;
  status: "running" | "pending_review" | "published" | "error" | "rejected" | "empty";
  current_node: string;
  token_usage: number;
  audit_trail: AuditStep[];
  dynamic_roster: string[];
  percentages: { students: StudentPercent[]; rubric_title?: string } | null;
  error: { reason: string; message: string } | null;
};
