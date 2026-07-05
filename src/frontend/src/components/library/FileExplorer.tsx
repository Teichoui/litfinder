import { useState, useCallback, useRef, useMemo } from 'react';

import { useMediaQuery } from '../../hooks/useMediaQuery';
import { useMountEffect } from '../../hooks/useMountEffect';
import type { LibraryFolder, DirEntry } from '../../services/api';
import {
  fetchLibraryFolders,
  listDirectory,
  renameEntry,
  makeDirectory,
  organizeFiles,
} from '../../services/api';
import { formatFileSize, formatDate } from '../../utils/formatters';

// ─── icons ────────────────────────────────────────────────────────────────────

const Icon = ({ d, className }: { d: string; className?: string }) => (
  <svg
    className={className ?? 'h-4 w-4'}
    viewBox="0 0 20 20"
    fill="currentColor"
    aria-hidden="true"
  >
    <path fillRule="evenodd" d={d} clipRule="evenodd" />
  </svg>
);

const FolderIcon = ({ className }: { className?: string }) => (
  <svg
    className={className ?? 'h-4 w-4'}
    viewBox="0 0 20 20"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
  </svg>
);

const AudioIcon = ({ className }: { className?: string }) => (
  <svg
    className={className ?? 'h-4 w-4'}
    viewBox="0 0 20 20"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.369 4.369 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z" />
  </svg>
);

const BookIcon = ({ className }: { className?: string }) => (
  <svg
    className={className ?? 'h-4 w-4'}
    viewBox="0 0 20 20"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M9 4.804A7.968 7.968 0 005.5 4c-1.255 0-2.443.29-3.5.804v10A7.969 7.969 0 015.5 14c1.669 0 3.218.51 4.5 1.385A7.962 7.962 0 0114.5 14c1.255 0 2.443.29 3.5.804v-10A7.968 7.968 0 0014.5 4c-1.255 0-2.443.29-3.5.804V12a1 1 0 11-2 0V4.804z" />
  </svg>
);

const DocIcon = ({ className }: { className?: string }) => (
  <Icon
    className={className ?? 'h-4 w-4'}
    d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4zm2 6a1 1 0 011-1h6a1 1 0 110 2H7a1 1 0 01-1-1zm1 3a1 1 0 100 2h6a1 1 0 100-2H7z"
  />
);

const ChevronRight = ({ className }: { className?: string }) => (
  <Icon
    className={className ?? 'h-3.5 w-3.5'}
    d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
  />
);

const ChevronLeft = ({ className }: { className?: string }) => (
  <Icon
    className={className ?? 'h-3.5 w-3.5'}
    d="M12.707 5.293a1 1 0 010 1.414L9.414 10l3.293 3.293a1 1 0 01-1.414 1.414l-4-4a1 1 0 010-1.414l4-4a1 1 0 011.414 0z"
  />
);

const RefreshIcon = ({ className }: { className?: string }) => (
  <Icon
    className={className ?? 'h-4 w-4'}
    d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
  />
);

const FolderPlusIcon = ({ className }: { className?: string }) => (
  <svg
    className={className ?? 'h-4 w-4'}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={2}
    aria-hidden="true"
  >
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      d="M9 13h6m-3-3v6m-9 1V7a2 2 0 012-2h6l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2z"
    />
  </svg>
);

// ─── helpers ──────────────────────────────────────────────────────────────────

const AUDIO_EXTS = new Set(['.mp3', '.m4a', '.m4b', '.flac', '.wav', '.aac', '.ogg', '.opus']);
const EBOOK_EXTS = new Set(['.epub', '.pdf', '.mobi', '.azw', '.azw3', '.djvu']);

const EntryIcon = ({ entry }: { entry: DirEntry }) => {
  if (entry.type === 'dir')
    return <FolderIcon className="h-4 w-4 flex-shrink-0 text-amber-500 dark:text-amber-400" />;
  const ext = entry.extension ?? '';
  if (AUDIO_EXTS.has(ext))
    return <AudioIcon className="h-4 w-4 flex-shrink-0 text-sky-500 dark:text-sky-400" />;
  if (EBOOK_EXTS.has(ext))
    return <BookIcon className="h-4 w-4 flex-shrink-0 text-emerald-600 dark:text-emerald-400" />;
  return <DocIcon className="h-4 w-4 flex-shrink-0 text-zinc-400" />;
};

// ─── move picker ──────────────────────────────────────────────────────────────

interface MovePickerProps {
  libraryFolders: LibraryFolder[];
  count: number;
  onConfirm: (destPath: string) => void;
  onCancel: () => void;
}

const MovePicker = ({ libraryFolders, count, onConfirm, onCancel }: MovePickerProps) => {
  const [path, setPath] = useState('');
  const [entries, setEntries] = useState<DirEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [creatingFolder, setCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const newFolderInputRef = useRef<HTMLInputElement>(null);

  const navigateTo = useCallback(async (target: string) => {
    setLoading(true);
    setError('');
    setCreatingFolder(false);
    try {
      const data = await listDirectory(target);
      setPath(data.path);
      setEntries(data.entries.filter((e) => e.type === 'dir'));
    } catch {
      setError('Failed to load folder');
    } finally {
      setLoading(false);
    }
  }, []);

  const activateNewFolder = useCallback(() => {
    setCreatingFolder(true);
    setNewFolderName('');
    setTimeout(() => newFolderInputRef.current?.focus(), 0);
  }, []);

  const commitNewFolder = useCallback(async () => {
    const name = newFolderName.trim();
    if (!name) {
      setCreatingFolder(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const result = await makeDirectory(path, name);
      setCreatingFolder(false);
      setNewFolderName('');
      // Jump straight into the new folder so "Move here" is one click away.
      await navigateTo(result.path);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create folder');
      setCreatingFolder(false);
      setLoading(false);
    }
  }, [path, newFolderName, navigateTo]);

  const crumbs = useMemo(() => {
    if (!path) return [];
    const root = libraryFolders.find((f) => path === f.path || path.startsWith(f.path + '/'));
    const rootCrumb = root
      ? { name: root.name, path: root.path }
      : { name: path.split('/').pop() || path, path };
    const result = [rootCrumb];
    if (root && path !== root.path) {
      const relative = path.slice(root.path.length).split('/').filter(Boolean);
      let acc = root.path;
      for (const part of relative) {
        acc = `${acc}/${part}`;
        result.push({ name: part, path: acc });
      }
    }
    return result;
  }, [path, libraryFolders]);

  const parent = crumbs.length > 1 ? crumbs[crumbs.length - 2].path : '';
  const movePickerContent = (() => {
    if (!path) {
      return (
        <ul className="divide-y divide-[color-mix(in_srgb,var(--border-muted)_60%,transparent)]">
          {libraryFolders.map((f) => (
            <li key={f.path}>
              <button
                type="button"
                onClick={() => void navigateTo(f.path)}
                className="hover-row flex w-full items-center gap-2 px-4 py-2.5 text-left"
              >
                <FolderIcon className="h-4 w-4 flex-shrink-0 text-amber-500 dark:text-amber-400" />
                <span className="font-medium">{f.name}</span>
                <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-40" />
              </button>
            </li>
          ))}
        </ul>
      );
    }
    if (loading) {
      return (
        <div className="flex h-32 items-center justify-center text-xs opacity-40">Loading...</div>
      );
    }
    if (entries.length === 0) {
      return (
        <div className="flex h-32 flex-col items-center justify-center gap-2">
          <p className="text-xs opacity-50">No subfolders - move here, or create a new one above</p>
          <button
            type="button"
            onClick={() => onConfirm(path)}
            className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-emerald-700"
          >
            Move {count} here
          </button>
        </div>
      );
    }
    return (
      <ul className="divide-y divide-[color-mix(in_srgb,var(--border-muted)_60%,transparent)]">
        {entries.map((e) => (
          <li key={e.path}>
            <button
              type="button"
              onClick={() => void navigateTo(e.path)}
              className="hover-row flex w-full items-center gap-2 px-4 py-2.5 text-left"
            >
              <FolderIcon className="h-4 w-4 flex-shrink-0 text-amber-500 dark:text-amber-400" />
              <span>{e.name}</span>
              <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-40" />
            </button>
          </li>
        ))}
      </ul>
    );
  })();

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-2 border-b border-(--border-muted) bg-(--bg-soft) px-3 py-2">
        {path && (
          <button
            type="button"
            onClick={() => (parent ? void navigateTo(parent) : setPath(''))}
            className="hover-action flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
            title="Up"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
        )}
        <div className="flex min-w-0 flex-1 items-center gap-0.5 overflow-hidden text-sm text-zinc-500 dark:text-zinc-400">
          {crumbs.length === 0 ? (
            <span className="text-xs opacity-50">Choose a destination folder</span>
          ) : (
            crumbs.map((crumb, i) => (
              <span
                key={crumb.path}
                className="flex min-w-0 flex-shrink-0 items-center gap-0.5 last:min-w-0 last:flex-shrink"
              >
                {i > 0 && <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 opacity-40" />}
                <button
                  type="button"
                  onClick={() => void navigateTo(crumb.path)}
                  className={`truncate transition-colors hover:text-zinc-900 dark:hover:text-zinc-100 ${
                    i === crumbs.length - 1 ? 'font-medium text-zinc-900 dark:text-zinc-100' : ''
                  }`}
                >
                  {crumb.name}
                </button>
              </span>
            ))
          )}
        </div>
        <div className="flex flex-shrink-0 items-center gap-1.5">
          {path && !creatingFolder && (
            <button
              type="button"
              onClick={activateNewFolder}
              className="hover-action flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full"
              title="Create new folder here"
            >
              <FolderPlusIcon className="h-3.5 w-3.5" />
            </button>
          )}
          {path && (
            <button
              type="button"
              onClick={() => onConfirm(path)}
              disabled={loading}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1 text-xs font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
            >
              Move {count} here
            </button>
          )}
          <button
            type="button"
            onClick={onCancel}
            className="hover-action flex h-7 items-center rounded-lg px-2 text-xs"
          >
            Cancel
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {error && <div className="px-4 py-2 text-xs text-red-700 dark:text-red-400">{error}</div>}
        {creatingFolder && (
          <div className="flex items-center gap-2 border-b border-(--border-muted) bg-sky-50/30 px-4 py-2.5 dark:bg-sky-900/10">
            <FolderIcon className="h-4 w-4 flex-shrink-0 text-amber-500 dark:text-amber-400" />
            <input
              ref={newFolderInputRef}
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void commitNewFolder();
                if (e.key === 'Escape') setCreatingFolder(false);
              }}
              onBlur={() => void commitNewFolder()}
              placeholder="New folder name"
              className="flex-1 border-b border-sky-500 bg-transparent pb-0.5 text-sm outline-none"
            />
          </div>
        )}
        {movePickerContent}
      </div>
    </div>
  );
};

// ─── main component ───────────────────────────────────────────────────────────

export const FileExplorer = () => {
  const isMobile = useMediaQuery('(max-width: 767px)');

  const [libraryFolders, setLibraryFolders] = useState<LibraryFolder[]>([]);
  const [currentPath, setCurrentPath] = useState('');
  const [entries, setEntries] = useState<DirEntry[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [movePickerOpen, setMovePickerOpen] = useState(false);

  const [renamingPath, setRenamingPath] = useState('');
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef<HTMLInputElement>(null);

  const [newFolderActive, setNewFolderActive] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const newFolderInputRef = useRef<HTMLInputElement>(null);

  // Anchor for shift-click range selection: index of the last row clicked
  // (not via checkbox), so "click first, shift+click last" selects everything
  // between them in one extra click instead of one click per item.
  const lastClickedIndexRef = useRef<number | null>(null);

  // ── data loading ──────────────────────────────────────────────────────────

  const loadRoots = useCallback(async () => {
    try {
      const folders = await fetchLibraryFolders();
      setLibraryFolders(folders);
    } catch {
      // non-fatal
    }
  }, []);

  useMountEffect(() => {
    void loadRoots();
  });

  const navigate = useCallback(async (path: string) => {
    if (!path) return;
    setMovePickerOpen(false);
    setLoading(true);
    setError('');
    setSelected(new Set());
    lastClickedIndexRef.current = null;
    setRenamingPath('');
    setNewFolderActive(false);
    try {
      const data = await listDirectory(path);
      setCurrentPath(data.path);
      setEntries(data.entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load directory');
    } finally {
      setLoading(false);
    }
  }, []);

  const refresh = useCallback(() => {
    if (currentPath) void navigate(currentPath);
  }, [currentPath, navigate]);

  // ── breadcrumbs ───────────────────────────────────────────────────────────

  const breadcrumbs = useMemo(() => {
    if (!currentPath) return [];
    const root = libraryFolders.find(
      (f) => currentPath === f.path || currentPath.startsWith(f.path + '/'),
    );
    const rootCrumb = root
      ? { name: root.name, path: root.path }
      : { name: currentPath.split('/').pop() || currentPath, path: currentPath };

    const crumbs = [rootCrumb];
    if (root && currentPath !== root.path) {
      const relative = currentPath.slice(root.path.length).split('/').filter(Boolean);
      let acc = root.path;
      for (const part of relative) {
        acc = `${acc}/${part}`;
        crumbs.push({ name: part, path: acc });
      }
    }
    return crumbs;
  }, [currentPath, libraryFolders]);

  const parentPath = breadcrumbs.length > 1 ? breadcrumbs[breadcrumbs.length - 2].path : '';

  // ── selection ─────────────────────────────────────────────────────────────

  // Always-additive toggle, used by the per-row checkbox (no modifier needed).
  const toggleSelect = useCallback((path: string, index: number) => {
    lastClickedIndexRef.current = index;
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  // Row click: plain click selects just that row, ctrl/cmd+click toggles it
  // into/out of the selection, shift+click selects the whole range from the
  // last clicked row to this one.
  const selectRow = useCallback(
    (
      path: string,
      index: number,
      modifiers: { shiftKey: boolean; metaKey: boolean; ctrlKey: boolean },
    ) => {
      if (modifiers.shiftKey && lastClickedIndexRef.current !== null) {
        const start = Math.min(lastClickedIndexRef.current, index);
        const end = Math.max(lastClickedIndexRef.current, index);
        setSelected(new Set(entries.slice(start, end + 1).map((e) => e.path)));
        return;
      }
      lastClickedIndexRef.current = index;
      if (modifiers.metaKey || modifiers.ctrlKey) {
        setSelected((prev) => {
          const next = new Set(prev);
          if (next.has(path)) {
            next.delete(path);
          } else {
            next.add(path);
          }
          return next;
        });
        return;
      }
      setSelected((prev) => (prev.size === 1 && prev.has(path) ? new Set() : new Set([path])));
    },
    [entries],
  );

  const selectAll = useCallback(() => {
    lastClickedIndexRef.current = null;
    setSelected((prev) =>
      prev.size === entries.length ? new Set() : new Set(entries.map((e) => e.path)),
    );
  }, [entries]);

  // ── rename ────────────────────────────────────────────────────────────────

  const startRename = useCallback((entry: DirEntry) => {
    setRenamingPath(entry.path);
    setRenameValue(entry.name);
    setTimeout(() => renameInputRef.current?.select(), 0);
  }, []);

  const commitRename = useCallback(async () => {
    if (!renamingPath || !renameValue.trim()) {
      setRenamingPath('');
      return;
    }
    const current = entries.find((e) => e.path === renamingPath);
    if (!current || renameValue.trim() === current.name) {
      setRenamingPath('');
      return;
    }
    setLoading(true);
    try {
      await renameEntry(renamingPath, renameValue.trim());
      setRenamingPath('');
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Rename failed');
      setRenamingPath('');
    } finally {
      setLoading(false);
    }
  }, [renamingPath, renameValue, entries, refresh]);

  // ── new folder ────────────────────────────────────────────────────────────

  const activateNewFolder = useCallback(() => {
    setNewFolderActive(true);
    setNewFolderName('');
    setTimeout(() => newFolderInputRef.current?.focus(), 0);
  }, []);

  const commitNewFolder = useCallback(async () => {
    if (!newFolderName.trim()) {
      setNewFolderActive(false);
      return;
    }
    setLoading(true);
    try {
      await makeDirectory(currentPath, newFolderName.trim());
      setNewFolderActive(false);
      setNewFolderName('');
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create folder');
      setNewFolderActive(false);
    } finally {
      setLoading(false);
    }
  }, [currentPath, newFolderName, refresh]);

  // ── move ──────────────────────────────────────────────────────────────────

  const commitMove = useCallback(
    async (destPath: string) => {
      if (!destPath || selected.size === 0) return;
      setMovePickerOpen(false);
      setLoading(true);
      setError('');
      try {
        const result = await organizeFiles(
          Array.from(selected).map((path) => ({ path })),
          destPath,
        );
        setSelected(new Set());
        if (result.failed_files.length > 0) {
          setError(`${result.failed_files.length} file(s) failed: ${result.failed_files[0].error}`);
        }
        refresh();
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Move failed');
      } finally {
        setLoading(false);
      }
    },
    [selected, refresh],
  );

  // ── derived ───────────────────────────────────────────────────────────────

  const singleSelected = selected.size === 1 ? entries.find((e) => selected.has(e.path)) : null;
  const getBreadcrumbClassName = (isCurrent: boolean) => {
    if (isCurrent) return 'font-medium text-zinc-900 dark:text-zinc-100';
    if (isMobile) return 'hidden';
    return '';
  };

  // ── render ────────────────────────────────────────────────────────────────

  const sidebar = (
    <div className="flex h-full flex-col overflow-y-auto bg-(--bg-soft)">
      <div className="flex-1 p-3">
        <p className="mb-2 px-1 text-[10px] font-medium tracking-wide uppercase opacity-60">
          Folders
        </p>
        {libraryFolders.length === 0 ? (
          <p className="px-1 text-xs opacity-50">No folders configured</p>
        ) : (
          <div className="space-y-0.5">
            {libraryFolders.map((folder) => {
              const isActive =
                currentPath === folder.path || currentPath.startsWith(folder.path + '/');
              return (
                <button
                  type="button"
                  key={folder.path}
                  onClick={() => void navigate(folder.path)}
                  className={`hover-surface flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition-colors ${
                    isActive ? 'bg-(--bg) font-medium' : ''
                  }`}
                >
                  <FolderIcon className="h-3.5 w-3.5 flex-shrink-0 text-amber-500 dark:text-amber-400" />
                  <span className="truncate">{folder.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );

  return (
    <div className="relative flex h-full text-sm">
      {/* desktop sidebar */}
      <div className="hidden w-52 flex-shrink-0 flex-col border-r border-(--border-muted) md:flex">
        {sidebar}
      </div>

      {/* main area */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* mobile: folder strip */}
        {isMobile && libraryFolders.length > 0 && !movePickerOpen && (
          <div className="scrollbar-none flex items-center gap-1.5 overflow-x-auto border-b border-(--border-muted) px-3 py-2">
            {libraryFolders.map((folder) => {
              const isActive =
                currentPath === folder.path || currentPath.startsWith(folder.path + '/');
              return (
                <button
                  type="button"
                  key={folder.path}
                  onClick={() => void navigate(folder.path)}
                  className={`flex flex-shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                    isActive
                      ? 'bg-emerald-600 text-white'
                      : 'border border-(--border-muted) hover:bg-(--bg-soft)'
                  }`}
                >
                  <FolderIcon className="h-3 w-3" />
                  {folder.name}
                </button>
              );
            })}
          </div>
        )}

        {/* toolbar */}
        <div className="flex min-h-[41px] items-center gap-1.5 border-b border-(--border-muted) px-3 py-2">
          {/* back button */}
          {parentPath && !movePickerOpen && (
            <button
              type="button"
              onClick={() => void navigate(parentPath)}
              className="hover-action flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full"
              aria-label="Up"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          )}

          {/* breadcrumb */}
          {!movePickerOpen && (
            <div className="flex min-w-0 flex-1 items-center gap-0.5 overflow-hidden text-sm text-zinc-500 dark:text-zinc-400">
              {breadcrumbs.length === 0 ? (
                <span className="text-xs opacity-50">
                  {isMobile ? 'Pick a folder above' : 'Select a folder'}
                </span>
              ) : (
                breadcrumbs.map((crumb, i) => (
                  <span
                    key={crumb.path}
                    className="flex min-w-0 flex-shrink-0 items-center gap-0.5 last:min-w-0 last:flex-shrink"
                  >
                    {i > 0 && <ChevronRight className="h-3.5 w-3.5 flex-shrink-0 opacity-40" />}
                    <button
                      type="button"
                      onClick={() => void navigate(crumb.path)}
                      className={`truncate transition-colors hover:text-zinc-900 dark:hover:text-zinc-100 ${getBreadcrumbClassName(
                        i === breadcrumbs.length - 1,
                      )}`}
                    >
                      {crumb.name}
                    </button>
                  </span>
                ))
              )}
            </div>
          )}

          {movePickerOpen && (
            <span className="flex-1 text-xs font-medium opacity-60">
              Moving {selected.size} item{selected.size !== 1 ? 's' : ''} — pick a destination
            </span>
          )}

          {/* actions */}
          <div className="flex flex-shrink-0 items-center gap-1">
            {selected.size > 0 && !movePickerOpen && (
              <button
                type="button"
                onClick={() => setMovePickerOpen(true)}
                className="flex items-center gap-1.5 rounded-lg border border-(--border-muted) px-2.5 py-1 text-xs font-medium transition-colors hover:bg-(--bg-soft)"
              >
                Move {selected.size}…
              </button>
            )}

            {currentPath && !movePickerOpen && (
              <button
                type="button"
                onClick={activateNewFolder}
                className="hover-action flex h-8 w-8 items-center justify-center rounded-full"
                title="New folder"
              >
                <FolderPlusIcon className="h-4 w-4" />
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                void loadRoots();
                refresh();
              }}
              disabled={loading}
              className="hover-action flex h-8 w-8 items-center justify-center rounded-full disabled:opacity-40"
              title="Refresh"
            >
              <RefreshIcon className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* error bar */}
        {error && (
          <div className="flex items-center justify-between gap-2 border-b border-red-200 bg-red-50 px-4 py-2 text-xs text-red-700 dark:border-red-800 dark:bg-red-900/20 dark:text-red-400">
            <span>{error}</span>
            <button
              type="button"
              onClick={() => setError('')}
              className="flex-shrink-0 opacity-70 hover:opacity-100"
            >
              <Icon
                className="h-3.5 w-3.5"
                d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              />
            </button>
          </div>
        )}

        {/* move picker */}
        {movePickerOpen ? (
          <div className="flex-1 overflow-hidden">
            <MovePicker
              libraryFolders={libraryFolders}
              count={selected.size}
              onConfirm={(dest) => void commitMove(dest)}
              onCancel={() => setMovePickerOpen(false)}
            />
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            {!currentPath && (
              <div className="flex h-full items-center justify-center text-sm opacity-50">
                {isMobile ? 'Pick a folder above' : 'Select a folder from the sidebar'}
              </div>
            )}
            {currentPath && entries.length === 0 && !loading && !newFolderActive && (
              <div className="flex h-full items-center justify-center text-sm opacity-50">
                Empty folder
              </div>
            )}
            {currentPath && (entries.length !== 0 || loading || newFolderActive) && (
              <table className="w-full">
                <thead>
                  <tr className="sticky top-0 z-10 border-b border-(--border-muted) bg-(--bg)">
                    <th className="w-8 py-2 pl-4">
                      <input
                        type="checkbox"
                        checked={entries.length > 0 && selected.size === entries.length}
                        onChange={selectAll}
                        className="rounded border-zinc-300 text-emerald-600 focus:ring-emerald-500 dark:border-zinc-600"
                      />
                    </th>
                    <th className="py-2 pl-2 text-left text-[11px] font-medium tracking-wide uppercase opacity-60">
                      Name
                    </th>
                    <th className="w-20 py-2 pr-4 text-right text-[11px] font-medium tracking-wide uppercase opacity-60">
                      Size
                    </th>
                    <th className="hidden w-32 py-2 pr-4 text-right text-[11px] font-medium tracking-wide uppercase opacity-60 sm:table-cell">
                      Modified
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[color-mix(in_srgb,var(--border-muted)_60%,transparent)]">
                  {newFolderActive && (
                    <tr className="bg-sky-50/30 dark:bg-sky-900/10">
                      <td className="py-2 pl-4" />
                      <td className="py-2 pl-2" colSpan={3}>
                        <div className="flex items-center gap-2">
                          <FolderIcon className="h-4 w-4 flex-shrink-0 text-amber-500 dark:text-amber-400" />
                          <input
                            ref={newFolderInputRef}
                            value={newFolderName}
                            onChange={(e) => setNewFolderName(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') void commitNewFolder();
                              if (e.key === 'Escape') setNewFolderActive(false);
                            }}
                            onBlur={() => void commitNewFolder()}
                            placeholder="New folder name"
                            className="w-48 border-b border-sky-500 bg-transparent pb-0.5 text-sm outline-none"
                          />
                        </div>
                      </td>
                    </tr>
                  )}

                  {entries.map((entry, index) => {
                    const isSelected = selected.has(entry.path);
                    const isRenaming = renamingPath === entry.path;

                    return (
                      <tr
                        key={entry.path}
                        className={`hover-row cursor-pointer transition-colors select-none ${
                          isSelected ? 'bg-emerald-50/50 dark:bg-emerald-900/10' : ''
                        }`}
                        onClick={(e) => {
                          if (isRenaming) return;
                          selectRow(entry.path, index, e);
                        }}
                        onDoubleClick={(e) => {
                          if (isRenaming) return;
                          if (entry.type === 'dir') {
                            void navigate(entry.path);
                          } else {
                            e.preventDefault();
                            startRename(entry);
                          }
                        }}
                      >
                        <td className="w-8 py-2 pl-4">
                          <input
                            type="checkbox"
                            checked={isSelected}
                            onChange={() => toggleSelect(entry.path, index)}
                            onClick={(e) => e.stopPropagation()}
                            className="rounded border-zinc-300 text-emerald-600 focus:ring-emerald-500 dark:border-zinc-600"
                          />
                        </td>
                        <td className="min-w-0 py-2 pr-4 pl-2">
                          <div className="flex min-w-0 items-center gap-2">
                            <EntryIcon entry={entry} />
                            {isRenaming ? (
                              <input
                                ref={renameInputRef}
                                value={renameValue}
                                onChange={(e) => setRenameValue(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') void commitRename();
                                  if (e.key === 'Escape') setRenamingPath('');
                                  e.stopPropagation();
                                }}
                                onBlur={() => void commitRename()}
                                onClick={(e) => e.stopPropagation()}
                                className="min-w-0 flex-1 border-b border-sky-500 bg-transparent pb-0.5 text-sm outline-none"
                              />
                            ) : (
                              <span
                                className={`truncate ${entry.type === 'dir' ? 'font-medium' : ''}`}
                                title={entry.name}
                              >
                                {entry.name}
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="w-20 py-2 pr-4 text-right text-xs tabular-nums opacity-60">
                          {entry.type === 'file' && entry.size != null
                            ? formatFileSize(entry.size)
                            : '—'}
                        </td>
                        <td className="hidden w-32 py-2 pr-4 text-right text-xs tabular-nums opacity-60 sm:table-cell">
                          {entry.modified != null ? formatDate(entry.modified) : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>
        )}

        {/* status bar */}
        {currentPath && !movePickerOpen && (
          <div className="flex items-center justify-between border-t border-(--border-muted) px-4 py-1.5 text-xs">
            <span className="opacity-60">
              {entries.length} item{entries.length !== 1 ? 's' : ''}
            </span>
            {singleSelected && !renamingPath && (
              <button
                type="button"
                onClick={() => startRename(singleSelected)}
                className="hover-action rounded px-2 py-0.5 text-xs opacity-60 transition-opacity hover:opacity-100"
              >
                Rename
              </button>
            )}
            {selected.size > 1 && <span className="opacity-60">{selected.size} selected</span>}
          </div>
        )}
      </div>
    </div>
  );
};
