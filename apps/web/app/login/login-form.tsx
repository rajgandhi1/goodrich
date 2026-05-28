"use client";

import { ArrowRight, LockKeyhole } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import * as React from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { loginAppUser } from "@/lib/api";
import { setLocalSession } from "@/lib/auth/local-session";
import { roleLabels, setCurrentAppUser } from "@/lib/auth/users";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectTo = searchParams.get("redirect") || "/dashboard";
  const [username, setUsername] = React.useState("");
  const [password, setPassword] = React.useState("");
  const [loading, setLoading] = React.useState(false);

  async function handlePasswordAuth(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    try {
      const user = await loginAppUser(username, password);
      setCurrentAppUser(user);
      setLocalSession();
      toast.success(`Signed in as ${user.id} (${roleLabels[user.role]})`);
      router.push(redirectTo);
      router.refresh();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Invalid username or password");
    } finally {
      setLoading(false);
    }
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="text-sm font-medium text-primary">Goodrich Gasket Pvt. Ltd.</div>
        <CardTitle className="flex items-center gap-2">
          <LockKeyhole className="h-5 w-5" />
          Quote workspace sign in
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handlePasswordAuth} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="username">Username</Label>
            <Input
              id="username"
              autoComplete="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </div>
          <Button type="submit" className="w-full" disabled={loading}>
            Continue
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </form>

        <div className="mt-4 rounded-md border bg-muted/30 px-3 py-2 text-xs text-muted-foreground">
          User accounts are created by admins in Settings. Self sign-up is disabled.
        </div>
      </CardContent>
    </Card>
  );
}
