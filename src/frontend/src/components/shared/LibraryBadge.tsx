import type { Book } from '../../types';

interface LibraryBadgeProps {
  book: Book;
  variant?: 'overlay' | 'inline';
}

interface Pill {
  key: string;
  label: string;
  className: string;
  title: string;
}

const buildPills = (book: Book): Pill[] => {
  const pills: Pill[] = [];
  const total =
    typeof book.series_count === 'number' && book.series_count > 0 ? book.series_count : null;

  // Ebook library — Kavita and Calibre-Web / CWA are both ebook libraries, so
  // their ownership folds into a single indicator. Series coverage uses the
  // larger of the two counts; "in library" is true if either server has it.
  const ebookOwned = Math.max(book.kavita_series_owned ?? 0, book.calibre_series_owned ?? 0);
  const ebookAvailable = Boolean(book.kavita_available || book.calibre_available);
  if (ebookOwned > 0) {
    pills.push({
      key: 'ebook-series',
      label: `Library ${ebookOwned}${total ? `/${total}` : ''}`,
      className: 'border border-indigo-700 bg-indigo-600',
      title: 'Books of this series already in your ebook library',
    });
  } else if (ebookAvailable) {
    pills.push({
      key: 'ebook',
      label: 'In Library',
      className: 'border border-indigo-700 bg-indigo-600',
      title: 'This book is already in your ebook library',
    });
  }

  // Audiobook library (Audiobookshelf)
  const audioOwned = book.abs_series_owned;
  if (typeof audioOwned === 'number' && audioOwned > 0) {
    pills.push({
      key: 'audio-series',
      label: `Audiobook ${audioOwned}${total ? `/${total}` : ''}`,
      className: 'border border-amber-700 bg-amber-600',
      title: 'Books of this series already in your audiobook library',
    });
  } else if (book.abs_available) {
    pills.push({
      key: 'audio',
      label: 'Audiobook',
      className: 'border border-amber-700 bg-amber-600',
      title: 'This audiobook is already in your Audiobookshelf library',
    });
  }

  return pills;
};

export const LibraryBadge = ({ book, variant = 'inline' }: LibraryBadgeProps) => {
  const pills = buildPills(book);
  if (pills.length === 0) {
    return null;
  }

  const base = 'inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-bold text-white';
  const overlayShadow =
    variant === 'overlay'
      ? { boxShadow: '0 2px 8px rgba(0,0,0,0.4), 0 1px 3px rgba(0,0,0,0.3)' }
      : undefined;

  return (
    <span className={variant === 'overlay' ? 'flex flex-col items-end gap-1' : 'inline-flex gap-1'}>
      {pills.map((pill) => (
        <span
          key={pill.key}
          className={`${base} ${pill.className}`}
          style={overlayShadow}
          title={pill.title}
        >
          {pill.label}
        </span>
      ))}
    </span>
  );
};
