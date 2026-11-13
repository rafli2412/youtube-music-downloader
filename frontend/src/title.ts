/** Conservative label cleanup for editable filename suggestions, never display titles. */
const noiseWords = /\b(?:official|resmi|music|musik|video|clip|klip|lyrics?|lyric|lirik|teks|text|audio|visuali[sz]er|mv|hd|hq|uhd|[248]k|1080p|720p|subtitles?|sub|subs|subtitle|terjemahan|translated|translation|english|indonesian|indonesia|indo|bahasa|with|dengan|dan|and|lagu|cc)\b/gi;
const versionWords = /\b(?:remix|mix|radio\s+edit|edit|version|versi|cover|live|acoustic|akustik|instrumental|remaster(?:ed)?|sped\s+up|slowed|reverb|original\s+mix)\b/i;
const promotion = /^(?:(?:out|available|stream|listen|watch|download)\s+now\b.*|(?:dengarkan|tonton|unduh)\s+sekarang\b.*|(?:jangan\s+lupa\s+)?subscribe\b.*|pre[- ]?save\b.*)$/i;

function cleanLabel(label: string): string {
  const text = label.trim();
  if (promotion.test(text)) return '';
  const remainder = text.replace(noiseWords, '').replace(/m\/v/gi, '').replace(/[\s\-–—|,:/]+/g, ' ').trim();
  // Unknown wording might be part of a song name: retain the whole group.
  if (!remainder) return '';
  // When a version is explicitly named, remove only presentation labels around it.
  if (versionWords.test(text)) {
    const candidate = text.replace(/\b(?:official|resmi|music\s+video|video\s+klip|video\s+musik|lirik\s+video|video\s+lirik|lyrics?\s+video|video|lyrics?|lirik|hd|hq|uhd|[248]k|1080p|720p)\b/gi, '').replace(/\s+/g, ' ').trim();
    if (/^(?:(?:remix|mix|radio\s+edit|edit|version|versi|cover|live|acoustic|akustik|instrumental|remaster(?:ed)?|sped\s+up|slowed|reverb)|\d{4}|[\s/&-])+$/i.test(candidate)) return candidate;
    return text.replace(/\b(?:official|resmi)\s+(?:(?:music|musik)\s+)?(?:video|audio|visuali[sz]er)\b|\b(?:lyrics?\s+video|lirik\s+video|video\s+lirik|video\s+klip\s+resmi)\b|\b(?:official|resmi|hd|hq|uhd|[248]k|1080p|720p)\b/gi, '').replace(/\s+/g, ' ').trim();
  }
  return text;
}

function withoutMatchingArtist(title: string, channel?: string | null): string {
  const normalized = (value: string) => value.normalize('NFKC').replace(/\s+/g, ' ').trim().toLowerCase();
  if (!channel?.trim()) return title;
  // Only known channel branding is ignored; arbitrary extra names are not fuzzy-matched.
  const label = '(?:official\\s+channel|music\\s+group|record\\s+label|official|topic|vevo|music|musik|records?|recordings?|entertainment|productions?|studios?|channel|tv|rekaman)';
  const separator = '[\\s._–—|:-]+';
  const prefix = new RegExp('^' + label + separator, 'i');
  const suffix = new RegExp(separator + label + '$', 'i');
  const wrappedSuffix = new RegExp('\\s*[([]' + label + '[)\\]]$', 'i');
  const initial = normalized(channel).replace(/^@/, '');
  const channelNames = new Set([initial]);
  const candidates = [initial];
  // Retain intermediate names, so real artist names containing a label still match exactly.
  for (let index = 0; index < candidates.length && index < 64; index++) {
    const current = candidates[index];
    for (const candidate of [
      current.replace(prefix, ''), current.replace(suffix, ''),
      current.replace(wrappedSuffix, ''), current.replace(/^vevo|vevo$/gi, ''),
    ]) {
      const cleaned = candidate.trim();
      if (cleaned && !channelNames.has(cleaned)) {
        channelNames.add(cleaned);
        candidates.push(cleaned);
      }
    }
  }
  for (const separator of title.matchAll(/\s+[-–—|:]\s+/g)) {
    const artist = title.slice(0, separator.index);
    const song = title.slice(separator.index! + separator[0].length).trim();
    if (song && channelNames.has(normalized(artist))) {
      // A repeated artist-looking prefix may actually be part of the song title.
      // Keep this ambiguous structure instead of stripping another part on each call.
      for (const nested of song.matchAll(/\s+[-–—|:]\s+/g)) {
        if (channelNames.has(normalized(song.slice(0, nested.index)))) return title;
      }
      return song;
    }
  }
  return title;
}

function hasSongText(value: string): boolean {
  const separator = /\s+[-–—|:](?:\s+|$)/.exec(value);
  return (separator ? value.slice(separator.index + separator[0].length) : value).trim().length > 0;
}

export function suggestFilename(title: string, channel?: string | null): string {
  let result = title.trim();
  while (true) {
    const previous = result;
    result = result.replace(/\(([^()[\]{}]*)\)|\[([^()[\]{}]*)\]|\{([^()[\]{}]*)\}/g, (group, round, square, curly, offset) => {
      const original = round ?? square ?? curly;
      const cleaned = cleanLabel(original);
      // A label-like group at the start of the song might be its actual name.
      if (!cleaned && !hasSongText(result.slice(0, offset))) return group;
      return cleaned ? group[0] + cleaned + group[group.length - 1] : '';
    });
    // Strip only trailing labelled segments, retaining artist and song separators.
    const pieces = result.split(/(\s+[-–—|•]\s+)/);
    while (pieces.length > 4 && cleanLabel(pieces[pieces.length - 1]) === '') pieces.splice(-2);
    result = pieces.join('');
    // Clear, multiword presentation suffixes are safe even without brackets.
    const withoutSuffix = result.replace(/\s+(?:official\s+(?:music\s+)?(?:video|audio|visuali[sz]er)|video\s+(?:klip\s+)?resmi|lirik\s+video|video\s+lirik)\s*$/i, '').replace(/\s+/g, ' ').trim();
    if (hasSongText(withoutSuffix)) result = withoutSuffix;
    if (result !== previous) result = result.replace(/\s+[-–—|•]\s*$/, '').trim();
    if (result === previous) break;
  }
  return withoutMatchingArtist(result || title.trim(), channel);
}
