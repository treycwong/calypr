"use client";

import { useEffect, useRef, useState } from "react";

import Link from "next/link";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type AssistantModelOption,
  deleteAccount,
  deleteProviderKey,
  deleteWorkspace,
  getSubscription,
  getWorkspace,
  listAgents,
  listAssistantModels,
  type LLMProvider,
  listLLMProviders,
  listWorkspaces,
  renameWorkspace,
  switchWorkspace,
  setAssistantModel,
  setDefaultModel as setDefaultModelApi,
  setProviderKey,
  startBillingPortal,
  uploadImage,
  type SubscriptionInfo,
} from "@/lib/api";
import { authClient } from "@/lib/auth-client";
import { PLAN_COPY } from "@/lib/plans";
import { useProviderKeys } from "@/lib/use-provider-keys";

/** What each tier means in the one place a user goes looking. `beta` keeps code export because
 * we don't take a shipped feature back off the cohort already using it. */
/** "August 24, 2026" from an ISO string. Empty for null so callers can guard on it. */
function formatDate(iso: string | null): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function SettingsView({
  name,
  email,
  image,
  initialTab = "account",
  manageable = false,
  providers: linkedProviders = [],
}: {
  name: string;
  email: string;
  image: string | null;
  initialTab?: string;
  /** Whether profile edits can persist — false on the dev auth path, which has no profile store. */
  manageable?: boolean;
  /** Social providers linked to this account, resolved server-side. */
  providers?: string[];
}) {
  // Local so the avatar preview updates as the URL is typed, and so a save that fails leaves
  // the user's text where they can fix it rather than snapping back to the server's value.
  const [profileName, setProfileName] = useState(name);
  const [profileImage, setProfileImage] = useState(image ?? "");
  const [profileMsg, setProfileMsg] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const initials = (profileName || email || "U").slice(0, 2).toUpperCase();
  const [wsName, setWsName] = useState("");
  const [savedMsg, setSavedMsg] = useState("");
  // The workspace as *persisted*, kept apart from the `wsName` input above. Delete-to-confirm
  // matches against this: typing a new name without saving must not arm a delete against a name
  // the workspace does not actually have.
  const [savedWs, setSavedWs] = useState<{ id: string; name: string } | null>(null);
  const [model, setModel] = useState("");
  const [modelOptions, setModelOptions] = useState<AssistantModelOption[]>([]);
  const [modelMsg, setModelMsg] = useState("");
  // The canvas default is a separate setting from the assistant's — different surfaces, and a
  // user may well want a cheap model drafting graphs and a stronger one running them.
  const [defaultModel, setDefaultModel] = useState("");
  const [defaultModelMsg, setDefaultModelMsg] = useState("");
  // The entitlement tier, so "why can/can't I export my code?" has a visible answer.
  const [plan, setPlan] = useState("free");
  const { keyed, refresh: refreshKeys } = useProviderKeys();
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  // Per-provider status line, so saving an OpenAI key doesn't flash a message on the Kimi row.
  const [keyMsg, setKeyMsg] = useState<Record<string, string>>({});
  // Subscription state for the Billing tab (plan + cycle date + portal availability).
  const [subscription, setSubscription] = useState<SubscriptionInfo | null>(null);
  const [portalMsg, setPortalMsg] = useState("");
  // Controlled so a return from Checkout/Portal (`?tab=billing` / `?upgraded=1`) lands here —
  // the initial tab is resolved server-side and passed in.
  const [tab, setTab] = useState(initialTab);

  const setMsg = (provider: string, text: string) =>
    setKeyMsg((prev) => ({ ...prev, [provider]: text }));

  useEffect(() => {
    getWorkspace()
      .then((w) => {
        setWsName(w.name);
        setSavedWs({ id: w.id, name: w.name });
        setModel(w.assistant_model ?? "");
        setDefaultModel(w.default_model ?? "");
        setPlan(w.plan ?? "free");
      })
      .catch(() => {});
    listAssistantModels()
      .then(setModelOptions)
      .catch(() => setModelOptions([]));
    listLLMProviders()
      .then(setProviders)
      .catch(() => setProviders([]));
    getSubscription()
      .then(setSubscription)
      .catch(() => setSubscription(null));
  }, []);

  async function openPortal() {
    setPortalMsg("Opening…");
    try {
      const url = await startBillingPortal();
      if (url) {
        window.location.href = url; // hand off to Stripe's hosted portal
      } else {
        setPortalMsg("Billing isn't available right now.");
      }
    } catch {
      setPortalMsg("Couldn't open billing. Try again.");
    }
  }

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

  async function uploadAvatar(file: File) {
    setUploading(true);
    setProfileMsg("Uploading…");
    try {
      // Reuses `/api/uploads` rather than adding an avatar-specific endpoint: it already does
      // the content-type allowlist, the magic-byte sniff and the 5MB streaming cap, and — the
      // part that matters here — it records an `upload` row against the workspace, so an
      // avatar is attributable storage and gets collected when the account is deleted. A
      // bespoke endpoint would have had to re-earn all four.
      const url = await uploadImage(file);
      // Fills the field rather than saving: the avatar above previews it immediately, and the
      // change isn't committed until Save, so a mis-picked file can just be replaced.
      setProfileImage(url);
      setProfileMsg("Uploaded — press Save to apply");
    } catch (e) {
      // The API's own message is worth showing: "only PNG, JPEG, WebP, or GIF images are
      // accepted" and "image exceeds the 5MB limit" both tell the user what to do next, which
      // a generic failure line would not.
      setProfileMsg(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function saveProfile() {
    setProfileMsg("Saving…");
    // One call for both fields: they're edited together and a partial save is a confusing
    // state to have to explain.
    const { error } = await authClient.updateUser({
      name: profileName.trim(),
      image: profileImage.trim() || undefined,
    });
    // Better Auth's client returns `{data, error}` and does **not** throw, so a try/catch here
    // would silently treat every failure as a success.
    setProfileMsg(error ? "Save failed" : "Saved ✓");
  }

  async function saveWorkspace() {
    setSavedMsg("Saving…");
    try {
      const w = await renameWorkspace(wsName.trim() || "Workspace");
      setWsName(w.name);
      setSavedWs({ id: w.id, name: w.name });
      setSavedMsg("Saved ✓");
    } catch {
      setSavedMsg("Save failed");
    }
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-8">
      <h1 className="text-xl font-semibold">Settings</h1>
      <Tabs value={tab} onValueChange={setTab} className="mt-6">
        <TabsList>
          <TabsTrigger value="account" data-testid="tab-account">
            Account
          </TabsTrigger>
          <TabsTrigger value="billing" data-testid="tab-billing">
            Billing
          </TabsTrigger>
          <TabsTrigger value="workspace" data-testid="tab-workspace">
            Workspace
          </TabsTrigger>
        </TabsList>

        <TabsContent value="account" className="mt-4">
          {/* --- Account information ------------------------------------------------------ */}
          <div className="rounded-lg border border-border p-5" data-testid="account-info-card">
            <div className="flex items-center gap-3">
              <Avatar className="h-12 w-12">
                {/* Previews `profileImage`, not the prop, so a URL edit updates live — the
                    point of the field is seeing what you're about to save. */}
                {profileImage ? <AvatarImage src={profileImage} alt="" /> : null}
                <AvatarFallback>{initials}</AvatarFallback>
              </Avatar>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium">{profileName || "—"}</span>
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

            <label htmlFor="account-name" className="text-sm font-medium">
              Display name
            </label>
            <p className="mt-0.5 text-xs text-muted-foreground">
              What appears on your account and shared runs.
            </p>
            <div className="mt-2 flex items-center gap-2">
              <Input
                id="account-name"
                className="max-w-xs"
                value={profileName}
                disabled={!manageable}
                onChange={(e) => setProfileName(e.target.value)}
                data-testid="account-name"
              />
            </div>

            <div className="mt-4 text-sm font-medium">Avatar</div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              Upload an image, or paste a link to one. Leave it empty to use your initials.
            </p>
            <div className="mt-2 flex items-center gap-2">
              {/* The file input is hidden and driven by a Button so it matches every other
                  control on this page — a bare `input[type=file]` renders as the browser's
                  chrome and is the one thing here that would look borrowed.

                  The **Button** is the user-facing gate, so it carries `disabled`; the input
                  itself doesn't, because it is unreachable except through that button. That
                  also leaves the wiring drivable by `setInputFiles` in e2e, which otherwise
                  couldn't cover it at all — the whole suite runs on the dev path, where
                  `manageable` is false. */}
              <input
                ref={fileRef}
                type="file"
                accept={ACCEPTED_IMAGE_TYPES}
                className="hidden"
                data-testid="account-image-file"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  // Reset first: picking the *same* file twice fires no change event
                  // otherwise, so a failed upload couldn't be retried by reselecting it.
                  e.target.value = "";
                  if (file) uploadAvatar(file);
                }}
              />
              <Button
                size="sm"
                variant="outline"
                disabled={!manageable || uploading}
                onClick={() => fileRef.current?.click()}
                data-testid="account-image-upload"
              >
                {uploading ? "Uploading…" : "Upload image"}
              </Button>
              <span className="text-xs text-muted-foreground">PNG, JPEG, WebP or GIF, up to 5MB.</span>
            </div>

            <label htmlFor="account-image" className="mt-3 block text-xs text-muted-foreground">
              Or paste an image URL
            </label>
            {/* Save lives below, not on this row — see the note at the save block. */}
            <div className="mt-2">
              <Input
                id="account-image"
                className="max-w-xs"
                value={profileImage}
                disabled={!manageable}
                placeholder="https://…"
                onChange={(e) => setProfileImage(e.target.value)}
                data-testid="account-image"
              />
            </div>

            {!manageable ? (
              <p className="mt-3 text-xs text-muted-foreground" data-testid="account-dev-notice">
                Development sign-in has no profile to edit — these fields are disabled because a
                save here wouldn&rsquo;t stick. Set Better Auth keys to enable real auth.
              </p>
            ) : null}

            {/* One Save for the whole section, on its own row.
                It used to sit inline beside the avatar-URL input, which read as "save this
                field" — so a name edit looked unsaved, or worse, looked like it needed a
                different button that doesn't exist. A single `updateUser` call has always sent
                both; the layout was the thing lying about it. The rule this follows: a control's
                position is a claim about its scope, so a section-scoped action belongs after the
                section, not welded to the last input in it — which is also why this needs no
                caption spelling out what it saves. The divider and the placement say it. */}
            <div className="mt-4 flex items-center gap-3 border-t border-border pt-4">
              <Button
                size="sm"
                onClick={saveProfile}
                disabled={!manageable}
                data-testid="account-save"
              >
                Save changes
              </Button>
              {profileMsg ? (
                <span className="text-xs text-muted-foreground" data-testid="account-saved">
                  {profileMsg}
                </span>
              ) : null}
            </div>

            <Separator className="my-4" />

            {/* Email is rendered as **text, not a disabled input**. It isn't a field you may
                not edit yet — it is not a field. The API trusts this address as the verified
                one from the provider (it matches against the beta invite list), so making it
                editable would let anyone self-grant a paid entitlement. */}
            <div className="text-sm font-medium">Email</div>
            <p className="mt-1 text-sm" data-testid="account-email">
              {email}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Your email comes from GitHub and can&rsquo;t be changed here.
            </p>

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
          </div>

          {/* --- Integrations ------------------------------------------------------------- */}
          {/* Connected state only, with no disconnect. GitHub is the only way in, so an
              "unlink" button is a button that locks you out of your own account. */}
          <div
            className="mt-4 rounded-lg border border-border p-5"
            data-testid="account-integrations-card"
          >
            <h2 className="text-sm font-medium">Account integrations</h2>
            <p className="mt-0.5 text-xs text-muted-foreground">
              How you sign in to Calypr.
            </p>
            <div
              className="mt-4 flex items-center justify-between gap-4"
              data-testid="account-integration-github"
              data-connected={linkedProviders.includes("github")}
            >
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium">GitHub</span>
                <span className="font-mono text-xs text-muted-foreground">
                  {manageable ? "OAuth" : "development sign-in"}
                </span>
              </div>
              <Badge variant={linkedProviders.includes("github") ? "default" : "outline"}>
                {linkedProviders.includes("github") ? "Connected" : "Not connected"}
              </Badge>
            </div>
          </div>

          {/* --- Danger ------------------------------------------------------------------- */}
          <DangerCard manageable={manageable} plan={plan} />
        </TabsContent>

        <TabsContent value="billing" className="mt-4">
          <div className="rounded-lg border border-border p-5" data-testid="billing-card">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-sm font-medium">Plan</h2>
              <Badge
                variant={plan === "free" ? "outline" : "default"}
                data-testid="billing-plan"
              >
                {PLAN_COPY[plan]?.label ?? plan}
              </Badge>
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {PLAN_COPY[plan]?.blurb ?? "Your workspace tier."}
            </p>

            {/* Cycle line: only meaningful once there's a subscription with a period end. */}
            {subscription?.current_period_end ? (
              <p className="mt-3 text-sm" data-testid="billing-cycle">
                {subscription.cancel_at_period_end ? (
                  <>
                    Your plan is set to cancel on{" "}
                    <span className="font-medium">
                      {formatDate(subscription.current_period_end)}
                    </span>
                    . You&rsquo;ll keep Plus until then.
                  </>
                ) : (
                  <>
                    Renews on{" "}
                    <span className="font-medium">
                      {formatDate(subscription.current_period_end)}
                    </span>
                    .
                  </>
                )}
              </p>
            ) : null}

            <Separator className="my-4" />

            <div className="flex flex-wrap items-center gap-3">
              {subscription?.portal_available ? (
                // Everything mutating (cancel, switch plan, update card, invoices) lives in
                // Stripe's hosted portal — we never see card data.
                <Button
                  size="sm"
                  onClick={openPortal}
                  data-testid="billing-manage"
                >
                  Manage billing
                </Button>
              ) : plan === "free" ? (
                <Link
                  href="/pricing"
                  className={buttonVariants({ size: "sm" })}
                  data-testid="billing-upgrade"
                >
                  Upgrade to Plus
                </Link>
              ) : null}
              {portalMsg ? (
                <span className="text-xs text-muted-foreground">{portalMsg}</span>
              ) : null}
            </div>

            <p className="mt-4 text-xs text-muted-foreground">
              Manage billing opens Stripe&rsquo;s secure portal to cancel, change plan, update
              your payment method, or download invoices. Your credit usage is under{" "}
              <button
                type="button"
                className="underline underline-offset-4"
                onClick={() => setTab("workspace")}
              >
                Workspace
              </button>
              .
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

          {/* Credits moved to the Usage tab: it is account-level (shared across every
              workspace), so it belongs next to projects and storage rather than under one
              workspace's settings. */}
          <p className="mt-4 text-xs text-muted-foreground">
            Credits, projects and storage are on the{" "}
            <Link href="/dashboard/usage" className="underline">
              Usage
            </Link>{" "}
            tab.
          </p>

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

          <DeleteWorkspaceCard workspace={savedWs} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/**
 * Delete Workspace.
 *
 * Type-to-confirm like `DangerCard`, but the phrase is **the workspace's own name** rather than a
 * fixed string. With several workspaces the question is not only "do you mean to delete
 * something" but "do you mean to delete *this* one", and typing the name is the only confirmation
 * that answers the second. Matched against the *saved* name, never the rename input — otherwise
 * an unsaved edit would arm the button against a name the workspace does not have.
 *
 * The project count is fetched rather than described in the abstract: "deletes 12 projects" is a
 * fact someone can weigh, where "deletes your projects" is a sentence people click past. If the
 * count can't be loaded the warning stays qualitative rather than guessing or claiming zero.
 *
 * The API refuses to delete the last workspace (`routers/workspaces.py`) because an account with
 * none would silently get a fresh "Personal" one on the next request. That refusal is mirrored
 * here as a disabled button with the reason — reaching a dead end after typing a name out is a
 * worse way to learn the rule — but the server stays the enforcement, not this.
 */
function DeleteWorkspaceCard({ workspace }: { workspace: { id: string; name: string } | null }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [projectCount, setProjectCount] = useState<number | null>(null);
  const [isOnly, setIsOnly] = useState<boolean | null>(null);

  useEffect(() => {
    // Both are "what would this destroy, and may it be destroyed at all" — cheap, and only paid
    // for on the Workspace tab. Either failing leaves the card usable: an unknown project count
    // falls back to qualitative copy, and an unknown workspace count defers to the server's 400.
    listAgents()
      .then((rows) => setProjectCount(rows.length))
      .catch(() => setProjectCount(null));
    listWorkspaces()
      .then((w) => setIsOnly(w.workspaces.length <= 1))
      .catch(() => setIsOnly(null));
  }, [workspace?.id]);

  const armed =
    !!workspace && typed.trim().toLowerCase() === workspace.name.trim().toLowerCase();

  async function confirmDelete() {
    if (!workspace) return;
    setBusy(true);
    setError("");
    try {
      await deleteWorkspace(workspace.id);
    } catch (e) {
      setBusy(false);
      // Keep the dialog open so the reason sits next to the button that failed — this is where
      // the server's "cannot delete your only workspace" surfaces if the mirror above was wrong.
      setError(e instanceof Error ? e.message : "Could not delete that workspace.");
      return;
    }
    // The cookie now points at a workspace that no longer exists. `resolve_workspace` would fall
    // back on its own, but clearing it is what makes the next request unambiguous rather than
    // merely survivable. A full navigation, not `router.refresh()`: we are leaving a workspace
    // that is gone, and every client page still holding its data has to be rebuilt from scratch.
    await switchWorkspace().catch(() => {});
    window.location.assign("/dashboard");
  }

  return (
    <div
      className="mt-4 rounded-lg border border-destructive/40 p-5"
      data-testid="ws-danger-card"
    >
      <h2 className="text-sm font-medium">Delete workspace</h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Permanently delete{" "}
        <span className="font-medium text-foreground">{workspace?.name ?? "this workspace"}</span>{" "}
        and everything inside it.
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
        <li data-testid="ws-delete-projects">
          {projectCount === null
            ? "Every project in this workspace"
            : projectCount === 1
              ? "Its 1 project"
              : `Its ${projectCount} projects`}
        </li>
        <li>Their run history, uploads and share links</li>
        <li>Any connectors and API keys saved here</li>
      </ul>
      {/* Says where the blast radius stops. Someone deleting one of several workspaces is
          reasonably worried about the other ones and about being billed. */}
      <p className="mt-3 text-xs text-muted-foreground">
        Your other workspaces, your account and your subscription are not affected. This
        can&rsquo;t be undone.
      </p>

      {isOnly ? (
        <p className="mt-3 text-xs text-muted-foreground" data-testid="ws-delete-only-notice">
          This is your only workspace, so it can&rsquo;t be deleted — your work would have nowhere
          to live. Create another one first, or delete your account from the Account tab.
        </p>
      ) : null}

      <div className="mt-4">
        <Button
          variant="destructive"
          size="sm"
          disabled={!workspace || !!isOnly}
          onClick={() => {
            setTyped("");
            setError("");
            setOpen(true);
          }}
          data-testid="ws-delete-open"
        >
          Delete workspace
        </Button>
      </div>

      <Dialog open={open} onOpenChange={(o) => !busy && setOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this workspace?</DialogTitle>
            <DialogDescription>
              This permanently deletes{" "}
              <span className="font-medium">{workspace?.name}</span>
              {projectCount === null
                ? " and every project in it"
                : projectCount === 1
                  ? " and its 1 project"
                  : ` and its ${projectCount} projects`}
              , along with their runs, uploads, share links and saved connectors. It can&rsquo;t be
              undone.
            </DialogDescription>
          </DialogHeader>
          <label htmlFor="ws-delete-confirm" className="text-sm">
            Type <span className="font-mono font-medium">{workspace?.name}</span> to confirm.
          </label>
          <Input
            id="ws-delete-confirm"
            value={typed}
            autoComplete="off"
            onChange={(e) => setTyped(e.target.value)}
            data-testid="ws-delete-input"
          />
          {error ? (
            <p className="text-sm text-destructive" data-testid="ws-delete-error">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogClose render={<Button variant="outline">Cancel</Button>} />
            <Button
              variant="destructive"
              disabled={!armed || busy}
              onClick={confirmDelete}
              data-testid="ws-delete-confirm"
            >
              {busy ? "Deleting…" : "Delete workspace"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

/** The exact phrase the confirm button waits for. Compared `.trim().toLowerCase()`, so the
 *  friction is deliberate but not pedantic about capitalisation or a trailing space. */
const CONFIRM_PHRASE = "delete my account";

/** Kept in step with the API's `_ALLOWED` map in `routers/uploads.py` — it is the enforcement,
 *  this is only the file picker's filter. */
const ACCEPTED_IMAGE_TYPES = "image/png,image/jpeg,image/webp,image/gif";

/**
 * Delete Account.
 *
 * **Type-to-confirm is a deliberate departure** from the one-click precedent in
 * `app/dashboard/page.tsx`. That guards a single rebuildable graph; this destroys every
 * workspace, cancels a paid subscription mid-period, and ends a session the user cannot get
 * back. Copying an affordance designed for the cheap case into the expensive one is the
 * mistake, not the departure.
 *
 * It also **adds the error handling that precedent omits**: the dialog stays open and renders
 * the server's message inline. The message that matters is the Stripe 502 — nothing was
 * deleted and retrying is right — and a toast is the wrong shape for that while a modal is up.
 */
function DangerCard({ manageable, plan }: { manageable: boolean; plan: string }) {
  const [open, setOpen] = useState(false);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const armed = typed.trim().toLowerCase() === CONFIRM_PHRASE;

  async function confirmDelete() {
    setBusy(true);
    setError("");
    try {
      // **Our API first, Better Auth second.** The reverse order destroys the identity we need
      // in order to *find* the account — orphaning a live subscription nobody can cancel. If
      // this succeeds and the next step fails, the account is already soft-deleted and every
      // call 401s, so a retry is harmless.
      const result = await deleteAccount();
      // Dev mode has no Better Auth identity to remove, and the proxy has already cleared the
      // only cookie the dev session has. Calling Better Auth anyway would hit its catch-all
      // with no secret configured and reject on the server for nothing.
      if (result.mode === "live") {
        // Better Auth's client returns `{data, error}` and **does not throw**, so this has to
        // be checked explicitly — a bare `await` here silently treats a refusal as success.
        const { error } = await authClient.deleteUser();
        if (error) {
          // It can still refuse (a session past `freshAge`, a transient failure). Our data is
          // already soft-deleted at this point and the account 401s everywhere, so the only
          // thing that matters now is not leaving a *valid session cookie* behind — being
          // signed in to an account that no longer works is the worst of both outcomes.
          await authClient.signOut().catch(() => {});
        }
      }
    } catch (e) {
      setBusy(false);
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
      return; // keep the dialog open, so the message sits next to the button that failed
    }
    // Whatever happened to step 2, never leave someone signed into an account that no longer
    // functions — every subsequent request would 401 with no explanation.
    window.location.href = "/sign-in?deleted=1";
  }

  return (
    <div
      className="mt-4 rounded-lg border border-destructive/40 p-5"
      data-testid="account-danger-card"
    >
      <h2 className="text-sm font-medium">Delete account</h2>
      <p className="mt-0.5 text-xs text-muted-foreground">
        Permanently delete your account and everything in it.
      </p>
      <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-muted-foreground">
        <li>Every workspace and project you own</li>
        <li>Your run history, uploads and share links</li>
        <li>Any remaining credit balance — no refund</li>
        {/* Named explicitly because it is a real cost the user is agreeing to, and the
            cancellation is immediate and unprorated. */}
        {plan !== "free" ? (
          <li>
            Your subscription is cancelled <strong>immediately</strong>, with no refund for the
            rest of the period
          </li>
        ) : null}
        <li>Any beta invite is forfeited</li>
      </ul>
      <p className="mt-3 text-xs text-muted-foreground">This can&rsquo;t be undone.</p>

      {!manageable ? (
        <p className="mt-3 text-xs text-muted-foreground" data-testid="account-delete-dev-notice">
          On the development sign-in there is no account to delete — this signs you out instead.
        </p>
      ) : null}

      <div className="mt-4">
        <Button
          variant="destructive"
          size="sm"
          onClick={() => {
            setTyped("");
            setError("");
            setOpen(true);
          }}
          data-testid="account-delete-open"
        >
          Delete account
        </Button>
      </div>

      <Dialog open={open} onOpenChange={(o) => !busy && setOpen(o)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete your account?</DialogTitle>
            <DialogDescription>
              This permanently deletes every workspace, project, run and upload on your account,
              cancels any subscription immediately, and signs you out. It can&rsquo;t be undone.
            </DialogDescription>
          </DialogHeader>
          <label htmlFor="account-delete-confirm" className="text-sm">
            Type <span className="font-mono font-medium">{CONFIRM_PHRASE}</span> to confirm.
          </label>
          <Input
            id="account-delete-confirm"
            value={typed}
            autoComplete="off"
            onChange={(e) => setTyped(e.target.value)}
            data-testid="account-delete-input"
          />
          {error ? (
            <p className="text-sm text-destructive" data-testid="account-delete-error">
              {error}
            </p>
          ) : null}
          <DialogFooter>
            <DialogClose render={<Button variant="outline">Cancel</Button>} />
            <Button
              variant="destructive"
              disabled={!armed || busy}
              onClick={confirmDelete}
              data-testid="account-delete-confirm"
            >
              {busy ? "Deleting…" : "Delete account"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
