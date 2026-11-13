import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultSongTags } from '../src/song-tags.ts';

test('prefills music tags and keeps release year separate from upload date', () => {
  const metadata = { title: 'Video title', track: 'Song title', artist: 'Artist', album: 'Album', release_year: '1998', published_date: '20260101', thumbnail: 'https://i.ytimg.com/a.jpg', duration: 10, channel: 'Publisher' };
  const value = defaultSongTags(metadata);
  assert.deepEqual(value, { enabled: true, title: 'Song title', artist: 'Artist', album: 'Album', year: '1998', cover: 'thumbnail' });
  value.title = 'Edited song title';
  assert.equal(metadata.track, 'Song title');
});

test('missing release data stays blank and missing thumbnail selects no cover', () => {
  const value = defaultSongTags({ title: 'Video', published_date: '20260101', channel: 'Publisher', duration: 10, thumbnail: null });
  assert.equal(value.title, 'Video');
  assert.equal(value.artist, '');
  assert.equal(value.album, '');
  assert.equal(value.year, '');
  assert.equal(value.cover, 'none');
});
