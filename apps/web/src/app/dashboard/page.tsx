import Link from "next/link";

import { AccountControl } from "@/components/auth/account-control";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { getSession } from "@/lib/auth";

type Health = { status: string; service?: string };

async function getApiHealth(): Promise<Health> {
  const base = process.env.CALYPR_API_URL ?? "http://localhost:8000";
  try {
    const res = await fetch(`${base}/health`, { cache: "no-store" });
    if (!res.ok) return { status: "unreachable" };
    return (await res.json()) as Health;
  } catch {
    return { status: "unreachable" };
  }
}

export default async function DashboardPage() {
  const session = await getSession();
  const health = await getApiHealth();
  const online = health.status === "ok";

  return (
    <main className="mx-auto w-full max-w-5xl flex-1 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Signed in as {session?.userId ?? "unknown"}
          </p>
        </div>
        <AccountControl />
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              Agent Canvas
              <Badge variant="secondary">Phase 2</Badge>
            </CardTitle>
            <CardDescription>Design an agent on the visual canvas.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/canvas"
              className={buttonVariants()}
              data-testid="open-canvas"
            >
              Open canvas
            </Link>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              API
              <Badge
                variant={online ? "default" : "destructive"}
                data-testid="api-status"
              >
                {online ? "online" : "offline"}
              </Badge>
            </CardTitle>
            <CardDescription>FastAPI runtime health.</CardDescription>
          </CardHeader>
          <CardContent className="font-mono text-xs text-muted-foreground">
            {health.service ?? "calypr-api"} · {health.status}
          </CardContent>
        </Card>
      </div>
    </main>
  );
}
