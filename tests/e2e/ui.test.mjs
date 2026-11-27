// Tests de bout en bout de l'interface (navigateur réel).
// Prérequis : serveur lancé (uvicorn app.main:app --port 8765) et fichiers de démo générés.
// Lancement : BASE_URL=http://127.0.0.1:8765 SAMPLES=samples/demo node --test tests/e2e/
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { chromium, devices } = require("playwright");

const BASE = process.env.BASE_URL || "http://127.0.0.1:8765";
const SAMPLES = path.resolve(process.env.SAMPLES || "samples/demo");
const SHOTS = process.env.SCREENSHOTS; // dossier optionnel pour les captures
let browser;

before(async () => { browser = await chromium.launch(); });
after(async () => { await browser.close(); });

async function newPage(options = {}) {
  const context = await browser.newContext(options);
  const page = await context.newPage();
  const problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  return { context, page, problems };
}

async function upload(page, file) {
  await page.goto(BASE + "/");
  await page.setInputFiles("#file-input", path.join(SAMPLES, file));
}

test("analyse complète d'un classeur avec macros", async () => {
  const { context, page, problems } = await newPage({ viewport: { width: 1280, height: 900 } });
  await upload(page, "suivi_achats_2019.xlsm");
  await page.waitForSelector("#report-view:not([hidden])", { timeout: 15000 });

  assert.equal(await page.textContent(".report-head h1"), "suivi_achats_2019.xlsm");
  const score = Number(await page.textContent(".gauge-value"));
  assert.ok(score > 0 && score <= 100, `score ${score}`);
  assert.equal(await page.locator(".finding.critical").count() > 0, true);
  const findings = await page.locator(".finding h3").allTextContents();
  assert.ok(findings.some((t) => t.includes("Dépendances vers d'autres fichiers")));
  assert.ok(findings.some((t) => t.includes("Feuilles super-masquées")));

  const entities = await page.locator(".entity h3").allTextContents();
  assert.deepEqual(entities, ["Paramètres", "TFournisseurs", "Commandes", "Synthèse", "Archives"]);
  assert.ok((await page.textContent("#entities-title + p + p")).includes("Commandes.Code fournisseur"));
  assert.ok((await page.locator(".plan > li").count()) >= 5);
  assert.ok((await page.textContent("#vba-title")).includes("Macros VBA"));
  assert.equal(await page.locator("details pre.code").count(), 1);

  // Dates au format français, pas ISO.
  const entitiesText = await page.innerText("#report-view .entity:nth-of-type(3)");
  assert.ok(entitiesText.includes("10/01/2019"), "date au format français");
  assert.ok(!/\d{4}-\d{2}-\d{2}T/.test(entitiesText), "date ISO affichée");

  // Aucune valeur technique ne doit fuiter dans le texte affiché.
  const visible = await page.innerText("#report-view");
  assert.ok(!/\b(null|undefined|NaN|\[object Object\])\b/.test(visible), "valeur technique affichée");

  // La jauge reflète le score (variable CSS posée via CSSOM, compatible CSP).
  const gaugeVar = await page.$eval(".gauge", (el) => el.style.getPropertyValue("--value"));
  assert.equal(Number(gaugeVar), score);

  // Exports
  const [json] = await Promise.all([page.waitForEvent("download"), page.click("[data-action=json]")]);
  assert.equal(json.suggestedFilename(), "suivi_achats_2019-diagnostic.json");
  const report = JSON.parse(fs.readFileSync(await json.path(), "utf8"));
  assert.equal(report.summary.sheets, 5);
  const [sql] = await Promise.all([page.waitForEvent("download"), page.click("[data-action=sql]")]);
  assert.ok(fs.readFileSync(await sql.path(), "utf8").includes("CREATE TABLE commandes"));

  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "rapport-desktop.png"), fullPage: true });

  // Retour à l'accueil
  await page.click(".report-head [data-action=reset]");
  assert.equal(await page.isVisible("#dropzone"), true);
  assert.deepEqual(problems, []);
  await context.close();
});

test("ancien fichier .xls : limites affichées", async () => {
  const { context, page, problems } = await newPage();
  await upload(page, "inventaire_2004.xls");
  await page.waitForSelector("#report-view:not([hidden])");
  assert.ok((await page.textContent(".notice")).includes("Excel 97-2003"));
  assert.ok((await page.textContent("#formulas-title + p")).includes("pas lisible"));
  assert.ok(!/\b(null|undefined|NaN)\b/.test(await page.innerText("#report-view")));
  assert.deepEqual(problems, []);
  await context.close();
});

test("fichier invalide : message d'erreur clair puis nouvel essai", async () => {
  const { context, page, problems } = await newPage();
  await page.goto(BASE + "/");
  await page.setInputFiles("#file-input", { name: "export.xls", mimeType: "application/vnd.ms-excel", buffer: Buffer.from("<html><table></table></html>") });
  await page.waitForSelector("#error-view:not([hidden])");
  assert.ok((await page.textContent("#error-message")).includes("HTML"));
  await page.click("#error-view [data-action=reset]");
  assert.equal(await page.isVisible("#dropzone"), true);
  // Seule l'erreur réseau 422 attendue peut apparaître dans la console.
  assert.ok(problems.every((p) => p.includes("422")), problems.join("\n"));
  await context.close();
});

test("données malveillantes affichées comme du texte (pas d'injection HTML)", async () => {
  const { context, page } = await newPage();
  await page.goto(BASE + "/");
  // Rapport réel, puis injection de HTML dans des champs qui viennent du fichier Excel.
  const form = new FormData();
  const file = fs.readFileSync(path.join(SAMPLES, "suivi_achats_2019.xlsm"));
  form.append("file", new Blob([file]), "suivi_achats_2019.xlsm");
  const body = await (await fetch(BASE + "/api/analyze", { method: "POST", body: form })).json();
  body.sheets[0].name = '<img src=x onerror="window.__pwned=1">';
  body.findings[0].title = "<script>window.__pwned=1</script>";
  body.vba.modules[0].preview = "</code><img src=x onerror=\"window.__pwned=1\">";
  await page.route("**/api/analyze", (route) => route.fulfill({ json: body }));
  await page.setInputFiles("#file-input", path.join(SAMPLES, "suivi_achats_2019.xlsm"));
  await page.waitForSelector("#report-view:not([hidden])");
  assert.equal(await page.evaluate(() => window.__pwned), undefined);
  assert.equal(await page.locator("#report-view img").count(), 0);
  assert.ok((await page.textContent("#report-view")).includes("<img src=x"));
  await context.close();
});

test("affichage mobile sans défilement horizontal", async () => {
  const { context, page, problems } = await newPage({ ...devices["iPhone 13"] });
  await page.goto(BASE + "/");
  const homeOverflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert.ok(homeOverflow <= 0, `débordement accueil : ${homeOverflow}px`);
  await page.setInputFiles("#file-input", path.join(SAMPLES, "suivi_achats_2019.xlsm"));
  await page.waitForSelector("#report-view:not([hidden])");
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert.ok(overflow <= 0, `débordement rapport : ${overflow}px`);
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "rapport-mobile.png"), fullPage: false });
  assert.deepEqual(problems, []);
  await context.close();
});

test("mode sombre et accueil", async () => {
  const { context, page } = await newPage({ colorScheme: "dark", viewport: { width: 1280, height: 800 } });
  await page.goto(BASE + "/");
  const bg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
  assert.equal(bg, "rgb(17, 20, 24)");
  assert.ok((await page.textContent("#limits")).includes("Mo max"));
  if (SHOTS) await page.screenshot({ path: path.join(SHOTS, "accueil-sombre.png") });
  await context.close();
});
