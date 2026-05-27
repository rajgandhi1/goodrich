"use client";
import * as React from "react";
import { Bell, Plus, ShieldCheck, SlidersHorizontal, Trash2, UserCog, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { createAppUser, deleteAppUser, getAccessSettingsRemote, listAppUsers, patchAppUser, putAccessSettingsRemote } from "@/lib/api";
import { ACCESS_SETTINGS_CHANGED_EVENT, AccessSettings, AppCapability, actionCapabilities, canRole, capabilityLabels, getAccessSettings, normalizeAccessSettings, pageCapabilities, saveAccessSettings } from "@/lib/auth/access-control";
import { AppRole, AppUser, canManageUsers, getAppUsers, getCurrentAppUser, roleLabels, saveAppUsers, USERS_CHANGED_EVENT } from "@/lib/auth/users";

const blankUser: AppUser = {
  id: "",
  name: "",
  email: "",
  password: "",
  role: "sales",
  active: true,
};

export function SettingsClient() {
  const [users, setUsers] = React.useState<AppUser[]>(() => getAppUsers());
  const [currentUser, setCurrentUserState] = React.useState(() => getCurrentAppUser());
  const [draftUser, setDraftUser] = React.useState<AppUser>(blankUser);
  const [accessSettings, setAccessSettings] = React.useState<AccessSettings>(() => getAccessSettings());
  const [draftWithWhom, setDraftWithWhom] = React.useState("");
  const canManage = canManageUsers(currentUser.role);

  React.useEffect(() => {
    listAppUsers()
      .then((rows) => {
        saveAppUsers(rows);
        setUsers(rows);
        setCurrentUserState(getCurrentAppUser());
      })
      .catch(() => {
        setUsers(getAppUsers());
      });
    getAccessSettingsRemote()
      .then((settings) => {
        const normalized = normalizeAccessSettings(settings);
        saveAccessSettings(normalized);
        setAccessSettings(normalized);
      })
      .catch(() => setAccessSettings(getAccessSettings()));
    const refresh = () => {
      setUsers(getAppUsers());
      setCurrentUserState(getCurrentAppUser());
      setAccessSettings(getAccessSettings());
    };
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  function persistUsers(next: AppUser[]) {
    saveAppUsers(next);
    setUsers(getAppUsers());
    setCurrentUserState(getCurrentAppUser());
  }

  function updateUser(userId: string, patch: Partial<AppUser>) {
    const next = users.map((user) => (user.id === userId ? { ...user, ...patch } : user));
    persistUsers(next);
    patchAppUser(userId, patch)
      .then((updated) => persistUsers(next.map((user) => (user.id === userId ? updated : user))))
      .catch((error) => toast.error(error instanceof Error ? error.message : "Could not update user"));
  }

  function persistAccess(next: AccessSettings, message = "Access settings saved") {
    const normalized = normalizeAccessSettings(next);
    saveAccessSettings(normalized);
    setAccessSettings(normalized);
    putAccessSettingsRemote(normalized)
      .then((saved) => {
        const serverSettings = normalizeAccessSettings(saved);
        saveAccessSettings(serverSettings);
        setAccessSettings(serverSettings);
        toast.success(message);
      })
      .catch((error) => toast.error(error instanceof Error ? error.message : "Could not save access settings"));
  }

  function addWithWhomOption() {
    const option = draftWithWhom.trim();
    if (!option) return;
    if (accessSettings.with_whom_options.some((value) => value.toLowerCase() === option.toLowerCase())) {
      toast.error("Option already exists");
      return;
    }
    persistAccess({ ...accessSettings, with_whom_options: [...accessSettings.with_whom_options, option] }, "With whom option added");
    setDraftWithWhom("");
  }

  function removeWithWhomOption(option: string) {
    persistAccess({
      ...accessSettings,
      with_whom_options: accessSettings.with_whom_options.filter((value) => value !== option),
    }, "With whom option removed");
  }

  function updateRoleCapability(role: AppRole, capability: AppCapability, enabled: boolean) {
    persistAccess({
      ...accessSettings,
      role_permissions: {
        ...accessSettings.role_permissions,
        [role]: {
          ...accessSettings.role_permissions[role],
          [capability]: enabled,
        },
      },
    });
  }

  async function addUser() {
    const username = draftUser.id.trim().toLowerCase();
    const password = String(draftUser.password || "").trim();
    if (!username) {
      toast.error("Enter a username for the user");
      return;
    }
    if (!password) {
      toast.error("Enter a password for the user");
      return;
    }
    if (users.some((user) => user.id.toLowerCase() === username)) {
      toast.error("User already exists");
      return;
    }
    try {
      const email = draftUser.email.trim().toLowerCase();
      const created = await createAppUser({ ...draftUser, id: username, email, name: draftUser.name.trim() || username, active: true });
      persistUsers([...users, { ...created, password }]);
      setDraftUser(blankUser);
      toast.success("User added");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not add user");
    }
  }

  async function removeUser(userId: string) {
    const user = users.find((row) => row.id === userId);
    if (!user) return;
    const activeAdmins = users.filter((row) => row.active && row.role === "admin" && row.id !== userId).length;
    if (user.role === "admin" && activeAdmins === 0) {
      toast.error("Keep at least one active admin user");
      return;
    }
    try {
      await deleteAppUser(userId);
      persistUsers(users.filter((row) => row.id !== userId));
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not remove user");
    }
  }

  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card>
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base"><UserCog className="h-4 w-4" />Account</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-3">
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <div>
              <div className="text-sm font-medium">Authentication</div>
              <div className="text-sm text-muted-foreground">Username and password sign in</div>
            </div>
            <Badge variant="secondary">Active</Badge>
          </div>
          <div className="rounded-md border px-3 py-2">
            <Label>Signed in user</Label>
            <div className="mt-1 text-sm font-medium">{currentUser.id}</div>
            <div className="text-xs text-muted-foreground">{currentUser.name} - {roleLabels[currentUser.role]}</div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base"><Bell className="h-4 w-4" />Preferences</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-3">
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <Label htmlFor="email-alerts" className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-secondary" />
              Email alerts
            </Label>
            <Switch id="email-alerts" />
          </div>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <SlidersHorizontal className="h-4 w-4" />
            Admin access controls
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 p-3">
          {!canManage && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              Only admin users can change access controls.
            </div>
          )}

          <div className="rounded-md border p-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-sm font-medium">With whom options</div>
              <Badge variant="outline">{accessSettings.with_whom_options.length} options</Badge>
            </div>
            {canManage && (
              <div className="mb-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                <Input value={draftWithWhom} onChange={(event) => setDraftWithWhom(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addWithWhomOption(); }} />
                <Button size="sm" onClick={addWithWhomOption}>
                  <Plus className="h-4 w-4" />
                  Add option
                </Button>
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {accessSettings.with_whom_options.map((option) => (
                <Badge key={option} variant="secondary" className="gap-1.5 rounded-md py-1">
                  {option}
                  {canManage && (
                    <button type="button" className="rounded-sm hover:bg-background/60" onClick={() => removeWithWhomOption(option)} aria-label={`Remove ${option}`}>
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </Badge>
              ))}
            </div>
          </div>

          <div className="overflow-auto rounded-md border">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="sticky left-0 bg-muted/50 px-3 py-2 font-medium">Role</th>
                  {[...pageCapabilities, ...actionCapabilities].map((capability) => (
                    <th key={capability} className="px-2 py-2 text-center text-xs font-medium">{capabilityLabels[capability]}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(roleLabels).map(([role, label]) => (
                  <tr key={role} className="border-t">
                    <td className="sticky left-0 bg-background px-3 py-2 font-medium">{label}</td>
                    {[...pageCapabilities, ...actionCapabilities].map((capability) => (
                      <td key={`${role}-${capability}`} className="px-2 py-2 text-center">
                        <Switch
                          checked={canRole(role as AppRole, capability, accessSettings)}
                          disabled={!canManage || role === "admin"}
                          onCheckedChange={(checked) => updateRoleCapability(role as AppRole, capability, checked)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card className="lg:col-span-2">
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <UserCog className="h-4 w-4" />
            Admin user management
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-3">
          {!canManage && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              Only admin users can add users or change roles.
            </div>
          )}

          {canManage && (
            <details className="rounded-md border p-3">
              <summary className="cursor-pointer text-sm font-medium">
                <span className="inline-flex items-center gap-2"><Plus className="h-4 w-4" />Add user</span>
              </summary>
              <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_1fr_180px_auto] md:items-end">
                <div className="space-y-1.5">
                  <Label>Username</Label>
                  <Input value={draftUser.id} onChange={(event) => setDraftUser((user) => ({ ...user, id: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Name</Label>
                  <Input value={draftUser.name} onChange={(event) => setDraftUser((user) => ({ ...user, name: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Password</Label>
                  <Input type="password" value={draftUser.password || ""} onChange={(event) => setDraftUser((user) => ({ ...user, password: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Role</Label>
                  <Select value={draftUser.role} onValueChange={(value) => setDraftUser((user) => ({ ...user, role: value as AppRole }))}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      {Object.entries(roleLabels).map(([role, label]) => <SelectItem key={role} value={role}>{label}</SelectItem>)}
                    </SelectContent>
                  </Select>
                </div>
                <Button size="sm" onClick={addUser}>
                  <Plus className="h-4 w-4" />
                  Add
                </Button>
              </div>
            </details>
          )}

          <div className="overflow-auto rounded-md border">
            <table className="w-full text-sm">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium">User</th>
                  <th className="px-3 py-2 font-medium">Username</th>
                  <th className="px-3 py-2 font-medium">Password</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Active</th>
                  <th className="px-3 py-2 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-t">
                    <td className="px-3 py-2">
                      {canManage ? (
                        <Input value={user.name} onChange={(event) => updateUser(user.id, { name: event.target.value })} />
                      ) : (
                        user.name
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{user.id}</td>
                    <td className="px-3 py-2">
                      {canManage ? (
                        <Input
                          type="password"
                          placeholder="Set new password"
                          onBlur={(event) => {
                            const password = event.target.value.trim();
                            if (!password) return;
                            updateUser(user.id, { password });
                            event.target.value = "";
                          }}
                        />
                      ) : (
                        <span className="text-muted-foreground">Managed by admin</span>
                      )}
                    </td>
                    <td className="px-3 py-2">
                      {canManage ? (
                        <Select value={user.role} onValueChange={(value) => updateUser(user.id, { role: value as AppRole })}>
                          <SelectTrigger className="w-40"><SelectValue /></SelectTrigger>
                          <SelectContent>
                            {Object.entries(roleLabels).map(([role, label]) => <SelectItem key={role} value={role}>{label}</SelectItem>)}
                          </SelectContent>
                        </Select>
                      ) : (
                        roleLabels[user.role]
                      )}
                    </td>
                    <td className="px-3 py-2">
                      <Switch checked={user.active} disabled={!canManage} onCheckedChange={(checked) => updateUser(user.id, { active: checked })} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Button variant="ghost" size="icon" disabled={!canManage || user.id === currentUser.id} onClick={() => removeUser(user.id)} aria-label={`Remove ${user.name}`}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
