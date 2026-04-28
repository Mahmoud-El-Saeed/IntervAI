import { cn } from '../../lib/utils';

export function Button({ className, variant = 'primary', ...props }) {
  const variants = {
    primary:
      'bg-primary-container text-on-primary-container shadow-glow hover:bg-primary/90',
    secondary:
      'border border-outline-variant bg-surface-container/70 text-on-surface hover:bg-surface-container-high/80',
    ghost: 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container-low/70',
    danger: 'bg-error-container text-on-error-container hover:opacity-90',
  };

  return (
    <button
      className={cn(
        'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50',
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}
