import type { ButtonHTMLAttributes } from 'react';

/** Shared Album-style hover and keyboard-focus help. */
export function TooltipButton({ tooltip, type = 'button', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { tooltip: string }) {
  return <button {...props} type={type} data-tooltip={tooltip} aria-description={tooltip} />;
}
