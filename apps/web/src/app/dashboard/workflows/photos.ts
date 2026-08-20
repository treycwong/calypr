/** Cover photography for the workflow cards.
 *
 * Resolved once against the Unsplash API and committed as static URLs, rather than searched at
 * runtime: a gallery that needs a live API call (and therefore an API key) to look right is a
 * gallery that renders eighteen empty rectangles the day the key expires. These are stable
 * `images.unsplash.com` links with imgix sizing params, so there is no key in the app, no
 * network round-trip beyond the image itself, and nothing to rate-limit.
 *
 * Sized for the card at 2x (cards are ~320px at the widest breakpoint), webp, quality 80.
 *
 * `by`/`href` are not decoration — the Unsplash licence asks that the photographer be credited
 * with a link back, which the card renders on hover. A template with no entry here falls back to
 * generative art, so a new workflow is never blocked on picking a photo.
 */
export type WorkflowPhoto = {
  src: string;
  alt: string;
  by: string;
  href: string;
};

/** Appended to attribution links — Unsplash's API guidelines require the referral params. */
export const UNSPLASH_UTM = "?utm_source=calypr&utm_medium=referral";

export const WORKFLOW_PHOTOS: Record<string, WorkflowPhoto> = {
  "tpl-flashcards": {
    src: "https://images.unsplash.com/photo-1631127875592-f71dac3fb582?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8bGFuZ3VhZ2UlMjBsZWFybmluZyUyMGZsYXNoY2FyZHN8ZW58MXwwfHx8MTc4NzI0MDUzOHww&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "woman in white and black tank top holding white printer paper",
    by: "Helena Lopes",
    href: "https://unsplash.com/@helenalopesph",
  },
  "tpl-quiz-me": {
    src: "https://images.unsplash.com/photo-1633613286848-e6f43bbafb8d?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8cXVpeiUyMHF1ZXN0aW9uJTIwbWFya3xlbnwxfDB8fHwxNzg3MjQwNTM5fDA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "a blue question mark on a pink background",
    by: "Towfiqu barbhuiya",
    href: "https://unsplash.com/@towfiqu999999",
  },
  "tpl-study-notes": {
    src: "https://images.unsplash.com/photo-1517842645767-c639042777db?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8c3R1ZHklMjBub3RlcyUyMG5vdGVib29rfGVufDF8MHx8fDE3ODcyNDA1NDB8MA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "brown fountain pen on notebook",
    by: "David Travis",
    href: "https://unsplash.com/@dtravisphd",
  },
  "tpl-study-notion": {
    src: "https://images.unsplash.com/photo-1612367980327-7454a7276aa7?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8bm90ZWJvb2slMjBwbGFubmluZyUyMGRlc2t8ZW58MXwwfHx8MTc4NzI0MDU0MXww&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "white spiral notebook on brown wooden table",
    by: "Kelly Sikkema",
    href: "https://unsplash.com/@kellysikkema",
  },
  "tpl-image-generation": {
    src: "https://images.unsplash.com/photo-1620641788421-7a1c342ea42e?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8YWJzdHJhY3QlMjBjb2xvcmZ1bCUyMGdyYWRpZW50JTIwYXJ0fGVufDF8MHx8fDE3ODcyNDA1NDJ8MA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "abstract purple and pink gradient waves",
    by: "Milad Fakurian",
    href: "https://unsplash.com/@fakurian",
  },
  "tpl-text-to-speech": {
    src: "https://images.unsplash.com/photo-1589903308904-1010c2294adc?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8c3R1ZGlvJTIwbWljcm9waG9uZXxlbnwxfDB8fHwxNzg3MjQwNTQ3fDA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "black and silver headphones on black and silver microphone",
    by: "Will Francis - AI & Marketing",
    href: "https://unsplash.com/@willfrancis",
  },
  "tpl-translate-speak": {
    src: "https://images.unsplash.com/photo-1543165796-5426273eaab3?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8Zm9yZWlnbiUyMGxhbmd1YWdlJTIwZGljdGlvbmFyeXxlbnwxfDB8fHwxNzg3MjQwNTQ4fDA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "open Dictionary",
    by: "Waldemar Brandt",
    href: "https://unsplash.com/@waldemarbrandt67w",
  },
  "tpl-label-reader": {
    src: "https://images.unsplash.com/photo-1648823161626-0e839927401b?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8Z3JvY2VyeSUyMHJlY2VpcHQlMjBwYXBlcnxlbnwxfDB8fHwxNzg3MjQwNTQ2fDA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "a hand holding a piece of paper with a bar code on it",
    by: "Am",
    href: "https://unsplash.com/@mahathirr",
  },
  "tpl-alt-text": {
    src: "https://images.unsplash.com/photo-1634947096506-6d9f114cf64e?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8YnJhaWxsZSUyMGFjY2Vzc2liaWxpdHl8ZW58MXwwfHx8MTc4NzI0MDU0NXww&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "a laptop computer sitting on top of a desk",
    by: "Elizabeth Woolner",
    href: "https://unsplash.com/@elizabeth_woolner",
  },
  "tpl-image-finder": {
    src: "https://images.unsplash.com/photo-1505744768106-34d8c47a1327?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8cGhvdG8lMjBwcmludHMlMjBvbiUyMHRhYmxlfGVufDF8MHx8fDE3ODcyNDA1NDR8MA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "clear eyeglasses on post cards",
    by: "Dan Gold",
    href: "https://unsplash.com/@danielcgold",
  },
  "tpl-street-photography": {
    src: "https://images.unsplash.com/photo-1687561114602-eb5701981823?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8c3RyZWV0JTIwcGhvdG9ncmFwaHklMjBmaWxtJTIwZ3JhaW58ZW58MXwwfHx8MTc4NzI0MDU0M3ww&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "a blue car parked in front of a house",
    by: "Matthew Woinarowicz",
    href: "https://unsplash.com/@mattxfotographs",
  },
  "tpl-market-research": {
    src: "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8bWFya2V0JTIwcmVzZWFyY2glMjBjaGFydHN8ZW58MXwwfHx8MTc4NzI0MDU1MHww&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "stock market candlestick chart on dark screen",
    by: "Maxim Hopman",
    href: "https://unsplash.com/@nampoh",
  },
  "tpl-contract-review": {
    src: "https://images.unsplash.com/photo-1450101499163-c8848c66ca85?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8bGVnYWwlMjBjb250cmFjdCUyMHNpZ25pbmd8ZW58MXwwfHx8MTc4NzI0MDU1MXww&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "man writing on paper",
    by: "Scott Graham",
    href: "https://unsplash.com/@amstram",
  },
  "tpl-trip-planner": {
    src: "https://images.unsplash.com/photo-1650526087824-163941841b52?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8dHJhdmVsJTIwbWFwJTIwcGxhbm5pbmd8ZW58MXwwfHx8MTc4NzI0MDU1Mnww&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "a map of the world with pins on it",
    by: "Leandro Barreto",
    href: "https://unsplash.com/@lpbarreto",
  },
  "tpl-customer-support": {
    src: "https://images.unsplash.com/photo-1553775282-20af80779df7?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8Y3VzdG9tZXIlMjBzdXBwb3J0JTIwaGVhZHNldHxlbnwxfDB8fHwxNzg3MjQwNTUzfDA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "black and brown headset near laptop computer",
    by: "Petr Macháček",
    href: "https://unsplash.com/@machec",
  },
  "tpl-routing": {
    src: "https://images.unsplash.com/photo-1533073526757-2c8ca1df9f1c?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8c2lnbnBvc3QlMjBkaXJlY3Rpb25zfGVufDF8MHx8fDE3ODcyNDA1NTR8MA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "silhouette of road signage during golden hour",
    by: "Javier Allegue Barros",
    href: "https://unsplash.com/@soymeraki",
  },
  "tpl-notion-assistant": {
    src: "https://images.unsplash.com/photo-1580934174026-8142803ebb5b?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8b3JnYW5pemVkJTIwZGVzayUyMG5vdGVzfGVufDF8MHx8fDE3ODcyNDA1NTV8MA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "yellow sticky notes on white wall",
    by: "Paper Textures",
    href: "https://unsplash.com/@inthemakingstudio",
  },
  "tpl-github-notion": {
    src: "https://images.unsplash.com/photo-1515879218367-8466d910aaa4?ixid=M3wxMDAzOTY3fDB8MXxzZWFyY2h8MXx8ZGV2ZWxvcGVyJTIwd29ya3NwYWNlJTIwY29kZXxlbnwxfDB8fHwxNzg3MjQwNTU2fDA&ixlib=rb-4.1.0&w=640&q=80&fm=webp&fit=crop",
    alt: "a computer screen with a bunch of code on it",
    by: "Chris Ried",
    href: "https://unsplash.com/@cdr6934",
  },
};
