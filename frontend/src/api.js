export const API = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? "" : "http://127.0.0.1:8000");

const TOKEN_KEY = "scheduler.auth.token";
const BUSINESS_KEY = "business-os.active-business";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY) || "";
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getBusinessId() {
  return localStorage.getItem(BUSINESS_KEY) || "";
}

export function setBusinessId(id) {
  if (id) localStorage.setItem(BUSINESS_KEY, String(id));
  else localStorage.removeItem(BUSINESS_KEY);
}

export async function api(path, options = {}) {
  const token = getToken();
  const businessId = getBusinessId();
  const response = await fetch(`${API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(businessId ? { "X-Business-Id": businessId } : {}),
      ...(options.headers || {}),
    },
  });

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/")) {
      window.dispatchEvent(new CustomEvent("scheduler:unauthorized"));
    }
    throw new Error(data?.detail || `Request failed: ${response.status}`);
  }
  return data;
}
