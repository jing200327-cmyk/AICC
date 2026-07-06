import type { ApiError } from '../types/leadImport';

interface ImportLogsPanelProps {
  logs: string[];
  error: ApiError | null;
}

export function ImportLogsPanel({ logs, error }: ImportLogsPanelProps) {
  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5 shadow-sm">
      <h2 className="text-base font-semibold text-gray-950">执行日志</h2>
      {error && (
        <div role="alert" className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          <p className="font-medium">{error.message}</p>
          {error.detail && <p className="mt-1 text-red-600">{error.detail}</p>}
        </div>
      )}
      {logs.length > 0 ? (
        <ul className="mt-4 space-y-2 text-sm text-gray-700">
          {logs.map((log, index) => <li key={`${index}-${log}`} className="rounded-md bg-gray-50 px-3 py-2">{log}</li>)}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-gray-500">暂无日志。</p>
      )}
    </section>
  );
}
