import type { Template } from "@/components/template-card";

export const templates: Template[] = [
  {
    id: "launchpad",
    name: "Launchpad",
    description:
      "A SaaS landing page with bold typography, smooth animations, and conversion-optimized layout.",
    price: 149,
    tags: ["SaaS", "Landing Page", "Framer Motion"],
    previewUrl: "/templates/launchpad",
    image: "/templates/launchpad-thumb.jpg",
    status: "coming-soon",
  },
  {
    id: "atelier",
    name: "Atelier",
    description:
      "A portfolio template with cinematic scroll animations and full-bleed imagery.",
    price: 149,
    tags: ["Portfolio", "Creative", "GSAP"],
    previewUrl: "/templates/atelier",
    image: "/templates/atelier-thumb.jpg",
    status: "coming-soon",
  },
  {
    id: "meridian",
    name: "Meridian",
    description:
      "A documentation-style template with clean navigation, search, and dark mode.",
    price: 149,
    tags: ["Docs", "SaaS", "Dark Mode"],
    previewUrl: "/templates/meridian",
    image: "/templates/meridian-thumb.jpg",
    status: "coming-soon",
  },
];

export function getTemplate(id: string): Template | undefined {
  return templates.find((t) => t.id === id);
}
