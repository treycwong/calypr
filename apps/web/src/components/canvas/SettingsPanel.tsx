"use client";

// The Settings sidebar panel (icon-rail "Settings" tab) — the one place workspace secrets are
// entered. Two sections: Connected Accounts (Tier A OAuth, e.g. Notion) and MCP Servers (Tier B,
// a pasted HTTPS URL + optional bearer). Secrets are sent to the API and stored encrypted; this
// panel only ever displays a name + a lock/tools state, never a token.
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  type Connector,
  createConnector,
  deleteConnector,
  deleteProviderKey,
  listConnectors,
  listProviderKeys,
  notionConnectUrl,
  type ProviderKeyInfo,
  setProviderKey,
  testConnector,
} from "@/lib/api";

// The Tier A catalog shown in the "Add Connection" modal. One entry per OAuth app we can
// connect; `kind` matches Connector.kind so a row can render as already-connected. Adding an
// app here is a UI-only change — the connect handler is wired in SettingsPanel.
const CONNECTOR_CATALOG: { kind: string; label: string; category: string; mark: string }[] = [
  { kind: "notion", label: "Notion", category: "Web", mark: "N" },
];

// Providers a workspace can BYO a key for; labels drive the API Keys section.
const PROVIDER_LABELS: Record<string, string> = {
  openai: "OpenAI",
  anthropic: "Anthropic",
  tavily: "Tavily",
  unsplash: "Unsplash",
};
// `moonshot` is deliberately absent: it is managed in Dashboard → Settings → Workspace, next
// to the assistant-model picker it unlocks, so there is exactly one place to put that key.

export function SettingsPanel() {
  const { toast } = useToast();
  const [connectors, setConnectors] = useState<Connector[]>([]);
  const [loading, setLoading] = useState(true);
  // Tier B add-server form.
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [saving, setSaving] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [connectOpen, setConnectOpen] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [providerKeys, setProviderKeys] = useState<ProviderKeyInfo[]>([]);

  // Listing fails without a DB (local dev) — leave the panel empty, no error toast.
  const refresh = () =>
    listConnectors()
      .then(setConnectors)
      .catch(() => setConnectors([]))
      .finally(() => setLoading(false));
  const refreshKeys = () =>
    listProviderKeys()
      .then(setProviderKeys)
      .catch(() => setProviderKeys([]));

  // Load once on mount; button handlers call refresh() explicitly after mutations.
  useEffect(() => {
    refresh();
    refreshKeys();
  }, []);

  const servers = connectors.filter((c) => c.kind === "mcp");
  // Everything that isn't a pasted MCP endpoint is an OAuth account from the catalog.
  const accounts = connectors.filter((c) => c.kind !== "mcp");

  // Each catalog entry maps to the API call that starts its OAuth handshake.
  const connectApp = async (kind: string) => {
    try {
      if (kind === "notion") {
        window.location.href = await notionConnectUrl();
        return;
      }
      toast("That connection isn't available yet.", "error");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Couldn't start that connection.", "error");
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
      setAddOpen(false);
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

  const saveKey = async (provider: string, key: string) => {
    try {
      await setProviderKey(provider, key);
      await refreshKeys();
      toast(`${PROVIDER_LABELS[provider]} key saved.`, "default");
    } catch {
      toast("Couldn't save that key.", "error");
    }
  };
  const removeKey = async (provider: string) => {
    try {
      await deleteProviderKey(provider);
      await refreshKeys();
    } catch {
      toast("Couldn't remove that key.", "error");
    }
  };

  return (
    <div className="flex flex-col gap-5" data-testid="connectors-panel">
      <section>
        <h3 className="mb-2 font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Connected accounts
        </h3>
        <div className="flex flex-col gap-2" data-testid="connected-accounts">
          {accounts.map((c) => (
            <ConnectorRow
              key={c.id}
              connector={c}
              testing={testing === c.id}
              onTest={() => test(c.id)}
              onRemove={() => remove(c.id)}
            />
          ))}
          {!loading && accounts.length === 0 ? (
            <p className="text-xs text-muted-foreground">No accounts connected yet.</p>
          ) : null}
        </div>
        <Dialog open={connectOpen} onOpenChange={setConnectOpen}>
          <DialogTrigger
            render={<Button size="sm" variant="outline" className="mt-3 w-full" />}
            data-testid="connection-add-open"
          >
            Add Connection
          </DialogTrigger>
          <DialogContent data-testid="connection-dialog">
            <DialogHeader>
              <DialogTitle>Add a connection</DialogTitle>
              <DialogDescription>
                Connect an account with OAuth. You&apos;ll be sent to the app to approve access.
              </DialogDescription>
            </DialogHeader>
            <div className="-mx-1 flex flex-col">
              {CONNECTOR_CATALOG.map((app) => {
                const connected = accounts.some((c) => c.kind === app.kind);
                return (
                  <div
                    key={app.kind}
                    className="flex items-center gap-3 border-b border-border px-1 py-2 last:border-b-0"
                    data-testid={`connection-row-${app.kind}`}
                  >
                    <span className="flex size-7 shrink-0 items-center justify-center rounded-md border border-border font-mono text-xs">
                      {app.mark}
                    </span>
                    <span className="min-w-0 flex-1 truncate">{app.label}</span>
                    <Button
                      size="sm"
                      variant="outline"
                      className="shrink-0"
                      disabled={connected}
                      onClick={() => connectApp(app.kind)}
                      data-testid={`connect-${app.kind}`}
                    >
                      {connected ? "Connected" : "Connect"}
                    </Button>
                  </div>
                );
              })}
            </div>
          </DialogContent>
        </Dialog>
      </section>

      <section>
        <h3 className="mb-2 font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">
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
        <Dialog open={addOpen} onOpenChange={setAddOpen}>
          <DialogTrigger
            render={<Button size="sm" variant="outline" className="mt-3 w-full" />}
            data-testid="mcp-add-open"
          >
            Add MCP Server
          </DialogTrigger>
          <DialogContent data-testid="mcp-add-dialog">
            <DialogHeader>
              <DialogTitle>Add MCP server</DialogTitle>
              <DialogDescription>
                Paste an HTTPS MCP endpoint. The bearer token is stored encrypted and never shown
                again.
              </DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-2">
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
            </div>
            <DialogFooter>
              <DialogClose render={<Button size="sm" variant="outline" />}>Cancel</DialogClose>
              <Button
                size="sm"
                onClick={addServer}
                disabled={saving || !name.trim() || !url.trim()}
                data-testid="mcp-add"
              >
                {saving ? "Saving…" : "Add server"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </section>

      <ApiKeysSection
        providerKeys={providerKeys}
        onSave={saveKey}
        onRemove={removeKey}
      />
    </div>
  );
}

function ApiKeysSection({
  providerKeys,
  onSave,
  onRemove,
}: {
  providerKeys: ProviderKeyInfo[];
  onSave: (provider: string, key: string) => void;
  onRemove: (provider: string) => void;
}) {
  const [provider, setProvider] = useState("");
  const [value, setValue] = useState("");
  const hasKey = providerKeys.find((p) => p.provider === provider)?.has_key ?? false;
  return (
    <section>
      <h3 className="mb-2 font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">
        API keys
      </h3>
      <p className="mb-2 text-xs text-muted-foreground">
        Bring your own provider keys. Stored encrypted; overrides the server key for your runs.
      </p>
      <select
        data-testid="key-provider"
        value={provider}
        onChange={(e) => {
          setProvider(e.target.value);
          setValue("");
        }}
        className="h-8 w-full rounded-md border border-input bg-background px-2 text-sm"
      >
        <option value="">Select a provider…</option>
        {Object.entries(PROVIDER_LABELS).map(([val, label]) => {
          const on = providerKeys.find((p) => p.provider === val)?.has_key;
          return (
            <option key={val} value={val}>
              {label}
              {on ? " • key on file" : ""}
            </option>
          );
        })}
      </select>
      {provider ? (
        <div className="mt-2 flex flex-col gap-2 rounded-md border border-border p-2">
          {hasKey ? (
            <div className="flex items-center justify-between">
              <span
                className="font-mono text-sm tracking-widest text-muted-foreground"
                data-testid="key-masked"
              >
                ••••••••••••
              </span>
              <button
                type="button"
                className="text-xs underline hover:text-foreground"
                onClick={() => onRemove(provider)}
                data-testid="key-remove"
              >
                remove
              </button>
            </div>
          ) : null}
          <div className="flex gap-2">
            <Input
              data-testid="key-input"
              type="password"
              placeholder={hasKey ? "Replace key…" : "Paste key…"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <Button
              size="sm"
              disabled={!value.trim()}
              data-testid="key-save"
              onClick={() => {
                onSave(provider, value.trim());
                setValue("");
              }}
            >
              Save
            </Button>
          </div>
        </div>
      ) : null}
    </section>
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
