import test from 'node:test';
import assert from 'node:assert/strict';
import { reviewablePreview } from '../src/download-draft.ts';
import type { JobState } from '../src/desktop.ts';

const job: JobState = { job_id: 'attempt-1', preview_id: 'preview-1', status: 'ready', busy: false, downloaded_bytes: 0, total_bytes: null, fraction: null, directory: '/tmp/audio', result: null, error: null, metadata: { title: 'Video', channel: 'Artist', duration: 10, published_date: null, thumbnail: null } };

test('failed attempts retain the same draft identity for retry', () => {
  assert.equal(reviewablePreview(job), 'preview-1');
  assert.equal(reviewablePreview({ ...job, job_id: 'attempt-2', status: 'failed', error: 'Verification required' }), 'preview-1');
  assert.equal(reviewablePreview({ ...job, job_id: 'attempt-3', status: 'cancelled' }), 'preview-1');
});

test('failed previews and new links do not reuse an old draft', () => {
  assert.equal(reviewablePreview({ ...job, status: 'failed', preview_id: null }), null);
  assert.equal(reviewablePreview({ ...job, status: 'idle', preview_id: null, metadata: null }), null);
  assert.equal(reviewablePreview({ ...job, job_id: 'new-video', preview_id: 'new-preview' }), 'new-preview');
});

test('busy and completed jobs cannot be submitted again', () => {
  assert.equal(reviewablePreview({ ...job, busy: true }), null);
  assert.equal(reviewablePreview({ ...job, status: 'downloading', busy: true }), null);
  assert.equal(reviewablePreview({ ...job, status: 'complete' }), null);
});
