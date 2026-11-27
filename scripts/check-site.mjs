// Vérifie le site généré dans dist/ : liens internes, ancres, métadonnées, RSS, sitemap, robots.txt.
// Usage : node scripts/check-site.mjs   (respecte BASE_PATH et SITE_URL comme le build)
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const DIST = new URL("../dist/", import.meta.url).pathname;
const BASE = (process.env.BASE_PATH || "/").replace(/\/?$/, "/");
const SITE = (process.env.SITE_URL || "https://example.com").replace(/\/$/, "");
const errors = [];
const fail = (file, msg) => errors.push(`${file}: ${msg}`);

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? walk(path) : [path];
  });
}

/** Chemin public (/Excel-auto/blog/x/) -> fichier dans dist, ou null. */
function resolve(href) {
  let path = decodeURIComponent(href.split(/[?#]/)[0]);
  if (!path.startsWith(BASE)) return null;
  path = path.slice(BASE.length);
  const candidates = [path, join(path, "index.html"), `${path}.html`];
  return candidates.map((c) => join(DIST, c)).find((c) => existsSync(c) && statSync(c).isFile()) ?? null;
}

const files = walk(DIST);
const html = files.filter((f) => f.endsWith(".html"));
const ids = new Map();
for (const file of html) {
  const content = readFileSync(file, "utf8");
  ids.set(file, new Set([...content.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1])));
}

for (const file of html) {
  const name = relative(DIST, file);
  const content = readFileSync(file, "utf8");
  const text = content
    .replace(/<(script|style|pre|code)[\s\S]*?<\/\1>/g, " ") // le code des articles peut légitimement contenir « NaN »
    .replace(/<[^>]+>/g, " ");

  if (!/<html lang="fr"/.test(content)) fail(name, "attribut lang manquant");
  const title = content.match(/<title>([^<]*)<\/title>/);
  if (!title || !title[1].trim()) fail(name, "titre manquant");
  if (!/<meta name="description" content="[^"]{20,}"/.test(content)) fail(name, "description manquante ou trop courte");
  const h1 = (content.match(/<h1[\s>]/g) || []).length;
  if (h1 !== 1) fail(name, `${h1} titres <h1> (1 attendu)`);
  if (/\b(undefined|NaN|\[object Object\])\b/.test(text)) fail(name, "valeur technique affichée dans la page");
  if (!/<link rel="canonical" href="https?:\/\//.test(content)) fail(name, "lien canonique manquant");

  for (const [, attr, href] of content.matchAll(/\s(href|src)="([^"]+)"/g)) {
    if (/^(https?:|mailto:|data:)/.test(href)) continue;
    if (href.startsWith("#")) {
      const id = decodeURIComponent(href.slice(1));
      if (id && !ids.get(file).has(id)) fail(name, `ancre introuvable : ${href}`);
      continue;
    }
    if (!href.startsWith("/")) { fail(name, `lien relatif inattendu (${attr}) : ${href}`); continue; }
    const target = resolve(href);
    if (!target) fail(name, `lien cassé (${attr}) : ${href}`);
    else if (href.includes("#")) {
      const id = decodeURIComponent(href.split("#")[1]);
      if (id && target.endsWith(".html") && !ids.get(target)?.has(id)) fail(name, `ancre introuvable : ${href}`);
    }
  }
}

// Flux RSS : bien formé, une entrée par article, liens absolus valides.
const posts = html.filter((f) => /\/blog\/[^/]+\/index\.html$/.test(f));
const rssPath = join(DIST, "rss.xml");
if (!existsSync(rssPath)) fail("rss.xml", "absent");
else {
  const rss = readFileSync(rssPath, "utf8");
  if (!rss.startsWith("<?xml") || !rss.includes("<rss")) fail("rss.xml", "format invalide");
  const items = [...rss.matchAll(/<item>[\s\S]*?<link>([^<]+)<\/link>[\s\S]*?<\/item>/g)].map((m) => m[1]);
  if (items.length !== posts.length) fail("rss.xml", `${items.length} entrées pour ${posts.length} articles`);
  for (const link of items) {
    if (!link.startsWith(SITE + BASE)) fail("rss.xml", `lien inattendu : ${link}`);
    else if (!resolve(link.slice(SITE.length))) fail("rss.xml", `lien cassé : ${link}`);
  }
}

// Sitemap et robots.txt
const sitemap = join(DIST, "sitemap-0.xml");
if (!existsSync(join(DIST, "sitemap-index.xml")) || !existsSync(sitemap)) fail("sitemap", "absent");
else {
  const locs = [...readFileSync(sitemap, "utf8").matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  if (locs.length < posts.length + 2) fail("sitemap", `seulement ${locs.length} pages`);
  for (const loc of locs) if (!resolve(loc.replace(SITE, ""))) fail("sitemap", `page absente : ${loc}`);
}
const robots = existsSync(join(DIST, "robots.txt")) ? readFileSync(join(DIST, "robots.txt"), "utf8") : "";
if (!robots.includes(`Sitemap: ${SITE}${BASE}sitemap-index.xml`)) fail("robots.txt", "lien vers le sitemap manquant");

if (!existsSync(join(DIST, "404.html"))) fail("404.html", "absente");

if (errors.length) {
  console.error(`✗ ${errors.length} problème(s) :\n  ${errors.join("\n  ")}`);
  process.exit(1);
}
console.log(`✓ Site vérifié : ${html.length} pages, ${posts.length} articles, base « ${BASE} ».`);
