// Tests de bout en bout du blog (navigateur réel).
// Prérequis : npm run build && npx astro preview --port 4321
// Lancement : BASE_URL=http://127.0.0.1:4321 npm run test:e2e
import { test, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { chromium, devices } from "playwright";

const BASE = (process.env.BASE_URL || "http://127.0.0.1:4321").replace(/\/$/, "");

// Les valeurs attendues sont calculées à partir des articles réels : les tests restent justes quand la veille
// automatique publie de nouveaux articles.
const BLOG_DIR = new URL("../../src/content/blog/", import.meta.url);
const field = (fm, name) => (fm.match(new RegExp(`^${name}:\\s*(.+)$`, "m")) || [])[1]?.trim().replace(/^"|"$/g, "");
const POSTS = fs.readdirSync(BLOG_DIR).filter((f) => f.endsWith(".md")).map((f) => {
  const fm = fs.readFileSync(new URL(f, BLOG_DIR), "utf8").split(/^---$/m)[1];
  return {
    slug: f.replace(/\.md$/, ""), title: field(fm, "title"), description: field(fm, "description"),
    date: new Date(field(fm, "pubDate")), category: field(fm, "category"),
    tags: JSON.parse(field(fm, "tags") || "[]"), featured: field(fm, "featured") === "true", draft: field(fm, "draft") === "true",
  };
}).filter((p) => !p.draft).sort((a, b) => b.date - a.date);
const N = POSTS.length;
const FEATURED = POSTS.find((p) => p.featured) ?? POSTS[0];
const OTHERS = POSTS.filter((p) => p !== FEATURED);
const byCategory = (c) => POSTS.filter((p) => p.category === c);
const norm = (t) => t.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
const matching = (q, cat = "") => POSTS.filter((p) => {
  const hay = norm(`${p.title} ${p.description} ${p.tags.join(" ")} ${p.category}`);
  return norm(q).split(/\s+/).filter(Boolean).every((t) => hay.includes(t)) && (!cat || p.category === cat);
}).length;
const plural = (n, word) => `${n} ${word}${n > 1 ? "s" : ""}`;
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

test("accueil magazine : à la une, à lire aussi, derniers articles, rubriques", async () => {
  const { context, page, problems } = await open("/");
  assert.equal(await page.title(), "Octet · Tech, dev, IA & gaming");
  assert.equal(await page.locator("h1").count(), 1); // titre principal (masqué visuellement)
  // À la une : l'article marqué « featured » ; ensuite, les plus récents (même jour : ordre par heure)
  assert.equal(await page.textContent(".post-card--featured h2"), FEATURED.title);
  assert.deepEqual(await page.locator(".side-list .post-card h3").allTextContents(), OTHERS.slice(0, 3).map((p) => p.title));
  assert.equal(await page.locator(".card-grid .post-card").count(), Math.min(6, Math.max(0, OTHERS.length - 3)));
  assert.equal(await page.textContent("section[aria-labelledby=latest-title] .section-head a"), `Tous les articles (${N}) →`);
  // Chaque carte a une illustration et un badge de rubrique
  const cards = await page.locator(".post-card").count();
  assert.equal(await page.locator(".post-card svg.cover").count(), cards);
  assert.equal(await page.locator(".post-card .badge").count(), cards);
  // Tuiles de rubriques avec compteurs
  assert.deepEqual(await page.locator(".cat-tile h3").allTextContents(), ["Gaming", "Hardware", "IA", "Dev"]);
  assert.equal(await page.textContent(".cat-tile >> nth=3 >> .count"), plural(byCategory("dev").length, "article"));
  assert.equal(await page.getAttribute("link[type='application/rss+xml']", "href"), "/rss.xml");
  // L'image et le titre mènent à l'article
  await page.locator(".post-card--featured .post-card__media").click();
  await page.waitForURL(new RegExp(`/blog/${FEATURED.slug}/$`));
  assert.deepEqual(problems, []);
  await context.close();
});

test("illustrations : uniques par article et stables d'un chargement à l'autre", async () => {
  const { context, page } = await open("/");
  const signature = () => page.locator(".card-grid .post-card svg.cover").evaluateAll((svgs) =>
    svgs.map((svg) => svg.innerHTML.replace(/id="[^"]+"|url\(#[^)]+\)/g, "")));
  const first = await signature();
  assert.equal(new Set(first).size, first.length, "deux articles ont la même illustration");
  await page.reload();
  assert.deepEqual(await signature(), first);
  // Identifiants SVG uniques dans la page (sinon les dégradés se mélangent)
  const ids = await page.locator("svg.cover [id]").evaluateAll((els) => els.map((e) => e.id));
  assert.equal(new Set(ids).size, ids.length);
  await context.close();
});

test("article : sommaire, code coloré et bouton Copier", async () => {
  const { context, page, problems } = await open("/blog/automatiser-excel-avec-python/");
  await context.grantPermissions(["clipboard-read", "clipboard-write"], { origin: BASE });
  assert.equal(await page.textContent("h1"), "Automatiser ses fichiers Excel avec Python");
  assert.match(await page.textContent(".post-hero .meta"), /24 novembre 2026.*min de lecture/);
  assert.equal(await page.textContent(".post-hero .badge"), "Dev");
  assert.equal(await page.locator(".post-cover svg.cover[role=img]").count(), 1);

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

  // Copier le lien de l'article
  await page.click("[data-copy-link]");
  await page.waitForSelector("[data-copy-link]:has-text('Lien copié !')");
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), `${BASE}/blog/automatiser-excel-avec-python/`);

  // Articles similaires : même rubrique en premier
  const related = page.locator(".related .post-card");
  assert.equal(await related.count(), 3);
  assert.deepEqual((await page.locator(".related .post-card .badge").allTextContents()).slice(0, 2), ["Dev", "Dev"]);
  assert.deepEqual(problems, []);
  await context.close();
});

test("thème : sombre par défaut, bascule en clair et reste mémorisé", async () => {
  const { context, page } = await open("/blog/git-commandes-essentielles/", { colorScheme: "light" });
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
  assert.equal(await visible(), N);
  for (const q of ["git", "productivite", "penurie ram", "zzzz"]) {  // sans accents, plusieurs mots
    await page.fill("#search", q);
    assert.equal(await visible(), matching(q), `recherche « ${q} »`);
  }
  assert.equal(await page.isVisible("#no-result"), true);
  await page.fill("#search", "");
  assert.equal(await visible(), N);
  // Filtre par rubrique, combinable avec la recherche
  await page.click(".chip[data-filter=hardware]");
  assert.equal(await page.getAttribute(".chip[data-filter=hardware]", "aria-pressed"), "true");
  assert.equal(await visible(), byCategory("hardware").length);
  await page.fill("#search", "guide");
  assert.equal(await visible(), matching("guide", "hardware"));
  await page.click(".chip[data-filter='']");
  await page.fill("#search", "");
  assert.equal(await visible(), N);
  await context.close();
});

test("rubriques : navigation et page de rubrique", async () => {
  const { context, page, problems } = await open("/");
  await page.click(".nav >> text=Gaming");
  await page.waitForURL(/\/categorie\/gaming\/$/);
  assert.equal(await page.textContent("h1"), "Gaming");
  assert.equal(await page.getAttribute(".nav a[aria-current=page]", "href"), "/categorie/gaming/");
  assert.deepEqual(await page.locator(".post-card h3").allTextContents(), byCategory("gaming").map((p) => p.title));
  await page.goto(BASE + "/categorie/dev/");
  assert.equal(await page.locator(".post-card").count(), byCategory("dev").length);
  // Le lien de recherche de l'en-tête ouvre la liste avec le champ actif
  await page.click("a[aria-label='Rechercher un article']");
  await page.waitForURL(/\/blog\/#search$/);
  assert.equal(await page.evaluate(() => document.activeElement?.id), "search");
  assert.deepEqual(problems, []);
  await context.close();
});

test("tags : liste et page d'un tag", async () => {
  const { context, page } = await open("/tags/");
  await page.click(".tag >> text=Python");
  await page.waitForURL(/\/tags\/python\/$/);
  assert.equal(await page.textContent("h1"), "#Python");
  assert.deepEqual(await page.locator(".post-card h3").allTextContents(), POSTS.filter((p) => p.tags.includes("Python")).map((p) => p.title));
  await context.close();
});

test("page 404 et flux RSS", async () => {
  const { context, page, response } = await open("/cette-page-n-existe-pas/");
  assert.equal(response.status(), 404);
  assert.equal(await page.textContent("h1"), "Page introuvable");
  const rss = await page.request.get(BASE + "/rss.xml");
  assert.equal(rss.status(), 200);
  assert.match(rss.headers()["content-type"], /xml/);
  assert.equal(((await rss.text()).match(/<item>/g) || []).length, N);
  await context.close();
});

test("mobile : pas de défilement horizontal, le code défile dans son cadre", async () => {
  for (const path of ["/", "/blog/automatiser-excel-avec-python/", "/blog/monter-son-pc-gamer-pendant-la-penurie/", "/blog/", "/categorie/hardware/"]) {
    const { context, page } = await open(path, { ...devices["iPhone SE"] });
    // Sur mobile, la zone d'affichage s'élargit pour englober le contenu : on compare donc chaque
    // élément à la largeur réelle de l'écran (les blocs de code défilent dans leur propre cadre).
    const result = await page.evaluate(() => {
      const width = window.screen.width;
      // Ignore ce qui est dans une zone qui défile d'elle-même (code, tableaux, menu des rubriques) ou qui est
      // rogné par son cadre (formes intérieures des illustrations) : rien de tout cela ne fait déborder la page.
      const inScroller = (el) => {
        if (el.closest("svg")) return true;
        for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
          if (["auto", "scroll", "hidden", "clip"].includes(getComputedStyle(p).overflowX)) return true;
        }
        return false;
      };
      const offenders = [...document.querySelectorAll("body *")]
        .filter((el) => !el.closest(".visually-hidden, .skip-link") && !inScroller(el))
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
