import type { CandidateStore } from '../types/leadImport';
import { Button } from './ui/button';

interface StoreConfirmationDialogProps {
  isOpen: boolean;
  candidateStores: CandidateStore[];
  onClose: () => void;
  onConfirm: (storeCode: string) => void;
}

export function StoreConfirmationDialog({ isOpen, candidateStores, onClose, onConfirm }: StoreConfirmationDialogProps) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" role="dialog" aria-modal="true" aria-labelledby="store-confirm-title">
      <div className="w-full max-w-lg rounded-md bg-white p-5 shadow-lg">
        <h2 id="store-confirm-title" className="text-lg font-semibold text-gray-900">需要人工确认门店</h2>
        <p className="mt-1 text-sm text-gray-500">请选择候选门店后重新提交，系统只允许使用注册表中的门店编码。</p>
        <div className="mt-4 space-y-2">
          {candidateStores.length > 0 ? candidateStores.map((store) => (
            <button
              key={store.store_code}
              type="button"
              onClick={() => onConfirm(store.store_code)}
              className="w-full rounded-md border border-gray-200 px-3 py-2 text-left text-sm hover:bg-gray-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-gray-900"
            >
              <span className="font-medium text-gray-900">{store.store_name}</span>
              <span className="ml-2 text-gray-500">{store.store_code} · {Math.round(store.confidence * 100)}%</span>
            </button>
          )) : <p className="text-sm text-gray-500">暂无候选门店，请联系管理员维护识别规则。</p>}
        </div>
        <div className="mt-5 flex justify-end">
          <Button type="button" variant="outline" onClick={onClose}>取消</Button>
        </div>
      </div>
    </div>
  );
}
