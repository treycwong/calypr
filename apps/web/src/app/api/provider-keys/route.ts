// Proxy the BYO provider-key list to the Python API, forwarding the tenant identity.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

export async function GET() {
  const r = await fetch(`${API_URL}/provider-keys`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}
