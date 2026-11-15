import type { ButtonHTMLAttributes } from 'react';

/** Native hover help plus the same description on keyboard focus. */
export function TooltipButton({ tooltip, type = 'button', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { tooltip: string }) {
  return <button {...props} type={type} title={tooltip} data-tooltip={tooltip} aria-description={tooltip} />;
}
