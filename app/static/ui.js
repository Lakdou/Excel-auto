/* Excel Auto — fonctions communes aux pages (aucune injection HTML : tout passe par textContent). */
"use strict";

(() => {
  /** Crée un élément DOM. attrs : class, text, data-*, aria-*… ; enfants : nœuds ou chaînes. */
  function h(tag, attrs, ...children) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = String(v);
      else el.setAttribute(k, v === true ? "" : String(v));
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      el.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return el;
  }

  const nf = new Intl.NumberFormat("fr-FR", { maximumFractionDigits: 6 });
  const fmt = (n) => (n === null || n === undefined ? "—" : nf.format(n));
  const plural = (n, one, many) => `${fmt(n)} ${n > 1 ? many : one}`;

  /** '2019-01-10T00:00:00' -> '10/01/2019' ; '2019-01-10T14:30:00' -> '10/01/2019 14:30'. */
  function formatValue(v) {
    if (v === null || v === undefined) return "";
    if (typeof v === "number") return fmt(v);
    if (typeof v === "boolean") return v ? "Oui" : "Non";
    const m = typeof v === "string" && /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2})(?::\d{2}(?:\.\d+)?)?)?$/.exec(v);
    if (!m) return String(v);
    const date = `${m[3]}/${m[2]}/${m[1]}`;
    return m[4] && `${m[4]}:${m[5]}` !== "00:00" ? `${date} ${m[4]}:${m[5]}` : date;
  }

  function fileSize(bytes) {
    if (bytes < 1024) return `${bytes} o`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1).replace(".", ",")} Ko`;
    return `${(bytes / 1024 / 1024).toFixed(1).replace(".", ",")} Mo`;
  }

  function download(filename, content, type) {
    const url = URL.createObjectURL(content instanceof Blob ? content : new Blob([content], { type }));
    const a = h("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ------------------------------------------------------- code d'accès
  const CODE_KEY = "excel-auto-access-code";
  const readCode = () => { try { return sessionStorage.getItem(CODE_KEY) || ""; } catch { return ""; } };
  const saveCode = (c) => { try { sessionStorage.setItem(CODE_KEY, c); } catch { /* stockage indisponible */ } };

  function askAccessCode() {
    return new Promise((resolve) => {
      const input = h("input", { type: "password", id: "access-code", autocomplete: "current-password", required: true });
      const dialog = h("dialog", { class: "modal", "aria-labelledby": "access-title" },
        h("form", { method: "dialog", class: "modal-body" },
          h("h2", { id: "access-title", text: "Code d'accès" }),
          h("p", { class: "card-sub", text: "Les applications contiennent des données : saisissez le code d'accès communiqué par votre administrateur." }),
          h("label", { class: "field" }, h("span", { text: "Code" }), input),
          h("div", { class: "modal-actions" },
            h("button", { type: "button", class: "btn", value: "cancel", "data-close": "" , text: "Annuler" }),
            h("button", { type: "submit", class: "btn btn-primary", value: "ok", text: "Valider" }),
          ),
        ),
      );
      dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close("cancel"));
      dialog.addEventListener("close", () => {
        const ok = dialog.returnValue === "ok" && input.value;
        if (ok) saveCode(input.value);
        dialog.remove();
        resolve(Boolean(ok));
      });
      document.body.append(dialog);
      dialog.showModal();
      input.focus();
    });
  }

  /** Appel à l'API (JSON ou FormData). Demande le code d'accès si nécessaire. Lève une ApiError. */
  class ApiError extends Error {
    constructor(status, detail, errors) {
      super(detail || `Erreur ${status}`);
      this.status = status;
      this.errors = errors || null;
    }
  }

  async function api(path, { method = "GET", json, body, raw = false } = {}, retried = false) {
    const headers = {};
    const code = readCode();
    if (code) headers["X-Access-Code"] = code;
    if (json !== undefined) {
      headers["Content-Type"] = "application/json";
      body = JSON.stringify(json);
    }
    let res;
    try {
      res = await fetch(path, { method, headers, body });
    } catch {
      throw new ApiError(0, "Impossible de contacter le serveur. Vérifiez votre connexion et réessayez.");
    }
    if (res.status === 401 && !retried) {
      if (await askAccessCode()) return api(path, { method, json, body: json !== undefined ? undefined : body, raw }, true);
    }
    if (!res.ok) {
      const payload = await res.json().catch(() => null);
      const detail = payload && (typeof payload.detail === "string" ? payload.detail : null);
      throw new ApiError(res.status, detail || `Erreur du serveur (${res.status}).`, payload && payload.errors);
    }
    if (raw) return res;
    if (res.status === 204) return null;
    return res.json();
  }

  window.XA = { h, fmt, plural, formatValue, fileSize, download, api, ApiError };
})();
