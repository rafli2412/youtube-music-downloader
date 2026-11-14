import test from 'node:test';
import assert from 'node:assert/strict';
import { DraftWriteQueue } from '../src/draft-storage.ts';

test('closing flush waits behind older autosaves and writes the latest edits last', async () => {
  const queue = new DraftWriteQueue();
  const writes: string[] = [];
  let release!: () => void;
  const held = new Promise<void>(resolve => { release = resolve; });
  const old = queue.enqueue(async () => { await held; writes.push('older edits'); });
  const closing = queue.enqueue(async () => { writes.push('latest filename, tags, and cover'); });
  assert.deepEqual(writes, []);
  release();
  await closing;
  await old;
  assert.deepEqual(writes, ['older edits', 'latest filename, tags, and cover']);
});

test('a failed save does not block the next save or a discard', async () => {
  const queue = new DraftWriteQueue();
  await assert.rejects(queue.enqueue(async () => { throw new Error('Disk full'); }));
  const writes: string[] = [];
  const save = queue.enqueue(async () => { writes.push('save'); });
  const clear = queue.enqueue(async () => { writes.push('clear'); });
  await Promise.all([save, clear]);
  assert.deepEqual(writes, ['save', 'clear']);
});
