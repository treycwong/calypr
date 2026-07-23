"use client";

import { useEffect, useState } from "react";

import Link from "next/link";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type AssistantModelOption,
  deleteProviderKey,
  getWorkspace,
  listAssistantModels,
  type LLMProvider,
  listLLMProviders,
  renameWorkspace,
  setAssistantModel,
  setDefaultModel as setDefaultModelApi,
  setProviderKey,
} from "@/lib/api";
import { useProviderKeys } from "@/lib/use-provider-keys";

/** What each tier means in the one place a user goes looking. `beta` keeps code export because
 * we don't take a shipped feature back off the cohort already using it. */
const PLAN_COPY: Record<string, { label: string; blurb: string }> = {
  free: {
    label: "Free",
    blurb: "3 projects. Code export is a Plus feature.",
  },
  beta: {
    label: "Beta",
    blurb: "Early access, including code export — editing the generated Python and applying it back to the canvas.",
  },
  plus: {
    label: "Plus",
    blurb: "20 projects and code export — the generated Python is yours to edit, download and run anywhere.",
  },
};

export function SettingsView({
  name,
  email,
  image,
}: {
  name: string;
  email: string;
  image: string | null;
}) {
  const initials = (name || email || "U").slice(0, 2).toUpperCase();
  const [wsName, setWsName] = useState("");
  const [savedMsg, setSavedMsg] = useState("");
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<AssistantModelOption[]>([]);
  const [modelMsg, setModelMsg] = useState("");
  // The canvas default is a separate setting from the assistant's — different surfaces, and a
  // user may well want a cheap model drafting graphs and a stronger one running them.
  const [defaultModel, setDefaultModel] = useState("");
  const [defaultModelMsg, setDefaultModelMsg] = useState("");
  // The entitlement tier, so "why can/can't I export my code?" has a visible answer.
  const [plan, setPlan] = useState("free");
  // Enforcement without a display is a limit nobody can plan around — a run refused for
  // "no credits" is only actionable if you can see where you stood.
  const [credits, setCredits] = useState<{
    allowance: number;
    remaining: number;
    used: number;
  } | null>(null);
  const { keyed, refresh: refreshKeys } = useProviderKeys();
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  // Per-provider status line, so saving an OpenAI key doesn't flash a message on the Kimi row.
  const [keyMsg, setKeyMsg] = useState<Record<string, string>>({});

  const setMsg = (provider: string, text: string) =>
    setKeyMsg((prev) => ({ ...prev, [provider]: text }));

  useEffect(() => {
    getWorkspace()
      .then((w) => {
        setWsName(w.name);
        setModel(w.assistant_model ?? "");
        setDefaultModel(w.default_model ?? "");
        setPlan(w.plan ?? "free");
        setCredits(w.credits ?? null);
      })
      .catch(() => {});
    listAssistantModels()
      .then(setModelOptions)
      .catch(() => setModelOptions([]));
    listLLMProviders()
      .then(setProviders)
      .catch(() => setProviders([]));
  }, []);

  async function saveModel(value: string) {
    const previous = model;
    setModel(value); // optimistic: the select shouldn't stall on the round-trip
    setModelMsg("Saving…");
    try {
      const w = await setAssistantModel(value);
      setModel(w.assistant_model ?? "");
      setModelMsg("Saved ✓");
    } catch {
      setModel(previous); // put the picker back on what's actually stored
      setModelMsg("Save failed");
    }
  }

  async function saveDefaultModel(value: string) {
    const previous = defaultModel;
    setDefaultModel(value); // optimistic, like the assistant picker above
    setDefaultModelMsg("Saving…");
    try {
      const w = await setDefaultModelApi(value);
      setDefaultModel(w.default_model ?? "");
      setDefaultModelMsg("Saved ✓");
    } catch {
      setDefaultModel(previous);
      setDefaultModelMsg("Save failed");
    }
  }

  async function saveKey(provider: string, key: string) {
    setMsg(provider, "Saving…");
    try {
      await setProviderKey(provider, key);
      refreshKeys(); // unlocks that provider's frontier model in the picker above
      setMsg(provider, "Key saved ✓");
    } catch {
      setMsg(provider, "Save failed");
    }
  }

  async function removeKey(provider: string) {
    setMsg(provider, "Removing…");
    try {
      await deleteProviderKey(provider);
      refreshKeys();
      // Removing a key un-selects the model it unlocked, so the stored setting can't point at
      // something every run would now refuse.
      const orphaned = modelOptions.find(
        (o) => o.value === model && o.byo_provider === provider,
      );
      if (orphaned) await saveModel("");
      setMsg(provider, "Key removed");
    } catch {
      setMsg(provider, "Remove failed");
    }
  }

  async function saveWorkspace() {
    setSavedMsg("Saving…");
    try {
      const w = await renameWorkspace(wsName.trim() || "Workspace");
      setWsName(w.name);
      setSavedMsg("Saved ✓");
    } catch {
      setSavedMsg("Save failed");
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-8">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Tabs defaultValue="account" className="mt-6">
        <TabsList>
          <TabsTrigger value="account" data-testid="tab-account">
            Account
          </TabsTrigger>
          <TabsTrigger value="workspace" data-testid="tab-workspace">
            Workspace
          </TabsTrigger>
        </TabsList>

        <TabsContent value="account" className="mt-4">
          <div className="rounded-lg border border-border p-5">
            <div className="flex items-center gap-3">
              <Avatar className="h-12 w-12">
                {image ? <AvatarImage src={image} alt="" /> : null}
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{name || "—"}</span>
                  <Badge
                    variant={plan === "free" ? "outline" : "default"}
                    data-testid="account-plan"
                  >
                    {PLAN_COPY[plan]?.label ?? plan}
                  </Badge>
                </div>
                <div className="truncate text-xs text-muted-foreground">{email}</div>
              </div>
            </div>
            <Separator className="my-4" />
            {/* What the tier actually gets you, rather than a bare word: "Beta" on its own
                tells you nothing about whether you can export your code. */}
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-xs text-muted-foreground">
                {PLAN_COPY[plan]?.blurb ?? "Your workspace tier."}
              </p>
              {plan === "free" ? (
                <Link
                  href="/pricing"
                  className="text-xs font-medium underline underline-offset-4"
                  data-testid="account-upgrade"
                >
                  Upgrade to Plus
                </Link>
              ) : null}
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Your account details come from your sign-in provider (GitHub).
            </p>
          </div>
        </TabsContent>

        <TabsContent value="workspace" className="mt-4">
          <div className="rounded-lg border border-border p-5">
            <label htmlFor="ws-name" className="text-sm font-medium">
              Workspace name
            </label>
            <p className="mt-0.5 text-xs text-muted-foreground">
              The name of your personal workspace.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <Input
                id="ws-name"
                className="max-w-xs"
                value={wsName}
                onChange={(e) => setWsName(e.target.value)}
                data-testid="ws-name"
              />
              <Button size="sm" onClick={saveWorkspace} data-testid="ws-save">
                Save
              </Button>
              {savedMsg ? (
                <span className="text-xs text-muted-foreground">{savedMsg}</span>
              ) : null}
            </div>
          </div>

          {credits && credits.allowance > 0 ? (
            <div className="mt-4 rounded-lg border border-border p-5" data-testid="ws-credits">
              <div className="flex items-baseline justify-between gap-4">
                <h2 className="text-sm font-medium">Usage this month</h2>
                <span className="text-xs text-muted-foreground">
                  <span data-testid="ws-credits-remaining" className="text-foreground">
                    {credits.remaining.toLocaleString()}
                  </span>{" "}
                  of {credits.allowance.toLocaleString()} credits left
                </span>
              </div>
              <div
                className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted"
                role="progressbar"
                aria-valuenow={credits.used}
                aria-valuemin={0}
                aria-valuemax={credits.allowance}
                aria-label="Credits used this month"
              >
                <div
                  className="h-full rounded-full bg-foreground transition-[width]"
                  style={{
                    width: `${Math.min(100, (credits.used / credits.allowance) * 100)}%`,
                  }}
                />
              </div>
              <p className="mt-3 text-xs text-muted-foreground">
                Credits meter what our keys spend on your behalf — runs and the AI assistant.
                They reset each month. Runs on{" "}
                <span className="text-foreground">your own API key</span> below cost nothing.
              </p>
              {credits.remaining === 0 ? (
                <p className="mt-2 text-xs text-amber-600 dark:text-amber-500">
                  You&rsquo;re out of credits until they reset. Add your own key below to keep
                  running{plan === "free" ? ", or upgrade to Plus" : ""}.
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="mt-4 rounded-lg border border-border p-5">
            <label htmlFor="ws-default-model" className="text-sm font-medium">
              Default model
            </label>
            <p className="mt-0.5 text-xs text-muted-foreground">
              What every block on the canvas runs on unless you pick a different model on the
              block itself. Templates and new blocks inherit this.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <select
                id="ws-default-model"
                data-testid="ws-default-model"
                className="h-9 max-w-xs flex-1 rounded-md border border-input bg-background px-2 text-sm"
                value={defaultModel}
                onChange={(e) => saveDefaultModel(e.target.value)}
              >
                {/* "" is the platform default rather than a model id, so it's named here
                    instead of coming from the server list (which calls it "Server default"). */}
                <option value="">OpenAI · gpt-4o-mini (default)</option>
                {modelOptions
                  .filter((o) => o.value !== "")
                  .map((o) => {
                    const locked = o.byo_provider !== null && !keyed.has(o.byo_provider);
                    return (
                      <option key={o.value} value={o.value} disabled={locked}>
                        {locked ? `${o.label} — add your own key below` : o.label}
                      </option>
                    );
                  })}
              </select>
              {defaultModelMsg ? (
                <span className="text-xs text-muted-foreground">{defaultModelMsg}</span>
              ) : null}
            </div>
          </div>

          <div className="mt-4 rounded-lg border border-border p-5">
            <label htmlFor="ws-assistant-model" className="text-sm font-medium">
              AI assistant model
            </label>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Which model drafts your graphs from a prompt in the chat box.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <select
                id="ws-assistant-model"
                data-testid="ws-assistant-model"
                className="h-9 max-w-xs flex-1 rounded-md border border-input bg-background px-2 text-sm"
                value={model}
                onChange={(e) => saveModel(e.target.value)}
              >
                {modelOptions.map((o) => {
                  // Frontier models run only on your own key — disabled until it's saved.
                  const locked = o.byo_provider !== null && !keyed.has(o.byo_provider);
                  return (
                    <option key={o.value} value={o.value} disabled={locked}>
                      {locked ? `${o.label} — add your own key below` : o.label}
                    </option>
                  );
                })}
              </select>
              {modelMsg ? (
                <span className="text-xs text-muted-foreground">{modelMsg}</span>
              ) : null}
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Frontier models (kimi-k3) run on your own API key and aren&rsquo;t billed
              through your plan.
            </p>

          </div>

          <div className="mt-4 rounded-lg border border-border p-5">
            <h2 className="text-sm font-medium">LLM providers</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Bring your own key for a provider. Keys are stored encrypted, never shown
              again, and used only for your own runs.
            </p>
            <div className="mt-4 flex flex-col divide-y divide-border">
              {providers.map((p) => (
                <ProviderRow
                  key={p.provider}
                  provider={p}
                  hasKey={keyed.has(p.provider)}
                  message={keyMsg[p.provider] ?? ""}
                  onSave={saveKey}
                  onRemove={removeKey}
                />
              ))}
            </div>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}

/** One provider in the list. A `coming_soon` provider is shown so the roadmap is visible, but
 * its input is disabled — the server would have no code path to use a key stored for it. */
function ProviderRow({
  provider,
  hasKey,
  message,
  onSave,
  onRemove,
}: {
  provider: LLMProvider;
  hasKey: boolean;
  message: string;
  onSave: (provider: string, key: string) => void;
  onRemove: (provider: string) => void;
}) {
  const [value, setValue] = useState("");
  const soon = provider.status === "coming_soon";
  const id = `ws-key-${provider.provider}`;

  return (
    <div className="flex flex-col gap-2 py-3 first:pt-0 last:pb-0">
      <div className="flex items-center gap-2">
        <label htmlFor={id} className="text-sm font-medium">
          {provider.label}
        </label>
        <span className="font-mono text-xs text-muted-foreground">
          {provider.model_label}
        </span>
        {soon ? (
          <span
            className="rounded-full border border-border px-2 py-0.5 text-[10px] uppercase tracking-wide text-muted-foreground"
            data-testid={`${id}-soon`}
          >
            Coming soon
          </span>
        ) : null}
        {hasKey && !soon ? (
          <span
            className="font-mono text-xs text-muted-foreground"
            data-testid={`${id}-onfile`}
          >
            •••• key on file
          </span>
        ) : null}
      </div>

      <div className="flex items-center gap-2">
        <Input
          id={id}
          data-testid={id}
          type="password"
          className="max-w-xs"
          disabled={soon}
          placeholder={
            soon ? "Not available yet" : hasKey ? "Replace key…" : "Paste key…"
          }
          value={value}
          onChange={(e) => setValue(e.target.value)}
        />
        <Button
          size="sm"
          data-testid={`${id}-save`}
          disabled={soon || !value.trim()}
          onClick={() => {
            onSave(provider.provider, value.trim());
            setValue(""); // never keep the secret in component state after it's sent
          }}
        >
          Save
        </Button>
        {hasKey && !soon ? (
          <Button
            size="sm"
            variant="ghost"
            data-testid={`${id}-remove`}
            onClick={() => onRemove(provider.provider)}
          >
            Remove
          </Button>
        ) : null}
        {message ? (
          <span className="text-xs text-muted-foreground">{message}</span>
        ) : null}
      </div>

      {provider.note ? (
        <p className="text-xs text-muted-foreground">{provider.note}</p>
      ) : null}
    </div>
  );
}
