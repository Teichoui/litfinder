import { useCallback, useRef, useState } from 'react';

import { useBodyScrollLock } from '../../hooks/useBodyScrollLock';
import { useEscapeKey } from '../../hooks/useEscapeKey';
import { useDependencyEffect } from '../../hooks/useMountEffect';
import {
  addWatchlistAuthor,
  fetchFieldOptions,
  fetchWatchlistAuthors,
  fetchWatchlistReleases,
  getMetadataProviders,
  removeWatchlistAuthor,
  updateWatchlistAuthor,
  updateWatchlistRelease,
  type DynamicFieldOption,
} from '../../services/api';
import type { WatchlistAuthor, WatchlistRelease } from '../../types';
import { ToggleSwitch } from '../shared';

interface WatchlistModalProps {
  isOpen: boolean;
  onClose: () => void;
  showToast: (message: string, type?: 'info' | 'success' | 'error') => void;
}

const AUTHOR_SEARCH_MIN_LENGTH = 2;
const AUTHOR_SEARCH_DEBOUNCE_MS = 300;

const releaseLabel = (release: WatchlistRelease): string =>
  release.book_data.title || release.provider_book_id;

export const WatchlistModal = ({ isOpen, onClose, showToast }: WatchlistModalProps) => {
  useBodyScrollLock(isOpen);
  useEscapeKey(isOpen, onClose);

  const [authors, setAuthors] = useState<WatchlistAuthor[]>([]);
  const [releases, setReleases] = useState<WatchlistRelease[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [authorQuery, setAuthorQuery] = useState('');
  const [authorOptions, setAuthorOptions] = useState<DynamicFieldOption[]>([]);
  const [isAdding, setIsAdding] = useState(false);
  const [hardcoverAvailable, setHardcoverAvailable] = useState(true);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const loadAll = useCallback(async () => {
    setIsLoading(true);
    try {
      const [authorsResult, releasesResult, providersResult] = await Promise.all([
        fetchWatchlistAuthors(),
        fetchWatchlistReleases('detected'),
        getMetadataProviders(),
      ]);
      setAuthors(authorsResult);
      setReleases(releasesResult);
      setHardcoverAvailable(
        providersResult.providers.some((p) => p.name === 'hardcover' && p.available),
      );
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Failed to load watchlist', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  useDependencyEffect(() => {
    if (isOpen) {
      void loadAll();
    }
  }, [isOpen, loadAll]);

  useDependencyEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    const query = authorQuery.trim();
    if (!hardcoverAvailable || query.length < AUTHOR_SEARCH_MIN_LENGTH) {
      setAuthorOptions([]);
      return () => {
        debounceRef.current = null;
      };
    }
    debounceRef.current = setTimeout(() => {
      // Explicitly target Hardcover regardless of the globally configured metadata
      // provider — added authors are always keyed by hardcover_author_id below.
      void fetchFieldOptions('/api/metadata/field-options?field=author&provider=hardcover', query)
        .then(setAuthorOptions)
        .catch(() => setAuthorOptions([]));
    }, AUTHOR_SEARCH_DEBOUNCE_MS);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [authorQuery, hardcoverAvailable]);

  const handleAddAuthor = async (option: DynamicFieldOption) => {
    const hardcoverAuthorId = option.value.startsWith('id:') ? option.value.slice(3) : null;
    if (!hardcoverAuthorId) return;

    setIsAdding(true);
    try {
      const created = await addWatchlistAuthor({
        author_name: option.label,
        hardcover_author_id: hardcoverAuthorId,
      });
      setAuthors((prev) => [...prev, created]);
      setAuthorQuery('');
      setAuthorOptions([]);
      showToast(`Watching ${created.author_name}`, 'success');
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Failed to add author', 'error');
    } finally {
      setIsAdding(false);
    }
  };

  const handleRemoveAuthor = async (watch: WatchlistAuthor) => {
    try {
      await removeWatchlistAuthor(watch.id);
      setAuthors((prev) => prev.filter((a) => a.id !== watch.id));
      showToast(`Stopped watching ${watch.author_name}`, 'success');
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Failed to remove author', 'error');
    }
  };

  const handleToggleActive = async (watch: WatchlistAuthor, isActive: boolean) => {
    try {
      const updated = await updateWatchlistAuthor(watch.id, { is_active: isActive });
      setAuthors((prev) => prev.map((a) => (a.id === watch.id ? updated : a)));
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Failed to update author', 'error');
    }
  };

  const handleReleaseAction = async (
    release: WatchlistRelease,
    actionStatus: 'skipped' | 'ignored',
  ) => {
    try {
      await updateWatchlistRelease(release.id, actionStatus);
      // The list only ever holds detected releases (fetched with action_status=detected),
      // so once actioned it no longer belongs here.
      setReleases((prev) => prev.filter((r) => r.id !== release.id));
    } catch (error) {
      showToast(error instanceof Error ? error.message : 'Failed to update release', 'error');
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      onKeyDown={(e) => {
        if (e.key === 'Escape') onClose();
      }}
      role="presentation"
    >
      <div className="relative mx-4 my-4 flex h-full max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-(--border-muted) bg-(--bg) shadow-2xl">
        <div className="flex items-center justify-between border-b border-(--border-muted) px-5 py-4">
          <h2 className="text-base font-semibold">Author Watchlist</h2>
          <button
            type="button"
            onClick={onClose}
            className="hover-action flex h-8 w-8 items-center justify-center rounded-full"
            aria-label="Close"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path
                fillRule="evenodd"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                clipRule="evenodd"
              />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {/* Add author */}
          <div className="relative mb-6">
            <label htmlFor="watchlist-author-search" className="mb-1 block text-sm font-medium">
              Add an author to watch
            </label>
            <input
              id="watchlist-author-search"
              type="text"
              value={authorQuery}
              onChange={(e) => setAuthorQuery(e.target.value)}
              disabled={isAdding || !hardcoverAvailable}
              placeholder={
                hardcoverAvailable ? 'Search by author name…' : 'Hardcover is not available'
              }
              className="w-full rounded-lg border border-(--border-muted) bg-(--bg-subtle) px-3 py-2 text-sm outline-hidden focus:border-emerald-500 disabled:opacity-60"
            />
            {!hardcoverAvailable && (
              <p className="mt-1 text-xs text-(--text-muted)">
                The watchlist looks up authors via Hardcover, which isn't configured or available
                right now.
              </p>
            )}
            {authorOptions.length > 0 && (
              <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-(--border-muted) bg-(--bg) shadow-lg">
                {authorOptions.map((option) => (
                  <li key={option.value}>
                    <button
                      type="button"
                      onClick={() => void handleAddAuthor(option)}
                      className="hover-action block w-full px-3 py-2 text-left text-sm"
                    >
                      {option.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Watched authors */}
          <div className="mb-6">
            <h3 className="mb-2 text-sm font-semibold text-(--text-muted)">Watched authors</h3>
            {authors.length === 0 && !isLoading && (
              <p className="text-sm text-(--text-muted)">
                No authors watched yet. Search above to add one.
              </p>
            )}
            <ul className="space-y-2">
              {authors.map((watch) => (
                <li
                  key={watch.id}
                  className="flex items-center justify-between rounded-lg border border-(--border-muted) px-3 py-2"
                >
                  <span className="text-sm">{watch.author_name}</span>
                  <div className="flex items-center gap-3">
                    <ToggleSwitch
                      checked={Boolean(watch.is_active)}
                      onChange={(checked) => void handleToggleActive(watch, checked)}
                      color="emerald"
                    />
                    <button
                      type="button"
                      onClick={() => void handleRemoveAuthor(watch)}
                      className="hover-action rounded-full p-1.5 text-red-500"
                      aria-label={`Stop watching ${watch.author_name}`}
                    >
                      <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
                        <path
                          fillRule="evenodd"
                          d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482 41.03 41.03 0 00-2.365-.298V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z"
                          clipRule="evenodd"
                        />
                      </svg>
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Detected releases */}
          <div>
            <h3 className="mb-2 text-sm font-semibold text-(--text-muted)">
              Detected releases
              {releases.length > 0 && ` (${releases.length})`}
            </h3>
            <p className="mb-3 text-xs text-(--text-muted)">
              New releases from watched authors show up here once detected. This requires a
              scheduled scan that hasn't been built yet, so this list will stay empty for now even
              with authors watched.
            </p>
            {releases.length === 0 && !isLoading && (
              <p className="text-sm text-(--text-muted)">No releases detected yet.</p>
            )}
            <ul className="space-y-2">
              {releases.map((release) => (
                <li
                  key={release.id}
                  className="flex items-center justify-between rounded-lg border border-(--border-muted) px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm">{releaseLabel(release)}</p>
                    <p className="text-xs text-(--text-muted)">
                      {release.content_type} · {release.provider}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void handleReleaseAction(release, 'skipped')}
                      className="hover-action rounded-full px-2.5 py-1 text-xs"
                    >
                      Skip
                    </button>
                    <button
                      type="button"
                      onClick={() => void handleReleaseAction(release, 'ignored')}
                      className="hover-action rounded-full px-2.5 py-1 text-xs"
                    >
                      Ignore
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
};
