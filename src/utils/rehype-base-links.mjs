/**
 * Extension Markdown : préfixe les liens internes des articles (« /blog/… ») avec le chemin de base du site,
 * pour qu'ils fonctionnent aussi sur GitHub Pages (« /depot/blog/… »). Les liens externes ne sont pas touchés.
 */
export default function rehypeBaseLinks(base = "/") {
  const prefix = base.replace(/\/$/, "");
  return () => (tree) => {
    if (!prefix) return;
    const visit = (node) => {
      if (node.type === "element" && node.tagName === "a" && node.properties) {
        const href = node.properties.href;
        if (typeof href === "string" && href.startsWith("/") && !href.startsWith("//") && !href.startsWith(`${prefix}/`)) {
          node.properties.href = prefix + href;
        }
      }
      (node.children || []).forEach(visit);
    };
    visit(tree);
  };
}
