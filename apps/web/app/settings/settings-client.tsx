"use client";
import * as React from "react";
import { Bell, Plus, ShieldCheck, Trash2, UserCog } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { createAppUser, deleteAppUser, listAppUsers, patchAppUser } from "@/lib/api";
import { AppRole, AppUser, canManageUsers, getAppUsers, getCurrentAppUser, roleLabels, saveAppUsers, setCurrentAppUser, USERS_CHANGED_EVENT } from "@/lib/auth/users";

const blankUser: AppUser = {
  id: "",
  name: "",
  email: "",
  role: "sales",
  active: true,
};

export function SettingsClient() {
  const [users, setUsers] = React.useState<AppUser[]>(() => getAppUsers());
  const [currentUser, setCurrentUserState] = React.useState(() => getCurrentAppUser());
  const [draftUser, setDraftUser] = React.useState<AppUser>(blankUser);
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
    const refresh = () => {
      setUsers(getAppUsers());
      setCurrentUserState(getCurrentAppUser());
    };
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
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

  async function addUser() {
    const email = draftUser.email.trim().toLowerCase();
    if (!email) {
      toast.error("Enter an email for the user");
      return;
    }
    if (users.some((user) => user.email.toLowerCase() === email || user.id === email)) {
      toast.error("User already exists");
      return;
    }
    try {
      const created = await createAppUser({ ...draftUser, id: email, email, name: draftUser.name.trim() || email.split("@")[0], active: true });
      persistUsers([...users, created]);
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
              <div className="text-sm text-muted-foreground">Supabase session or local dev session</div>
            </div>
            <Badge variant="secondary">Active</Badge>
          </div>
          <div className="space-y-2">
            <Label>Current app user</Label>
            <Select value={currentUser.id} onValueChange={(value) => { setCurrentAppUser(value); setCurrentUserState(getCurrentAppUser()); }}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {users.filter((user) => user.active).map((user) => (
                  <SelectItem key={user.id} value={user.id}>
                    {user.name} - {roleLabels[user.role]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="text-xs text-muted-foreground">
              The selected user controls role-based approval actions in this workspace.
            </div>
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
              <div className="mt-3 grid gap-3 md:grid-cols-[1fr_1fr_180px_auto] md:items-end">
                <div className="space-y-1.5">
                  <Label>Name</Label>
                  <Input value={draftUser.name} onChange={(event) => setDraftUser((user) => ({ ...user, name: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Email</Label>
                  <Input type="email" value={draftUser.email} onChange={(event) => setDraftUser((user) => ({ ...user, email: event.target.value }))} />
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
                  <th className="px-3 py-2 font-medium">Email</th>
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
                    <td className="px-3 py-2 text-muted-foreground">{user.email || user.id}</td>
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
