// Notion's OAuth redirect lands here (top-level browser navigation, so it carries the user's
// cookie). We forward the code to the Python API for the token exchange + encrypted storage,
// then redirect the browser back to the canvas with a status flag. The code never reaches the
// client bundle — it's read here server-side and posted straight to the API.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

export async function GET(req: Request) {
  const url = new URL(req.url);
  const code = url.searchParams.get("code");
  // The CSRF state we issued when the flow started; Notion echoes it back unchanged. The API
  // rejects the callback if it is missing or doesn't belong to this workspace.
  const state = url.searchParams.get("state") ?? "";
  const error = url.searchParams.get("error");
  const done = (status: string) =>
    Response.redirect(new URL(`/canvas?connected=notion&status=${status}`, url.origin), 303);

  if (error || !code) return done(error ? "denied" : "missing_code");

  const r = await fetch(`${API_URL}/connectors/notion/callback`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body: JSON.stringify({ code, state }),
  });
  return done(r.ok ? "ok" : "error");
}
