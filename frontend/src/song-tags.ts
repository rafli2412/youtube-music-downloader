import type { SongTags, VideoMetadata } from './desktop';
import { officialChannelArtist, suggestFilename, suggestVideoFilename } from './title.ts';

export function defaultSongTags(video?: VideoMetadata | null): SongTags {
  const artist = video?.artist?.trim() || (video ? officialChannelArtist(video) : '');
  const suggestion = video ? suggestVideoFilename(video) : '';
  const title = artist ? suggestFilename(suggestion, artist) : suggestion;
  const publishedYear = video?.published_date?.match(/^(\d{4})\d{4}$/)?.[1] ?? '';
  return { enabled: true, title, artist, album: video?.album ?? '', year: publishedYear || video?.release_year || '', track_number: video?.track_number ?? '', cover: video?.thumbnail ? 'thumbnail' : 'none' };
}
