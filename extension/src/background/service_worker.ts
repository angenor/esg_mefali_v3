// F24 — Service worker MV3 : reçoit les messages DETECT_URL des content
// scripts, consulte un cache LRU local (chrome.storage.local) avant
// d'appeler /api/extension/v1/detect.

import { detectUrl, AuthExpiredError } from "@/shared/api";
import type { DetectMessage, DetectMessageResponse } from "@/shared/types";
import { TTLLRU } from "@/shared/lru";

const CACHE_KEY_PREFIX = "detect_cache:";
const CACHE_TTL_MS = 60 * 60 * 1000; // 1 heure
const MAX_CACHE_ENTRIES = 200;

// Cache mémoire éphémère par cycle SW. Une copie persistée dans
// chrome.storage.local sous forme de map permet la rétention LRU.
const memCache = new TTLLRU<{
  match: import("@/shared/types").DetectResponse | null;
}>(MAX_CACHE_ENTRIES, CACHE_TTL_MS);

async function readPersistentCache(
  url: string,
): Promise<{
  match: import("@/shared/types").DetectResponse | null;
} | null> {
  return new Promise((resolve) => {
    if (typeof chrome === "undefined" || !chrome.storage?.local) {
      resolve(null);
      return;
    }
    chrome.storage.local.get([CACHE_KEY_PREFIX + url], (res) => {
      const entry = res?.[CACHE_KEY_PREFIX + url];
      if (entry && entry.expiresAt > Date.now()) {
        resolve(entry.payload);
      } else {
        resolve(null);
      }
    });
  });
}

async function writePersistentCache(
  url: string,
  payload: { match: import("@/shared/types").DetectResponse | null },
): Promise<void> {
  if (typeof chrome === "undefined" || !chrome.storage?.local) return;
  return new Promise((resolve) => {
    chrome.storage.local.set(
      {
        [CACHE_KEY_PREFIX + url]: {
          payload,
          expiresAt: Date.now() + CACHE_TTL_MS,
        },
      },
      () => resolve(),
    );
  });
}

async function isAuthenticated(): Promise<boolean> {
  return new Promise((resolve) => {
    if (typeof chrome === "undefined" || !chrome.storage?.session) {
      resolve(false);
      return;
    }
    chrome.storage.session.get(["extension_token"], (res) => {
      resolve(!!res?.extension_token);
    });
  });
}

async function handleDetect(
  message: DetectMessage,
): Promise<DetectMessageResponse> {
  if (!(await isAuthenticated())) {
    return { ok: true, match: null };
  }
  const cached = memCache.get(message.url);
  if (cached) {
    return { ok: true, match: cached.match };
  }
  const persisted = await readPersistentCache(message.url);
  if (persisted) {
    memCache.set(message.url, persisted);
    return { ok: true, match: persisted.match };
  }
  try {
    const match = await detectUrl(message.url);
    const payload = { match: match ?? null };
    memCache.set(message.url, payload);
    await writePersistentCache(message.url, payload);
    return { ok: true, match: payload.match };
  } catch (err) {
    if (err instanceof AuthExpiredError) {
      return { ok: false, error: "AUTH_EXPIRED" };
    }
    return {
      ok: false,
      error: err instanceof Error ? err.message : "Erreur",
    };
  }
}

// Exports pour test (non utilisés à l'exécution).
export { handleDetect, memCache };

if (
  typeof chrome !== "undefined" &&
  chrome.runtime?.onMessage &&
  typeof chrome.runtime.onMessage.addListener === "function"
) {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    const m = message as { type?: string; url?: string };
    if (m?.type === "DETECT_URL" && typeof m.url === "string") {
      handleDetect({ type: "DETECT_URL", url: m.url }).then(sendResponse);
      return true; // async response
    }
    if (m?.type === "AUTH_EXPIRED") {
      // Forwardé par api.ts ; on relaie aux popups ouverts.
      try {
        chrome.runtime.sendMessage({ type: "AUTH_EXPIRED" }).catch(() => {});
      } catch {
        /* ignore */
      }
      return false;
    }
    return false;
  });
}
