/**
 * API helper — all HTTP calls go through this module.
 * Automatically injects JWT Authorization header.
 */
const API = (() => {
  const BASE_URL = "";  // Same origin; Flask serves frontend + backend

  function getHeaders(extra = {}) {
    const headers = { "Content-Type": "application/json", ...extra };
    const token = localStorage.getItem("sf_token");
    if (token) headers["Authorization"] = `Bearer ${token}`;
    return headers;
  }

  async function request(method, path, body = null) {
    const opts = { method, headers: getHeaders() };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(BASE_URL + path, opts);
    const json = await res.json().catch(() => ({ success: false, message: "Invalid JSON response" }));
    return json;
  }

  return {
    get:    (path)         => request("GET",    path),
    post:   (path, data)   => request("POST",   path, data),
    put:    (path, data)   => request("PUT",    path, data),
    delete: (path)         => request("DELETE", path),
  };
})();
