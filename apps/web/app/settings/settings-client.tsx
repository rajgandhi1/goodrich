"use client";
import * as React from "react";
import { Bell, CheckCircle2, Edit3, KeyRound, MoreVertical, Plus, ShieldCheck, SlidersHorizontal, Trash2, UserCog, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { createAppUser, deleteAppUser, getAccessSettingsRemote, getCurrentAppUserRemote, listAppUsers, loginAppUser, patchAppUser, putAccessSettingsRemote } from "@/lib/api";
import { ACCESS_SETTINGS_CHANGED_EVENT, AccessSettings, AppCapability, actionCapabilities, canRole, capabilityLabels, getAccessSettings, normalizeAccessSettings, pageCapabilities, saveAccessSettings } from "@/lib/auth/access-control";
import { AppRole, AppUser, canManageUsers, getCurrentAppUser, roleLabels, setCurrentAppUser, USERS_CHANGED_EVENT } from "@/lib/auth/users";

const blankUser: AppUser = {
  id: "",
  name: "",
  email: "",
  designation: "",
  contact: "",
  password: "",
  role: "sales",
  active: true,
};

export function SettingsClient() {
  const [users, setUsers] = React.useState<AppUser[]>([]);
  const [currentUser, setCurrentUserState] = React.useState(() => getCurrentAppUser());
  const [draftUser, setDraftUser] = React.useState<AppUser>(blankUser);
  const [adminPassword, setAdminPassword] = React.useState("");
  const [addedUserId, setAddedUserId] = React.useState("");
  const [addUserOpen, setAddUserOpen] = React.useState(false);
  const [editingUser, setEditingUser] = React.useState<AppUser | null>(null);
  const [accessSettings, setAccessSettings] = React.useState<AccessSettings>(() => getAccessSettings());
  const [draftWithWhom, setDraftWithWhom] = React.useState("");
  const canManage = canManageUsers(currentUser.role);

  React.useEffect(() => {
    getCurrentAppUserRemote()
      .then((user) => {
        setCurrentAppUser(user);
        setCurrentUserState(user);
      })
      .catch(() => setCurrentUserState(getCurrentAppUser()));
    listAppUsers()
      .then((rows) => {
        setUsers(rows);
        setCurrentUserState(getCurrentAppUser());
      })
      .catch(() => {
        setUsers([]);
      });
    getAccessSettingsRemote()
      .then((settings) => {
        const normalized = normalizeAccessSettings(settings);
        saveAccessSettings(normalized);
        setAccessSettings(normalized);
      })
      .catch(() => setAccessSettings(getAccessSettings()));
    const refresh = () => {
      listAppUsers().then(setUsers).catch(() => setUsers([]));
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
    setUsers(next);
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
    const verifiedPassword = adminPassword.trim();
    const password = String(draftUser.password || "").trim();
    if (!verifiedPassword) {
      toast.error("Enter your admin password before adding a user");
      return;
    }
    if (!username) {
      toast.error("Enter a User ID / username");
      return;
    }
    if (!draftUser.name.trim()) {
      toast.error("Enter the employee name");
      return;
    }
    if (!password) {
      toast.error("Set a temporary password for the employee");
      return;
    }
    if (users.some((user) => user.id.toLowerCase() === username)) {
      toast.error("User already exists");
      return;
    }
    try {
      await loginAppUser(currentUser.id, verifiedPassword);
      const email = draftUser.email.trim().toLowerCase();
      const created = await createAppUser({ ...draftUser, id: username, email, name: draftUser.name.trim() || username, active: true });
      persistUsers([...users, created]);
      setDraftUser(blankUser);
      setAdminPassword("");
      setAddedUserId(created.id);
      setAddUserOpen(false);
      toast.success(`${created.name || created.id} added to the user list`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not add user");
    }
  }

  function saveEditedUser() {
    if (!editingUser) return;
    const password = String(editingUser.password || "").trim();
    const patch: Partial<AppUser> = {
      name: editingUser.name,
      designation: editingUser.designation || "",
      contact: editingUser.contact || "",
      email: editingUser.email,
      role: editingUser.role,
      active: editingUser.active,
      ...(password ? { password } : {}),
    };
    updateUser(editingUser.id, patch);
    setEditingUser(null);
    toast.success("User details updated");
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
            <div className="flex items-center justify-between gap-3 rounded-md border p-3">
              <div>
                <div className="text-sm font-medium">Employee users</div>
                <div className="text-xs text-muted-foreground">Add a permanent username with editable employee details.</div>
              </div>
              <Button size="sm" onClick={() => setAddUserOpen(true)}>
                <Plus className="h-4 w-4" />
                Add employee user
              </Button>
              {addedUserId && (
                <div className="flex items-center gap-2 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-800 dark:border-green-900/50 dark:bg-green-950/30 dark:text-green-200">
                  <CheckCircle2 className="h-4 w-4" />
                  User {addedUserId} has been added to the list.
                </div>
              )}
            </div>
          )}

          <div className="overflow-auto rounded-md border">
            <table className="w-full min-w-[980px] text-sm">
              <thead className="bg-muted/50 text-left">
                <tr>
                  <th className="px-3 py-2 font-medium">User ID</th>
                  <th className="px-3 py-2 font-medium">Employee name</th>
                  <th className="px-3 py-2 font-medium">Designation</th>
                  <th className="px-3 py-2 font-medium">Contact</th>
                  <th className="px-3 py-2 font-medium">Email ID</th>
                  <th className="px-3 py-2 font-medium">Role</th>
                  <th className="px-3 py-2 font-medium">Active</th>
                  <th className="px-3 py-2 text-right font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className={user.id === addedUserId ? "border-t bg-green-50/70 dark:bg-green-950/20" : "border-t"}>
                    <td className="px-3 py-2 font-mono text-xs">{user.id}</td>
                    <td className="px-3 py-2 font-medium">{user.name || "Vacant / To Be Hired"}</td>
                    <td className="px-3 py-2">{user.designation || <span className="text-muted-foreground">Not set</span>}</td>
                    <td className="px-3 py-2">{user.contact || <span className="text-muted-foreground">Not set</span>}</td>
                    <td className="px-3 py-2">{user.email || <span className="text-muted-foreground">Not set</span>}</td>
                    <td className="px-3 py-2">
                      <Badge variant="secondary">{roleLabels[user.role]}</Badge>
                    </td>
                    <td className="px-3 py-2">
                      <Switch checked={user.active} disabled={!canManage} onCheckedChange={(checked) => updateUser(user.id, { active: checked })} />
                    </td>
                    <td className="px-3 py-2 text-right">
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <Button variant="ghost" size="icon" disabled={!canManage} aria-label={`Manage ${user.name || user.id}`}>
                            <MoreVertical className="h-4 w-4" />
                          </Button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                          <DropdownMenuItem onSelect={() => setEditingUser({ ...user, password: "" })}>
                            <Edit3 className="mr-2 h-4 w-4" />
                            Edit
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem disabled={user.id === currentUser.id} onSelect={() => removeUser(user.id)}>
                            <Trash2 className="mr-2 h-4 w-4" />
                            Remove
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={addUserOpen} onOpenChange={setAddUserOpen}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>Add employee user</DialogTitle>
            <DialogDescription>Create a permanent User ID and set the employee credentials for first login.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 lg:grid-cols-[280px_minmax(0,1fr)]">
            <div className="rounded-md border bg-muted/20 p-3">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                <KeyRound className="h-4 w-4" />
                Step 1: Admin verification
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="admin-password">Admin password</Label>
                <Input
                  id="admin-password"
                  type="password"
                  autoComplete="current-password"
                  value={adminPassword}
                  onChange={(event) => setAdminPassword(event.target.value)}
                />
              </div>
            </div>

            <div className="rounded-md border p-3">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium">
                <UserCog className="h-4 w-4" />
                Step 2: Employee credentials
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="space-y-1.5">
                  <Label>User ID / Username</Label>
                  <Input placeholder="usr-004" value={draftUser.id} onChange={(event) => setDraftUser((user) => ({ ...user, id: event.target.value }))} />
                  <div className="text-xs text-muted-foreground">Locked to the account after saving.</div>
                </div>
                <div className="space-y-1.5">
                  <Label>Employee name</Label>
                  <Input value={draftUser.name} onChange={(event) => setDraftUser((user) => ({ ...user, name: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Designation</Label>
                  <Input value={draftUser.designation || ""} onChange={(event) => setDraftUser((user) => ({ ...user, designation: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Contact no</Label>
                  <Input value={draftUser.contact || ""} onChange={(event) => setDraftUser((user) => ({ ...user, contact: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Email ID</Label>
                  <Input type="email" value={draftUser.email} onChange={(event) => setDraftUser((user) => ({ ...user, email: event.target.value }))} />
                </div>
                <div className="space-y-1.5">
                  <Label>Set temporary password</Label>
                  <Input type="password" autoComplete="new-password" value={draftUser.password || ""} onChange={(event) => setDraftUser((user) => ({ ...user, password: event.target.value }))} />
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
              </div>
              <div className="mt-4 text-xs text-muted-foreground">
                Keep the username permanent so historical activity stays linked even if employee details change later.
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => { setDraftUser(blankUser); setAdminPassword(""); setAddUserOpen(false); }}>
              Cancel
            </Button>
            <Button onClick={addUser}>
              <Plus className="h-4 w-4" />
              Save & Add User
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={Boolean(editingUser)} onOpenChange={(open) => { if (!open) setEditingUser(null); }}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>Edit user details</DialogTitle>
            <DialogDescription>User ID is permanent. Employee details can be updated when a seat changes hands.</DialogDescription>
          </DialogHeader>
          {editingUser && (
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-1.5">
                <Label>User ID / Username</Label>
                <Input value={editingUser.id} disabled />
              </div>
              <div className="space-y-1.5">
                <Label>Employee name</Label>
                <Input value={editingUser.name} onChange={(event) => setEditingUser((user) => user ? { ...user, name: event.target.value } : user)} />
              </div>
              <div className="space-y-1.5">
                <Label>Designation</Label>
                <Input value={editingUser.designation || ""} onChange={(event) => setEditingUser((user) => user ? { ...user, designation: event.target.value } : user)} />
              </div>
              <div className="space-y-1.5">
                <Label>Contact no</Label>
                <Input value={editingUser.contact || ""} onChange={(event) => setEditingUser((user) => user ? { ...user, contact: event.target.value } : user)} />
              </div>
              <div className="space-y-1.5">
                <Label>Email ID</Label>
                <Input type="email" value={editingUser.email} onChange={(event) => setEditingUser((user) => user ? { ...user, email: event.target.value } : user)} />
              </div>
              <div className="space-y-1.5">
                <Label>Role</Label>
                <Select value={editingUser.role} onValueChange={(value) => setEditingUser((user) => user ? { ...user, role: value as AppRole } : user)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(roleLabels).map(([role, label]) => <SelectItem key={role} value={role}>{label}</SelectItem>)}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Set new temporary password</Label>
                <Input
                  type="password"
                  autoComplete="new-password"
                  placeholder="Leave blank to keep current"
                  value={editingUser.password || ""}
                  onChange={(event) => setEditingUser((user) => user ? { ...user, password: event.target.value } : user)}
                />
              </div>
              <div className="flex items-center justify-between rounded-md border px-3 py-2">
                <Label>Active user</Label>
                <Switch checked={editingUser.active} onCheckedChange={(checked) => setEditingUser((user) => user ? { ...user, active: checked } : user)} />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingUser(null)}>Cancel</Button>
            <Button onClick={saveEditedUser}>Save changes</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
