import test from 'node:test';
import assert from 'node:assert/strict';
import { suggestFilename, suggestVideoFilename } from '../src/title.ts';

const cases: [string, string][] = [
  ['FSTVLST - Apa Kabar Opus (Lirik Video)', 'FSTVLST - Apa Kabar Opus'],
  ['Artist - Song [Official Music Video] [4K]', 'Artist - Song'],
  ['Artist - Song (Video Klip Resmi) (Lirik Lagu)', 'Artist - Song'],
  ['Artist - Song [English Subtitles] [Terjemahan Indonesia]', 'Artist - Song'],
  ['Artist - Song - Lyrics - HD', 'Artist - Song'],
  ['Artist - Song | Subscribe to our channel', 'Artist - Song'],
  ['Artist - Song [Out now on Spotify]', 'Artist - Song'],
  ['Artist - Song (Jangan lupa subscribe)', 'Artist - Song'],
  ['Artist - Song Official Music Video', 'Artist - Song'],
  ['Artist - Song (Official Video (HD))', 'Artist - Song'],
  ['Artist - Song (Remix) [Official Video]', 'Artist - Song (Remix)'],
  ['Artist - Song (Official Remix Video)', 'Artist - Song (Remix)'],
  ['Artist - Song (Radio Edit) (1998 Version) [Lyrics]', 'Artist - Song (Radio Edit) (1998 Version)'],
  ['Artist - Song (Live at Wembley) (Acoustic Cover) (Remastered 2020)', 'Artist - Song (Live at Wembley) (Acoustic Cover) (Remastered 2020)'],
  ['Artist - Video Games', 'Artist - Video Games'],
  ['Artist - The Official Story (A Song About Lyrics)', 'Artist - The Official Story (A Song About Lyrics)'],
  ['Artist - Love Lyrics', 'Artist - Love Lyrics'],
  ['Artist - Song (Spatial Audio)', 'Artist - Song (Spatial Audio)'],
  ['Artist — Song (English Version)', 'Artist — Song (English Version)'],
  ['Artist - Song (Cover Me In Lyrics)', 'Artist - Song (Cover Me In Lyrics)'],
  ['Artist — Song - (Lyrics)', 'Artist — Song'],
  ['Official', 'Official'],
  ['(Official Video)', '(Official Video)'],
];
for (const [input, expected] of cases) {
  test(`suggests a conservative filename for ${input}`, () => {
    assert.equal(suggestFilename(input), expected);
    assert.equal(suggestFilename(expected), expected, 'cleanup must be idempotent');
  });
}

const channelCases: [string, string | null, string][] = [
  ['Hindia - Berdansalah, Karir Tak Ada Artinya (Official Lyric Video)', 'Hindia', 'Berdansalah, Karir Tak Ada Artinya'],
  ['HINDIA - Song (Live)', ' hindia ', 'Song (Live)'],
  ['FSTVLST - Apa Kabar Opus (Lirik Video)', 'GUWA AHMAD', 'FSTVLST - Apa Kabar Opus'],
  ['Hindia feat. Artist - Song', 'Hindia', 'Hindia feat. Artist - Song'],
  ['Hindia - Song', 'Hindia Music', 'Song'],
  ['Hindia - Song', 'Hindia - Topic', 'Song'],
  ['Hindia - Song', 'HINDIA Official', 'Song'],
  ['Hindia - Song', 'Hindia Official - Topic', 'Song'],
  ['Hindia - Song', 'Hindia - Topic Official', 'Song'],
  ['Hindia - Song', 'Official Hindia', 'Song'],
  ['Hindia - Song', 'Hindia (Official)', 'Song'],
  ['Hindia - Song', 'Hindia [Official]', 'Song'],
  ['Hindia - Song', 'Hindia - Official', 'Song'],
  ['The Official Story - Song', 'The Official Story - Topic', 'Song'],
  ['The Story - Song', 'The Official Story', 'The Story - Song'],
  ['Hindia - Song', 'Hindia Official Music', 'Song'],
  ['Hindia - Song', 'Another Artist - Topic', 'Hindia - Song'],
  ['Hindia - Song', 'HindiaVEVO', 'Song'],
  ['Hindia - Song', 'HINDIAvevo', 'Song'],
  ['Hindia - Song', 'VEVOHindia', 'Song'],
  ['Hindia - Song', 'Hindia VEVO Official - Topic', 'Song'],
  ['Hindia - Song', 'Official HindiaVEVO', 'Song'],
  ['Hindia - Song', 'Hindia Records', 'Song'],
  ['Hindia - Song', 'Hindia Recordings', 'Song'],
  ['Hindia - Song', 'Musik Hindia Channel', 'Song'],
  ['Hindia - Song', 'Hindia Entertainment', 'Song'],
  ['Hindia - Song', '@HindiaVEVO', 'Song'],
  ['Hindia - Song', 'AnotherArtistVEVO', 'Hindia - Song'],
  ['Hindia - Song', 'Hindia Fan Uploads', 'Hindia - Song'],
  ['Music Hindia - Song', 'Music Hindia Music', 'Song'],
  ['Hindia - Song', null, 'Hindia - Song'],
  ['Hindia', 'Hindia', 'Hindia'],
  ['AC - DC — Song (Remix)', 'AC - DC', 'Song (Remix)'],
];
for (const [title, channel, expected] of channelCases) {
  test(`matches artist prefix conservatively against channel: ${title} / ${channel}`, () => {
    assert.equal(suggestFilename(title, channel), expected);
    assert.equal(suggestFilename(expected, channel), expected, 'channel cleanup must be stable');
  });
}

const protectedTitles: [string, string | null, string][] = [
  ['Artist - Lyrics (Official Video)', null, 'Artist - Lyrics'],
  ['Artist - Video (Official Music Video)', null, 'Artist - Video'],
  ['Artist - Official Music Video', null, 'Artist - Official Music Video'],
  ['Artist - (Video) [Official Video]', null, 'Artist - (Video)'],
  ['Artist - Lyrics - HD', 'Artist', 'Lyrics'],
  ['Artist - Video [Lyrics]', 'ArtistVEVO', 'Video'],
  ['Hindia - Hindia - Song', 'Hindia', 'Hindia - Hindia - Song'],
  ['Hindia - Hindia - Song [Official Video]', 'Hindia', 'Hindia - Hindia - Song'],
];
for (const [title, channel, expected] of protectedTitles) {
  test(`protects actual song text and stays stable: ${title}`, () => {
    assert.equal(suggestFilename(title, channel), expected);
    assert.equal(suggestFilename(expected, channel), expected);
  });
}

test('cleanup remains stable across artist, title, label, and channel combinations', () => {
  for (const artist of ['Hindia', 'Artist', 'AC - DC']) {
    for (const song of ['Song', 'Lyrics', 'Video', '(Lyrics)', 'Hindia - Song', 'Artist - Song', 'Song - Lyrics', 'Official Music Video', 'Song (Live)']) {
      for (const tag of ['', ' (Official Video)', ' [Lyrics]', ' - HD', ' (Official Video (HD))']) {
        for (const channel of [null, 'Hindia', 'Artist', 'AC - DC', 'ArtistVEVO']) {
          const title = `${artist} - ${song}${tag}`;
          const suggestion = suggestFilename(title, channel);
          assert.equal(suggestFilename(suggestion, channel), suggestion, `${title} / ${channel}`);
          assert.ok(suggestion.trim(), 'suggestions must never be empty');
        }
      }
    }
  }
});

const metadataCases = [
  { video: { title: 'Messy upload (Official Video)', channel: 'HindiaVEVO', track: 'Song', artist: 'Hindia' }, expected: 'Song' },
  { video: { title: 'Messy upload [Lyrics]', channel: 'Music Label', track: 'Song', artist: 'Hindia' }, expected: 'Hindia - Song' },
  { video: { title: 'Artist - Upload [Lyrics]', channel: 'Artist', track: 'Lyrics', artist: 'Artist' }, expected: 'Lyrics' },
  { video: { title: 'Artist - Upload', channel: 'Label', track: 'Official Music Video', artist: 'Artist' }, expected: 'Artist - Official Music Video' },
  { video: { title: 'Hindia - Song [Lyrics]', channel: 'Hindia', track: '', artist: 'Hindia' }, expected: 'Song' },
  { video: { title: 'Hindia - Song [Lyrics]', channel: 'Hindia', track: 'Underlying Song' }, expected: 'Song' },
  { video: { title: 'Hindia - Song (Remix) [Official Video]', channel: 'Hindia', track: 'Song', artist: 'Hindia' }, expected: 'Song (Remix)' },
  { video: { title: 'Artist - Song (Cover)', channel: 'Performer', track: 'Song', artist: 'Original Artist' }, expected: 'Artist - Song (Cover)' },
  { video: { title: 'Hindia - Song (1998 Version)', channel: 'Hindia', track: 'Song (Version)', artist: 'Hindia' }, expected: 'Song (1998 Version)' },
  { video: { title: 'Song (Radio Edit)', channel: 'Artist Official', track: 'Song (Radio Edit)', artist: 'Artist' }, expected: 'Song (Radio Edit)' },
  { video: { title: 'Upload [Lyrics]', channel: 'Label', track: ' Song ', artist: ' Artist A & Artist B ' }, expected: 'Artist A & Artist B - Song' },
];
for (const { video, expected } of metadataCases) {
  test(`uses metadata or conservative fallback: ${video.title} / ${video.track}`, () => {
    const original = { ...video };
    assert.equal(suggestVideoFilename(video), expected);
    assert.deepEqual(video, original, 'preview metadata must remain unchanged');
  });
}

const creditCases = [
  { title: 'Artist feat. Guest - Song [Official Video]', channel: 'Artist', track: 'Song', artist: 'Artist', expected: 'Artist feat. Guest - Song' },
  { title: 'Artist ft. Guest - Song', channel: 'Artist', track: 'Song', artist: 'Artist', expected: 'Artist ft. Guest - Song' },
  { title: 'Artist featuring Guest - Song', channel: 'Label', track: 'Song', artist: 'Artist', expected: 'Artist featuring Guest - Song' },
  { title: 'Artist & Guest - Song', channel: 'Artist & Guest', track: 'Song', artist: 'Artist', expected: 'Artist & Guest - Song' },
  { title: 'Artist x Guest - Song', channel: 'Artist', track: 'Song', artist: 'Artist', expected: 'Artist x Guest - Song' },
  { title: 'Artist - Song (feat. Guest)', channel: 'Artist', track: 'Song', artist: 'Artist', expected: 'Song (feat. Guest)' },
  { title: 'Artist - Song (feat. Guest A & Guest B)', channel: 'Artist', track: 'Song (feat. Guest A)', artist: 'Artist', expected: 'Song (feat. Guest A & Guest B)' },
  { title: 'Artist - Song (DJ Example Remix) [Official Video]', channel: 'Artist', track: 'Song (Remix)', artist: 'Artist', expected: 'Song (DJ Example Remix)' },
  { title: 'Artist - Song - DJ Example Remix', channel: 'Artist', track: 'Song (Remix)', artist: 'Artist', expected: 'Song - DJ Example Remix' },
  { title: 'Artist - Song (Remix by DJ Example)', channel: 'Artist', track: 'Song (Remix)', artist: 'Artist', expected: 'Song (Remix by DJ Example)' },
  { title: 'Artist - Song (DJ - Example Remix)', channel: 'Artist', track: 'Song (Example Remix)', artist: 'Artist', expected: 'Song (DJ - Example Remix)' },
  { title: 'Artist feat. Mary - Jane - Song', channel: 'Artist', track: 'Song', artist: 'Artist & Mary', expected: 'Artist feat. Mary - Jane - Song' },
  { title: 'Artist - Song (DJ Example Remix)', channel: 'Artist', track: 'Song (DJ Example Remix)', artist: 'Artist', expected: 'Song (DJ Example Remix)' },
  { title: 'Artist - Song (Ann Remix)', channel: 'Artist', track: 'Song (Joanne Remix)', artist: 'Artist', expected: 'Song (Ann Remix)' },
  { title: 'Artist - Song (feat. Guest) [Lyrics]', channel: 'Artist', track: 'Song (featuring Guest)', artist: 'Artist', expected: 'Song (featuring Guest)' },
  { title: 'Artist - Song (DJ Example Remix)', channel: 'Artist', track: 'Song (DJ Example Remix)', artist: 'Artist', expected: 'Song (DJ Example Remix)' },
];
for (const { expected, ...video } of creditCases) {
  test(`retains featured artists and remixer credits: ${video.title}`, () => {
    assert.equal(suggestVideoFilename(video), expected);
    const parsed = suggestFilename(video.title, video.channel);
    assert.equal(suggestFilename(parsed, video.channel), parsed);
  });
}

test('matching a collaborative channel does not erase its credited artists', () => {
  assert.equal(suggestFilename('Artist & Guest - Song', 'Artist & Guest Official'), 'Artist & Guest - Song');
});
