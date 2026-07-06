import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AppLayout } from './components/AppLayout';
import { ErrorBoundary } from './components/ErrorBoundary';
import { LeadImportPage } from './pages/LeadImportPage';

function PlaceholderPage({ title }: { title: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>
        <p className="mt-2 text-sm text-gray-500">功能入口已预留，暂未开放。</p>
      </div>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<LeadImportPage />} />
            <Route path="/auto-call" element={<PlaceholderPage title="自动外呼" />} />
            <Route path="/dashboard" element={<PlaceholderPage title="数据看板" />} />
            <Route path="/settings" element={<PlaceholderPage title="系统配置" />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </ErrorBoundary>
  );
}

export default App;
