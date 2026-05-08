// F24 — Client fetch wrapper avec injection bearer + handler 401.

import type {
  ActiveApplicationItem,
  AuthExchangeResponse,
  DetectResponse,
  ProfileSnapshot,
} from "./types";

const DEFAULT_API_BASE = "http://localhost:8000";

export class AuthExpiredError extends Error {
  constructor() {
    super("Session expirée");
    this.name = "AuthExpiredError";
  }
}

export class NetworkError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "NetworkError";
  }
}

function getBaseUrl(): string {
  // import.meta.env.VITE_API_BASE_URL si défini, sinon localhost.
  // Lecture défensive (chrome storage runtime override possible plus tard).
  try {
    const env = (import.meta as unknown as { env?: Record<string, string> })
      .env;
    if (env?.VITE_API_BASE_URL) return env.VITE_API_BASE_URL;
  } catch {
    /* ignore */
  }
  return DEFAULT_API_BASE;
}

async function getStoredToken(): Promise<string | null> {
  return new Promise((resolve) => {
    if (typeof chrome === "undefined" || !chrome.storage?.session) {
      resolve(null);
      return;
    }
    chrome.storage.session.get(["extension_token"], (res) => {
      resolve((res?.extension_token as string | undefined) ?? null);
    });
  });
}

async function notifyAuthExpired(): Promise<void> {
  if (typeof chrome === "undefined" || !chrome.runtime?.sendMessage) return;
  try {
    await chrome.runtime.sendMessage({ type: "AUTH_EXPIRED" });
  } catch {
    /* runtime indispo (test) */
  }
}

export interface ApiFetchOptions {
  method?: string;
  body?: unknown;
  withAuth?: boolean;
  signal?: AbortSignal;
}

export async function apiFetch<T>(
  path: string,
  opts: ApiFetchOptions = {},
): Promise<T> {
  const url = getBaseUrl().replace(/\/$/, "") + path;
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };
  if (opts.withAuth !== false) {
    const token = await getStoredToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }
  let response: Response;
  try {
    response = await fetch(url, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
    });
  } catch (err) {
    throw new NetworkError(
      err instanceof Error ? err.message : "Erreur réseau",
    );
  }

  if (response.status === 401) {
    await notifyAuthExpired();
    throw new AuthExpiredError();
  }
  if (response.status === 204) {
    return null as unknown as T;
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const json = (await response.json()) as { detail?: string };
      if (json?.detail) detail = json.detail;
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

// API typée : 4 endpoints F24.

export async function authExchange(
  email: string,
  password: string,
): Promise<AuthExchangeResponse> {
  return apiFetch<AuthExchangeResponse>("/api/extension/v1/auth/exchange", {
    method: "POST",
    body: { email, password },
    withAuth: false,
  });
}

export async function fetchProfileSnapshot(): Promise<ProfileSnapshot> {
  return apiFetch<ProfileSnapshot>("/api/extension/v1/me/profile-snapshot");
}

export async function detectUrl(url: string): Promise<DetectResponse | null> {
  return apiFetch<DetectResponse | null>("/api/extension/v1/detect", {
    method: "POST",
    body: { url },
  });
}

export async function fetchActiveApplications(): Promise<
  ActiveApplicationItem[]
> {
  return apiFetch<ActiveApplicationItem[]>(
    "/api/extension/v1/applications/active",
  );
}
