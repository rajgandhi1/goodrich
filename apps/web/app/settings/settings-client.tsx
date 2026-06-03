"use client";
import * as React from "react";
import { AlertCircle, Bell, Building2, CheckCircle2, Edit3, KeyRound, Loader2, Lock, MoreVertical, Plus, ShieldCheck, SlidersHorizontal, Trash2, UserCog, X } from "lucide-react";
import { toast } from "sonner";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PageIntro } from "@/components/app-shell/page-intro";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { createAppUser, deleteAppUser, getAccessSettingsRemote, getBusinessMasterData, getCurrentAppUserRemote, listAppUsers, loginAppUser, patchAppUser, putAccessSettingsRemote, putBusinessMasterData, type BusinessMasterData, type CustomerRecord } from "@/lib/api";
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

const blankCustomer: CustomerRecord = {
  id: "", name: "", address_line1: "", address_line2: "", city: "", state: "", pin_code: "", country: "",
  contact_name: "", designation: "", email: "", phone: "", gst_no: "", default_currency: "INR", payment_terms: "", delivery_terms: "", active: true,
};

type AccessSaveState = "idle" | "saving" | "saved" | "error";

export function SettingsClient() {
  const [users, setUsers] = React.useState<AppUser[]>([]);
  const [currentUser, setCurrentUserState] = React.useState(() => getCurrentAppUser());
  const [draftUser, setDraftUser] = React.useState<AppUser>(blankUser);
  const [adminPassword, setAdminPassword] = React.useState("");
  const [addedUserId, setAddedUserId] = React.useState("");
  const [addUserOpen, setAddUserOpen] = React.useState(false);
  const [editingUser, setEditingUser] = React.useState<AppUser | null>(null);
  const [accessSettings, setAccessSettings] = React.useState<AccessSettings>(() => getAccessSettings());
  const confirmedAccessSettings = React.useRef(accessSettings);
  const [accessSaveState, setAccessSaveState] = React.useState<AccessSaveState>("idle");
  const [previewRole, setPreviewRole] = React.useState<AppRole>("sales");
  const [draftWithWhom, setDraftWithWhom] = React.useState("");
  const [masterData, setMasterData] = React.useState<BusinessMasterData>({ customers: [], epc_names: [] });
  const [draftCustomer, setDraftCustomer] = React.useState<CustomerRecord>(blankCustomer);
  const [draftEpc, setDraftEpc] = React.useState("");
  const canManage = canManageUsers(currentUser.role);
  const accessSavePending = accessSaveState === "saving";
  const previewCapabilities = [...pageCapabilities, ...actionCapabilities]
    .filter((capability) => canRole(previewRole, capability, accessSettings))
    .map((capability) => capabilityLabels[capability]);

  const confirmAccessSettings = React.useCallback((settings: AccessSettings, notify = false) => {
    const normalized = normalizeAccessSettings(settings);
    confirmedAccessSettings.current = normalized;
    if (notify) saveAccessSettings(normalized);
    setAccessSettings(normalized);
    return normalized;
  }, []);

  const reloadConfirmedAccessSettings = React.useCallback(async (notify = false) => {
    const settings = await getAccessSettingsRemote();
    return confirmAccessSettings(settings, notify);
  }, [confirmAccessSettings]);

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
    reloadConfirmedAccessSettings()
      .catch(() => setAccessSettings(getAccessSettings()));
    getBusinessMasterData().then(setMasterData).catch(() => setMasterData({ customers: [], epc_names: [] }));
    const refresh = () => {
      listAppUsers().then(setUsers).catch(() => setUsers([]));
      setCurrentUserState(getCurrentAppUser());
      reloadConfirmedAccessSettings().catch(() => setAccessSettings(confirmedAccessSettings.current));
    };
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener(ACCESS_SETTINGS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, [reloadConfirmedAccessSettings]);

  async function persistMasterData(next: BusinessMasterData, message: string) {
    try {
      const saved = await putBusinessMasterData(next);
      setMasterData(saved);
      toast.success(message);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save master data");
    }
  }

  function addCustomer() {
    const name = draftCustomer.name.trim();
    if (!name) return toast.error("Enter the customer name");
    const id = draftCustomer.id.trim() || name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
    if (masterData.customers.some((row) => row.id === id)) return toast.error("Customer already exists");
    void persistMasterData({ ...masterData, customers: [...masterData.customers, { ...draftCustomer, id, name }] }, "Customer added");
    setDraftCustomer(blankCustomer);
  }

  function addEpc() {
    const value = draftEpc.trim();
    if (!value || masterData.epc_names.some((row) => row.toLowerCase() === value.toLowerCase())) return;
    void persistMasterData({ ...masterData, epc_names: [...masterData.epc_names, value] }, "EPC option added");
    setDraftEpc("");
  }

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

  async function persistAccess(next: AccessSettings, message = "Access settings saved") {
    if (accessSavePending) return;
    const previous = confirmedAccessSettings.current;
    const normalized = normalizeAccessSettings(next);
    setAccessSettings(normalized);
    setAccessSaveState("saving");
    try {
      const saved = await putAccessSettingsRemote(normalized);
      try {
        await reloadConfirmedAccessSettings(true);
      } catch {
        confirmAccessSettings(saved, true);
      }
      setAccessSaveState("saved");
      toast.success(message);
    } catch (error) {
      setAccessSettings(previous);
      try {
        await reloadConfirmedAccessSettings();
      } catch {
        setAccessSettings(previous);
      }
      setAccessSaveState("error");
      toast.error(error instanceof Error ? error.message : "Could not save access settings");
    }
  }

  function addWithWhomOption() {
    const option = draftWithWhom.trim();
    if (!option) return;
    if (accessSettings.with_whom_options.some((value) => value.toLowerCase() === option.toLowerCase())) {
      toast.error("Option already exists");
      return;
    }
    void persistAccess({ ...accessSettings, with_whom_options: [...accessSettings.with_whom_options, option] }, "With whom option added");
    setDraftWithWhom("");
  }

  function removeWithWhomOption(option: string) {
    void persistAccess({
      ...accessSettings,
      with_whom_options: accessSettings.with_whom_options.filter((value) => value !== option),
    }, "With whom option removed");
  }

  function updateRoleCapability(role: AppRole, capability: AppCapability, enabled: boolean) {
    setPreviewRole(role);
    void persistAccess({
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
      <PageIntro className="lg:col-span-2" title="Workspace setup" description="Users, access rules, and business defaults." />
      <Card className="order-5">
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base"><UserCog className="h-4 w-4" />Current account</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2 p-3 sm:grid-cols-2">
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <div>
              <div className="text-sm font-medium">Authentication</div>
              <div className="text-xs text-muted-foreground">Username and password</div>
            </div>
            <Badge variant="secondary">Active</Badge>
          </div>
          <div className="rounded-md border px-3 py-2">
            <div className="text-sm font-medium">{currentUser.id}</div>
            <div className="text-xs text-muted-foreground">{currentUser.name} - {roleLabels[currentUser.role]}</div>
          </div>
        </CardContent>
      </Card>

      <Card className="order-5">
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base"><Bell className="h-4 w-4" />Preferences</CardTitle>
        </CardHeader>
        <CardContent className="p-3">
          <div className="flex items-center justify-between rounded-md border px-3 py-2">
            <Label htmlFor="email-alerts" className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-secondary" />
              Email alerts
            </Label>
            <Switch id="email-alerts" />
          </div>
        </CardContent>
      </Card>

      <Card className="order-3 lg:col-span-2">
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base"><Building2 className="h-4 w-4" />Business data</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 p-3">
          <div className="flex flex-wrap items-center gap-3 text-sm text-muted-foreground">
            <Badge variant="outline">{masterData.customers.length} customers</Badge>
            <Badge variant="outline">{masterData.epc_names.length} EPC presets</Badge>
            <span>Used as defaults in enquiry and quotation forms.</span>
          </div>
          {!canManage ? <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">Only admin users can edit master data.</div> : null}
          {canManage ? (
            <details className="rounded-md border bg-background">
              <summary className="cursor-pointer px-3 py-2 text-sm font-medium">Add customer</summary>
              <div className="grid gap-2 border-t p-3 md:grid-cols-3">
                <Input placeholder="Customer name *" value={draftCustomer.name} onChange={(event) => setDraftCustomer({ ...draftCustomer, name: event.target.value })} />
                <Input placeholder="Address line 1" value={draftCustomer.address_line1} onChange={(event) => setDraftCustomer({ ...draftCustomer, address_line1: event.target.value })} />
                <Input placeholder="City" value={draftCustomer.city} onChange={(event) => setDraftCustomer({ ...draftCustomer, city: event.target.value })} />
                <Input placeholder="Country" value={draftCustomer.country} onChange={(event) => setDraftCustomer({ ...draftCustomer, country: event.target.value })} />
                <Input placeholder="Contact person" value={draftCustomer.contact_name} onChange={(event) => setDraftCustomer({ ...draftCustomer, contact_name: event.target.value })} />
                <Input placeholder="Designation" value={draftCustomer.designation} onChange={(event) => setDraftCustomer({ ...draftCustomer, designation: event.target.value })} />
                <Input placeholder="Email" value={draftCustomer.email} onChange={(event) => setDraftCustomer({ ...draftCustomer, email: event.target.value })} />
                <Input placeholder="Phone" value={draftCustomer.phone} onChange={(event) => setDraftCustomer({ ...draftCustomer, phone: event.target.value })} />
                <Input placeholder="GST number" value={draftCustomer.gst_no} onChange={(event) => setDraftCustomer({ ...draftCustomer, gst_no: event.target.value })} />
                <Input placeholder="Payment terms default" value={draftCustomer.payment_terms} onChange={(event) => setDraftCustomer({ ...draftCustomer, payment_terms: event.target.value })} />
                <Input placeholder="Delivery terms default" value={draftCustomer.delivery_terms} onChange={(event) => setDraftCustomer({ ...draftCustomer, delivery_terms: event.target.value })} />
                <Button size="sm" onClick={addCustomer}><Plus className="h-4 w-4" />Add customer</Button>
              </div>
            </details>
          ) : null}
          <div className="overflow-auto rounded-md border">
            <table className="w-full min-w-[820px] text-sm">
              <thead className="bg-muted/50 text-left"><tr><th className="px-3 py-2">Customer</th><th className="px-3 py-2">Address</th><th className="px-3 py-2">Contact</th><th className="px-3 py-2">Commercial defaults</th><th /></tr></thead>
              <tbody>{masterData.customers.map((customer) => <tr key={customer.id} className="border-t">
                <td className="px-3 py-2 font-medium">{customer.name}</td><td className="px-3 py-2">{[customer.address_line1, customer.city, customer.country].filter(Boolean).join(", ") || "-"}</td>
                <td className="px-3 py-2">{customer.contact_name || customer.email || customer.phone || "-"}</td><td className="px-3 py-2">{customer.payment_terms || customer.delivery_terms || "-"}</td>
                <td className="px-3 py-2 text-right">{canManage ? <Button variant="ghost" size="sm" onClick={() => void persistMasterData({ ...masterData, customers: masterData.customers.filter((row) => row.id !== customer.id) }, "Customer removed")}><Trash2 className="h-4 w-4" /></Button> : null}</td>
              </tr>)}</tbody>
            </table>
          </div>
          <details className="rounded-md border bg-background">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium">EPC presets</summary>
            <div className="space-y-3 border-t p-3">
              {canManage ? <div className="flex gap-2"><Input placeholder="Add EPC / project company preset" value={draftEpc} onChange={(event) => setDraftEpc(event.target.value)} /><Button size="sm" onClick={addEpc}><Plus className="h-4 w-4" />Add EPC</Button></div> : null}
              <div className="flex flex-wrap gap-2">{masterData.epc_names.map((epc) => <Badge key={epc} variant="secondary">{epc}{canManage ? <button className="ml-1" onClick={() => void persistMasterData({ ...masterData, epc_names: masterData.epc_names.filter((row) => row !== epc) }, "EPC option removed")}><X className="h-3 w-3" /></button> : null}</Badge>)}</div>
            </div>
          </details>
        </CardContent>
      </Card>

      <Card className="order-2 lg:col-span-2">
        <CardHeader className="flex flex-row items-center justify-between gap-3 border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <SlidersHorizontal className="h-4 w-4" />
            Access controls
          </CardTitle>
          <div className="text-right" aria-live="polite">
            {accessSaveState === "idle" && <span className="text-xs text-muted-foreground">Ready to edit</span>}
            {accessSaveState === "saving" && <span className="flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="h-3.5 w-3.5 animate-spin" />Saving...</span>}
            {accessSaveState === "saved" && <span className="flex items-center gap-1 text-xs text-green-700 dark:text-green-300"><CheckCircle2 className="h-3.5 w-3.5" />Saved</span>}
            {accessSaveState === "error" && <span className="flex items-center gap-1 text-xs text-red-700 dark:text-red-300"><AlertCircle className="h-3.5 w-3.5" />Could not save. Server settings restored.</span>}
          </div>
        </CardHeader>
        <CardContent className="space-y-3 p-3">
          {!canManage && (
            <div className="rounded-md border bg-muted/30 p-3 text-sm text-muted-foreground">
              Only admin users can change access controls.
            </div>
          )}

          <details className="rounded-md border bg-background">
            <summary className="flex cursor-pointer items-center justify-between gap-3 px-3 py-2">
              <div className="text-sm font-medium">With whom options</div>
              <Badge variant="outline">{accessSettings.with_whom_options.length} options</Badge>
            </summary>
            <div className="border-t p-3">
            {canManage && (
              <div className="mb-3 grid gap-2 md:grid-cols-[minmax(0,1fr)_auto]">
                <Input value={draftWithWhom} onChange={(event) => setDraftWithWhom(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") addWithWhomOption(); }} disabled={accessSavePending} />
                <Button size="sm" onClick={addWithWhomOption} disabled={accessSavePending}>
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
                    <button type="button" className="rounded-sm hover:bg-background/60 disabled:opacity-50" onClick={() => removeWithWhomOption(option)} disabled={accessSavePending} aria-label={`Remove ${option}`}>
                      <X className="h-3 w-3" />
                    </button>
                  )}
                </Badge>
              ))}
            </div>
            </div>
          </details>

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
                    <td className="sticky left-0 bg-background px-3 py-2 font-medium">
                      <div>{label}</div>
                      {role === "admin" && (
                        <div className="mt-1 flex items-center gap-1 text-xs font-normal text-muted-foreground">
                          <Lock className="h-3 w-3" />
                          Full access (locked)
                        </div>
                      )}
                    </td>
                    {[...pageCapabilities, ...actionCapabilities].map((capability) => (
                      <td key={`${role}-${capability}`} className="px-2 py-2 text-center">
                        <Switch
                          checked={canRole(role as AppRole, capability, accessSettings)}
                          disabled={!canManage || role === "admin" || accessSavePending}
                          onCheckedChange={(checked) => updateRoleCapability(role as AppRole, capability, checked)}
                        />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <details className="rounded-md border bg-background">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium">Permission preview</summary>
            <div className="border-t p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <div className="text-xs text-muted-foreground">Check what a configured role can open or change.</div>
              </div>
              <Select value={previewRole} onValueChange={(value) => setPreviewRole(value as AppRole)}>
                <SelectTrigger className="w-48" aria-label="Preview role permissions"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {Object.entries(roleLabels).map(([role, label]) => <SelectItem key={role} value={role}>{label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="mt-3 text-sm">
              Users with this role can access: <span className="text-muted-foreground">{previewCapabilities.join(", ") || "No configured pages or actions"}</span>
            </div>
            </div>
          </details>
        </CardContent>
      </Card>

      <Card className="order-1 lg:col-span-2">
        <CardHeader className="border-b px-4 py-3">
          <CardTitle className="flex items-center gap-2 text-base">
            <UserCog className="h-4 w-4" />
            Users
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
                <div className="text-xs text-muted-foreground">{users.length} user(s) in this workspace.</div>
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
