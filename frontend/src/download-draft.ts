import type { JobState } from './desktop';

/** A stable preview identity survives failed attempts; a new link needs a new preview. */
export function reviewablePreview(job: JobState): string | null {
  if (job.busy || !job.metadata || !['ready', 'failed', 'cancelled'].includes(job.status)) return null;
  return job.preview_id ?? (job.status === 'ready' ? job.job_id : null);
}
