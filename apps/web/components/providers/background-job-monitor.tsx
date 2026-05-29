"use client";

import * as React from "react";
import { toast } from "sonner";

import { getJobStatus } from "@/lib/api";
import {
  BACKGROUND_JOBS_EVENT,
  BackgroundExtractionJob,
  listBackgroundJobs,
  removeBackgroundJob,
} from "@/lib/background-jobs";

function openQuote(job: BackgroundExtractionJob) {
  if (!job.quoteId) return;
  window.location.href = `/quotes?quote=${job.quoteId}`;
}

export function BackgroundJobMonitor() {
  const [jobs, setJobs] = React.useState<BackgroundExtractionJob[]>([]);

  React.useEffect(() => {
    const sync = () => setJobs(listBackgroundJobs());
    sync();
    window.addEventListener(BACKGROUND_JOBS_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(BACKGROUND_JOBS_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  React.useEffect(() => {
    if (!jobs.length) return undefined;
    let cancelled = false;

    async function poll() {
      for (const job of listBackgroundJobs()) {
        try {
          const status = await getJobStatus(job.id);
          if (cancelled) return;
          if (status.status === "succeeded") {
            removeBackgroundJob(job.id);
            toast.success(`${job.label} is ready`, {
              description: `${status.parsed_count} item(s) added to the list.`,
              action: job.quoteId ? { label: "Open", onClick: () => openQuote(job) } : undefined,
            });
          } else if (status.status === "failed") {
            removeBackgroundJob(job.id);
            toast.error(`${job.label} failed`, {
              description: status.error ?? "Could not create the item list.",
              action: job.quoteId ? { label: "Open", onClick: () => openQuote(job) } : undefined,
            });
          }
        } catch (error) {
          if (cancelled) return;
          const message = error instanceof Error ? error.message : "";
          if (message.includes("404")) removeBackgroundJob(job.id);
        }
      }
    }

    void poll();
    const timer = window.setInterval(() => void poll(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [jobs]);

  return null;
}
