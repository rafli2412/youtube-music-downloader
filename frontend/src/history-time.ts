export function historyTime(value: string, now = new Date()): { label: string; full: string } {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { label: 'Date unavailable', full: 'Date unavailable' };
  const pad = (number: number) => String(number).padStart(2, '0');
  const time = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
  const days = Math.round((Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()) - Date.UTC(date.getFullYear(), date.getMonth(), date.getDate())) / 86400000);
  const recent = now.getTime() >= date.getTime() && now.getTime() - date.getTime() < 7 * 86400000;
  const day = recent && days === 0 ? 'Today' : recent && days === 1 ? 'Yesterday'
    : recent ? new Intl.DateTimeFormat('en-GB', { weekday: 'long' }).format(date)
    : `${pad(date.getDate())}/${pad(date.getMonth() + 1)}/${date.getFullYear()}`;
  const full = new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZoneName: 'short' }).format(date);
  return { label: `${day}, ${time}`, full };
}
