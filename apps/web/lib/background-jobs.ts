"use client";

export const BACKGROUND_JOBS_EVENT = "ggpl-background-jobs-changed";

export type BackgroundExtractionJob = {
  id: string;
  quoteId: string | null;
  sourceType: string;
  label: string;
  startedAt: string;
};

let inMemoryJobs: BackgroundExtractionJob[] = [];

function readJobs(): BackgroundExtractionJob[] {
  return inMemoryJobs;
}

function writeJobs(jobs: BackgroundExtractionJob[]) {
  inMemoryJobs = jobs;
  if (typeof window === "undefined") return;
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
