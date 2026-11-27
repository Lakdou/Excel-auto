/** Réglages du blog : c'est le seul fichier à modifier pour le personnaliser. */
export const SITE = {
  title: "Octet",
  tagline: "Tech, dev, IA & gaming",
  description:
    "Des articles concrets sur le développement, l'IA, le matériel PC et le gaming : du code qui marche et l'actu décryptée.",
  author: "Lakdou",
  lang: "fr",
  locale: "fr-FR",
  links: {
    github: "https://github.com/Lakdou",
  },
} as const;

/**
 * Rubriques du magazine. Chaque article en choisit une (champ « category » de l'en-tête).
 * `from` / `to` : dégradé des illustrations ; `accent` : couleur des badges et titres de rubrique.
 */
export const CATEGORIES = {
  gaming: {
    label: "Gaming",
    description: "Consoles, sorties, prix et coulisses du jeu vidéo.",
    from: "#6d28d9",
    to: "#db2777",
    accent: "#c026d3",
    icon: "gamepad",
  },
  hardware: {
    label: "Hardware",
    description: "Composants, pénuries, guides d'achat et montage de PC.",
    from: "#0369a1",
    to: "#06b6d4",
    accent: "#0891b2",
    icon: "ram",
  },
  ia: {
    label: "IA",
    description: "Intelligence artificielle appliquée : outils, usages, limites.",
    from: "#047857",
    to: "#84cc16",
    accent: "#059669",
    icon: "neural",
  },
  dev: {
    label: "Dev",
    description: "Code, automatisation et outils pour développeurs.",
    from: "#c2410c",
    to: "#f59e0b",
    accent: "#ea580c",
    icon: "code",
  },
} as const;

export type CategoryKey = keyof typeof CATEGORIES;
export const CATEGORY_KEYS = Object.keys(CATEGORIES) as [CategoryKey, ...CategoryKey[]];

/** Pictogrammes disponibles pour les illustrations (champ facultatif « icon » d'un article). */
export const ICONS = ["gamepad", "ram", "neural", "code", "branch", "sheet", "rocket", "tower"] as const;
export type IconKey = (typeof ICONS)[number];
