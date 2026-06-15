import { useState } from 'react';
import type { DownloadDestination } from '../services/api';
import { getDownloadDestinations } from '../services/api';
import { useMountEffect } from './useMountEffect';

export function useDownloadDestinations(): DownloadDestination[] {
  const [destinations, setDestinations] = useState<DownloadDestination[]>([]);

  useMountEffect(() => {
    void getDownloadDestinations().then(setDestinations);
  });

  return destinations;
}
