import rss from "@astrojs/rss";
import type { APIContext } from "astro";
import { SITE } from "../config";
import { getPosts, url } from "../utils/posts";

export async function GET(context: APIContext) {
  const posts = await getPosts();
  return rss({
    title: `${SITE.title} · ${SITE.tagline}`,
    description: SITE.description,
    site: new URL(url("/"), context.site),
    items: posts.map((post) => ({
      title: post.data.title,
      description: post.data.description,
      pubDate: post.data.pubDate,
      categories: post.data.tags,
      link: url(`/blog/${post.id}/`),
    })),
    customData: `<language>fr-fr</language>`,
  });
}
