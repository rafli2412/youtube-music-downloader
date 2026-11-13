import { useState } from 'react';
import type { VideoMetadata } from './desktop';

export function durationLabel(seconds: number | null): string {
  if (seconds === null || !Number.isFinite(seconds) || seconds < 0) return 'Not available';
  const total = Math.floor(seconds);
  const minutes = Math.floor(total / 60);
  const remainder = String(total % 60).padStart(2, '0');
  return minutes >= 60 ? `${Math.floor(minutes / 60)}:${String(minutes % 60).padStart(2, '0')}:${remainder}` : `${minutes}:${remainder}`;
}

export function VideoDetails({ video }: { video: VideoMetadata }) {
  const [failedImage, setFailedImage] = useState<string | null>(null);
  let thumbnail: string | null = null;
  try {
    const url = new URL(video.thumbnail ?? '');
    if (url.protocol === 'https:' && (url.hostname === 'ytimg.com' || url.hostname.endsWith('.ytimg.com'))) thumbnail = url.href;
  } catch { /* Missing thumbnails use the placeholder. */ }
  const date = video.published_date;
  const publishedAt = typeof video.published_timestamp === 'number' ? new Date(video.published_timestamp * 1000) : null;
  const published = publishedAt && Number.isFinite(publishedAt.getTime())
    ? publishedAt.toLocaleString(undefined, { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', timeZoneName: 'short' })
    : date && /^\d{8}$/.test(date) ? `${date.slice(0, 4)}-${date.slice(4, 6)}-${date.slice(6, 8)}` : 'Not available';
  return <section className="video-details" aria-label="YouTube video details">
    <div className="video-thumbnail">{thumbnail && failedImage !== thumbnail ? <img src={thumbnail} alt={`Thumbnail for ${video.title ?? 'this video'}`} referrerPolicy="no-referrer" onError={() => setFailedImage(thumbnail)} /> : <span>Thumbnail unavailable</span>}</div>
    <div className="video-information"><h3>{video.title ?? 'Untitled video'}</h3><dl>
      <div><dt>Channel</dt><dd>{video.channel ?? 'Not available'}</dd></div>
      <div><dt>Duration</dt><dd>{durationLabel(video.duration)}</dd></div>
      <div><dt>Published</dt><dd>{published}</dd></div>
    </dl></div>
  </section>;
}
