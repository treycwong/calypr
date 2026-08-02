// List the account's workspaces (the sidebar switcher) and create new ones.
import { internalHeaders } from "@/lib/api-headers";

const API_URL = process.env.CALYPR_API_URL ?? "http://localhost:8000";

export const dynamic = "force-dynamic";

const json = (text: string, status: number) =>
  new Response(text, { status, headers: { "content-type": "application/json" } });

export async function GET() {
  const r = await fetch(`${API_URL}/workspaces`, {
    cache: "no-store",
    headers: await internalHeaders(),
  });
  return json(await r.text(), r.status);
}

export async function POST(req: Request) {
  const body = await req.text();
  const r = await fetch(`${API_URL}/workspaces`, {
    method: "POST",
    headers: { "content-type": "application/json", ...(await internalHeaders()) },
    body,
  });
  // 402 (workspace_cap) passes through with its body intact — the dialog renders the message.
  return json(await r.text(), r.status);
}
