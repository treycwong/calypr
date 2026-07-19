"use client";

// The Settings sidebar panel (icon-rail "Settings" tab) — the one place workspace secrets are
// entered. Two sections: Connected Accounts (Tier A OAuth, e.g. Notion) and MCP Servers (Tier B,
// a pasted HTTPS URL + optional bearer). Secrets are sent to the API and stored encrypted; this
// panel only ever displays a name + a lock/tools state, never a token.
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  type Connector,
  createConnector,
  deleteConnector,
  listConnectors,
  notionConnectUrl,
  testConnector,
} from "@/lib/api";

export function SettingsPanel() {
  const { toast } = useToast();
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  // Tier B add-server form.
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);

  // Listing fails without a DB (local dev) — leave the panel empty, no error toast.
  const refresh = () =>
    listConnectors()
      .then(setConnectors)
      .catch(() => setConnectors([]))
      .finally(() => setLoading(false));

  // Load once on mount; button handlers call refresh() explicitly after mutations.
  useEffect(() => {
    refresh();
  }, []);

  const notion = connectors.filter((c) => c.kind === "notion");
  const servers = connectors.filter((c) => c.kind === "mcp");

  const connectNotion = async () => {
    try {
      window.location.href = await notionConnectUrl();
    } catch (e) {
      toast(e instanceof Error ? e.message : "Couldn't start Notion connect.", "error");
    }
  };

  const addServer = async () => {
    if (!name.trim() || !url.trim()) return;
    setSaving(true);
    try {
      await createConnector({ name: name.trim(), url: url.trim(), secret });
      setName("");
      setUrl("");
      setSecret("");
      await refresh();
      toast("MCP server saved.", "default");
    } catch {
      toast("Couldn't save that server — check the URL.", "error");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: string) => {
    try {
      await deleteConnector(id);
      await refresh();
    } catch {
      toast("Couldn't remove that connector.", "error");
    }
  };

  const test = async (id: string) => {
    setTesting(id);
    try {
      const res = await testConnector(id);
      toast(
        res.ok ? `Connected — ${res.tools.length} tool(s) found.` : (res.error ?? "Test failed."),
        res.ok ? "default" : "error",
      );
    } catch {
      toast("Test failed.", "error");
    } finally {
      setTesting(null);
    }
  };

  return (
    <div className="flex flex-col gap-5" data-testid="settings-panel">
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Connected accounts
        </h3>
        {notion.length === 0 ? (
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            onClick={connectNotion}
            data-testid="connect-notion"
          >
            Connect Notion
          </Button>
        ) : (
          notion.map((c) => (
            <ConnectorRow
              key={c.id}
              connector={c}
              testing={testing === c.id}
              onTest={() => test(c.id)}
              onRemove={() => remove(c.id)}
            />
          ))
        )}
      </section>

      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          MCP servers
        </h3>
        <div className="flex flex-col gap-2" data-testid="mcp-servers">
          {servers.map((c) => (
            <ConnectorRow
              key={c.id}
              connector={c}
              testing={testing === c.id}
              onTest={() => test(c.id)}
              onRemove={() => remove(c.id)}
            />
          ))}
          {!loading && servers.length === 0 ? (
            <p className="text-xs text-muted-foreground">No servers yet.</p>
          ) : null}
        </div>
        <div className="mt-3 flex flex-col gap-2 rounded-md border border-border p-2">
          <Input
            data-testid="mcp-name"
            placeholder="Name (e.g. My server)"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <Input
            data-testid="mcp-url"
            type="url"
            placeholder="https://your-mcp-server/mcp"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
          />
          <Input
            data-testid="mcp-secret"
            type="password"
            placeholder="Bearer token (optional)"
            value={secret}
            onChange={(e) => setSecret(e.target.value)}
          />
          <Button
            size="sm"
            onClick={addServer}
            disabled={saving || !name.trim() || !url.trim()}
            data-testid="mcp-add"
          >
            {saving ? "Saving…" : "Add server"}
          </Button>
        </div>
      </section>
    </div>
  );
}

function ConnectorRow({
  connector,
  testing,
  onTest,
  onRemove,
}: {
  connector: Connector;
  testing: boolean;
  onTest: () => void;
  onRemove: () => void;
}) {
  const host = connector.url ? safeHost(connector.url) : "";
  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-border px-2 py-1.5">
      <div className="min-w-0">
        <div className="truncate text-sm">{connector.name}</div>
        {host ? <div className="truncate text-xs text-muted-foreground">{host}</div> : null}
      </div>
      <div className="flex shrink-0 gap-1">
        <Button size="sm" variant="ghost" onClick={onTest} disabled={testing}>
          {testing ? "…" : "Test"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onRemove}>
          Remove
        </Button>
      </div>
    </div>
  );
}

function safeHost(url: string): string {
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}
