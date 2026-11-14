import { useEffect, useState } from 'react';
import type { CoverSelection, SongTags } from './desktop';

export function TagEditor({ value, onChange, cover, thumbnail, onChooseCover, disabled, suggestedAlbum }: {
  value: SongTags; onChange: (value: SongTags) => void; cover: CoverSelection | null;
  thumbnail: string | null; onChooseCover: (file?: File, source?: 'paste' | 'drop') => void; disabled: boolean; suggestedAlbum?: string | null;
}) {
  const [dragging, setDragging] = useState(false);
  const [imageError, setImageError] = useState('');
  const receive = (files: File[], source: 'paste' | 'drop') => {
    if (disabled || !value.enabled) return;
    if (files.length === 0) { setImageError(''); onChooseCover(undefined, source); return; }
    if (files.length !== 1) { setImageError('Add one image at a time.'); return; }
    const file = files[0];
    if (file.type && !['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
      if (file.type.startsWith('image/')) { setImageError(''); onChooseCover(undefined, source); return; }
      setImageError('Choose a JPEG, PNG, or WebP image.'); return;
    }
    if (file.size > 10 * 1024 * 1024) { setImageError('Cover images must be 10 MB or smaller.'); return; }
    setImageError(''); onChooseCover(file);
  };
  useEffect(() => {
    if (value.cover !== 'local' || disabled || !value.enabled) return;
    const paste = (event: ClipboardEvent) => {
      const target = event.target;
      const editing = (element: EventTarget | null) => element instanceof HTMLElement
        && (element.matches('input, textarea, select') || element.isContentEditable);
      if (editing(target) || editing(document.activeElement)) return;
      event.preventDefault();
      receive(Array.from(event.clipboardData?.files ?? []), 'paste');
    };
    document.addEventListener('paste', paste);
    return () => document.removeEventListener('paste', paste);
  });
  const preview = value.cover === 'local' ? cover?.preview : value.cover === 'thumbnail' ? thumbnail : null;
  return <section className="tag-editor" aria-labelledby="tags-heading">
    <div className="tag-heading"><h3 id="tags-heading">Song tags</h3><label className="tag-toggle"><input type="checkbox" checked={value.enabled} onChange={event => onChange({ ...value, enabled: event.target.checked })} disabled={disabled} />Include tags and artwork</label></div>
    {value.enabled && <>
    <p className="folder-hint">These appear in music players. Changing the filename does not change the song title.</p>
    <fieldset disabled={disabled}>
      <div className="tag-grid">{(['title', 'artist', 'album', 'year', 'track_number'] as const).map(field => <div key={field}><label htmlFor={`tag-${field}`}>{field === 'title' ? 'Song title' : field === 'year' ? 'Release year' : field === 'track_number' ? 'Track number' : field[0].toUpperCase() + field.slice(1)}</label><input id={`tag-${field}`} type="text" value={value[field] ?? ''} onChange={event => onChange({ ...value, [field]: field === 'track_number' ? event.target.value.replace(/[^0-9]/g, '') : event.target.value })} placeholder="Not available — optional" maxLength={field === 'year' ? 4 : 1000} pattern={field === 'year' ? '[0-9]{4}' : field === 'track_number' ? '[0-9]*' : undefined} inputMode={field === 'year' || field === 'track_number' ? 'numeric' : undefined} />{field === 'album' && suggestedAlbum && value.album === suggestedAlbum && <p className="folder-hint">Suggested from the video description — please verify.</p>}</div>)}</div>
      <p className="folder-hint">Year defaults to the video publication year. Verify the album, year, and track number before saving.</p>
      <label htmlFor="cover-source">Album cover</label><div className="cover-controls"><select id="cover-source" value={value.cover} onChange={event => onChange({ ...value, cover: event.target.value as SongTags['cover'] })}><option value="thumbnail" disabled={!thumbnail}>Video thumbnail</option><option value="local">Select an image</option><option value="none">No cover</option></select></div>
      {value.cover === 'local' && <>
        <button type="button" className={`cover-dropzone${dragging ? ' dragging' : ''}`} aria-label="Select cover image: browse, drop, or paste" onClick={() => { setImageError(''); onChooseCover(); }}
          onDragOver={event => { event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; if (!disabled && value.enabled) setDragging(true); }}
          onDragLeave={() => setDragging(false)} onDrop={event => { event.preventDefault(); setDragging(false); receive(Array.from(event.dataTransfer.files), 'drop'); }}>
          <svg aria-hidden="true" width="48" height="48" viewBox="0 0 48 48" fill="none" stroke="currentColor" strokeWidth="2"><rect x="6" y="8" width="31" height="27" rx="3"/><path d="M12 40h30V16M7 29l9-9 8 8 5-5 8 8"/><circle cx="28" cy="16" r="3"/></svg>
          <span>Choose an image</span><span className="cover-drop-hint">Click to browse · Drag &amp; drop · Copy &amp; paste</span>
          <span className="cover-drop-hint">JPEG, PNG or WebP · Up to 10 MB</span>
        </button>
        {imageError && <p role="alert" className="error-message">{imageError}</p>}
      </>}
      {value.cover === 'local' && <p className="folder-hint">{cover?.name ?? 'Choose a JPEG, PNG, or WebP image (up to 10 MB).'}</p>}
      {preview && <img className="album-cover-preview" src={preview} alt="Selected album cover" referrerPolicy="no-referrer" />}
      {value.cover === 'thumbnail' && <p className="folder-hint">The video thumbnail may differ from the original album cover.</p>}
    </fieldset>
    </>}
  </section>;
}
