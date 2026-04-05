/**
 * api.js — thin fetch wrapper
 * Injects X-API-Key from localStorage if set.
 * All methods return parsed JSON or throw an ApiError.
 */

export class ApiError extends Error {
  constructor(status, statusText, body) {
    const message =
      body?.message || body?.error || body?.detail || statusText || "Unknown error";
    super(`HTTP ${status}: ${message}`);
    this.status = status;
    this.body = body;
    this.name = "ApiError";
  }
}

function getApiKey() {
  try {
    return localStorage.getItem("x-api-key") || "";
  } catch {
    return "";
  }
}

function buildHeaders(extra = {}) {
  const headers = { "Content-Type": "application/json", ...extra };
  const key = getApiKey();
  if (key) headers["X-API-Key"] = key;
  return headers;
}

async function parseResponse(res) {
  let body = null;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    try {
      body = await res.json();
    } catch {
      body = null;
    }
  } else {
    body = await res.text();
  }
  if (!res.ok) throw new ApiError(res.status, res.statusText, body);
  return body;
}

export const api = {
  /** @returns {{ data: any, status: number, duration: number, headers: Headers }} */
  async raw(method, path, body = undefined) {
    const opts = {
      method,
      headers: buildHeaders(),
    };
    if (body !== undefined && method !== "GET" && method !== "DELETE") {
      opts.body = JSON.stringify(body);
    }
    const t0 = performance.now();
    const res = await fetch(path, opts);
    const duration = Math.round(performance.now() - t0);
    const ct = res.headers.get("content-type") || "";
    let data = null;
    if (ct.includes("application/json")) {
      try { data = await res.json(); } catch { data = null; }
    } else {
      data = await res.text();
    }
    return { data, status: res.status, statusText: res.statusText, duration, headers: res.headers, ok: res.ok };
  },

  async get(path) {
    const r = await this.raw("GET", path);
    if (!r.ok) throw new ApiError(r.status, r.statusText, r.data);
    return r.data;
  },

  async post(path, body) {
    const r = await this.raw("POST", path, body);
    if (!r.ok) throw new ApiError(r.status, r.statusText, r.data);
    return r.data;
  },

  async put(path, body) {
    const r = await this.raw("PUT", path, body);
    if (!r.ok) throw new ApiError(r.status, r.statusText, r.data);
    return r.data;
  },

  async del(path) {
    const r = await this.raw("DELETE", path);
    if (!r.ok) throw new ApiError(r.status, r.statusText, r.data);
    return r.data;
  },
};
