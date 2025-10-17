/* api.js - updated to accept AbortSignal for abortable requests */

/* =======================
   Configuration / Defaults
   ======================= */
const API_BASE = "http://192.168.1.13:20202";
const DEFAULT_OPTIONS = {
  timeout_ms: 10000,
  retries: 2,
  retry_base_delay_ms: 250,
  cache_ttl_ms: 5 * 60 * 1000,
  max_cache_size: 1000,
};
const JSON_HEADER = { "Content-Type": "application/json" };

/* =======================
   Helpers & validators
   ======================= */
function _validate_string(name, value, { allow_empty = false, max_length = 1000 } = {}) {
  if (typeof value !== "string") throw new Error(`${name} must be a string`);
  if (!allow_empty && value.trim() === "") throw new Error(`${name} must not be empty`);
  if (max_length && value.length > max_length) throw new Error(`${name} exceeds maximum length of ${max_length}`);
}
function _validate_ids_array(name, ids) {
  if (!Array.isArray(ids)) throw new Error(`${name} must be an array`);
  if (!ids.length) throw new Error(`${name} must not be empty`);
  for (const id of ids) {
    if (!["string", "number"].includes(typeof id)) throw new Error(`${name} must contain strings or numbers`);
  }
}
function _validate_tag(name, tag) {
  if (typeof tag !== "object" || tag === null) throw new Error(`${name} must be an object`);
  if (tag.id === undefined && tag.value === undefined) throw new Error(`${name} must have id or value`);
}
function _sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/* =======================
   ApiClient Class
   - Encapsulates fetch logic, retries, timeout, and caching
   - Now supports an external AbortSignal passed in as an option to public methods.
   ======================= */
class ApiClient {
  constructor(base_url = API_BASE, options = {}) {
    this.base_url = base_url.replace(/\/+$/, "");
    this.options = { ...DEFAULT_OPTIONS, ...options };
    this._cache = new Map();
  }

  _build_url(path, params = null) {
    const normalized_path = path.startsWith("/") ? path : `/${path}`;
    const url = new URL(`${this.base_url}${normalized_path}`);
    if (params && typeof params === "object") {
      Object.keys(params).forEach((k) => {
        const v = params[k];
        if (v !== undefined && v !== null) url.searchParams.append(k, String(v));
      });
    }
    return url.toString();
  }

  _cache_get(url) {
    const entry = this._cache.get(url);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
      this._cache.delete(url);
      return null;
    }
    return entry.value;
  }

  _cache_set(url, value, ttl_ms = null) {
    const ttl = ttl_ms === null ? this.options.cache_ttl_ms : ttl_ms;
    const expiresAt = Date.now() + ttl;
    if (this._cache.size >= this.options.max_cache_size) {
      const firstKey = this._cache.keys().next().value;
      this._cache.delete(firstKey);
    }
    this._cache.set(url, { value, expiresAt });
  }

  /**
   * Low-level fetch wrapper with:
   *  - support for external abort signal (external_signal)
   *  - internal timeout (this.options.timeout_ms)
   *  - retries on transient network/server errors with backoff
   *
   * External abort behavior:
   *  - If external_signal is provided, we wire it to our internal controller so when external aborts, fetch is aborted.
   *
   * @param {string} url - full URL
   * @param {Object} fetch_opts - fetch options (method, headers, body, etc.)
   * @param {Array<number>} ok_statuses - allowed statuses
   * @param {Object} opts - { expect_json, cache_get, cache_set }
   * @param {AbortSignal|null} external_signal - optional external AbortSignal (if provided, will cause early abort)
   */
  async _fetch_with_retry(url, fetch_opts = {}, ok_statuses = [200], { expect_json = true, cache_get = false, cache_set = false } = {}, external_signal = null) {
    const is_get = (!fetch_opts.method || fetch_opts.method.toUpperCase() === "GET");
    if (is_get && cache_get) {
      const cached = this._cache_get(url);
      if (cached !== null) return { cached: true, status: 200, data: cached, response: null };
    }

    let attempt = 0;
    const max_attempts = Math.max(1, (this.options.retries || 0) + 1);
    const base_delay = this.options.retry_base_delay_ms || 200;

    // We'll create one controller per attempt so timeouts/retries are isolated.
    while (attempt < max_attempts) {
      attempt += 1;

      // Composite controller: if external_signal aborts, we abort this controller.
      const controller = new AbortController();
      const internal_signal = controller.signal;

      // Wire external signal to this controller (if provided)
      let externalListener;
      if (external_signal) {
        // If external_signal already aborted, abort immediately
        if (external_signal.aborted) {
          controller.abort();
        } else {
          externalListener = () => controller.abort();
          external_signal.addEventListener("abort", externalListener, { once: true });
        }
      }

      // Timeout handling
      const timeout_ms = this.options.timeout_ms;
      const timer = setTimeout(() => controller.abort(), timeout_ms);

      try {
        const opts_with_signal = { ...fetch_opts, signal: internal_signal };
        const res = await fetch(url, opts_with_signal);
        clearTimeout(timer);
        if (externalListener) external_signal.removeEventListener("abort", externalListener);

        if (!res.ok && !ok_statuses.includes(res.status)) {
          if (res.status >= 500 && attempt < max_attempts) {
            const jitter = Math.random() * 100;
            const delay = base_delay * 2 ** (attempt - 1) + jitter;
            await _sleep(delay);
            continue; // retry
          }
          throw new Error(`Request failed (${res.status} ${res.statusText}): ${url}`);
        }

        if (expect_json) {
          if (res.status === 204) {
            if (cache_set && is_get) this._cache_set(url, null);
            return { cached: false, status: res.status, data: null, response: res };
          }
          const json = await res.json();
          if (cache_set && is_get) this._cache_set(url, json);
          return { cached: false, status: res.status, data: json, response: res };
        } else {
          if (cache_set && is_get) this._cache_set(url, null);
          return { cached: false, status: res.status, data: null, response: res };
        }
      } catch (err) {
        clearTimeout(timer);
        if (externalListener && external_signal) external_signal.removeEventListener("abort", externalListener);
        const is_abort = err && err.name === "AbortError";
        const is_network_error = !(err && err.name === "AbortError") && (err instanceof TypeError || /network/i.test(String(err)));

        // Retry for network/timeouts if attempts remain
        if ((is_abort || is_network_error) && attempt < max_attempts) {
          const jitter = Math.random() * 100;
          const delay = base_delay * 2 ** (attempt - 1) + jitter;
          await _sleep(delay);
          continue;
        }
        // Otherwise rethrow
        throw err;
      }
    } // end attempts

    throw new Error(`Request failed after ${max_attempts} attempts: ${url}`);
  }

  /* Convenience methods now accept an optional options object where you can pass signal */
  async get_json(path, params = null, { cache = true, ok_statuses = [200], signal = null } = {}) {
    const url = this._build_url(path, params);
    const result = await this._fetch_with_retry(url, { method: "GET" }, ok_statuses, { expect_json: true, cache_get: cache, cache_set: cache }, signal);
    return result.data;
  }

  async post_json(path, payload, { ok_statuses = [200], signal = null } = {}) {
    const url = this._build_url(path);
    const res = await this._fetch_with_retry(url, { method: "POST", headers: JSON_HEADER, body: JSON.stringify(payload) }, ok_statuses, { expect_json: true }, signal);
    return res.data;
  }

  async post_void(path, payload, { ok_statuses = [200, 204], signal = null } = {}) {
    const url = this._build_url(path);
    await this._fetch_with_retry(url, { method: "POST", headers: JSON_HEADER, body: JSON.stringify(payload) }, ok_statuses, { expect_json: false }, signal);
    return;
  }

  async post_raw_array(path, array_body, { ok_statuses = [200], signal = null } = {}) {
    const url = this._build_url(path);
    const res = await this._fetch_with_retry(url, { method: "POST", headers: JSON_HEADER, body: JSON.stringify(array_body) }, ok_statuses, { expect_json: true }, signal);
    return res.data;
  }

  async delete(path, { ok_statuses = [200, 204], expect_json = false, signal = null } = {}) {
    const url = this._build_url(path);
    const res = await this._fetch_with_retry(url, { method: "DELETE" }, ok_statuses, { expect_json }, signal);
    return res.data;
  }

  get_media_preview_url(media, type = "image") {
    if (!media || media.id === undefined || media.id === null) return "";
    if (type === "image") return `${this.base_url}/image/preview/${media.id}`;
    if (type === "video") return `${this.base_url}/video/preview/${media.id}`;
    return "";
  }
  get_media_full_url(media, type = "image") {
    if (!media || media.id === undefined || media.id === null) return "";
    if (type === "image") return `${this.base_url}/image/full/${media.id}`;
    if (type === "video") return `${this.base_url}/video/full/${media.id}`;
    return "";
  }
}

/* =======================
   Default client instance
   ======================= */
const api_client = new ApiClient(API_BASE, {
  timeout_ms: 10000,
  retries: 2,
  retry_base_delay_ms: 250,
  cache_ttl_ms: 5 * 60 * 1000,
  max_cache_size: 1000,
});

/* =======================
   High-level API (now accept options with optional signal)
   ======================= */
export async function search_tags_by_prefix(keyword, limit = 10, opts = {}) {
  if (!keyword) return [];
  _validate_string("keyword", keyword, { allow_empty: false, max_length: 200 });
  return await api_client.get_json("/search_tags_by_prefix", { keyword: String(keyword), limit }, { cache: true, signal: opts.signal });
}
export async function search_tags_fuzzy(keyword, limit = 10, opts = {}) {
  if (!keyword) return [];
  _validate_string("keyword", keyword, { allow_empty: false, max_length: 200 });
  return await api_client.get_json("/search_tags_fuzzy", { keyword: String(keyword), limit }, { cache: true, signal: opts.signal });
}
export async function search_media_by_tags(include_tags, exclude_tags, limit = 30, offset = 0, favorite_only = false, user_id = null, cached = false, opts = {}) {
  if (!Array.isArray(include_tags)) throw new Error("include_tags must be an array");
  if (!Array.isArray(exclude_tags)) throw new Error("exclude_tags must be an array");
  const payload = { include_tags, exclude_tags, limit, offset, favorite_only, user_id, cached };
  return await api_client.post_json("/search_media_by_tags", payload, { signal: opts.signal });
}
export async function save_search_history(include_tags, exclude_tags, favorite_only = false, user_id = null, opts = {}) {
  if (!Array.isArray(include_tags)) throw new Error("include_tags must be an array");
  if (!Array.isArray(exclude_tags)) throw new Error("exclude_tags must be an array");
  const payload = { include_tags, exclude_tags, favorite_only, user_id };
  return await api_client.post_json("/search_history", payload, { signal: opts.signal });
}
export async function get_search_history(limit = 20, user_id = null, opts = {}) {
  const parsed_limit = Number(limit) || 20;
  const params = { limit: parsed_limit };
  if (user_id !== null) params.user_id = String(user_id);
  return await api_client.get_json("/search_history", params, { cache: true, signal: opts.signal });
}
export async function fetch_media_with_tags(id, opts = {}) {
  if (id === undefined || id === null) throw new Error("id is required");
  return await api_client.get_json("/fetch_media_with_tags", { id: String(id) }, { signal: opts.signal });
}
export async function fetch_media_with_tags_batch(ids, opts = {}) {
  if (!Array.isArray(ids) || !ids.length) return [];
  _validate_ids_array("ids", ids);
  return await api_client.post_raw_array("/fetch_media_with_tags_batch", ids, { signal: opts.signal });
}
export function get_media_preview_url(media, type = "image") {
  return api_client.get_media_preview_url(media, type);
}
export function get_media_full_url(media, type = "image") {
  return api_client.get_media_full_url(media, type);
}
export async function preflight(ids, opts = {}) {
  if (!Array.isArray(ids) || !ids.length) return;
  _validate_ids_array("ids", ids);
  return await api_client.post_void("/preflight", ids, { signal: opts.signal });
}
export async function fetch_recommendations(id, opts = {}) {
  if (id === undefined || id === null) throw new Error("id is required");
  return await api_client.get_json(`/suggestion/${String(id)}`, null, { signal: opts.signal });
}
export async function fetch_media_batch(ids, opts = {}) {
  if (!ids || !ids.length) return [];
  _validate_ids_array("ids", ids);
  try {
    await preflight(ids, { signal: opts.signal });
  } catch (e) {
    console.warn("Preflight failed", e);
  }
  return await fetch_media_with_tags_batch(ids, { signal: opts.signal });
}
export async function add_favorite_media(media_id, opts = {}) {
  if (media_id === undefined || media_id === null) throw new Error("media_id is required");
  await api_client._fetch_with_retry(api_client._build_url(`/favorite/media/${media_id}`), { method: "POST" }, [200, 204], { expect_json: false }, opts.signal);
  return;
}
export async function remove_favorite_media(media_id, opts = {}) {
  if (media_id === undefined || media_id === null) throw new Error("media_id is required");
  await api_client._fetch_with_retry(api_client._build_url(`/favorite/media/${media_id}`), { method: "DELETE" }, [200, 204], { expect_json: false }, opts.signal);
  return;
}
export async function get_favorite_media(opts = {}) {
  return await api_client.get_json("/favorite/media", null, { cache: true, signal: opts.signal });
}
export async function add_favorite_tag(tag, opts = {}) {
  _validate_tag("tag", tag);
  await api_client._fetch_with_retry(api_client._build_url("/favorite/tag"), { method: "POST", headers: JSON_HEADER, body: JSON.stringify({ id: tag.id, value: tag.value }) }, [200, 204], { expect_json: false }, opts.signal);
  return;
}
export async function remove_favorite_tag(tag_id, opts = {}) {
  if (tag_id === undefined || tag_id === null) throw new Error("tag_id is required");
  await api_client._fetch_with_retry(api_client._build_url(`/favorite/tag/${tag_id}`), { method: "DELETE" }, [200, 204], { expect_json: false }, opts.signal);
  return;
}
export async function get_favorite_tags(opts = {}) {
  return await api_client.get_json("/favorite/tag", null, { cache: true, signal: opts.signal });
}

/* Backwards-compatible aliases (camelCase) */
export const searchTagsByPrefix = search_tags_by_prefix;
export const searchTagsFuzzy = search_tags_fuzzy;
export const searchMediaByTags = search_media_by_tags;
export const saveSearchHistory = save_search_history;
export const getSearchHistory = get_search_history;
export const fetchMediaWithTags = fetch_media_with_tags;
export const fetchMediaWithTagsBatch = fetch_media_with_tags_batch;
export const getMediaPreviewUrl = get_media_preview_url;
export const getMediaFullUrl = get_media_full_url;
export const preflightCall = preflight;
export const fetchRecommendations = fetch_recommendations;
export const fetchMediaBatch = fetch_media_batch;
export const addFavoriteMedia = add_favorite_media;
export const removeFavoriteMedia = remove_favorite_media;
export const getFavoriteMedia = get_favorite_media;
export const addFavoriteTag = add_favorite_tag;
export const removeFavoriteTag = remove_favorite_tag;
export const getFavoriteTags = get_favorite_tags;

/* Notes:
 - To fully abort network requests, your code should pass an AbortSignal to public methods (I've added opts.signal parameters).
 - The client still provides timeouts and retries; external abort will cancel immediately.
*/