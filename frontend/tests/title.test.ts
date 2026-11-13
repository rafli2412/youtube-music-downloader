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
