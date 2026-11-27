/* Excel Auto — exécution d'une application générée à partir d'un classeur. */
"use strict";

(() => {
  const { h, fmt, plural, formatValue, download, api } = window.XA;
  const $ = (sel) => document.querySelector(sel);
  const params = new URLSearchParams(window.location.search);
  const projectId = params.get("id") || "";
  const base = `api/projects/${encodeURIComponent(projectId)}`;
  const PAGE = 50;

  let spec = null;
  let counts = {};
  const state = { entity: null, q: "", sort: null, desc: false, offset: 0 };

  const STATUS = {
    verified: ["ok", "Vérifiée", "Mêmes résultats qu'Excel sur toutes les lignes."],
    partial: ["warning", "Partielle", "Résultats différents d'Excel sur certaines lignes : à contrôler."],
    volatile: ["info", "Date du jour", "Dépend de la date du jour : non comparable avec le fichier."],
    unverified: ["info", "Non vérifiée", "Le fichier ne contenait pas les résultats calculés par Excel."],
    unsupported: ["critical", "Non convertie", "La colonne est devenue une saisie classique (valeurs conservées)."],
  };

  // ------------------------------------------------------------ formatage
  const money = new Intl.NumberFormat("fr-FR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const pct = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 2 });
  const isError = (v) => typeof v === "string" && /^#(REF!|N\/A|DIV\/0!|VALUE!|NAME\?|NUM!|NULL!|SPILL!|CALC!)$/.test(v);

  function display(value, field) {
    if (value === null || value === undefined || value === "") return "";
    if (isError(value)) return h("span", { class: "badge critical", text: value });
    if (typeof value === "number") {
      if (field.type === "currency") return money.format(value);
      if (field.type === "percent") return pct.format(value);
      return fmt(value);
    }
    if (field.type === "datetime" || field.type === "date") return formatValue(value);
    return formatValue(value);
  }

  const entitySpec = (name) => spec.entities.find((e) => e.name === name);
  const isComputed = (f) => f.rule && f.rule.status !== "unsupported";

  // ------------------------------------------------------------ navigation
  function route() {
    const hash = decodeURIComponent(window.location.hash.slice(1));
    const [view, arg] = hash.split("/").filter(Boolean);
    if (view === "parametres") return renderParameters();
    if (view === "regles") return renderRules();
    if (view === "historique") return renderHistory();
    const entity = view === "t" && entitySpec(arg) ? arg : spec.entities[0].name;
    if (state.entity !== entity) Object.assign(state, { entity, q: "", sort: null, desc: false, offset: 0 });
    return renderTable();
  }

  function renderNav() {
    const hash = decodeURIComponent(window.location.hash.slice(1)) || `t/${spec.entities[0].name}`;
    const link = (href, label, extra) => h("a", { href: `#${href}`, class: hash === href ? "active" : null,
      "aria-current": hash === href ? "page" : null }, h("span", { text: label }), extra || null);
    const rules = spec.generation.rules;
    const ruleTotal = Object.values(rules).reduce((a, b) => a + b, 0);
    $("#app-nav").replaceChildren(
      h("div", { class: "nav-title", text: "Tables" }),
      ...spec.entities.map((e) => link(`t/${e.name}`, e.label, h("span", { class: "count", text: fmt(counts[e.name]) }))),
      h("div", { class: "nav-title", text: "Application" }),
      spec.parameters.length ? link("parametres", "Paramètres", h("span", { class: "count", text: spec.parameters.length })) : null,
      link("regles", "Règles de calcul", ruleTotal ? h("span", { class: "count", text: ruleTotal }) : null),
      link("historique", "Historique"),
    );
  }

  function setMain(...children) {
    $("#app-main").replaceChildren(...children.filter(Boolean));
  }

  function errorBox(message) {
    return h("div", { class: "error-box", role: "alert" }, h("h2", { text: "Erreur" }), h("p", { text: message }));
  }

  // ------------------------------------------------------------ table
  async function renderTable() {
    renderNav();
    const es = entitySpec(state.entity);
    const query = new URLSearchParams({ q: state.q, offset: state.offset, limit: PAGE, desc: state.desc });
    if (state.sort) query.set("sort", state.sort);
    let data;
    try {
      data = await api(`${base}/entities/${es.name}/rows?${query}`);
    } catch (err) {
      setMain(errorBox(err.message));
      return;
    }
    counts[es.name] = state.q ? counts[es.name] : data.total;

    const search = h("input", { type: "search", class: "search", placeholder: "Rechercher…", value: state.q,
      "aria-label": `Rechercher dans ${es.label}` });
    let timer;
    search.addEventListener("input", () => {
      clearTimeout(timer);
      timer = setTimeout(() => { state.q = search.value; state.offset = 0; renderTable().then(() => focusSearch()); }, 250);
    });

    const head = h("tr", {}, es.fields.map((f) => {
      const sorted = state.sort === f.name;
      const btn = h("button", { type: "button", class: "th-sort", "data-sort": f.name,
        title: isComputed(f) ? `Calculé : ${f.rule.display || ""}` : null },
        f.label, isComputed(f) ? h("span", { class: "fx", "aria-label": "calculé", text: "ƒ" }) : null,
        sorted ? h("span", { "aria-hidden": "true", text: state.desc ? " ▼" : " ▲" }) : null);
      return h("th", { scope: "col", "aria-sort": sorted ? (state.desc ? "descending" : "ascending") : null }, btn);
    }));
    const numeric = new Set(["integer", "decimal", "currency", "percent"]);
    const body = h("tbody", {}, data.rows.map((row) =>
      h("tr", { tabindex: "0", "data-row": row._id, class: "clickable" }, es.fields.map((f) =>
        h("td", { class: numeric.has(f.type) ? "num" : null }, display(row[f.name], f))))));

    const from = data.total ? data.offset + 1 : 0;
    const to = data.offset + data.rows.length;
    setMain(
      h("div", { class: "view-head" },
        h("div", {},
          h("h1", { text: es.label }),
          h("div", { class: "meta", text: `${plural(data.total, "ligne", "lignes")}${state.q ? " trouvée(s)" : ""} · importé depuis ${es.source}` })),
        h("div", { class: "actions" },
          search,
          h("button", { type: "button", class: "btn btn-primary", "data-action": "add", text: "Ajouter" }))),
      data.rows.length
        ? h("div", { class: "table-wrap data-table" }, h("table", {}, h("thead", {}, head), body))
        : h("p", { class: "empty", text: state.q ? "Aucun résultat." : "Aucune ligne pour l'instant." }),
      data.total > PAGE ? h("div", { class: "pager" },
        h("button", { type: "button", class: "btn", "data-page": "prev", disabled: data.offset === 0, text: "Précédent" }),
        h("span", { class: "meta", text: `${fmt(from)}–${fmt(to)} sur ${fmt(data.total)}` }),
        h("button", { type: "button", class: "btn", "data-page": "next", disabled: to >= data.total, text: "Suivant" })) : null,
    );
  }

  function focusSearch() {
    const input = $(".search");
    if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
  }

  // ------------------------------------------------------------ formulaire
  async function referenceOptions(ref) {
    try {
      const data = await api(`${base}/entities/${ref.entity}/rows?limit=200&sort=${encodeURIComponent(ref.field)}`);
      return data.total <= 200 ? data.rows.map((r) => r[ref.field]).filter((v) => v !== null) : null;
    } catch {
      return null;
    }
  }

  function inputFor(f, value, options) {
    const id = `f-${f.name}`;
    const common = { id, name: f.name, "aria-describedby": `${id}-err` };
    if (f.type === "boolean") {
      return h("input", { ...common, type: "checkbox", checked: value === true });
    }
    const choices = options || f.choices;
    if (choices && (f.strict_choices || options)) {
      const select = h("select", common,
        h("option", { value: "", text: f.required ? "— Choisir —" : "(vide)" }),
        choices.map((c) => h("option", { value: String(c), text: String(c), selected: String(value ?? "") === String(c) })));
      if (value !== null && value !== undefined && value !== "" && !choices.map(String).includes(String(value))) {
        select.append(h("option", { value: String(value), text: `${value} (valeur actuelle)`, selected: true }));
      }
      return select;
    }
    if (f.type === "date") return h("input", { ...common, type: "date", value: value ? String(value).slice(0, 10) : "" });
    if (f.type === "datetime") return h("input", { ...common, type: "datetime-local", value: value ? String(value).slice(0, 16) : "" });
    if (["integer", "decimal", "currency", "percent"].includes(f.type)) {
      let shown = value;
      if (typeof value === "number" && f.type === "percent") shown = +(value * 100).toFixed(10);
      const input = h("input", { ...common, type: "text", inputmode: f.type === "integer" ? "numeric" : "decimal",
        value: shown === null || shown === undefined ? "" : String(shown).replace(".", ",") });
      return f.type === "percent" ? h("div", { class: "suffix" }, input, h("span", { text: "%" })) : input;
    }
    const input = h("input", { ...common, type: "text", value: value ?? "", maxlength: "10000" });
    if (f.choices && !f.strict_choices) {
      input.setAttribute("list", `${id}-list`);
      return h("div", {}, input, h("datalist", { id: `${id}-list` }, f.choices.map((c) => h("option", { value: String(c) }))));
    }
    return input;
  }

  function readValue(form, f) {
    const el = form.elements[f.name];
    if (!el) return undefined;
    if (f.type === "boolean") return el.checked;
    const v = el.value.trim();
    if (f.type === "percent" && v !== "") {
      const n = Number(v.replace(/\s/g, "").replace(",", "."));
      return Number.isFinite(n) ? n / 100 : v;
    }
    return v;
  }

  async function openForm(rowId) {
    const es = entitySpec(state.entity);
    const dialog = $("#row-dialog");
    let row = {};
    if (rowId) {
      try { row = await api(`${base}/entities/${es.name}/rows/${rowId}`); } catch (err) { setMain(errorBox(err.message)); return; }
    }
    const refOptions = {};
    await Promise.all(es.fields.filter((f) => f.references && !isComputed(f)).map(async (f) => {
      refOptions[f.name] = await referenceOptions(f.references);
    }));

    const fields = es.fields.map((f) => {
      if (isComputed(f)) {
        return h("div", { class: "field computed" },
          h("span", { class: "field-label" }, f.label, h("span", { class: "fx", text: "ƒ" })),
          h("div", { class: "computed-value" }, rowId ? (display(row[f.name], f) || "—") : "Calculé à l'enregistrement"),
          h("small", { class: "meta", text: `Calcul : ${f.rule.display}` }));
      }
      return h("div", { class: "field" },
        h("label", { for: `f-${f.name}`, class: "field-label" }, f.label, f.required ? h("span", { class: "req", "aria-label": "obligatoire", text: " *" }) : null),
        inputFor(f, row[f.name], refOptions[f.name]),
        h("small", { class: "field-error", id: `f-${f.name}-err`, role: "alert" }));
    });

    const del = rowId ? h("button", { type: "button", class: "btn btn-danger", "data-delete": "", text: "Supprimer" }) : null;
    const form = h("form", { class: "modal-body", novalidate: true },
      h("h2", { id: "row-dialog-title", text: rowId ? `Modifier — ${es.label}` : `Ajouter — ${es.label}` }),
      h("div", { class: "form-grid" }, fields),
      h("p", { class: "form-message", role: "alert" }),
      h("div", { class: "modal-actions" },
        del,
        h("span", { class: "spacer" }),
        h("button", { type: "button", class: "btn", "data-close": "", text: "Annuler" }),
        h("button", { type: "submit", class: "btn btn-primary", text: "Enregistrer" })),
    );
    dialog.replaceChildren(form);

    form.querySelector("[data-close]").addEventListener("click", () => dialog.close());
    if (del) {
      del.addEventListener("click", async () => {
        if (!del.dataset.confirm) {
          del.dataset.confirm = "1";
          del.textContent = "Confirmer la suppression";
          return;
        }
        try {
          await api(`${base}/entities/${es.name}/rows/${rowId}`, { method: "DELETE" });
          dialog.close();
          await refresh();
        } catch (err) {
          form.querySelector(".form-message").textContent = err.message;
          del.removeAttribute("data-confirm");
          del.textContent = "Supprimer";
        }
      });
    }
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      form.querySelectorAll(".field-error").forEach((el) => { el.textContent = ""; });
      form.querySelector(".form-message").textContent = "";
      const payload = {};
      for (const f of es.fields) if (!isComputed(f)) payload[f.name] = readValue(form, f);
      const submit = form.querySelector("[type=submit]");
      submit.disabled = true;
      try {
        if (rowId) await api(`${base}/entities/${es.name}/rows/${rowId}`, { method: "PATCH", json: payload });
        else await api(`${base}/entities/${es.name}/rows`, { method: "POST", json: payload });
        dialog.close();
        await refresh();
      } catch (err) {
        submit.disabled = false;
        if (err.errors) {
          for (const [name, msg] of Object.entries(err.errors)) {
            const slot = form.querySelector(`#f-${CSS.escape(name)}-err`);
            if (slot) slot.textContent = msg;
          }
          const first = form.querySelector(".field-error:not(:empty)");
          if (first) first.previousElementSibling?.focus?.();
          form.querySelector(".form-message").textContent = "Veuillez corriger les champs signalés.";
        } else {
          form.querySelector(".form-message").textContent = err.message;
        }
      }
    });
    dialog.showModal();
    const firstInput = form.querySelector("input, select");
    if (firstInput) firstInput.focus();
  }

  async function refresh() {
    const data = await api(base);
    counts = data.counts;
    await renderTable();
  }

  // ------------------------------------------------------------ paramètres
  async function renderParameters() {
    renderNav();
    let data;
    try { data = await api(`${base}/parameters`); } catch (err) { setMain(errorBox(err.message)); return; }
    setMain(
      h("div", { class: "view-head" }, h("div", {},
        h("h1", { text: "Paramètres" }),
        h("div", { class: "meta", text: "Valeurs utilisées par les calculs. Les modifier recalcule automatiquement toutes les lignes concernées." }))),
      data.items.length ? h("div", { class: "param-list" }, data.items.map((p) => {
        const input = h("input", { type: p.type === "date" ? "date" : "text", id: `p-${p.name}`,
          value: p.value === null ? "" : (p.type === "decimal" ? String(p.value).replace(".", ",") : String(p.value)),
          inputmode: p.type === "decimal" ? "decimal" : null });
        const msg = h("small", { class: "meta", role: "status" });
        const form = h("form", { class: "card param" },
          h("label", { for: `p-${p.name}`, class: "field-label", text: p.label }),
          h("div", { class: "param-row" }, input, h("button", { type: "submit", class: "btn btn-primary", text: "Enregistrer" })),
          h("small", { class: "meta", text: `Origine : ${p.source}` }), msg);
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          msg.textContent = "";
          try {
            const res = await api(`${base}/parameters/${encodeURIComponent(p.name)}`, { method: "PUT", json: { value: input.value } });
            msg.textContent = `Enregistré · ${plural(res.recomputed_rows, "ligne recalculée", "lignes recalculées")}.`;
          } catch (err) {
            msg.textContent = (err.errors && err.errors.value) || err.message;
          }
        });
        return form;
      })) : h("p", { class: "empty", text: "Aucun paramètre." }),
    );
  }

  // ------------------------------------------------------------ règles
  function renderRules() {
    renderNav();
    const g = spec.generation;
    const blocks = spec.entities.map((es) => {
      const computed = es.fields.filter((f) => f.rule);
      const anomalies = es.fields.filter((f) => f.anomalies);
      if (!computed.length && !anomalies.length) return null;
      return h("section", { class: "card" },
        h("h2", { text: es.label }),
        computed.map((f) => {
          const [cls, label, help] = STATUS[f.rule.status] || STATUS.unsupported;
          const v = f.rule.verification;
          return h("article", { class: "rule" },
            h("h3", {}, f.label, h("span", { class: `badge ${cls}`, title: help, text: label })),
            f.rule.display ? h("p", {}, h("span", { class: "meta", text: "Règle : " }), h("code", { text: f.rule.display })) : null,
            f.rule.excel ? h("p", {}, h("span", { class: "meta", text: `Formule Excel (ligne ${f.rule.excel_row}) : ` }), h("code", { text: f.rule.excel })) : null,
            v ? h("p", { class: "meta", text: `Vérification : ${fmt(v.matches)} / ${fmt(v.checked)} ligne(s) identique(s) à Excel.` }) : null,
            f.rule.reason ? h("p", { class: "meta", text: `Raison : ${f.rule.reason}` }) : null,
            v && v.examples.length && f.rule.status !== "volatile" ? h("div", { class: "table-wrap" }, h("table", {},
              h("thead", {}, h("tr", {}, ["Ligne Excel", "Valeur Excel", "Valeur calculée"].map((t) => h("th", { text: t })))),
              h("tbody", {}, v.examples.map((x) => h("tr", {},
                h("td", { text: x.row }), h("td", { text: formatValue(x.excel) }), h("td", { text: formatValue(x.app) })))))) : null,
          );
        }),
        anomalies.map((f) => h("article", { class: "rule" },
          h("h3", {}, f.label, h("span", { class: "badge warning", text: "Données à nettoyer" })),
          h("p", { class: "meta", text: `${plural(f.anomalies.count, "valeur ne respecte", "valeurs ne respectent")} pas le type « ${f.type} » : conservée(s) telle(s) quelle(s).` }),
          h("ul", { class: "chips" }, f.anomalies.examples.map((x) => h("li", { class: "chip", text: `ligne ${x.row} : ${formatValue(x.value)}` }))))),
      );
    });
    setMain(
      h("div", { class: "view-head" }, h("div", {},
        h("h1", { text: "Règles de calcul" }),
        h("div", { class: "meta", text: "Lors de la génération, chaque formule Excel a été traduite, recalculée sur toutes les lignes importées et comparée aux résultats d'Excel. Les calculs se font désormais automatiquement à chaque saisie." }))),
      h("div", { class: "kpis" }, Object.entries(g.rules).filter(([, n]) => n).map(([status, n]) =>
        h("div", { class: "kpi" }, h("div", { class: "kpi-value", text: fmt(n) }), h("div", { class: "kpi-label", text: STATUS[status][1] })))),
      g.warnings.length ? h("div", { class: "notice", role: "note" }, h("ul", {}, g.warnings.map((w) => h("li", { text: w })))) : null,
      ...blocks.filter(Boolean),
      blocks.some(Boolean) ? null : h("p", { class: "empty", text: "Ce classeur ne contient pas de colonne calculée." }),
    );
  }

  // ------------------------------------------------------------ historique
  async function renderHistory() {
    renderNav();
    let data;
    try { data = await api(`${base}/history?limit=100`); } catch (err) { setMain(errorBox(err.message)); return; }
    const label = (entity, field) => {
      const es = entity && entitySpec(entity);
      const f = es && es.fields.find((x) => x.name === field);
      if (f) return f.label;
      const p = spec.parameters.find((x) => x.name === field);
      return p ? p.label : field;
    };
    setMain(
      h("div", { class: "view-head" }, h("div", {},
        h("h1", { text: "Historique" }),
        h("div", { class: "meta", text: `${plural(data.total, "événement", "événements")} · qui a changé quoi, et quand` }))),
      h("ol", { class: "history" }, data.items.map((item) => h("li", {},
        h("div", { class: "history-head" },
          h("strong", { text: item.summary }),
          h("span", { class: "meta", text: new Date(item.ts).toLocaleString("fr-FR") })),
        Object.keys(item.changes).length ? h("ul", { class: "changes" }, Object.entries(item.changes).slice(0, 12).map(([field, [before, after]]) =>
          h("li", {}, h("span", { class: "meta", text: `${label(item.entity, field)} : ` }),
            before !== null ? h("del", { text: formatValue(before) }) : null,
            before !== null && after !== null ? " → " : null,
            after !== null ? h("ins", { text: formatValue(after) }) : null))) : null))),
    );
  }

  // ------------------------------------------------------------ démarrage
  async function init() {
    if (!projectId) {
      setMain(errorBox("Aucune application indiquée."));
      return;
    }
    try {
      const data = await api(base);
      spec = data.spec;
      counts = data.counts;
    } catch (err) {
      setMain(errorBox(err.status === 404 ? "Cette application n'existe pas ou a été supprimée." : err.message));
      return;
    }
    document.title = `${spec.title} — Excel Auto`;
    $("#app-title").textContent = spec.title;
    window.addEventListener("hashchange", route);

    document.addEventListener("click", async (e) => {
      const sortBtn = e.target.closest("[data-sort]");
      if (sortBtn) {
        const f = sortBtn.dataset.sort;
        if (state.sort === f) state.desc = !state.desc; else Object.assign(state, { sort: f, desc: false });
        state.offset = 0;
        return renderTable();
      }
      const page = e.target.closest("[data-page]");
      if (page) {
        state.offset = Math.max(0, state.offset + (page.dataset.page === "next" ? PAGE : -PAGE));
        return renderTable();
      }
      const row = e.target.closest("tr[data-row]");
      if (row) return openForm(Number(row.dataset.row));
      const action = e.target.closest("[data-action]");
      if (!action) return;
      if (action.dataset.action === "add") return openForm(null);
      if (action.dataset.action === "export") {
        try {
          const res = await api(`${base}/export.xlsx`, { raw: true });
          download(`${spec.title.replace(/[^\w-]+/g, "_")}.xlsx`, await res.blob());
        } catch (err) {
          setMain(errorBox(err.message));
        }
      }
    });
    document.addEventListener("keydown", (e) => {
      const row = e.target.closest && e.target.closest("tr[data-row]");
      if (row && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openForm(Number(row.dataset.row)); }
    });
    route();
  }

  document.addEventListener("DOMContentLoaded", init);
})();
