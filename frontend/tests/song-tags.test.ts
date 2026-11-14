import test from 'node:test';
import assert from 'node:assert/strict';
import { defaultSongTags } from '../src/song-tags.ts';

test('prefills music tags and keeps release year separate from upload date', () => {
  const metadata = { title: 'Video title', track: 'Song title', artist: 'Artist', album: 'Album', release_year: '1998', published_date: '20260101', thumbnail: 'https://i.ytimg.com/a.jpg', duration: 10, channel: 'Publisher' };
  const value = defaultSongTags(metadata);
  assert.deepEqual(value, { enabled: true, title: 'Song title', artist: 'Artist', album: 'Album', year: '2026', track_number: '', cover: 'thumbnail' });
  value.title = 'Edited song title';
  assert.equal(metadata.track, 'Song title');
});

test('missing release data stays blank and missing thumbnail selects no cover', () => {
  const value = defaultSongTags({ title: 'Video', published_date: '20260101', channel: 'Publisher', duration: 10, thumbnail: null });
  assert.equal(value.title, 'Video');
  assert.equal(value.artist, '');
  assert.equal(value.album, '');
  assert.equal(value.year, '2026');
  assert.equal(value.cover, 'none');
});

const base = { title: 'Hindia - Berdansalah, Karir Tak Ada Artinya (Official Lyric Video)', channel: 'Hindia', channel_is_verified: true, duration: 10, published_date: '20231015', thumbnail: null };
test('verified matching channel supplies artist and parsed song title', () => {
  const tags = defaultSongTags(base);
  assert.equal(tags.artist, 'Hindia');
  assert.equal(tags.title, 'Berdansalah, Karir Tak Ada Artinya');
  assert.equal(tags.year, '2023');
});
test('unofficial lyric uploads do not supply their channel as artist', () => {
  assert.equal(defaultSongTags({ ...base, channel: 'Lyric fan', channel_is_verified: false }).artist, '');
  assert.equal(defaultSongTags({ ...base, channel_is_verified: false }).artist, '');
  assert.equal(defaultSongTags({ ...base, channel: 'Lyric fan', channel_is_verified: true }).artist, '');
});
test('known official branding matches while metadata credits remain intact', () => {
  for (const channel of ['Hindia - Topic', 'HindiaVEVO', 'Hindia Official']) {
    assert.equal(defaultSongTags({ ...base, channel, channel_is_verified: false }).artist, 'Hindia');
  }
  const tags = defaultSongTags({ ...base, track: 'Song', artist: 'Hindia feat. Guest', title: 'Hindia feat. Guest - Song', track_number: '12', album: 'Album' });
  assert.equal(tags.artist, 'Hindia feat. Guest');
  assert.match(tags.title, /Guest/);
  assert.equal(tags.track_number, '12');
  assert.equal(tags.album, 'Album');
});

test('description album suggestions prefill tags without mutating preview metadata', () => {
  const video = { ...base, album: 'Description Album', album_source: 'description' as const };
  const tags = defaultSongTags(video);
  assert.equal(tags.album, 'Description Album');
  tags.album = 'Edited Album';
  assert.equal(video.album, 'Description Album');
  assert.equal(defaultSongTags({ ...base, album: null }).album, '');
});
