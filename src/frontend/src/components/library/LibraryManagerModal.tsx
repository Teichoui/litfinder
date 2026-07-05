import { useBodyScrollLock } from '../../hooks/useBodyScrollLock';
import { useEscapeKey } from '../../hooks/useEscapeKey';
import { FileExplorer } from './FileExplorer';

interface LibraryManagerModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const LibraryManagerModal = ({ isOpen, onClose }: LibraryManagerModalProps) => {
  useBodyScrollLock(isOpen);
  useEscapeKey(isOpen, onClose);

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
      onKeyDown={(e) => { if (e.key === 'Escape') onClose(); }}
      role="presentation"
    >
      <div className="relative flex flex-col w-full h-full max-w-6xl max-h-[90vh] mx-4 my-4 bg-(--bg) rounded-2xl shadow-2xl overflow-hidden border border-(--border-muted)">
        <div className="flex items-center justify-between px-5 py-4 border-b border-(--border-muted)">
          <h2 className="text-base font-semibold">Library File Manager</h2>
          <button type="button"
            onClick={onClose}
            className="hover-action h-8 w-8 flex items-center justify-center rounded-full"
            aria-label="Close"
          >
            <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor">
              <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z" clipRule="evenodd" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-hidden">
          <FileExplorer />
        </div>
      </div>
    </div>
  );
};
