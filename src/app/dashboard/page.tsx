import Link from "next/link";

export default function DashboardPage() {
  return (
    <div>
      <p className="text-muted-foreground mb-8">
        Welcome to your Calypr dashboard. Manage your templates, settings, and
        support requests.
      </p>
      <div className="grid gap-4 sm:grid-cols-3">
        <Link
          href="/dashboard/templates"
          className="rounded-xl border border-border p-5 hover:bg-muted/30 transition-colors"
        >
          <h3 className="font-medium text-sm mb-1">My Templates</h3>
          <p className="text-xs text-muted-foreground">
            View purchased templates and GitHub repos
          </p>
        </Link>
        <Link
          href="/dashboard/support"
          className="rounded-xl border border-border p-5 hover:bg-muted/30 transition-colors"
        >
          <h3 className="font-medium text-sm mb-1">Support</h3>
          <p className="text-xs text-muted-foreground">
            Get help or report an issue
          </p>
        </Link>
        <Link
          href="/dashboard/customize"
          className="rounded-xl border border-border p-5 hover:bg-muted/30 transition-colors"
        >
          <h3 className="font-medium text-sm mb-1">White-Glove</h3>
          <p className="text-xs text-muted-foreground">
            Let us customize your template
          </p>
        </Link>
      </div>
    </div>
  );
}
