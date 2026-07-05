import type { CSSProperties } from 'react';

import { useSearchMode } from '../contexts/SearchModeContext';
import type { Book, ButtonStateInfo } from '../types';
import { BookDownloadButton } from './BookDownloadButton';
import { BookGetButton } from './BookGetButton';
import { BookInLibraryButton } from './BookInLibraryButton';

type ButtonSize = 'sm' | 'md';
type ButtonVariant = 'default' | 'icon';

const isOwnedForContentType = (book: Book, contentType?: string): boolean => {
  if (contentType === 'audiobook') {
    return Boolean(book.abs_available);
  }
  if (contentType === 'ebook') {
    return Boolean(book.kavita_available);
  }
  return Boolean(book.kavita_available) || Boolean(book.abs_available);
};

interface BookActionButtonProps {
  book: Book;
  buttonState: ButtonStateInfo;
  onDownload: (book: Book) => Promise<void>;
  onGetReleases: (book: Book) => void;
  isLoadingReleases?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
  fullWidth?: boolean;
  className?: string;
  style?: CSSProperties;
}

export function BookActionButton({
  book,
  buttonState,
  onDownload,
  onGetReleases,
  isLoadingReleases,
  size,
  variant = 'default',
  fullWidth,
  className,
  style,
}: BookActionButtonProps) {
  const { searchMode, contentType } = useSearchMode();
  const activeContentType =
    book.content_type === 'ebook' || book.content_type === 'audiobook'
      ? book.content_type
      : contentType;
  const isOwnedForActiveContentType = isOwnedForContentType(book, activeContentType);

  // When the item is already in the user's library (ebook in Kavita or audiobook
  // in Audiobookshelf), replace the idle Get/Download control with a disabled
  // "In Library" button. Active states (queued/downloading/complete/error) still
  // show the real button so in-flight downloads remain visible.
  const isOwned = isOwnedForActiveContentType && buttonState.state === 'download';

  if (isOwned) {
    return (
      <BookInLibraryButton
        title={book.title}
        size={size}
        variant={variant}
        fullWidth={fullWidth}
        className={className}
        style={style}
      />
    );
  }

  if (searchMode === 'universal') {
    return (
      <BookGetButton
        book={book}
        onGetReleases={onGetReleases}
        buttonState={buttonState}
        isLoading={isLoadingReleases}
        size={size}
        variant={variant}
        fullWidth={fullWidth}
        className={className}
        style={style}
      />
    );
  }

  return (
    <BookDownloadButton
      buttonState={buttonState}
      onDownload={() => onDownload(book)}
      size={size}
      variant={variant === 'default' ? 'primary' : 'icon'}
      fullWidth={fullWidth}
      className={className}
      style={style}
      ariaLabel={buttonState.text}
    />
  );
}
