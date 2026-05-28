"use client";

import { LogOut, Settings, UserCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { getCurrentAppUserRemote, logoutAppUser } from "@/lib/api";
import { clearLocalSession } from "@/lib/auth/local-session";
import { getSupabaseBrowserClient } from "@/lib/auth/supabase";
import { getCurrentAppUser, roleLabels, setCurrentAppUser, USERS_CHANGED_EVENT } from "@/lib/auth/users";

export function UserMenu() {
  const router = useRouter();
  const [user, setUser] = React.useState(() => getCurrentAppUser());

  React.useEffect(() => {
    const refresh = () => setUser(getCurrentAppUser());
    getCurrentAppUserRemote()
      .then((remoteUser) => {
        setCurrentAppUser(remoteUser);
        setUser(remoteUser);
      })
      .catch(() => setUser(getCurrentAppUser()));
    window.addEventListener(USERS_CHANGED_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(USERS_CHANGED_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, []);

  async function signOut() {
    const supabase = getSupabaseBrowserClient();
    if (supabase) {
      await supabase.auth.signOut();
    }
    await logoutAppUser().catch(() => undefined);
    clearLocalSession();
    toast.success("Signed out");
    router.push("/login");
    router.refresh();
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Open user menu">
          <UserCircle className="h-5 w-5" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>
          <div>{user.name || "GGPL user"}</div>
          <div className="text-xs font-normal text-muted-foreground">{roleLabels[user.role]}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => router.push("/settings")}>
          <Settings className="mr-2 h-4 w-4" />
          Settings
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={signOut}>
          <LogOut className="mr-2 h-4 w-4" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
