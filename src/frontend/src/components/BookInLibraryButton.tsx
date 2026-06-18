import type { CSSProperties } from 'react';

type ButtonSize = 'sm' | 'md';
type ButtonVariant = 'default' | 'icon';

interface BookInLibraryButtonProps {
  title?: string;
  size?: ButtonSize;
  variant?: ButtonVariant;
  fullWidth?: boolean;
  className?: string;
  style?: CSSProperties;
}

const sizeClasses: Record<ButtonSize, string> = {
  sm: 'px-2.5 py-1.5 text-xs',
  md: 'px-4 py-2.5 text-sm',
};

const iconSizeClasses: Record<ButtonSize, string> = {
  sm: 'p-1.5',
  md: 'p-1.5 sm:p-2',
};

const iconSizes: Record<ButtonSize, string> = {
  sm: 'w-3.5 h-3.5',
  md: 'w-4 h-4',
};

const iconOnlySizes: Record<ButtonSize, string> = {
  sm: 'w-4 h-4',
  md: 'w-4 h-4 sm:w-5 sm:h-5',
};

const CheckIcon = ({ className }: { className: string }) => (
  <svg className={className} fill="none" stroke="currentColor" viewBox="0 0 24 24" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
  </svg>
);

/**
 * Disabled placeholder shown in place of the Get/Download button when an item is
 * already present in the user's library (Kavita ebook or Audiobookshelf audiobook).
 */
export const BookInLibraryButton = ({
  title,
  size = 'md',
  variant = 'default',
  fullWidth = false,
  className = '',
  style,
}: BookInLibraryButtonProps) => {
  const tooltip = title ? `Already in your library: ${title}` : 'Already in your library';

  if (variant === 'icon') {
    return (
      <button
        type="button"
        disabled
        title={tooltip}
        aria-label={tooltip}
        style={style}
        className={`flex cursor-not-allowed items-center justify-center rounded-full text-gray-400 opacity-70 dark:text-gray-500 ${iconSizeClasses[size]} ${className}`.trim()}
      >
        <CheckIcon className={iconOnlySizes[size]} />
      </button>
    );
  }

  return (
    <button
      type="button"
      disabled
      title={tooltip}
      aria-label={tooltip}
      style={style}
      className={`inline-flex cursor-not-allowed items-center justify-center gap-1.5 rounded-sm bg-gray-500 text-white opacity-75 ${sizeClasses[size]} ${fullWidth ? 'w-full' : ''} ${className}`.trim()}
    >
      <CheckIcon className={iconSizes[size]} />
      <span>In Library</span>
    </button>
  );
};
