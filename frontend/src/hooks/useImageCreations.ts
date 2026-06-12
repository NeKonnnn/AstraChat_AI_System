import { useCallback, useEffect, useMemo, useState } from 'react';
import { getApiUrl, getAuthFetchHeaders } from '../config/api';
import { useAuth } from '../contexts/AuthContext';
import { useAppContext } from '../contexts/AppContext';
import {
  extractCreationsFromChats,
  mergeCreationItems,
  type ImageCreationItem,
} from '../utils/imageCreations';

export function useImageCreations(limit = 500) {
  const { token } = useAuth();
  const { state } = useAppContext();
  const [apiItems, setApiItems] = useState<ImageCreationItem[]>([]);
  const [loading, setLoading] = useState(true);

  const localItems = useMemo(
    () => extractCreationsFromChats(state.chats),
    [state.chats],
  );

  const loadCreations = useCallback(async () => {
    setLoading(true);
    try {
      const r = await fetch(getApiUrl(`/api/image-generation/creations?limit=${limit}`), {
        headers: getAuthFetchHeaders(),
      });
      if (!r.ok) throw new Error(String(r.status));
      const data = await r.json();
      setApiItems(Array.isArray(data.items) ? data.items : []);
    } catch {
      setApiItems([]);
    } finally {
      setLoading(false);
    }
  }, [limit]);

  useEffect(() => {
    void loadCreations();
  }, [loadCreations, token]);

  useEffect(() => {
    const refresh = () => void loadCreations();
    window.addEventListener('astrachatCreationsUpdated', refresh);
    return () => window.removeEventListener('astrachatCreationsUpdated', refresh);
  }, [loadCreations]);

  const items = useMemo(
    () => mergeCreationItems(apiItems, localItems),
    [apiItems, localItems],
  );

  return { items, loading, reload: loadCreations };
}
