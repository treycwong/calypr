// Proxy "start Notion OAuth" to the Python API — returns the authorize URL the client opens.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

export async function GET() {
  const r = await fetch(`${API_URL}/connectors/notion/connect`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}
