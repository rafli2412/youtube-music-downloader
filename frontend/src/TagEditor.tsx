import type { CoverSelection, SongTags } from './desktop';

export function TagEditor({ value, onChange, cover, thumbnail, onChooseCover, disabled, suggestedAlbum }: {
  value: SongTags; onChange: (value: SongTags) => void; cover: CoverSelection | null;
  thumbnail: string | null; onChooseCover: () => void; disabled: boolean; suggestedAlbum?: string | null;
}) {
  const preview = value.cover === 'local' ? cover?.preview : value.cover === 'thumbnail' ? thumbnail : null;
  return <section className="tag-editor" aria-labelledby="tags-heading">
    <div className="tag-heading"><h3 id="tags-heading">Song tags</h3><label className="tag-toggle"><input type="checkbox" checked={value.enabled} onChange={event => onChange({ ...value, enabled: event.target.checked })} disabled={disabled} />Include tags and artwork</label></div>
    <p className="folder-hint">These appear in music players. Changing the filename does not change the song title.</p>
    <fieldset disabled={disabled || !value.enabled}>
      <div className="tag-grid">{(['title', 'artist', 'album', 'year', 'track_number'] as const).map(field => <div key={field}><label htmlFor={`tag-${field}`}>{field === 'title' ? 'Song title' : field === 'year' ? 'Release year' : field === 'track_number' ? 'Track number' : field[0].toUpperCase() + field.slice(1)}</label><input id={`tag-${field}`} type="text" value={value[field] ?? ''} onChange={event => onChange({ ...value, [field]: field === 'track_number' ? event.target.value.replace(/[^0-9]/g, '') : event.target.value })} placeholder="Not available — optional" maxLength={field === 'year' ? 4 : 1000} pattern={field === 'year' ? '[0-9]{4}' : field === 'track_number' ? '[0-9]*' : undefined} inputMode={field === 'year' || field === 'track_number' ? 'numeric' : undefined} />{field === 'album' && suggestedAlbum && value.album === suggestedAlbum && <p className="folder-hint">Suggested from the video description — please verify.</p>}</div>)}</div>
      <p className="folder-hint">Year defaults to the video publication year. Verify the album, year, and track number before saving.</p>
      <label htmlFor="cover-source">Album cover</label><div className="cover-controls"><select id="cover-source" value={value.cover} onChange={event => onChange({ ...value, cover: event.target.value as SongTags['cover'] })}><option value="thumbnail" disabled={!thumbnail}>Video thumbnail</option><option value="local">Local image</option><option value="none">No cover</option></select><button className="secondary-button" type="button" onClick={onChooseCover}>Choose image…</button></div>
      {value.cover === 'local' && <p className="folder-hint">{cover?.name ?? 'Choose a JPEG, PNG, or WebP image (up to 10 MB).'}</p>}
      {preview && <img className="album-cover-preview" src={preview} alt="Selected album cover" referrerPolicy="no-referrer" />}
      {value.cover === 'thumbnail' && <p className="folder-hint">The video thumbnail may differ from the original album cover.</p>}
    </fieldset>
  </section>;
}
