import { TooltipButton } from './TooltipButton';
import type { ButtonHTMLAttributes } from 'react';

type HistoryIcon = 'refresh' | 'remove' | 'folder' | 'youtube' | 'clear-selection' | 'remove-selected';

function Icon({ name }: { name: HistoryIcon }) {
  const shapes = {
    refresh: <><path d="M20 7v5h-5" /><path d="M19 12a7 7 0 1 0-2 5M20 12l-3-5" /></>,
    remove: <><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 10v7M14 10v7" /></>,
    folder: <><path d="M3 9V5h6l2 2h10v4M3 9h18l-3 10H5L3 9Z" /></>,
    youtube: <><rect x="3" y="5" width="18" height="14" rx="4" /><path d="m10 9 5 3-5 3V9Z" /></>,
    'clear-selection': <><rect x="4" y="4" width="16" height="16" rx="3" /><path d="m9 9 6 6M15 9l-6 6" /></>,
    'remove-selected': <><path d="M3 8h15M7 8V5h7v3M5 8l1 12h10l1-12M10 11v6M13 11v6M17 3l3 3M20 3l-3 3" /></>,
  };
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{shapes[name]}</svg>;
}

export function HistoryIconButton({ icon, label, hint, className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { icon: HistoryIcon; label: string; hint?: string }) {
  const descriptions: Record<HistoryIcon, string> = {
    refresh: 'Reload saved downloads while keeping the current search. Selection will be cleared.',
    remove: 'Remove this history entry only. The MP3 file is kept.',
    folder: 'Show this MP3 in Finder or File Explorer.',
    youtube: 'Open this video on YouTube in your browser.',
    'clear-selection': 'Uncheck all selected history entries without removing anything.',
    'remove-selected': 'Remove the selected history entries only. All MP3 files are kept.',
  };
  const tooltip = hint ? `${descriptions[icon]} ${hint}` : descriptions[icon];
  return <span className="history-icon-wrap"><TooltipButton tooltip={tooltip} {...props} type="button" className={`history-icon-button ${className}`} aria-label={label}><Icon name={icon} /></TooltipButton></span>;
}
