"use client";

import { useEffect, useState } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
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
              <div>
                <div className="text-sm font-medium">{name || "—"}</div>
                <div className="text-xs text-muted-foreground">{email}</div>
              </div>
            </div>
            <Separator className="my-4" />
            <p className="text-xs text-muted-foreground">
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
