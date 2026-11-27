// Tests de bout en bout du blog (navigateur réel).
// Prérequis : npm run build && npx astro preview --port 4321
// Lancement : BASE_URL=http://127.0.0.1:4321 npm run test:e2e
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import { chromium, devices } from "playwright";

const BASE = (process.env.BASE_URL || "http://127.0.0.1:4321").replace(/\/$/, "");
let browser;

before(async () => { browser = await chromium.launch(); });
after(async () => { await browser.close(); });

async function open(path, options = {}) {
  const context = await browser.newContext(options);
  const page = await context.newPage();
  const problems = [];
  page.on("pageerror", (e) => problems.push(`pageerror: ${e.message}`));
  page.on("console", (m) => { if (m.type() === "error") problems.push(`console: ${m.text()}`); });
  const response = await page.goto(BASE + path);
  return { context, page, problems, response };
}

test("accueil : derniers articles et thèmes", async () => {
  const { context, page, problems } = await open("/");
  assert.equal(await page.title(), "Octet · Tech, dev, IA & gaming");
  const titles = await page.locator(".post-card h3").allTextContents();
  assert.equal(titles.length, 5); // les 5 plus récents
  assert.equal(titles[0], "Gaming : ce que la pénurie de mémoire change pour les joueurs"); // le plus récent d'abord
  assert.equal(titles[1], "Monter ou améliorer son PC gamer pendant la pénurie de RAM"); // même jour : ordre par heure
  assert.equal(await page.textContent(".section-head a"), "Tout voir (7) →");
  assert.ok((await page.locator(".tag").count()) >= 5);
  assert.equal(await page.getAttribute("link[type='application/rss+xml']", "href"), "/rss.xml");
  // Toute la carte est cliquable
  await page.locator(".post-card").first().click({ position: { x: 20, y: 20 } });
  await page.waitForURL(/\/blog\/gaming-ce-que-la-penurie-de-memoire-change\/$/);
  assert.deepEqual(problems, []);
  await context.close();
});

test("article : sommaire, code coloré et bouton Copier", async () => {
  const { context, page, problems } = await open("/blog/automatiser-excel-avec-python/");
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  assert.equal(await page.textContent("h1"), "Automatiser ses fichiers Excel avec Python");
  assert.match(await page.textContent(".post-header .meta"), /24 novembre 2026.*min de lecture/);

  const toc = await page.locator(".toc a").allTextContents();
  assert.ok(toc.includes("Consolider plusieurs fichiers"));
  await page.click(".toc a >> text=Consolider plusieurs fichiers");
  await page.waitForFunction(() => location.hash === "#consolider-plusieurs-fichiers");

  const blocks = page.locator(".code-block");
  assert.ok((await blocks.count()) >= 5);
  assert.equal(await page.locator(".code-block .code-lang").first().textContent(), "bash");
  assert.ok((await page.locator("pre.astro-code span[style]").count()) > 20, "coloration syntaxique");

  const block = blocks.nth(1);
  await block.hover();
  await block.locator(".copy-btn").click();
  await block.locator(".copy-btn.copied").waitFor();  // l'écriture dans le presse-papiers est asynchrone
  assert.equal(await block.locator(".copy-btn").textContent(), "Copié !");
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  assert.ok(copied.startsWith("import pandas as pd"), copied.slice(0, 40));

  // Navigation entre articles
  assert.ok(await page.locator(".post-nav a").count() >= 1);
  assert.deepEqual(problems, []);
  await context.close();
});

test("thème sombre : suit l'appareil, bascule et reste mémorisé", async () => {
  const { context, page } = await open("/blog/git-commandes-essentielles/", { colorScheme: "dark" });
  const theme = () => page.evaluate(() => document.documentElement.dataset.theme);
  const codeColor = () => page.locator("pre.astro-code").first().evaluate((el) => getComputedStyle(el).backgroundColor);
  assert.equal(await theme(), "dark");
  const darkCode = await codeColor();
  await page.click("[data-theme-toggle]");
  assert.equal(await theme(), "light");
  assert.equal(await page.getAttribute("[data-theme-toggle]", "aria-pressed"), "false");
  assert.notEqual(await codeColor(), darkCode, "les blocs de code changent aussi de thème");
  await page.reload();
  assert.equal(await theme(), "light", "choix conservé après rechargement");
  await context.close();
});

test("articles : recherche instantanée, insensible aux accents", async () => {
  const { context, page } = await open("/blog/");
  const visible = () => page.locator(".post-card:visible").count();
  assert.equal(await visible(), 7);
  await page.fill("#search", "git");
  assert.equal(await visible(), 1);
  await page.fill("#search", "productivite");  // sans accent -> « Productivité »
  assert.equal(await visible(), 1);
  await page.fill("#search", "penurie ram");   // plusieurs mots, sans accents
  assert.equal(await visible(), 3);
  await page.fill("#search", "zzzz");
  assert.equal(await visible(), 0);
  assert.equal(await page.isVisible("#no-result"), true);
  await page.fill("#search", "");
  assert.equal(await visible(), 7);
  await context.close();
});

test("tags : liste et page d'un tag", async () => {
  const { context, page } = await open("/tags/");
  await page.click(".tag >> text=Python");
  await page.waitForURL(/\/tags\/python\/$/);
  assert.equal(await page.textContent("h1"), "#Python");
  assert.deepEqual(await page.locator(".post-card h3").allTextContents(), ["Automatiser ses fichiers Excel avec Python"]);
  await context.close();
});

test("page 404 et flux RSS", async () => {
  const { context, page, response } = await open("/cette-page-n-existe-pas/");
  assert.equal(response.status(), 404);
  assert.equal(await page.textContent("h1"), "Page introuvable");
  const rss = await page.request.get(BASE + "/rss.xml");
  assert.equal(rss.status(), 200);
  assert.match(rss.headers()["content-type"], /xml/);
  assert.equal(((await rss.text()).match(/<item>/g) || []).length, 7);
  await context.close();
});

test("mobile : pas de défilement horizontal, le code défile dans son cadre", async () => {
  for (const path of ["/", "/blog/automatiser-excel-avec-python/", "/blog/monter-son-pc-gamer-pendant-la-penurie/", "/blog/"]) {
    const { context, page } = await open(path, { ...devices["iPhone SE"] });
    // Sur mobile, la zone d'affichage s'élargit pour englober le contenu : on compare donc chaque
    // élément à la largeur réelle de l'écran (les blocs de code défilent dans leur propre cadre).
    const result = await page.evaluate(() => {
      const width = window.screen.width;
      const offenders = [...document.querySelectorAll("body *")]
        .filter((el) => !el.closest("pre, table, .visually-hidden, .skip-link"))
        .filter((el) => el.getBoundingClientRect().right > width + 1)
        .map((el) => `${el.tagName.toLowerCase()}.${el.className}`);
      return { width, layout: document.documentElement.scrollWidth, offenders: offenders.slice(0, 5) };
    });
    assert.equal(result.layout, result.width, `${path} : page de ${result.layout}px pour un écran de ${result.width}px`);
    assert.deepEqual(result.offenders, [], `${path} : éléments qui dépassent`);
    await context.close();
  }
});

test("accessibilité : lien d'évitement et navigation au clavier", async () => {
  const { context, page } = await open("/");
  await page.keyboard.press("Tab");
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), "Aller au contenu");
  assert.equal(await page.evaluate(() => getComputedStyle(document.activeElement).left), "16px");
  await page.keyboard.press("Enter");
  assert.ok(page.url().endsWith("#contenu"));
  await context.close();
});

test("articles gaming : liens internes entre articles et sources externes", async () => {
  const { context, page, problems } = await open("/blog/gaming-ce-que-la-penurie-de-memoire-change/");
  assert.equal(await page.textContent("h1"), "Gaming : ce que la pénurie de mémoire change pour les joueurs");
  const external = await page.locator(".prose a[href^='http']").count();
  assert.ok(external >= 4, "sources citées");
  await page.click(".prose a >> text=guide pour monter son PC pendant la pénurie");
  await page.waitForURL(/\/blog\/monter-son-pc-gamer-pendant-la-penurie\/$/);
  assert.equal(await page.textContent("h1"), "Monter ou améliorer son PC gamer pendant la pénurie de RAM");
  assert.deepEqual(problems, []);
  await context.close();
});
