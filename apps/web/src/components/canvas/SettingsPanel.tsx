"use client";

// The Settings sidebar panel (icon-rail "Settings" tab) — the one place workspace secrets are
// entered. Two sections: Connected Accounts (Tier A OAuth, e.g. Notion) and API Keys. Secrets are
// sent to the API and stored encrypted; this panel only ever displays a name + a lock/tools
// state, never a token.
//
// Tier B ("paste your own MCP server URL") is deliberately not offered here — see the comment
// above the `servers` section below. The backend route still exists and still works.
import { Eye, EyeOff, MoreHorizontal, Plus } from "lucide-react";
import { useEffect, useState } from "react";

import { BrandMark } from "@/components/canvas/BrandMark";
import { TILE_CLASS } from "@/components/canvas/Palette";
import { DeleteConfirm } from "@/components/canvas/playground/DeleteConfirm";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import {
  type Connector,
  createGithubConnector,
  deleteConnector,
  deleteProviderKey,
  listConnectors,
  listProviderKeys,
  notionConnectUrl,
  type ProviderKeyInfo,
  setProviderKey,
  testConnector,
} from "@/lib/api";
import { invalidateConnectors } from "@/lib/use-connectors";

// The Tier A catalog shown in the "Add Connection" modal. One entry per app we can connect;
// `kind` matches Connector.kind so a row can render as already-connected. Adding an app here is
// a UI-only change — the connect handler is wired in SettingsPanel.
//
// `auth` says how the handshake happens: "oauth" redirects to the provider's consent screen,
// "token" collects a token in a form here (GitHub hosts its own MCP server and takes a PAT, so
// there is no redirect to make).
const CONNECTOR_CATALOG: {
  kind: string;
  label: string;
  category: string;
  mark: string;
  auth: "oauth" | "token";
}[] = [
  { kind: "notion", label: "Notion", category: "Web", mark: "N", auth: "oauth" },
  { kind: "github", label: "GitHub", category: "Dev", mark: "GH", auth: "token" },
];

// GitHub scopes its MCP tools by URL path; these are the surfaces worth offering. "" is
// GitHub's own default set. Mirrors GITHUB_TOOLSETS in the API schema.
const GITHUB_TOOLSET_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "Default (recommended)" },
  { value: "repos", label: "Repositories" },
  { value: "issues", label: "Issues" },
  { value: "pull_requests", label: "Pull requests" },
  { value: "actions", label: "Actions" },
  { value: "all", label: "Everything" },
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
  const [connectOpen, setConnectOpen] = useState(false);
  const [testing, setTesting] = useState<string | null>(null);
  const [providerKeys, setProviderKeys] = useState<ProviderKeyInfo[]>([]);
  const [githubOpen, setGithubOpen] = useState(false);
  // The account awaiting a Disconnect confirmation. Disconnecting is one menu click from Test,
  // and rebuilding an OAuth connection costs a round trip through the provider's consent screen,
  // so it asks first.
  const [disconnecting, setDisconnecting] = useState<Connector | null>(null);

  // Listing fails without a DB (local dev) — leave the panel empty, no error toast.
  const refresh = () => {
    // This panel is where connectors change, so it owns clearing the shared cache the Tool
    // node's label and dropdown read from — otherwise a connector added here stays invisible
    // on the canvas until a reload.
    invalidateConnectors();
    return listConnectors()
      .then(setConnectors)
      .catch(() => setConnectors([]))
      .finally(() => setLoading(false));
  };
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

  // Each catalog entry maps to the API call that starts its handshake — a redirect for OAuth
  // apps, or a local form for token apps.
  const connectApp = async (kind: string) => {
    try {
      if (kind === "github") {
        setConnectOpen(false);
        setGithubOpen(true);
        return;
      }
      if (kind === "notion") {
        // `assign` rather than `location.href = …`: same navigation, but it isn't a write to a
        // value outside the component, which the react-hooks/immutability rule (correctly)
        // flags — that lint error predates this change and was the only one in the app.
        window.location.assign(await notionConnectUrl());
        return;
      }
      toast("That connection isn't available yet.", "error");
    } catch (e) {
      toast(e instanceof Error ? e.message : "Couldn't start that connection.", "error");
    }
  };

  const remove = async (id: string) => {
    try {
      await deleteConnector(id);
      await refresh();
    } catch {
      toast("Couldn't remove that connector.", "error");
    } finally {
      setDisconnecting(null);
    }
  };

  // "API key" / "Reconnect" both land here: the API has no update endpoint for a connector, so
  // changing the credential means running the original handshake again. For GitHub that is the
  // PAT form (saving replaces the stored token); for Notion it is the OAuth redirect. Either way
  // the user ends up re-authorising, which is what the menu item promises.
  const reconnect = (c: Connector) => void connectApp(c.kind);

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
        {/* Add lives on the header rather than as a tile in the grid: as a tile it was one more
            card competing with the accounts, and it moved every time one was added or removed.
            On the header it sits still, and the section title says what it adds. */}
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Connected accounts
          </h3>
          <button
            type="button"
            onClick={() => setConnectOpen(true)}
            data-testid="connection-add-open"
            aria-label="Add connection"
            title="Add connection"
            className="-my-1 shrink-0 rounded-md p-1 text-muted-foreground transition hover:bg-white/10 hover:text-foreground"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>
        {/* The same two-column grid the Blocks and Templates panels use, so every sidebar panel
            reads as one system. */}
        <div className="grid grid-cols-2 gap-2" data-testid="connected-accounts">
          {accounts.map((c) => (
            <ConnectorCard
              key={c.id}
              connector={c}
              testing={testing === c.id}
              onTest={() => test(c.id)}
              onRemove={() => setDisconnecting(c)}
              onCredential={() => reconnect(c)}
            />
          ))}
        </div>
        {!loading && accounts.length === 0 ? (
          <p className="text-xs text-muted-foreground">No accounts connected yet.</p>
        ) : null}
        <Dialog open={connectOpen} onOpenChange={setConnectOpen}>
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
        <GithubConnectDialog
          open={githubOpen}
          onOpenChange={setGithubOpen}
          onSaved={async () => {
            setGithubOpen(false);
            await refresh();
            toast("GitHub connected.", "default");
          }}
          onError={() => toast("Couldn't save that GitHub token.", "error")}
        />
      </section>

      {/* Tier B ("paste your own MCP server URL") is hidden from Settings: it's a
          bring-your-own-server path, and the servers people actually run are on their own
          machine at localhost, which this cloud backend can't reach (and blocks reaching, as an
          SSRF guard). App connections — Notion above — are the web-shaped path and stay.

          A workspace that already saved servers still sees them, so nothing is orphaned: they
          remain testable and removable, there's just no way to add more. Empty (every workspace
          today) renders nothing at all. The Tool node's connector dropdown is untouched — Notion
          rides the same `provider: "mcp"` plumbing and would break if this were ripped out. */}
      {servers.length > 0 ? (
        <section>
          <h3 className="mb-2 font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">
            MCP servers
          </h3>
          <p className="mb-2 text-xs text-muted-foreground">
            Adding new servers is paused while we focus on app connections. Your existing servers
            keep working.
          </p>
          <div className="grid grid-cols-2 gap-2" data-testid="mcp-servers">
            {servers.map((c) => (
              <ConnectorCard
                key={c.id}
                connector={c}
                testing={testing === c.id}
                onTest={() => test(c.id)}
                // No `onCredential`: a pasted MCP endpoint has no handshake to re-run — it is a
                // URL someone typed, and there is no add form for these any more.
                onRemove={() => setDisconnecting(c)}
              />
            ))}
          </div>
        </section>
      ) : null}

      <ApiKeysSection
        providerKeys={providerKeys}
        onSave={saveKey}
        onRemove={removeKey}
      />

      <DeleteConfirm
        open={disconnecting !== null}
        testId="connector-disconnect-confirm"
        title="Disconnect this account?"
        confirmLabel="Continue"
        description={
          `Calypr will forget its credential for ${disconnecting?.name ?? "this account"}. ` +
          "Agents using it will stop working until you connect again — and connecting again means " +
          "authorising through the provider."
        }
        onConfirm={() => disconnecting && void remove(disconnecting.id)}
        onOpenChange={(o) => !o && setDisconnecting(null)}
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
  // `""` = no dialog open. A tile opens the dialog for that provider.
  const [provider, setProvider] = useState("");
  const info = providerKeys.find((p) => p.provider === provider) ?? null;
  return (
    <section>
      <h3 className="mb-2 font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Models
      </h3>
      <p className="mb-2 text-xs text-muted-foreground">
        Bring your own provider keys. Stored encrypted; overrides the server key for your runs.
      </p>
      {/* A tile per provider rather than a dropdown: four options behind a `<select>` hid which
          ones already had a key, which is the only thing you come to this section to find out.
          Only the ones that *do* say so — a "No key" caption under every unkeyed provider was
          three quarters of the grid repeating the absence of news. */}
      <div className="grid grid-cols-2 gap-2" data-testid="key-providers">
        {Object.entries(PROVIDER_LABELS).map(([val, label]) => {
          const on = providerKeys.find((p) => p.provider === val)?.has_key;
          return (
            <button
              key={val}
              type="button"
              data-testid={`key-provider-${val}`}
              onClick={() => setProvider(val)}
              className={TILE_CLASS}
            >
              <BrandMark kind={val} className="h-5 w-5" />
              <span className="w-full truncate text-xs font-medium">{label}</span>
              {on ? (
                <span className="flex items-center gap-1 text-[11px] text-muted-foreground">
                  <span
                    className="h-1.5 w-1.5 rounded-full bg-emerald-400"
                    data-testid={`key-onfile-${val}`}
                  />
                  Key on file
                </span>
              ) : null}
            </button>
          );
        })}
      </div>

      <ProviderKeyDialog
        provider={provider}
        info={info}
        onOpenChange={(open) => !open && setProvider("")}
        onSave={onSave}
        onRemove={onRemove}
      />
    </section>
  );
}

/** Add, replace or remove one provider's BYO key.
 *
 * **The saved key is never shown, because the server has never been able to send it.** It is
 * Fernet ciphertext decrypted only at run time, and `ProviderKeySet` is documented write-only.
 * What is shown instead is `key_hint` — the last 4 characters, stored in the clear at write time
 * (migration `0020`) — which answers the question people actually have here: *is the key on file
 * the one I think it is?* The eye toggle reveals what **you are typing**, so you can check a
 * paste before saving; there is nothing to un-hide about the stored one. */
function ProviderKeyDialog({
  provider,
  info,
  onOpenChange,
  onSave,
  onRemove,
}: {
  provider: string;
  info: ProviderKeyInfo | null;
  onOpenChange: (open: boolean) => void;
  onSave: (provider: string, key: string) => void;
  onRemove: (provider: string) => void;
}) {
  const [value, setValue] = useState("");
  const [reveal, setReveal] = useState(false);
  const hasKey = info?.has_key ?? false;
  const hint = info?.key_hint ?? null;
  const label = PROVIDER_LABELS[provider] ?? provider;

  const close = () => {
    setValue("");
    setReveal(false);
    onOpenChange(false);
  };

  return (
    <Dialog open={!!provider} onOpenChange={(o) => (o ? onOpenChange(true) : close())}>
      <DialogContent data-testid="key-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <BrandMark kind={provider} className="h-5 w-5" />
            {label} API key
          </DialogTitle>
          <DialogDescription>
            {hasKey
              ? "Saving replaces the key on file. Runs pick up the new one immediately."
              : `Paste your ${label} key. It's encrypted on our server and never shown again.`}
          </DialogDescription>
        </DialogHeader>

        {hasKey ? (
          <div className="flex items-center justify-between gap-2 rounded-md border border-border px-2.5 py-2">
            <span className="font-mono text-sm text-muted-foreground" data-testid="key-masked">
              {/* The dots are a fixed-width mask, not the key's real length — that would leak
                  something about the secret for nothing. */}
              ••••••••••••{hint ? ` ${hint}` : ""}
            </span>
            <button
              type="button"
              className="shrink-0 text-xs text-muted-foreground underline hover:text-foreground"
              onClick={() => onRemove(provider)}
              data-testid="key-remove"
            >
              Remove
            </button>
          </div>
        ) : null}

        <div className="flex gap-2">
          <div className="relative flex-1">
            <Input
              data-testid="key-input"
              type={reveal ? "text" : "password"}
              className="pr-8"
              placeholder={hasKey ? "Replace key…" : "Paste key…"}
              value={value}
              onChange={(e) => setValue(e.target.value)}
            />
            <button
              type="button"
              onClick={() => setReveal((r) => !r)}
              aria-label={reveal ? "Hide key" : "Show key"}
              title={reveal ? "Hide what you typed" : "Show what you typed"}
              data-testid="key-reveal"
              className="absolute inset-y-0 right-0 flex w-8 items-center justify-center text-muted-foreground transition hover:text-foreground"
            >
              {reveal ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={close} data-testid="key-cancel">
            Cancel
          </Button>
          <Button
            disabled={!value.trim()}
            data-testid="key-save"
            onClick={() => {
              onSave(provider, value.trim());
              close();
            }}
          >
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** Collect a GitHub PAT and the scope it may be used at.
 *
 * GitHub hosts its own MCP server, so connecting is a token paste rather than a redirect. The
 * token is posted straight to the API (encrypted there) and never kept in component state after
 * save. Read-only is on by default: an agent that can push commits or open PRs by accident is a
 * bad first run, and the box is one click away when that is what the user wants. */
function GithubConnectDialog({
  open,
  onOpenChange,
  onSaved,
  onError,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
  onError: () => void;
}) {
  const [pat, setPat] = useState("");
  const [toolset, setToolset] = useState("");
  const [readonly, setReadonly] = useState(true);
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      await createGithubConnector({ pat: pat.trim(), toolset, readonly });
      setPat("");
      setToolset("");
      setReadonly(true);
      onSaved();
    } catch {
      onError();
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="github-dialog">
        <DialogHeader>
          <DialogTitle>Connect GitHub</DialogTitle>
          <DialogDescription>
            Paste a fine-grained personal access token. It&apos;s encrypted on our server and
            never shown again.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <Input
            type="password"
            placeholder="github_pat_…"
            value={pat}
            onChange={(e) => setPat(e.target.value)}
            data-testid="github-pat"
          />
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Tools
            <select
              className="h-8 rounded-md border border-border bg-transparent px-2 text-sm text-foreground"
              value={toolset}
              onChange={(e) => setToolset(e.target.value)}
              data-testid="github-toolset"
            >
              {GITHUB_TOOLSET_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <input
              type="checkbox"
              checked={!readonly}
              onChange={(e) => setReadonly(!e.target.checked)}
              data-testid="github-allow-writes"
            />
            Allow writes (create issues, comments, pull requests)
          </label>
          <Button
            size="sm"
            disabled={!pat.trim() || saving}
            onClick={save}
            data-testid="github-save"
          >
            {saving ? "Connecting…" : "Connect"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/** A connected account, as a tile: the app's mark on top, its name, and a live status line.
 *
 * Test and Disconnect moved into a 3-dot menu. As bare buttons they sat at the same weight as the
 * account name, which put "Remove" one mis-click from a connection that takes an OAuth round trip
 * to rebuild — and Test, which most people press once, was permanently on screen. */
function ConnectorCard({
  connector,
  testing,
  onTest,
  onRemove,
  onCredential,
}: {
  connector: Connector;
  testing: boolean;
  onTest: () => void;
  onRemove: () => void;
  /** Re-run the handshake. Omitted for connectors that have none (a pasted MCP URL), which drops
   *  the menu item rather than showing one that does nothing. */
  onCredential?: () => void;
}) {
  const host = connector.url ? safeHost(connector.url) : "";
  // How this app was connected decides what "change the credential" can even mean. A token app
  // (GitHub) can be handed a new PAT; an OAuth app (Notion) has no key to edit — the only way to
  // change what we hold is to walk its consent screen again.
  const auth = CONNECTOR_CATALOG.find((a) => a.kind === connector.kind)?.auth;
  return (
    <div
      // The brand mark carries the identity, so the account name is a tooltip rather than a line
      // of text: at tile width most names truncated anyway, and two lines of chrome above a
      // one-word status made the card taller than everything it sits next to.
      title={[connector.name, host].filter(Boolean).join(" · ")}
      // The same tile the Blocks and Templates grids use, so a card here is the same shape and
      // height as one two tabs over. Padding-sized boxes came out visibly squatter.
      className={`${TILE_CLASS} relative`}
      data-testid={`connector-card-${connector.kind}`}
    >
      <BrandMark kind={connector.kind} className="h-5 w-5" />
      <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
        {testing ? (
          "Testing…"
        ) : (
          <>
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
            Connected
          </>
        )}
      </div>
      <DropdownMenu>
        <DropdownMenuTrigger
          aria-label={`${connector.name} actions`}
          data-testid={`connector-menu-${connector.kind}`}
          className="absolute top-1 right-1 rounded-md p-1 text-muted-foreground transition hover:bg-white/10 hover:text-foreground data-[popup-open]:bg-white/10 data-[popup-open]:text-foreground"
        >
          <MoreHorizontal className="h-3.5 w-3.5" />
        </DropdownMenuTrigger>
        {/* Opens to the right of the card rather than below it: anchored under the trigger, the
            menu covered the card's own mark and status, so you couldn't see which account you
            were about to disconnect. */}
        <DropdownMenuContent side="right" align="start" className="w-auto min-w-36">
          <DropdownMenuItem
            data-testid={`connector-test-${connector.kind}`}
            onClick={onTest}
            disabled={testing}
          >
            Test
          </DropdownMenuItem>
          {onCredential ? (
            <DropdownMenuItem
              data-testid={`connector-credential-${connector.kind}`}
              onClick={onCredential}
            >
              {auth === "token" ? "API key" : "Reconnect"}
            </DropdownMenuItem>
          ) : null}
          <DropdownMenuItem
            variant="destructive"
            data-testid={`connector-disconnect-${connector.kind}`}
            onClick={onRemove}
          >
            Disconnect
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
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
