"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";

type Purchase = {
  id: string;
  template_id: string;
  template_name: string;
  repo: string;
  latest_version: string;
  github_repo_access: boolean;
  purchased_at: string;
};

export default function DashboardTemplatesPage() {
  const { isLoaded, userId } = useAuth();
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isLoaded || !userId) return;
    fetch("/api/user")
      .then((r) => r.json())
      .then((data) => {
        setPurchases(data.purchases || []);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  }, [isLoaded, userId]);

  if (!isLoaded || loading) {
    return <p className="text-sm text-muted-foreground">Loading...</p>;
  }

  if (purchases.length === 0) {
    return (
      <div className="text-center py-16">
        <h2 className="text-lg font-medium mb-2">No templates yet</h2>
        <p className="text-sm text-muted-foreground mb-6">
          Browse our catalog and purchase your first template.
        </p>
        <Link
          href="/templates"
          className="text-sm text-foreground underline underline-offset-4 hover:text-muted-foreground"
        >
          Browse Templates
        </Link>
      </div>
    );
  }

  return (
    <div>
      <h2 className="text-lg font-medium mb-4">My Templates</h2>
      <div className="space-y-3">
        {purchases.map((p) => (
          <div
            key={p.id}
            className="rounded-xl border border-border p-5 flex items-center justify-between"
          >
            <div>
              <div className="flex items-center gap-2 mb-1">
                <h3 className="font-medium text-sm">{p.template_name}</h3>
                {!p.github_repo_access && (
                  <Badge variant="secondary" className="text-xs">
                    Access Pending
                  </Badge>
                )}
              </div>
              <p className="text-xs text-muted-foreground">
                v{p.latest_version} &middot; Purchased{" "}
                {new Date(p.purchased_at).toLocaleDateString()}
              </p>
            </div>
            {p.github_repo_access && (
              <Link
                href={`https://github.com/${p.repo}`}
                target="_blank"
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Open Repo &rarr;
              </Link>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
