// Setup Vitest : mocks chrome.* APIs partagés entre tests.

import { beforeEach, vi } from "vitest";

interface FakeStorageArea {
  data: Record<string, unknown>;
  get(
    keys: string[] | string | null,
    cb: (res: Record<string, unknown>) => void,
  ): void;
  set(items: Record<string, unknown>, cb?: () => void): void;
  remove(keys: string[] | string, cb?: () => void): void;
  clear(cb?: () => void): void;
}

function createFakeStorage(): FakeStorageArea {
  const data: Record<string, unknown> = {};
  return {
    data,
    get(keys, cb) {
      const out: Record<string, unknown> = {};
      const list = Array.isArray(keys) ? keys : keys ? [keys] : Object.keys(data);
      for (const k of list) {
        if (k in data) out[k] = data[k];
      }
      cb(out);
    },
    set(items, cb) {
      Object.assign(data, items);
      cb?.();
    },
    remove(keys, cb) {
      const list = Array.isArray(keys) ? keys : [keys];
      for (const k of list) delete data[k];
      cb?.();
    },
    clear(cb) {
      for (const k of Object.keys(data)) delete data[k];
      cb?.();
    },
  };
}

(globalThis as unknown as { chrome: any }).chrome = {
  storage: {
    session: createFakeStorage(),
    local: createFakeStorage(),
  },
  runtime: {
    sendMessage: vi.fn().mockResolvedValue(undefined),
    onMessage: { addListener: vi.fn() },
    lastError: undefined,
  },
  i18n: {
    getMessage: (key: string) => "",
  },
  tabs: {
    create: vi.fn(),
  },
};

beforeEach(() => {
  // Reset des fakes storage entre tests.
  const c = (globalThis as unknown as { chrome: any }).chrome;
  c.storage.session = createFakeStorage();
  c.storage.local = createFakeStorage();
  c.runtime.sendMessage = vi.fn().mockResolvedValue(undefined);
  c.runtime.onMessage = { addListener: vi.fn() };
  c.runtime.lastError = undefined;
  c.tabs.create = vi.fn();
});
