import type { ButtonHTMLAttributes } from 'react';

/** Show visual help on icon-only controls; retain accessible descriptions for all buttons. */
export function TooltipButton({ tooltip, iconOnly = false, type = 'button', ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { tooltip: string; iconOnly?: boolean }) {
  return <button {...props} type={type} data-tooltip={iconOnly ? tooltip : undefined} aria-description={tooltip} />;
}
