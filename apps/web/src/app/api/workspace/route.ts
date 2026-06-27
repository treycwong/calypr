// Proxy the current workspace (rename) to the Python API, forwarding the tenant identity.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

export async function PATCH(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/workspaces/current`, {
    method: "PATCH",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body,
  });
  return json(await r.text(), r.status);
}
