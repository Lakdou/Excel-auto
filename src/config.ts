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
 * `accent` : couleur de la rubrique (badges, illustrations, filtres).
 */
export const CATEGORIES = {
  gaming: {
    label: "Gaming",
    description: "Consoles, sorties, prix et coulisses du jeu vidéo.",
    accent: "#ff2a3d",
    icon: "gamepad",
  },
  hardware: {
    label: "Hardware",
    description: "Composants, pénuries, guides d'achat et montage de PC.",
    accent: "#ff8a00",
    icon: "ram",
  },
  ia: {
    label: "IA",
    description: "Intelligence artificielle appliquée : outils, usages, limites.",
    accent: "#00d4ff",
    icon: "neural",
  },
  dev: {
    label: "Dev",
    description: "Code, automatisation et outils pour développeurs.",
    accent: "#b8ff2a",
    icon: "code",
  },
} as const;

export type CategoryKey = keyof typeof CATEGORIES;
export const CATEGORY_KEYS = Object.keys(CATEGORIES) as [CategoryKey, ...CategoryKey[]];

/** Pictogrammes disponibles pour les illustrations (champ facultatif « icon » d'un article). */
export const ICONS = ["gamepad", "ram", "neural", "code", "branch", "sheet", "rocket", "tower"] as const;
export type IconKey = (typeof ICONS)[number];
