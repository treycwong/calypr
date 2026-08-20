import { permanentRedirect } from "next/navigation";

// Renamed to /dashboard/workflows. Kept as a redirect rather than deleted: the nav entry has
// shipped, so this path is in browser histories and bookmarks.
export default function TemplatesPage() {
  permanentRedirect("/dashboard/workflows");
}
