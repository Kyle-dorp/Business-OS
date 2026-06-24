(() => {
  "use strict";

  const VERSION = "0.2.0";
  const STORAGE_KEY = "business-os-vnext-state-v2";
  const SESSION_UNLOCK_KEY = "business-os-owner-unlocked";
  const DEFAULT_PIN_HASH = "9de45f0d87b959b2d3931e2f1af5ec09e39fe369308e00b42028c63c99b678d8";

  const FIELD_TYPES = [
    ["number", "Number"],
    ["text", "Short text"],
    ["textarea", "Notes"],
    ["currency", "Currency"],
    ["percentage", "Percentage"],
    ["time", "Time"],
    ["timeRange", "Time range"],
    ["date", "Date"],
    ["yesNo", "Yes / no"],
    ["checkbox", "Checkbox"],
    ["heading", "Heading"]
  ];

  const clone = (value) => JSON.parse(JSON.stringify(value));
  const uid = (prefix = "id") =>
    `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`;

  const escapeHTML = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  function defaultState() {
    return {
      version: VERSION,
      theme: {
        mode: "light",
        accent: "#2f6f61",
        radius: "soft"
      },
      ownerPin: {
        hash: DEFAULT_PIN_HASH,
        temporary: true
      },
      pages: {},
      history: [],
      audit: []
    };
  }

  function loadState() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY));
      if (!parsed || typeof parsed !== "object") return defaultState();
      const base = defaultState();
      return {
        ...base,
        ...parsed,
        theme: { ...base.theme, ...(parsed.theme || {}) },
        ownerPin: { ...base.ownerPin, ...(parsed.ownerPin || {}) },
        pages: parsed.pages && typeof parsed.pages === "object" ? parsed.pages : {},
        history: Array.isArray(parsed.history) ? parsed.history : [],
        audit: Array.isArray(parsed.audit) ? parsed.audit : []
      };
    } catch {
      return defaultState();
    }
  }

  let state = loadState();
  let activeTab = "quick";
  let drawerOpen = false;
  let currentKey = "";
  let renderQueued = false;
  let observerPause = false;

  function saveState(reason = "Saved") {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    toast(reason);
  }

  function snapshot(label) {
    state.history.unshift({
      id: uid("history"),
      at: new Date().toISOString(),
      label,
      pages: clone(state.pages),
      theme: clone(state.theme)
    });
    state.history = state.history.slice(0, 25);
  }

  function addAudit(action, scope, detail) {
    state.audit.unshift({
      id: uid("audit"),
      at: new Date().toISOString(),
      action,
      scope,
      detail
    });
    state.audit = state.audit.slice(0, 100);
  }

  function pageTitle() {
    const candidates = [
      document.querySelector("main h1"),
      document.querySelector("#content h1"),
      document.querySelector("[role='main'] h1"),
      document.querySelector("header h1"),
      document.querySelector("h1")
    ];
    const found = candidates.find((node) => node && node.textContent.trim());
    if (found) return found.textContent.trim();

    const activeNav = document.querySelector(
      ".nav-item.active, [aria-current='page'], nav .active"
    );
    if (activeNav && activeNav.textContent.trim()) return activeNav.textContent.trim();
    return document.title.replace(/\s+[—|-].*$/, "").trim() || "Current page";
  }

  function pageKey() {
    const route = `${location.pathname}${location.hash}`;
    return `${route}::${pageTitle().toLowerCase().replace(/\s+/g, "-")}`;
  }

  function ensurePage(key = pageKey()) {
    if (!state.pages[key]) {
      state.pages[key] = {
        key,
        title: pageTitle(),
        description: "Custom fields for this page",
        fields: [],
        values: {},
        chat: [
          {
            id: uid("msg"),
            role: "assistant",
            text:
              "Tell me what you want changed. I will show a preview with a clearly named approval button before anything is applied."
          }
        ],
        proposals: []
      };
    }
    return state.pages[key];
  }

  function applyTheme() {
    document.body.classList.add("bos-vnext");
    document.documentElement.style.setProperty("--bos-accent", state.theme.accent);
    document.documentElement.style.setProperty(
      "--bos-accent-soft",
      colorWithAlpha(state.theme.accent, 0.11)
    );
    if (state.theme.radius === "compact") {
      document.documentElement.style.setProperty("--bos-radius", "12px");
    } else if (state.theme.radius === "round") {
      document.documentElement.style.setProperty("--bos-radius", "25px");
    } else {
      document.documentElement.style.setProperty("--bos-radius", "18px");
    }
  }

  function colorWithAlpha(hex, alpha) {
    const value = String(hex).replace("#", "");
    if (!/^[0-9a-f]{6}$/i.test(value)) return "rgba(47,111,97,.11)";
    const n = parseInt(value, 16);
    const r = (n >> 16) & 255;
    const g = (n >> 8) & 255;
    const b = n & 255;
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function mainContainer() {
    return (
      document.querySelector("main") ||
      document.querySelector("#content") ||
      document.querySelector("[role='main']") ||
      document.querySelector(".content") ||
      document.body
    );
  }

  function inputValue(page, fieldId, suffix = "") {
    const dateKey = new Date().toISOString().slice(0, 10);
    return page.values?.[dateKey]?.[`${fieldId}${suffix}`] ?? "";
  }

  function setInputValue(page, fieldId, value, suffix = "") {
    const dateKey = new Date().toISOString().slice(0, 10);
    page.values ||= {};
    page.values[dateKey] ||= {};
    page.values[dateKey][`${fieldId}${suffix}`] = value;
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function renderField(page, field) {
    const label = escapeHTML(field.label || "Untitled field");
    const common = `data-bos-field="${escapeHTML(field.id)}"`;
    let control = "";

    switch (field.type) {
      case "textarea":
        control = `<textarea ${common} placeholder="${escapeHTML(field.placeholder || "")}">${escapeHTML(
          inputValue(page, field.id)
        )}</textarea>`;
        break;
      case "currency":
        control = `<input ${common} type="number" min="0" step="0.01" inputmode="decimal" value="${escapeHTML(
          inputValue(page, field.id)
        )}" placeholder="0.00">`;
        break;
      case "percentage":
        control = `<input ${common} type="number" min="0" step="0.1" inputmode="decimal" value="${escapeHTML(
          inputValue(page, field.id)
        )}" placeholder="0">`;
        break;
      case "time":
        control = `<input ${common} type="time" value="${escapeHTML(inputValue(page, field.id))}">`;
        break;
      case "timeRange":
        control = `
          <div class="bos-time-range">
            <input data-bos-field="${escapeHTML(field.id)}" data-bos-suffix="_start" type="time" value="${escapeHTML(
          inputValue(page, field.id, "_start")
        )}">
            <span>to</span>
            <input data-bos-field="${escapeHTML(field.id)}" data-bos-suffix="_end" type="time" value="${escapeHTML(
          inputValue(page, field.id, "_end")
        )}">
          </div>`;
        break;
      case "date":
        control = `<input ${common} type="date" value="${escapeHTML(inputValue(page, field.id))}">`;
        break;
      case "yesNo":
        control = `
          <select ${common}>
            <option value="">Choose…</option>
            <option value="yes" ${inputValue(page, field.id) === "yes" ? "selected" : ""}>Yes</option>
            <option value="no" ${inputValue(page, field.id) === "no" ? "selected" : ""}>No</option>
          </select>`;
        break;
      case "checkbox":
        control = `<label class="bos-row"><input ${common} type="checkbox" ${
          inputValue(page, field.id) === true ? "checked" : ""
        }> <span>${label}</span></label>`;
        break;
      case "heading":
        return `
          <div class="bos-custom-field bos-heading-field" data-width="${escapeHTML(
            field.width || "full"
          )}">
            <h3>${label}</h3>
            ${field.help ? `<p class="bos-help">${escapeHTML(field.help)}</p>` : ""}
          </div>`;
      case "text":
        control = `<input ${common} type="text" value="${escapeHTML(
          inputValue(page, field.id)
        )}" placeholder="${escapeHTML(field.placeholder || "")}">`;
        break;
      case "number":
      default:
        control = `<input ${common} type="number" min="${escapeHTML(
          field.min ?? 0
        )}" step="${escapeHTML(field.step ?? 1)}" inputmode="numeric" value="${escapeHTML(
          inputValue(page, field.id)
        )}" placeholder="0">`;
    }

    return `
      <div class="bos-custom-field" data-width="${escapeHTML(
        field.width || "full"
      )}" data-label-position="${escapeHTML(field.labelPosition || "top")}">
        ${
          field.type === "checkbox"
            ? control
            : `<label>${label}${field.required ? " *" : ""}</label>${control}`
        }
        ${field.help ? `<div class="bos-help">${escapeHTML(field.help)}</div>` : ""}
      </div>`;
  }

  function renderWorkspace() {
    const key = pageKey();
    currentKey = key;
    const page = ensurePage(key);
    let workspace = document.getElementById("bos-custom-workspace");

    if (!page.fields.length) {
      if (workspace) workspace.remove();
      return;
    }

    const host = mainContainer();
    if (!workspace) {
      workspace = document.createElement("section");
      workspace.id = "bos-custom-workspace";
      host.insertBefore(workspace, host.firstChild);
    }

    workspace.dataset.pageKey = key;
    workspace.innerHTML = `
      <div class="bos-workspace-head">
        <div>
          <h2>${escapeHTML(page.title)}</h2>
          <p>${escapeHTML(page.description || "Today’s custom business record")}</p>
        </div>
        <span class="bos-status">Custom layout</span>
      </div>
      <div class="bos-custom-grid">
        ${page.fields.map((field) => renderField(page, field)).join("")}
      </div>`;

    workspace.querySelectorAll("[data-bos-field]").forEach((input) => {
      const handler = () => {
        const id = input.dataset.bosField;
        const suffix = input.dataset.bosSuffix || "";
        const value = input.type === "checkbox" ? input.checked : input.value;
        setInputValue(page, id, value, suffix);
      };
      input.addEventListener("input", handler);
      input.addEventListener("change", handler);
    });
  }

  function ensureBaseUI() {
    if (!document.getElementById("bos-edit-page")) {
      const button = document.createElement("button");
      button.id = "bos-edit-page";
      button.type = "button";
      button.innerHTML = `
        <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M4 20h4l11-11a2.8 2.8 0 0 0-4-4L4 16v4Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
        </svg>
        Edit this page`;
      button.addEventListener("click", () => requireOwner(openDrawer));
      document.body.appendChild(button);
    }

    if (!document.getElementById("bos-toast-region")) {
      const region = document.createElement("div");
      region.id = "bos-toast-region";
      region.className = "bos-toast-region";
      region.setAttribute("aria-live", "polite");
      document.body.appendChild(region);
    }
  }

  function toast(message) {
    ensureBaseUI();
    const region = document.getElementById("bos-toast-region");
    const node = document.createElement("div");
    node.className = "bos-toast";
    node.textContent = message;
    region.appendChild(node);
    setTimeout(() => node.remove(), 3300);
  }

  async function sha256(value) {
    const data = new TextEncoder().encode(String(value));
    const digest = await crypto.subtle.digest("SHA-256", data);
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  }

  function isUnlocked() {
    return sessionStorage.getItem(SESSION_UNLOCK_KEY) === "yes";
  }

  function requireOwner(callback) {
    if (isUnlocked()) {
      callback();
      return;
    }

    openModal({
      title: "Owner approval",
      kicker: "Protected editing",
      body: `
        <div class="bos-stack">
          <p class="bos-help">Enter the owner PIN to customize layouts or approve a change.</p>
          ${
            state.ownerPin.temporary
              ? `<div class="bos-temp-pin"><strong>Temporary PIN is active.</strong><br>Change it from Advanced settings after setup.</div>`
              : ""
          }
          <form id="bos-pin-form" class="bos-stack">
            <div class="bos-field">
              <label for="bos-pin-input">Owner PIN</label>
              <input id="bos-pin-input" type="password" inputmode="numeric" autocomplete="current-password" maxlength="12" required autofocus>
            </div>
            <div id="bos-pin-error" class="bos-help" role="alert"></div>
            <button class="bos-button bos-button-primary" type="submit">Unlock editing</button>
          </form>
        </div>`
    });

    const form = document.getElementById("bos-pin-form");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const input = document.getElementById("bos-pin-input");
      const error = document.getElementById("bos-pin-error");
      const attempt = await sha256(input.value);
      if (attempt !== state.ownerPin.hash) {
        error.textContent = "That PIN was not accepted.";
        input.value = "";
        input.focus();
        return;
      }
      sessionStorage.setItem(SESSION_UNLOCK_KEY, "yes");
      closeModal();
      callback();
    });
  }

  function openModal({ title, kicker = "Business-OS", body }) {
    closeModal();
    const backdrop = document.createElement("div");
    backdrop.id = "bos-modal-backdrop";
    backdrop.className = "bos-modal-backdrop";
    backdrop.innerHTML = `
      <section class="bos-modal" role="dialog" aria-modal="true">
        <header class="bos-modal-header">
          <div>
            <div class="bos-kicker">${escapeHTML(kicker)}</div>
            <h2>${escapeHTML(title)}</h2>
          </div>
          <button class="bos-icon-button" type="button" data-bos-close-modal aria-label="Close">×</button>
        </header>
        <div class="bos-modal-body">${body}</div>
      </section>`;
    backdrop.addEventListener("click", (event) => {
      if (event.target === backdrop || event.target.closest("[data-bos-close-modal]")) {
        closeModal();
      }
    });
    document.body.appendChild(backdrop);
  }

  function closeModal() {
    document.getElementById("bos-modal-backdrop")?.remove();
  }

  function openDrawer() {
    closeDrawer();
    drawerOpen = true;
    currentKey = pageKey();
    ensurePage(currentKey);

    const backdrop = document.createElement("div");
    backdrop.id = "bos-drawer-backdrop";
    backdrop.className = "bos-drawer-backdrop";

    const drawer = document.createElement("aside");
    drawer.id = "bos-drawer";
    drawer.className = "bos-drawer";
    drawer.setAttribute("aria-label", "Edit current page");

    backdrop.addEventListener("click", closeDrawer);
    document.body.append(backdrop, drawer);
    renderDrawer();
  }

  function closeDrawer() {
    drawerOpen = false;
    document.getElementById("bos-drawer")?.remove();
    document.getElementById("bos-drawer-backdrop")?.remove();
  }

  function renderDrawer() {
    const drawer = document.getElementById("bos-drawer");
    if (!drawer) return;

    const page = ensurePage(currentKey);
    drawer.innerHTML = `
      <header class="bos-drawer-header">
        <div>
          <div class="bos-kicker">Editing ${escapeHTML(pageTitle())}</div>
          <h2>Make this page yours</h2>
        </div>
        <button class="bos-icon-button" type="button" data-bos-close-drawer aria-label="Close">×</button>
      </header>
      <nav class="bos-tabs" aria-label="Editing mode">
        <button class="bos-tab" data-bos-tab="quick" aria-selected="${
          activeTab === "quick"
        }">Quick changes</button>
        <button class="bos-tab" data-bos-tab="ai" aria-selected="${
          activeTab === "ai"
        }">Ask AI</button>
        <button class="bos-tab" data-bos-tab="advanced" aria-selected="${
          activeTab === "advanced"
        }">Advanced</button>
      </nav>
      <div class="bos-drawer-body">
        ${activeTab === "quick" ? renderQuick(page) : ""}
        ${activeTab === "ai" ? renderAI(page) : ""}
        ${activeTab === "advanced" ? renderAdvanced(page) : ""}
      </div>`;

    drawer.querySelector("[data-bos-close-drawer]")?.addEventListener("click", closeDrawer);
    drawer.querySelectorAll("[data-bos-tab]").forEach((button) => {
      button.addEventListener("click", () => {
        activeTab = button.dataset.bosTab;
        renderDrawer();
      });
    });

    if (activeTab === "quick") bindQuick(page);
    if (activeTab === "ai") bindAI(page);
    if (activeTab === "advanced") bindAdvanced(page);
  }

  function renderQuick(page) {
    return `
      <div class="bos-stack">
        ${
          state.ownerPin.temporary
            ? `<div class="bos-temp-pin"><strong>Temporary owner PIN is active.</strong><br>Daily users will not see these controls unless they unlock editing.</div>`
            : ""
        }

        <section class="bos-section">
          <div class="bos-row bos-between">
            <div>
              <h3>Page fields</h3>
              <p>Add only what this business needs. Daily users see the finished layout, not the builder.</p>
            </div>
            <button class="bos-button bos-button-primary bos-button-small" data-bos-add-field>+ Add field</button>
          </div>
          <div class="bos-field-list" style="margin-top:12px">
            ${
              page.fields.length
                ? page.fields
                    .map(
                      (field, index) => `
                <div class="bos-field-item" data-field-id="${escapeHTML(field.id)}">
                  <div>
                    <strong>${escapeHTML(field.label)}</strong>
                    <small>${escapeHTML(field.type)} · ${escapeHTML(
                        field.width === "half" ? "half width" : "full width"
                      )}</small>
                  </div>
                  <div class="bos-row">
                    <button class="bos-button bos-button-small" data-field-action="up" ${
                      index === 0 ? "disabled" : ""
                    }>↑</button>
                    <button class="bos-button bos-button-small" data-field-action="down" ${
                      index === page.fields.length - 1 ? "disabled" : ""
                    }>↓</button>
                    <button class="bos-button bos-button-small" data-field-action="edit">Edit</button>
                    <button class="bos-button bos-button-small bos-button-danger" data-field-action="delete">×</button>
                  </div>
                </div>`
                    )
                    .join("")
                : `<div class="bos-help">No custom fields yet. Add one here or describe the layout in Ask AI.</div>`
            }
          </div>
        </section>

        <section class="bos-section">
          <h3>Theme</h3>
          <p>One calm visual system across every page.</p>
          <div class="bos-stack" style="margin-top:12px">
            <div class="bos-field">
              <label>Accent color</label>
              <input id="bos-accent" type="color" value="${escapeHTML(state.theme.accent)}">
            </div>
            <div class="bos-field">
              <label>Card shape</label>
              <select id="bos-radius">
                <option value="compact" ${
                  state.theme.radius === "compact" ? "selected" : ""
                }>Compact</option>
                <option value="soft" ${state.theme.radius === "soft" ? "selected" : ""}>Soft</option>
                <option value="round" ${state.theme.radius === "round" ? "selected" : ""}>Extra round</option>
              </select>
            </div>
            <button class="bos-button" data-bos-save-theme>Save theme</button>
          </div>
        </section>
      </div>`;
  }

  function bindQuick(page) {
    document.querySelector("[data-bos-add-field]")?.addEventListener("click", () =>
      openFieldEditor(page)
    );

    document.querySelectorAll("[data-field-id]").forEach((row) => {
      row.querySelectorAll("[data-field-action]").forEach((button) => {
        button.addEventListener("click", () => {
          const id = row.dataset.fieldId;
          const index = page.fields.findIndex((field) => field.id === id);
          if (index < 0) return;
          const action = button.dataset.fieldAction;

          if (action === "edit") return openFieldEditor(page, page.fields[index]);
          if (action === "delete") {
            snapshot(`Before deleting ${page.fields[index].label}`);
            page.fields.splice(index, 1);
            addAudit("delete", page.title, id);
            saveState("Field removed");
          }
          if (action === "up" && index > 0) {
            snapshot("Before moving a field");
            [page.fields[index - 1], page.fields[index]] = [
              page.fields[index],
              page.fields[index - 1]
            ];
            saveState("Field moved");
          }
          if (action === "down" && index < page.fields.length - 1) {
            snapshot("Before moving a field");
            [page.fields[index + 1], page.fields[index]] = [
              page.fields[index],
              page.fields[index + 1]
            ];
            saveState("Field moved");
          }
          renderWorkspace();
          renderDrawer();
        });
      });
    });

    document.querySelector("[data-bos-save-theme]")?.addEventListener("click", () => {
      snapshot("Before theme update");
      state.theme.accent = document.getElementById("bos-accent").value;
      state.theme.radius = document.getElementById("bos-radius").value;
      applyTheme();
      addAudit("theme_update", "global", clone(state.theme));
      saveState("Theme updated");
    });
  }

  function openFieldEditor(page, existing = null) {
    const field = existing || {
      id: uid("field"),
      label: "",
      type: "number",
      width: "full",
      labelPosition: "top",
      required: false,
      help: "",
      placeholder: ""
    };

    openModal({
      title: existing ? "Edit field" : "Add field",
      kicker: page.title,
      body: `
        <form id="bos-field-form" class="bos-stack">
          <div class="bos-field">
            <label>Question or label</label>
            <input name="label" required value="${escapeHTML(field.label)}" placeholder="Example: Soups sold today">
          </div>
          <div class="bos-row">
            <div class="bos-field bos-grow">
              <label>Answer type</label>
              <select name="type">
                ${FIELD_TYPES.map(
                  ([value, label]) =>
                    `<option value="${value}" ${field.type === value ? "selected" : ""}>${label}</option>`
                ).join("")}
              </select>
            </div>
            <div class="bos-field bos-grow">
              <label>Width</label>
              <select name="width">
                <option value="full" ${field.width === "full" ? "selected" : ""}>Full row</option>
                <option value="half" ${field.width === "half" ? "selected" : ""}>Half row</option>
              </select>
            </div>
          </div>
          <div class="bos-field">
            <label>Label placement</label>
            <select name="labelPosition">
              <option value="top" ${
                field.labelPosition === "top" ? "selected" : ""
              }>Question above answer</option>
              <option value="inline" ${
                field.labelPosition === "inline" ? "selected" : ""
              }>Question beside answer</option>
            </select>
          </div>
          <div class="bos-field">
            <label>Small instruction (optional)</label>
            <input name="help" value="${escapeHTML(field.help || "")}" placeholder="Example: Count only completed orders">
          </div>
          <label class="bos-row">
            <input name="required" type="checkbox" ${field.required ? "checked" : ""}>
            <span>Require an answer</span>
          </label>
          <button class="bos-button bos-button-primary" type="submit">${
            existing ? "Save field" : "Add field"
          }</button>
        </form>`
    });

    document.getElementById("bos-field-form").addEventListener("submit", (event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const updated = {
        ...field,
        label: String(data.get("label") || "").trim(),
        type: String(data.get("type") || "number"),
        width: String(data.get("width") || "full"),
        labelPosition: String(data.get("labelPosition") || "top"),
        help: String(data.get("help") || "").trim(),
        required: data.get("required") === "on"
      };

      snapshot(existing ? `Before editing ${existing.label}` : `Before adding ${updated.label}`);
      if (existing) Object.assign(existing, updated);
      else page.fields.push(updated);

      addAudit(existing ? "field_update" : "field_add", page.title, clone(updated));
      saveState(existing ? "Field updated" : "Field added");
      closeModal();
      renderWorkspace();
      renderDrawer();
    });
  }

  function renderAI(page) {
    return `
      <div class="bos-chat">
        <div class="bos-messages" id="bos-messages">
          ${page.chat
            .map(
              (message) => `
            <div class="bos-message bos-message-${escapeHTML(message.role)}">${escapeHTML(
                message.text
              )}</div>`
            )
            .join("")}
          ${page.proposals
            .filter((proposal) => proposal.status === "pending")
            .map((proposal) => renderProposal(proposal))
            .join("")}
        </div>
        <form class="bos-chat-form" id="bos-chat-form">
          <textarea id="bos-chat-input" placeholder="Example: Put soups and French dips beside each other with the numbers underneath." required></textarea>
          <button class="bos-button bos-button-primary" type="submit">Send</button>
        </form>
      </div>`;
  }

  function renderProposal(proposal) {
    return `
      <article class="bos-proposal" data-proposal-id="${escapeHTML(proposal.id)}">
        <div class="bos-proposal-head">
          <strong>${escapeHTML(proposal.title)}</strong>
          <small>Nothing changes until you approve.</small>
        </div>
        <div class="bos-proposal-body">
          <div class="bos-proposal-change"><span>Type</span><strong>${escapeHTML(
            proposal.typeLabel
          )}</strong></div>
          <div class="bos-proposal-change"><span>Where</span><strong>${escapeHTML(
            proposal.scopeLabel
          )}</strong></div>
          <div class="bos-proposal-change"><span>Change</span><strong>${escapeHTML(
            proposal.summary
          )}</strong></div>
          <div class="bos-proposal-change"><span>Data affected</span><strong>${escapeHTML(
            proposal.dataImpact
          )}</strong></div>
        </div>
        <div class="bos-proposal-actions">
          <button class="bos-button bos-button-primary" data-proposal-action="approve">${escapeHTML(
            proposal.approvalLabel
          )}</button>
          <button class="bos-button" data-proposal-action="revise">Keep editing</button>
          <button class="bos-button bos-button-danger" data-proposal-action="cancel">Cancel</button>
        </div>
      </article>`;
  }

  function bindAI(page) {
    const messages = document.getElementById("bos-messages");
    if (messages) messages.scrollTop = messages.scrollHeight;

    document.getElementById("bos-chat-form")?.addEventListener("submit", (event) => {
      event.preventDefault();
      const input = document.getElementById("bos-chat-input");
      const text = input.value.trim();
      if (!text) return;

      page.chat.push({ id: uid("msg"), role: "user", text });
      const proposal = createProposal(page, text);
      page.chat.push({
        id: uid("msg"),
        role: "assistant",
        text: proposal.lead
      });
      page.proposals.push(proposal);
      input.value = "";
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
      renderDrawer();
    });

    document.querySelectorAll("[data-proposal-id]").forEach((card) => {
      card.querySelectorAll("[data-proposal-action]").forEach((button) => {
        button.addEventListener("click", () => {
          const proposal = page.proposals.find((item) => item.id === card.dataset.proposalId);
          if (!proposal) return;
          const action = button.dataset.proposalAction;

          if (action === "cancel") {
            proposal.status = "cancelled";
            page.chat.push({
              id: uid("msg"),
              role: "assistant",
              text: "Cancelled. No changes were made."
            });
            saveState("Proposal cancelled");
            renderDrawer();
            return;
          }

          if (action === "revise") {
            document.getElementById("bos-chat-input").value =
              `Adjust this proposal: ${proposal.summary}. `;
            document.getElementById("bos-chat-input").focus();
            return;
          }

          if (action === "approve") {
            requireOwner(() => approveProposal(page, proposal));
          }
        });
      });
    });
  }

  function createProposal(page, text) {
    const lower = text.toLowerCase();
    const isClosing = /clos(e|ing)|daily report|closing chart/.test(
      `${page.title} ${lower}`.toLowerCase()
    );
    const isSchedule = /schedule|shift|employee hours/.test(lower);
    const isInventory = /inventory|stock|on hand|target stock/.test(lower);
    const isTheme = /theme|color|dark|light|round|easier on the eyes/.test(lower);
    const sideBySide = /beside|side by side|next to|same row|two columns/.test(lower);
    const soupExample = /soup/.test(lower) && /french dip/.test(lower);

    if (isSchedule || isInventory) {
      const label = isSchedule ? "schedule edit" : "inventory edit";
      return {
        id: uid("proposal"),
        status: "pending",
        kind: isSchedule ? "schedule_data" : "inventory_data",
        title: `Proposed ${label}`,
        typeLabel: "Business data",
        scopeLabel: isSchedule ? "Schedule" : "Inventory",
        summary: text,
        dataImpact: "Specific records must be confirmed by the connected Business-OS backend.",
        approvalLabel: isSchedule ? "Approve schedule edit" : "Approve inventory edit",
        lead:
          "I identified this as a real business-data change. Review the scope below before approving.",
        payload: { text }
      };
    }

    if (isTheme) {
      const accent = lower.includes("blue")
        ? "#315f8a"
        : lower.includes("purple")
        ? "#66548a"
        : lower.includes("orange")
        ? "#a76028"
        : lower.includes("red")
        ? "#934a43"
        : "#2f6f61";

      return {
        id: uid("proposal"),
        status: "pending",
        kind: "theme_update",
        title: "Proposed visual theme",
        typeLabel: "Appearance",
        scopeLabel: "Every page",
        summary: "Use a calmer background, softer cards, consistent spacing, and the selected accent.",
        dataImpact: "Appearance only. Business records do not change.",
        approvalLabel: "Approve business theme",
        lead: "I prepared a visual-only theme update. Your business data will not be touched.",
        payload: { accent, radius: "soft" }
      };
    }

    if (soupExample) {
      return {
        id: uid("proposal"),
        status: "pending",
        kind: "layout_update",
        title: "Proposed closing-chart layout",
        typeLabel: "Layout",
        scopeLabel: page.title,
        summary:
          "Place “Soups for the day” and “French dips for the day” in one two-column row, with labels above number fields.",
        dataImpact: "Layout only. Existing saved answers remain unchanged.",
        approvalLabel: isClosing
          ? "Approve closing chart layout"
          : `Approve ${page.title.toLowerCase()} layout`,
        lead:
          "I understood the layout: two equal fields beside each other, with each answer directly below its label.",
        payload: {
          ensureFields: [
            {
              label: "Soups for the day",
              type: "number",
              width: "half",
              labelPosition: "top"
            },
            {
              label: "French dips for the day",
              type: "number",
              width: "half",
              labelPosition: "top"
            }
          ]
        }
      };
    }

    if (sideBySide) {
      const firstTwo = page.fields.slice(0, 2).map((field) => field.id);
      return {
        id: uid("proposal"),
        status: "pending",
        kind: "layout_update",
        title: "Proposed page layout",
        typeLabel: "Layout",
        scopeLabel: page.title,
        summary:
          firstTwo.length === 2
            ? "Place the first two fields beside each other and put their answers below their labels."
            : "Create a two-column row. Add fields first if this page does not already have two.",
        dataImpact: "Layout only. Existing saved answers remain unchanged.",
        approvalLabel: isClosing
          ? "Approve closing chart layout"
          : `Approve ${page.title.toLowerCase()} layout`,
        lead: "I prepared a layout-only proposal so no saved business data is at risk.",
        payload: { makeHalf: firstTwo }
      };
    }

    const quoted = [...text.matchAll(/["“]([^"”]+)["”]/g)].map((match) => match[1]);
    const label =
      quoted[0] ||
      text
        .replace(/^(please\s+)?(add|create|make)\s+(a\s+)?/i, "")
        .replace(/\b(field|question|box)\b/gi, "")
        .trim()
        .slice(0, 80) ||
      "New field";

    const type = /time.*range|from.*to/.test(lower)
      ? "timeRange"
      : /note|comment|explain/.test(lower)
      ? "textarea"
      : /yes.?no/.test(lower)
      ? "yesNo"
      : /money|cost|price|sales|\$/.test(lower)
      ? "currency"
      : /time/.test(lower)
      ? "time"
      : /number|count|sold|quantity|how many/.test(lower)
      ? "number"
      : "text";

    return {
      id: uid("proposal"),
      status: "pending",
      kind: "layout_update",
      title: "Proposed page field",
      typeLabel: "Layout",
      scopeLabel: page.title,
      summary: `Add “${label}” as a ${FIELD_TYPES.find(([value]) => value === type)?.[1] || type} field.`,
      dataImpact: "Layout only. Existing saved answers remain unchanged.",
      approvalLabel: isClosing
        ? "Approve closing chart layout"
        : `Approve ${page.title.toLowerCase()} layout`,
      lead: "I converted your request into a safe page-layout proposal.",
      payload: {
        ensureFields: [
          {
            label,
            type,
            width: /half|beside|two column/.test(lower) ? "half" : "full",
            labelPosition: /answer.*below|under/.test(lower) ? "top" : "top"
          }
        ]
      }
    };
  }

  async function approveProposal(page, proposal) {
    snapshot(`Before ${proposal.approvalLabel}`);

    if (proposal.kind === "layout_update") {
      const payload = proposal.payload || {};

      (payload.ensureFields || []).forEach((incoming) => {
        const existing = page.fields.find(
          (field) => field.label.toLowerCase() === incoming.label.toLowerCase()
        );
        if (existing) {
          Object.assign(existing, incoming);
        } else {
          page.fields.push({
            id: uid("field"),
            required: false,
            help: "",
            placeholder: "",
            ...incoming
          });
        }
      });

      (payload.makeHalf || []).forEach((id) => {
        const field = page.fields.find((item) => item.id === id);
        if (field) {
          field.width = "half";
          field.labelPosition = "top";
        }
      });

      proposal.status = "approved";
      page.chat.push({
        id: uid("msg"),
        role: "assistant",
        text: "Approved and applied. The updated layout is now visible on this page."
      });
      addAudit("layout_approved", page.title, clone(proposal));
      saveState("Layout approved");
      renderWorkspace();
      renderDrawer();
      return;
    }

    if (proposal.kind === "theme_update") {
      state.theme = { ...state.theme, ...proposal.payload };
      proposal.status = "approved";
      page.chat.push({
        id: uid("msg"),
        role: "assistant",
        text: "Approved and applied. The new theme is active across Business-OS."
      });
      addAudit("theme_approved", "global", clone(proposal));
      applyTheme();
      saveState("Theme approved");
      renderDrawer();
      return;
    }

    const host = window.BusinessOSHost;
    if (host && typeof host.applyApprovedAction === "function") {
      await host.applyApprovedAction(clone(proposal));
      proposal.status = "approved";
      page.chat.push({
        id: uid("msg"),
        role: "assistant",
        text: "Approved and sent to the connected Business-OS data service."
      });
      addAudit("data_approved", proposal.scopeLabel, clone(proposal));
      saveState("Data edit approved");
      renderDrawer();
      return;
    }

    proposal.status = "awaiting_integration";
    page.chat.push({
      id: uid("msg"),
      role: "assistant",
      text:
        "Your approval was recorded, but this frontend upgrade is not connected to the current data-writing service yet, so no schedule or inventory record was changed."
    });
    addAudit("data_approval_unhandled", proposal.scopeLabel, clone(proposal));
    saveState("Approval recorded; no data changed");
    renderDrawer();
  }

  function renderAdvanced(page) {
    const history = state.history.slice(0, 8);
    return `
      <div class="bos-stack">
        <section class="bos-section">
          <h3>Advanced layout JSON</h3>
          <p>For technical setup only. Daily users never need this screen.</p>
          <textarea id="bos-json-editor" class="bos-json-editor">${escapeHTML(
            JSON.stringify(
              {
                title: page.title,
                description: page.description,
                fields: page.fields
              },
              null,
              2
            )
          )}</textarea>
          <div class="bos-row" style="margin-top:10px">
            <button class="bos-button bos-button-primary" data-bos-save-json>Validate and save</button>
          </div>
        </section>

        <section class="bos-section">
          <h3>Owner PIN</h3>
          <p>The temporary setup PIN can be replaced without exposing it in logs or the page.</p>
          <form id="bos-change-pin" class="bos-stack" style="margin-top:12px">
            <div class="bos-field">
              <label>New PIN</label>
              <input name="pin" type="password" inputmode="numeric" minlength="4" maxlength="12" required>
            </div>
            <div class="bos-field">
              <label>Confirm new PIN</label>
              <input name="confirm" type="password" inputmode="numeric" minlength="4" maxlength="12" required>
            </div>
            <button class="bos-button" type="submit">Change owner PIN</button>
          </form>
        </section>

        <section class="bos-section">
          <h3>Version history</h3>
          <p>Restore a previous layout or theme after an unwanted edit.</p>
          <div class="bos-field-list" style="margin-top:12px">
            ${
              history.length
                ? history
                    .map(
                      (item) => `
                <div class="bos-field-item" data-history-id="${escapeHTML(item.id)}">
                  <div>
                    <strong>${escapeHTML(item.label)}</strong>
                    <small>${escapeHTML(new Date(item.at).toLocaleString())}</small>
                  </div>
                  <button class="bos-button bos-button-small" data-restore-history>Restore</button>
                </div>`
                    )
                    .join("")
                : `<div class="bos-help">No layout changes have been saved yet.</div>`
            }
          </div>
        </section>
      </div>`;
  }

  function bindAdvanced(page) {
    document.querySelector("[data-bos-save-json]")?.addEventListener("click", () => {
      try {
        const parsed = JSON.parse(document.getElementById("bos-json-editor").value);
        if (!Array.isArray(parsed.fields)) throw new Error("fields must be an array");
        parsed.fields.forEach((field, index) => {
          if (!field || typeof field !== "object") throw new Error(`Field ${index + 1} is invalid`);
          if (!field.label || !field.type) throw new Error(`Field ${index + 1} needs label and type`);
          field.id ||= uid("field");
          field.width ||= "full";
          field.labelPosition ||= "top";
        });

        snapshot("Before advanced layout save");
        page.title = String(parsed.title || page.title);
        page.description = String(parsed.description || page.description);
        page.fields = parsed.fields;
        addAudit("advanced_layout_update", page.title, { fieldCount: page.fields.length });
        saveState("Advanced layout saved");
        renderWorkspace();
        renderDrawer();
      } catch (error) {
        toast(`Could not save: ${error.message}`);
      }
    });

    document.getElementById("bos-change-pin")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = new FormData(event.currentTarget);
      const pin = String(data.get("pin") || "");
      const confirm = String(data.get("confirm") || "");
      if (!/^\d{4,12}$/.test(pin)) {
        toast("Use a 4–12 digit PIN.");
        return;
      }
      if (pin !== confirm) {
        toast("The two PIN entries do not match.");
        return;
      }
      state.ownerPin.hash = await sha256(pin);
      state.ownerPin.temporary = false;
      sessionStorage.setItem(SESSION_UNLOCK_KEY, "yes");
      addAudit("owner_pin_changed", "security", "PIN hash updated");
      saveState("Owner PIN changed");
      renderDrawer();
    });

    document.querySelectorAll("[data-history-id]").forEach((row) => {
      row.querySelector("[data-restore-history]")?.addEventListener("click", () => {
        const item = state.history.find((entry) => entry.id === row.dataset.historyId);
        if (!item) return;
        snapshot("Before restoring history");
        state.pages = clone(item.pages);
        state.theme = clone(item.theme);
        addAudit("history_restore", "global", item.label);
        saveState("Previous version restored");
        applyTheme();
        currentKey = pageKey();
        renderWorkspace();
        renderDrawer();
      });
    });
  }

  function scheduleRender() {
    if (observerPause || renderQueued) return;
    renderQueued = true;
    requestAnimationFrame(() => {
      renderQueued = false;
      const nextKey = pageKey();
      if (nextKey !== currentKey) {
        currentKey = nextKey;
        ensurePage(nextKey);
        renderWorkspace();
        if (drawerOpen) renderDrawer();
      }
    });
  }

  function boot() {
    applyTheme();
    ensureBaseUI();
    currentKey = pageKey();
    ensurePage(currentKey);
    renderWorkspace();

    const observer = new MutationObserver(scheduleRender);
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true
    });

    window.addEventListener("popstate", scheduleRender);
    window.addEventListener("hashchange", scheduleRender);

    window.BusinessOSVNext = {
      version: VERSION,
      openEditor: () => requireOwner(openDrawer),
      getState: () => clone(state),
      propose: (text) => {
        const page = ensurePage(pageKey());
        const proposal = createProposal(page, String(text || ""));
        page.proposals.push(proposal);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        return clone(proposal);
      }
    };
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
