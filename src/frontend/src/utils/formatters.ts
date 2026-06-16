const FILE_SIZE_UNITS = ['B', 'KB', 'MB', 'GB', 'TB'] as const;

export const formatFileSize = (bytes: number): string => {
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < FILE_SIZE_UNITS.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(1)} ${FILE_SIZE_UNITS[unitIndex]}`;
};

export const formatDuration = (seconds: number): string => {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours > 0 ? `${hours}h ${minutes}m` : `${minutes}m`;
};

export const formatDate = (unixSeconds: number): string =>
  new Date(unixSeconds * 1000).toLocaleDateString();
