import test from 'node:test';
import assert from 'node:assert/strict';
import { suggestFilename } from '../src/title.ts';

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
  });
}
