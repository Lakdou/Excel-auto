import { getCollection, type CollectionEntry } from "astro:content";
import { CATEGORIES, SITE, type CategoryKey } from "../config";

export type Post = CollectionEntry<"blog">;

/** Articles publiés (hors brouillons), du plus récent au plus ancien. */
export async function getPosts(): Promise<Post[]> {
  const posts = await getCollection("blog", ({ data }) => !data.draft);
  return posts.sort((a, b) => b.data.pubDate.valueOf() - a.data.pubDate.valueOf());
}

/** Temps de lecture estimé (230 mots par minute, blocs de code comptés à moitié). */
export function readingTime(markdown: string = ""): number {
  const code = (markdown.match(/```[\s\S]*?```/g) || []).join(" ");
  const prose = markdown.replace(/```[\s\S]*?```/g, " ");
  const words = (text: string) => text.split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round((words(prose) + words(code) / 2) / 230));
}

const dateFormat = new Intl.DateTimeFormat(SITE.locale, { day: "numeric", month: "long", year: "numeric", timeZone: "UTC" });

export function formatDate(date: Date): string {
  return dateFormat.format(date);
}

/** « Intelligence artificielle » -> « intelligence-artificielle ». */
export function slugify(text: string): string {
  return text
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Préfixe une URL interne avec le chemin de base du site (utile sur GitHub Pages). */
export function url(path: string = "/"): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  const clean = path.startsWith("/") ? path : `/${path}`;
  return `${base}${clean}` || "/";
}

/** Tous les tags avec leur nombre d'articles, triés par popularité puis par nom. */
export function tagCounts(posts: Post[]): { tag: string; slug: string; count: number }[] {
  const counts = new Map<string, { tag: string; count: number }>();
  for (const post of posts) {
    for (const tag of post.data.tags) {
      const slug = slugify(tag);
      const entry = counts.get(slug) ?? { tag, count: 0 };
      entry.count += 1;
      counts.set(slug, entry);
    }
  }
  return [...counts.entries()]
    .map(([slug, { tag, count }]) => ({ tag, slug, count }))
    .sort((a, b) => b.count - a.count || a.tag.localeCompare(b.tag, "fr"));
}

/** Article « à la une » : le plus récent marqué featured, sinon le plus récent tout court. */
export function featuredPost(posts: Post[]): Post | undefined {
  return posts.find((p) => p.data.featured) ?? posts[0];
}

/** Articles liés : même rubrique d'abord, puis tags communs, puis les plus récents. */
export function relatedPosts(post: Post, posts: Post[], count = 3): Post[] {
  const score = (other: Post) =>
    (other.data.category === post.data.category ? 10 : 0) +
    other.data.tags.filter((t) => post.data.tags.includes(t)).length;
  return posts
    .filter((p) => p.id !== post.id)
    .map((p, index) => ({ p, s: score(p), index }))
    .sort((a, b) => b.s - a.s || a.index - b.index)
    .slice(0, count)
    .map(({ p }) => p);
}

export function category(key: CategoryKey) {
  return CATEGORIES[key];
}
