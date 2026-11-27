/* Excel Auto — interface du diagnostic.
 * Aucun HTML n'est injecté depuis les données : tout passe par textContent (protection XSS).
 */
"use strict";

(() => {
  const $ = (sel) => document.querySelector(sel);
  const views = ["upload-view", "loading-view", "error-view", "report-view"];
  let maxUploadMb = 50;
  let lastReport = null;

  const SEVERITY = { critical: "Critique", warning: "Attention", info: "Info" };
  const STATE = { visible: "Visible", hidden: "Masquée", veryHidden: "Super-masquée" };
  const VALIDATION = {
    list: "Liste", whole: "Nombre entier", decimal: "Nombre décimal", date: "Date", time: "Heure",
    textLength: "Longueur de texte", custom: "Formule personnalisée", any: "Aucune",
  };

  /** Crée un élément DOM. attrs : class, text, title, data-*, aria-*… enfants : nœuds ou chaînes. */
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

  const nf = new Intl.NumberFormat("fr-FR");
  const fmt = (n) => (n === null || n === undefined ? "—" : nf.format(n));
  const plural = (n, one, many) => `${fmt(n)} ${n > 1 ? many : one}`;

  /** '2019-01-10T00:00:00' -> '10/01/2019' ; '2019-01-10T14:30:00' -> '10/01/2019 14:30'. */
  function formatValue(v) {
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

  function show(id) {
    for (const v of views) $("#" + v).hidden = v !== id;
    window.scrollTo({ top: 0 });
  }

  function showError(message) {
    $("#error-message").textContent = message;
    show("error-view");
  }

  // ------------------------------------------------------------------ envoi
  async function analyze(file) {
    if (!file) return;
    if (file.size > maxUploadMb * 1024 * 1024) {
      showError(`Le fichier fait ${fileSize(file.size)} : la limite est de ${maxUploadMb} Mo.`);
      return;
    }
    $("#loading-name").textContent = file.name;
    show("loading-view");
    const body = new FormData();
    body.append("file", file, file.name);
    try {
      const res = await fetch("api/analyze", { method: "POST", body });
      const payload = await res.json().catch(() => null);
      if (!res.ok) {
        showError((payload && payload.detail) || `Erreur du serveur (${res.status}).`);
        return;
      }
      lastReport = payload;
      renderReport(payload);
      show("report-view");
    } catch (err) {
      showError("Impossible de contacter le serveur. Vérifiez votre connexion et réessayez.");
    }
  }

  function download(filename, content, type) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const a = h("a", { href: url, download: filename });
    document.body.append(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  const baseName = (r) => r.file.name.replace(/\.[^.]+$/, "") || "classeur";

  // ---------------------------------------------------------------- rendu
  function renderReport(r) {
    const root = $("#report-view");
    const sections = [
      renderHead(r),
      r.limitations.length ? renderLimitations(r) : null,
      renderOverview(r),
      renderFindings(r),
      renderPlan(r),
      renderEntities(r),
      renderFormulas(r),
      renderVba(r),
      renderSheets(r),
      renderNamesAndValidations(r),
    ];
    // replaceChildren convertirait null en texte « null » : on retire les sections absentes.
    root.replaceChildren(...sections.filter(Boolean));
  }

  function renderHead(r) {
    const f = r.file;
    const date = new Date(f.analyzed_at).toLocaleString("fr-FR");
    return h("div", { class: "report-head" },
      h("div", {},
        h("h1", { text: f.name }),
        h("div", { class: "meta", text: `${f.format_label} · ${fileSize(f.size_bytes)} · analysé le ${date}` }),
      ),
      h("div", { class: "actions" },
        h("button", { type: "button", class: "btn", "data-action": "json", text: "Exporter (JSON)" }),
        r.sql_schema ? h("button", { type: "button", class: "btn", "data-action": "sql", text: "Schéma SQL" }) : null,
        h("button", { type: "button", class: "btn", "data-action": "print", text: "Imprimer / PDF" }),
        h("button", { type: "button", class: "btn btn-primary", "data-action": "reset", text: "Nouvelle analyse" }),
      ),
    );
  }

  function renderLimitations(r) {
    return h("div", { class: "notice", role: "note" },
      h("strong", { text: "À savoir sur cette analyse" }),
      h("ul", {}, r.limitations.map((l) => h("li", { text: l }))),
    );
  }

  function renderOverview(r) {
    const c = r.complexity;
    const s = r.summary;
    const gauge = h("div", { class: `gauge level-${c.level}`, role: "img", "aria-label": `Score de complexité ${c.score} sur 100` },
      h("div", { class: "gauge-inner" },
        h("span", { class: "gauge-value", text: c.score }),
        h("span", { class: "gauge-max", text: "/ 100" }),
      ),
    );
    gauge.style.setProperty("--value", String(c.score));
    const effort = c.effort_days.low === c.effort_days.high
      ? `${fmt(c.effort_days.low)} j`
      : `${fmt(c.effort_days.low)} à ${fmt(c.effort_days.high)} jours`;

    const errors = r.formulas.computed_errors || 0;
    const kpis = [
      [s.sheets, "Feuilles", s.hidden_sheets ? `dont ${s.hidden_sheets} masquée(s)` : ""],
      [s.formulas, "Formules", `${fmt(s.unique_formulas)} règle(s) distincte(s)`],
      [s.tables_detected, "Tableaux de données", `${fmt(s.data_rows)} ligne(s)`],
      [s.vba_lines, "Lignes de macros", `${fmt(s.vba_modules)} module(s)`],
      [s.external_links, "Liens externes", "vers d'autres fichiers"],
      [errors, "Cellules en erreur", "#REF!, #N/A…"],
    ];
    if (!r.formulas.available) kpis[1] = [null, "Formules", "non lisibles en .xls"];

    const maxPts = Math.max(1, ...c.factors.map((x) => x.points));
    return h("div", { class: "overview" },
      h("section", { class: "card score", "aria-labelledby": "score-title" },
        h("h2", { id: "score-title", text: "Complexité de migration" }),
        gauge,
        h("div", { class: "level", text: c.level_label }),
        h("div", { class: "effort" },
          h("strong", { text: effort }),
          h("span", { text: "Effort estimé pour reconstruire le fichier en application web (indicatif)" }),
        ),
      ),
      h("section", { class: "card", "aria-labelledby": "kpi-title" },
        h("h2", { id: "kpi-title", text: "Vue d'ensemble" }),
        h("div", { class: "kpis" }, kpis.map(([v, label, note]) =>
          h("div", { class: "kpi" },
            h("div", { class: "kpi-value", text: fmt(v) }),
            h("div", { class: "kpi-label", text: label }),
            note ? h("div", { class: "kpi-note", text: note }) : null,
          ))),
        h("h3", { text: "Ce qui fait la complexité" }),
        c.factors.length
          ? h("ul", { class: "factors" }, c.factors.map((f) => {
              const bar = h("span");
              bar.style.width = `${Math.max(3, (f.points / maxPts) * 100)}%`;
              return h("li", { class: "factor" },
                h("span", { text: f.label }),
                h("span", { class: "factor-points", text: `+${fmt(f.points)}` }),
                h("div", { class: "bar", "aria-hidden": "true" }, bar),
              );
            }))
          : h("p", { class: "empty", text: "Aucun facteur de complexité notable." }),
      ),
    );
  }

  function renderFindings(r) {
    const items = r.findings;
    return h("section", { class: "card", "aria-labelledby": "findings-title" },
      h("h2", { id: "findings-title" }, "Points de vigilance ", h("span", { class: "count", text: items.length })),
      items.length
        ? h("div", { class: "findings" }, items.map((f) =>
            h("article", { class: `finding ${f.severity}` },
              h("h3", {}, h("span", { class: `badge ${f.severity}`, text: SEVERITY[f.severity] }), f.title),
              h("p", { text: f.detail }),
              f.examples.length ? h("ul", { class: "chips" }, f.examples.map((e) => h("li", { class: "chip", text: e }))) : null,
            )))
        : h("p", { class: "empty", text: "Aucun point de vigilance : le fichier est sain." }),
    );
  }

  function renderPlan(r) {
    return h("section", { class: "card", "aria-labelledby": "plan-title" },
      h("h2", { id: "plan-title", text: "Plan de migration proposé" }),
      h("p", { class: "card-sub", text: "Comment ce classeur devient une application web." }),
      h("ol", { class: "plan" }, r.migration_plan.map((step) =>
        h("li", {},
          h("div", {},
            h("h3", { text: step.step }),
            h("p", { text: step.description }),
            h("ul", {}, step.items.map((i) => h("li", { text: i }))),
          ),
        ))),
    );
  }

  function fillBar(rate) {
    const pct = Math.round(rate * 100);
    const bar = h("span");
    bar.style.width = `${pct}%`;
    return h("div", { class: "fill" }, h("div", { class: "bar", "aria-hidden": "true" }, bar), h("span", { class: "pct", text: `${pct}%` }));
  }

  function columnNotes(c, pk) {
    const notes = [];
    if (c.field === pk) notes.push(h("span", { class: "badge ok", text: "Clé" }));
    if (c.references) notes.push(h("span", { class: "badge info", text: `→ ${c.references.entity}` }));
    if (c.computed) notes.push(h("span", { class: "badge neutral", text: "Calculé" }));
    if (c.type === "mixed") notes.push(h("span", { class: "badge warning", text: `Cohérence ${Math.round(c.type_consistency * 100)}%` }));
    if (c.errors) notes.push(h("span", { class: "badge critical", text: `${c.errors} erreur(s)` }));
    const detail = [];
    if (c.choices) detail.push(`Choix : ${c.choices.slice(0, 8).join(", ")}${c.choices.length > 8 ? "…" : ""}`);
    else if (c.min !== undefined) detail.push(`De ${fmt(c.min)} à ${fmt(c.max)}`);
    else if (c.samples.length) detail.push(`Ex. : ${c.samples.map(formatValue).join(" · ")}`);
    return h("td", {}, h("div", { class: "chips" }, notes), detail.length ? h("div", { class: "meta", text: detail.join(" ") }) : null);
  }

  function renderEntities(r) {
    const list = r.entities;
    return h("section", { class: "card", "aria-labelledby": "entities-title" },
      h("h2", { id: "entities-title" }, "Modèle de données détecté ", h("span", { class: "count", text: list.length })),
      h("p", { class: "card-sub", text: "Tableaux trouvés dans le classeur et structure de base de données proposée." }),
      r.relations && r.relations.length
        ? h("p", {}, h("strong", { text: "Relations détectées : " }), r.relations.map((x) => x.label).join(" ; "))
        : null,
      list.length ? list.map((e) =>
        h("div", { class: "entity" },
          h("div", { class: "entity-head" },
            h("h3", { text: e.name }),
            h("span", { class: `badge ${e.kind === "view" ? "neutral" : "ok"}`, text: e.kind === "view" ? "Vue calculée" : "Table" }),
            h("span", { class: "meta", text: `${e.range} · ${plural(e.rows, "ligne", "lignes")} · ${e.source === "excel_table" ? "tableau Excel" : "détection automatique"}` }),
          ),
          h("div", { class: "table-wrap" },
            h("table", {},
              h("thead", {}, h("tr", {}, ["Colonne", "Champ", "Type", "Remplissage", "Remarques"].map((t) => h("th", { scope: "col", text: t })))),
              h("tbody", {}, e.columns.map((c) =>
                h("tr", {},
                  h("td", { text: c.name }),
                  h("td", {}, h("code", { text: c.field })),
                  h("td", {}, c.type_label, h("div", { class: "meta", text: c.sql_type })),
                  h("td", {}, fillBar(c.fill_rate)),
                  columnNotes(c, e.primary_key_candidate),
                ))),
            ),
          ),
        ))
        : h("p", { class: "empty", text: "Aucun tableau structuré détecté (en-têtes + lignes)." }),
    );
  }

  function renderFormulas(r) {
    const f = r.formulas;
    if (!f.available) {
      return h("section", { class: "card", "aria-labelledby": "formulas-title" },
        h("h2", { id: "formulas-title", text: "Formules" }),
        h("p", { class: "empty", text: "Le texte des formules n'est pas lisible dans le format .xls. Enregistrez le fichier en .xlsx pour les analyser." }),
      );
    }
    const maxCount = Math.max(1, ...f.top_functions.map((x) => x.count));
    return h("section", { class: "card", "aria-labelledby": "formulas-title" },
      h("h2", { id: "formulas-title" }, "Formules ", h("span", { class: "count", text: fmt(f.total) })),
      f.total === 0 ? h("p", { class: "empty", text: "Aucune formule dans ce classeur." }) :
      h("div", { class: "two-col" },
        h("div", {},
          h("h3", { text: "Fonctions les plus utilisées" }),
          h("ul", { class: "factors" }, f.top_functions.map((fn) => {
            const bar = h("span");
            bar.style.width = `${Math.max(3, (fn.count / maxCount) * 100)}%`;
            return h("li", { class: "factor" },
              h("code", { text: fn.name }),
              h("span", { class: "factor-points", text: fmt(fn.count) }),
              h("div", { class: "bar", "aria-hidden": "true" }, bar));
          })),
        ),
        h("div", {},
          h("h3", { text: "Indicateurs" }),
          h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {},
            [
              ["Règles de calcul distinctes", f.unique],
              ["Fonctions différentes", f.distinct_functions],
              ["Appels de recherche (RECHERCHEV…)", f.lookup_calls],
              ["Formules volatiles", f.volatile_formulas],
              ["Formules avec valeurs en dur", f.hardcoded_constants_formulas],
              ["Imbrication maximale", f.max_nesting_depth],
              ["Formules matricielles", f.array_formulas],
            ].map(([k, v]) => h("tr", {}, h("td", { text: k }), h("td", { class: "num", text: fmt(v) })))))),
          f.sheet_dependencies.length ? h("div", {},
            h("h3", { text: "Dépendances entre feuilles" }),
            h("ul", {}, f.sheet_dependencies.map((d) => h("li", { text: `${d.from} → ${d.to} (${plural(d.formulas, "formule", "formules")})` }))),
          ) : null,
          f.external_references.length ? h("div", {},
            h("h3", { text: "Fichiers externes référencés" }),
            h("ul", {}, f.external_references.map((d) => h("li", { text: `${d.target} (${plural(d.formulas, "formule", "formules")})` }))),
          ) : null,
        ),
      ),
    );
  }

  function renderVba(r) {
    const v = r.vba;
    return h("section", { class: "card", "aria-labelledby": "vba-title" },
      h("h2", { id: "vba-title" }, "Macros VBA ", h("span", { class: "count", text: v.module_count })),
      !v.present ? h("p", { class: "empty", text: "Aucune macro dans ce classeur." }) : h("div", {},
        v.error ? h("p", { class: "notice", text: v.error }) : null,
        h("p", { text: `${plural(v.lines_of_code, "ligne de code", "lignes de code")} · ${plural(v.procedures, "procédure", "procédures")}` }),
        v.intents.length ? h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Ce que font les macros", "Équivalent dans l'application", "Modules"].map((t) => h("th", { scope: "col", text: t })))),
          h("tbody", {}, v.intents.map((i) => h("tr", {},
            h("td", {}, i.label, i.risk === "high" ? h("span", { class: "badge critical", text: " Risque" }) : null),
            h("td", { text: i.web_equivalent }),
            h("td", { text: i.modules.join(", ") }))))),
        ) : null,
        v.modules.map((m) => h("details", {},
          h("summary", { text: `${m.name} — ${plural(m.lines_of_code, "ligne", "lignes")}${m.procedures.length ? " · " + m.procedures.join(", ") : ""}` }),
          m.triggers.length ? h("p", {}, h("strong", { text: "Déclenchement automatique : " }), m.triggers.map((t) => `${t.procedure} (${t.when})`).join(", ")) : null,
          h("pre", { class: "code" }, h("code", { text: m.preview + (m.truncated ? "\n…" : "") })),
        )),
      ),
    );
  }

  function renderSheets(r) {
    const legacy = !r.formulas.available;
    const cols = ["Feuille", "État", "Plage", "Cellules", "Formules", "Tableaux", "Graphiques", "Validations"];
    return h("section", { class: "card", "aria-labelledby": "sheets-title" },
      h("h2", { id: "sheets-title" }, "Feuilles ", h("span", { class: "count", text: r.sheets.length })),
      h("div", { class: "table-wrap" }, h("table", {},
        h("thead", {}, h("tr", {}, cols.map((t) => h("th", { scope: "col", text: t })))),
        h("tbody", {}, r.sheets.map((s) => h("tr", {},
          h("td", {}, s.name, s.kind === "chartsheet" ? h("span", { class: "meta", text: " (feuille graphique)" }) : null),
          h("td", {},
            h("span", { class: `badge ${s.state === "visible" ? "ok" : s.state === "veryHidden" ? "warning" : "neutral"}`, text: STATE[s.state] || s.state }),
            s.protected ? h("span", { class: "badge neutral", text: " Protégée" }) : null),
          h("td", {}, h("code", { text: s.dimensions || "—" })),
          h("td", { class: "num", text: fmt(s.non_empty_cells) }),
          h("td", { class: "num", text: legacy ? "—" : fmt(s.formulas) }),
          h("td", { text: s.tables.length ? s.tables.join(", ") : "—" }),
          h("td", { class: "num", text: fmt(s.charts) }),
          h("td", { class: "num", text: fmt(s.data_validations) }),
        )))),
      ),
    );
  }

  function renderNamesAndValidations(r) {
    if (!r.names.length && !r.validations.length) return null;
    return h("section", { class: "card", "aria-labelledby": "names-title" },
      h("h2", { id: "names-title", text: "Paramètres et règles de saisie" }),
      r.names.length ? h("details", { open: r.names.length <= 8 },
        h("summary", { text: `Noms définis (${r.names.length})` }),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Nom", "Portée", "Fait référence à", ""].map((t) => h("th", { scope: "col", text: t })))),
          h("tbody", {}, r.names.map((n) => h("tr", {},
            h("td", {}, h("code", { text: n.name })),
            h("td", { text: n.scope }),
            h("td", {}, h("code", { text: n.refers_to })),
            h("td", {}, n.broken ? h("span", { class: "badge critical", text: "Cassé" }) : null, n.hidden ? h("span", { class: "badge neutral", text: "Masqué" }) : null),
          ))))),
      ) : null,
      r.validations.length ? h("details", { open: r.validations.length <= 8 },
        h("summary", { text: `Validations de données (${r.validations.length})` }),
        h("div", { class: "table-wrap" }, h("table", {},
          h("thead", {}, h("tr", {}, ["Feuille", "Plage", "Type", "Règle"].map((t) => h("th", { scope: "col", text: t })))),
          h("tbody", {}, r.validations.map((v) => h("tr", {},
            h("td", { text: v.sheet }),
            h("td", {}, h("code", { text: v.range })),
            h("td", { text: VALIDATION[v.type] || v.type }),
            h("td", { text: v.choices ? v.choices.join(", ") : v.rule || "—" }),
          ))))),
      ) : null,
    );
  }

  // ----------------------------------------------------------- événements
  function init() {
    const input = $("#file-input");
    const zone = $("#dropzone");

    input.addEventListener("change", () => {
      analyze(input.files[0]);
      input.value = "";
    });
    zone.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") { e.preventDefault(); input.click(); }
    });
    ["dragenter", "dragover"].forEach((t) => zone.addEventListener(t, (e) => {
      e.preventDefault();
      zone.classList.add("is-over");
    }));
    ["dragleave", "drop"].forEach((t) => zone.addEventListener(t, (e) => {
      e.preventDefault();
      zone.classList.remove("is-over");
    }));
    zone.addEventListener("drop", (e) => analyze(e.dataTransfer.files[0]));
    // Évite que le navigateur ouvre le fichier si on le lâche à côté de la zone.
    window.addEventListener("dragover", (e) => e.preventDefault());
    window.addEventListener("drop", (e) => e.preventDefault());

    document.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-action]");
      if (!btn) return;
      const action = btn.dataset.action;
      if (action === "reset") { lastReport = null; show("upload-view"); }
      else if (action === "print") window.print();
      else if (action === "json" && lastReport) download(`${baseName(lastReport)}-diagnostic.json`, JSON.stringify(lastReport, null, 2), "application/json");
      else if (action === "sql" && lastReport) download(`${baseName(lastReport)}-schema.sql`, lastReport.sql_schema, "text/plain");
    });

    fetch("api/config").then((r) => r.json()).then((cfg) => {
      maxUploadMb = cfg.max_upload_mb;
      $("#limits").textContent = `${cfg.extensions.join(", ")} · ${cfg.max_upload_mb} Mo max.`;
    }).catch(() => {});
    fetch("api/health").then((r) => r.json()).then((x) => { $("#version").textContent = `v${x.version}`; }).catch(() => {});
  }

  document.addEventListener("DOMContentLoaded", init);
})();
