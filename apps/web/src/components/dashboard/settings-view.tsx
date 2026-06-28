"use client";

import { useEffect, useState } from "react";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { getWorkspace, renameWorkspace } from "@/lib/api";

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

  useEffect(() => {
    getWorkspace()
      .then((w) => setWsName(w.name))
      .catch(() => {});
  }, []);

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
        </TabsContent>
      </Tabs>
    </div>
  );
}
