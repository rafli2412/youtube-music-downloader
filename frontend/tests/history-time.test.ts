import test from 'node:test';
import assert from 'node:assert/strict';
import { historyTime } from '../src/history-time.ts';

const now = new Date(2026, 10, 15, 14, 30);
const at = (day: number, hour = 12) => new Date(2026, 10, day, hour, 5).toISOString();
test('recent timestamps show today, yesterday, or weekday with full accessible date', () => {
  assert.equal(historyTime(at(15), now).label, 'Today, 12:05');
  assert.equal(historyTime(at(14), now).label, 'Yesterday, 12:05');
  assert.equal(historyTime(at(13), now).label, 'Friday, 12:05');
  assert.match(historyTime(at(13), now).full, /13 November 2026/);
});
test('seven-day boundary and older dates use DD/MM/YYYY and local HH:MM', () => {
  assert.equal(historyTime(at(8), now).label, '08/11/2026, 12:05');
  assert.equal(historyTime(new Date(now.getTime() - 7 * 86400000).toISOString(), now).label, '08/11/2026, 14:30');
  assert.equal(historyTime(at(9), now).label, 'Monday, 12:05');
  assert.equal(historyTime(at(16), now).label, '16/11/2026, 12:05');
});
test('calendar-day labels remain correct across month and year boundaries', () => {
  const january = new Date(2027, 0, 1, 10, 0);
  assert.equal(historyTime(new Date(2026, 11, 31, 23, 5).toISOString(), january).label, 'Yesterday, 23:05');
  assert.equal(historyTime('not a date', now).label, 'Date unavailable');
});
