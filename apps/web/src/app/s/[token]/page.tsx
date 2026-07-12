import { ShareRunner } from "./ShareRunner";

export const dynamic = "force-dynamic";

// Public share page: /s/{token}. Anyone (logged-out) can open it, see the agent's name, and run
// it — the GraphSpec never reaches the client. The name fetch + run happen client-side against
// the anonymous /api/s/* proxies.
export default async function SharePage({
  params,
}: {
  params: Promise<{ token: string }>;
}) {
  const { token } = await params;
  return <ShareRunner token={token} />;
}
