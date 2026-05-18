"use client";

import * as React from "react";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";

import { GasketChatWidget } from "@/components/chat/gasket-chat-widget";
import { BackgroundJobMonitor } from "@/components/providers/background-job-monitor";
import { PostHogProvider } from "@/lib/posthog";

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <PostHogProvider>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        {children}
        <BackgroundJobMonitor />
        <GasketChatWidget />
        <Toaster richColors position="top-right" closeButton />
      </ThemeProvider>
    </PostHogProvider>
  );
}
