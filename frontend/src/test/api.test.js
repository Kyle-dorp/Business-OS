/**
 * The one function every screen goes through.
 *
 * Nothing in the frontend talks to the backend except api(), which means three
 * properties here are load-bearing for the whole product: the workspace header
 * that makes multi-tenancy work at all, the bearer token, and what happens on
 * a 401.
 *
 * That last one is the subtle one. A 401 anywhere signs the user out — except
 * on /auth/*, where a 401 is just a wrong password. Getting that backwards
 * means a failed login tears down the session that is trying to be created,
 * and the user sees the sign-in form flicker instead of "wrong password".
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, getBusinessId, getToken, setBusinessId, setToken } from "../api.js";

function mockFetch({ ok = true, status = 200, body = {} } = {}) {
  const spy = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  });
  globalThis.fetch = spy;
  return spy;
}

function lastCall(spy) {
  const [url, options] = spy.mock.calls.at(-1);
  return { url, options, headers: options.headers };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

// --------------------------------------------------------------- credentials

describe("what gets sent", () => {
  it("sends the workspace header when one is chosen", async () => {
    setToken("t0k3n");
    setBusinessId(42);
    const spy = mockFetch();

    await api("/platform/accounts");

    const { headers } = lastCall(spy);
    expect(headers["X-Business-Id"]).toBe("42");
    expect(headers.Authorization).toBe("Bearer t0k3n");
  });

  it("omits the headers entirely when signed out", async () => {
    const spy = mockFetch();

    await api("/auth/setup-status");

    const { headers } = lastCall(spy);
    expect(headers).not.toHaveProperty("Authorization");
    expect(headers).not.toHaveProperty("X-Business-Id");
  });

  it("never sends an empty bearer token", async () => {
    // `Authorization: Bearer ` reads as a malformed credential rather than as
    // no credential, and the backend is entitled to treat it differently.
    setToken("");
    const spy = mockFetch();

    await api("/health");

    expect(lastCall(spy).headers).not.toHaveProperty("Authorization");
  });

  it("lets a caller override a header", async () => {
    setToken("t0k3n");
    const spy = mockFetch();

    await api("/public/book/1", { headers: { Authorization: "" } });

    expect(lastCall(spy).headers.Authorization).toBe("");
  });

  it("keeps the caller's method and body", async () => {
    const spy = mockFetch();

    await api("/platform/contacts", {
      method: "POST",
      body: JSON.stringify({ name: "Acme" }),
    });

    const { options } = lastCall(spy);
    expect(options.method).toBe("POST");
    expect(JSON.parse(options.body)).toEqual({ name: "Acme" });
  });
});

// ------------------------------------------------------------------- storage

describe("remembering who you are", () => {
  it("keeps the token across a reload", () => {
    setToken("abc");
    expect(getToken()).toBe("abc");
  });

  it("clearing the token removes it rather than storing an empty string", () => {
    setToken("abc");
    setToken("");
    expect(localStorage.getItem("token")).toBeNull();
    expect(getToken()).toBe("");
  });

  it("stores the workspace id as a string", () => {
    setBusinessId(7);
    expect(getBusinessId()).toBe("7");
  });

  it("clearing the workspace removes it", () => {
    setBusinessId(7);
    setBusinessId(null);
    expect(getBusinessId()).toBe("");
  });
});

// ------------------------------------------------------------------ failures

describe("when the request fails", () => {
  it("throws the message the backend gave", async () => {
    mockFetch({ ok: false, status: 400, body: { detail: "Add at least one invoice line" } });

    await expect(api("/platform/invoices")).rejects.toThrow(
      "Add at least one invoice line",
    );
  });

  it("falls back to the status when there is no message", async () => {
    mockFetch({ ok: false, status: 502, body: null });

    await expect(api("/platform/accounts")).rejects.toThrow("502");
  });

  it("survives a response that is not JSON at all", async () => {
    // A proxy timeout or an HTML error page. Throwing "Unexpected token <"
    // here would replace a readable failure with a parser error.
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 504,
      json: async () => {
        throw new SyntaxError("Unexpected token <");
      },
    });

    await expect(api("/platform/accounts")).rejects.toThrow("504");
  });
});

// ------------------------------------------------------------------ the 401

describe("session expiry", () => {
  function listenForSignOut() {
    const seen = [];
    const handler = () => seen.push(true);
    window.addEventListener("scheduler:unauthorized", handler);
    return { seen, stop: () => window.removeEventListener("scheduler:unauthorized", handler) };
  }

  it("a 401 signs the user out", async () => {
    const listener = listenForSignOut();
    mockFetch({ ok: false, status: 401, body: { detail: "Sign in required" } });

    await expect(api("/platform/accounts")).rejects.toThrow();

    expect(listener.seen).toHaveLength(1);
    listener.stop();
  });

  it("a 401 from signing in does NOT sign the user out", async () => {
    // The one that matters. A wrong password is a 401, and treating it as an
    // expired session tears down the login attempt that is in progress.
    const listener = listenForSignOut();
    mockFetch({ ok: false, status: 401, body: { detail: "Incorrect username or password" } });

    await expect(api("/auth/login", { method: "POST" })).rejects.toThrow(
      "Incorrect username or password",
    );

    expect(listener.seen).toHaveLength(0);
    listener.stop();
  });

  it("other failures do not sign the user out", async () => {
    const listener = listenForSignOut();
    mockFetch({ ok: false, status: 403, body: { detail: "Admin access required" } });

    await expect(api("/admin/customers")).rejects.toThrow();

    expect(listener.seen).toHaveLength(0);
    listener.stop();
  });
});

// --------------------------------------------------------------------- paths

describe("where the request goes", () => {
  it("joins the path onto the API base", async () => {
    const spy = mockFetch();

    await api("/platform/accounts");

    expect(lastCall(spy).url).toMatch(/\/platform\/accounts$/);
  });

  it("does not double the slash", async () => {
    const spy = mockFetch();

    await api("/health");

    expect(lastCall(spy).url).not.toMatch(/\/\/health/);
  });
});
