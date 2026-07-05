import type { ReactNode } from 'react';
import { createContext, useContext, useMemo } from 'react';

import type { ContentType, SearchMode } from '../types';

interface SearchModeContextValue {
  searchMode: SearchMode;
  contentType?: ContentType;
  isUniversalMode: boolean;
}

const SearchModeContext = createContext<SearchModeContextValue | null>(null);

export function useSearchMode(): SearchModeContextValue {
  const ctx = useContext(SearchModeContext);
  if (!ctx) {
    throw new Error('useSearchMode must be used within SearchModeProvider');
  }
  return ctx;
}

interface SearchModeProviderProps {
  searchMode: SearchMode;
  contentType?: ContentType;
  children: ReactNode;
}

export function SearchModeProvider({ searchMode, contentType, children }: SearchModeProviderProps) {
  const value = useMemo(
    () => ({ searchMode, contentType, isUniversalMode: searchMode === 'universal' }),
    [searchMode, contentType],
  );

  return <SearchModeContext.Provider value={value}>{children}</SearchModeContext.Provider>;
}
