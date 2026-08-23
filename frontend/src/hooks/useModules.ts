import { useState, useEffect } from 'react';

export interface Module {
  key: string;
  name: string;
  enabled: boolean;
  icon?: string;
}

interface UseModulesReturn {
  modules: Module[];
  isLoading: boolean;
  error: Error | null;
  enableModule: (moduleKey: string) => Promise<void>;
  disableModule: (moduleKey: string) => Promise<void>;
  refetch: () => Promise<void>;
}

export function useModules(workspaceId: string): UseModulesReturn {
  const [modules, setModules] = useState<Module[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchModules = async () => {
    try {
      setIsLoading(true);
      const response = await fetch(`/api/modules/enabled?workspace_id=${workspaceId}`);
      if (!response.ok) throw new Error('Failed to fetch modules');
      const data = await response.json();
      setModules(data.modules || []);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
      setModules([]);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (workspaceId) {
      fetchModules();
    }
  }, [workspaceId]);

  const enableModule = async (moduleKey: string) => {
    try {
      const response = await fetch(`/api/modules/${moduleKey}/enable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId }),
      });
      if (!response.ok) throw new Error('Failed to enable module');
      await fetchModules();
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    }
  };

  const disableModule = async (moduleKey: string) => {
    try {
      const response = await fetch(`/api/modules/${moduleKey}/disable`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ workspace_id: workspaceId }),
      });
      if (!response.ok) throw new Error('Failed to disable module');
      await fetchModules();
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Unknown error'));
    }
  };

  return {
    modules,
    isLoading,
    error,
    enableModule,
    disableModule,
    refetch: fetchModules,
  };
}
