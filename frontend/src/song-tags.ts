import type { SongTags, VideoMetadata } from './desktop';

export function defaultSongTags(video?: VideoMetadata | null): SongTags {
  return { enabled: true, title: video?.track ?? video?.title ?? '', artist: video?.artist ?? '', album: video?.album ?? '', year: video?.release_year ?? '', cover: video?.thumbnail ? 'thumbnail' : 'none' };
}

