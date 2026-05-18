"use client";

export const BACKGROUND_JOBS_EVENT = "ggpl-background-jobs-changed";

const STORAGE_KEY = "ggpl.backgroundExtractionJobs";

export type BackgroundExtractionJob = {
  id: string;
  quoteId: string | null;
  sourceType: string;
  label: string;
  startedAt: string;
};

function readJobs(): BackgroundExtractionJob[] {
  if (typeof window === "undefined") return [];
  try {
    const parsed = JSON.parse(window.localStorage.getItem(STORAGE_KEY) ?? "[]");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeJobs(jobs: BackgroundExtractionJob[]) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
  window.dispatchEvent(new Event(BACKGROUND_JOBS_EVENT));
}

export function listBackgroundJobs(): BackgroundExtractionJob[] {
  return readJobs();
}

export function addBackgroundJob(job: BackgroundExtractionJob) {
  const jobs = readJobs().filter((item) => item.id !== job.id);
  writeJobs([...jobs, job]);
}

export function removeBackgroundJob(jobId: string) {
  writeJobs(readJobs().filter((job) => job.id !== jobId));
}
