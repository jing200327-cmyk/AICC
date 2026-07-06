import { BarChart3, FileUp, Phone, Settings } from 'lucide-react';
import { NavLink } from 'react-router-dom';

const items = [
  { title: '新增线索导入', href: '/', icon: FileUp, disabled: false },
  { title: '自动外呼', href: '/auto-call', icon: Phone, disabled: true },
  { title: '数据看板', href: '/dashboard', icon: BarChart3, disabled: true },
  { title: '系统配置', href: '/settings', icon: Settings, disabled: true },
];

export function Sidebar() {
  return (
    <aside className="flex min-h-screen w-72 flex-none flex-col border-r border-gray-200 bg-white">
      <div className="border-b border-gray-200 px-5 py-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-md bg-gray-900 text-white">
            <FileUp className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-gray-950">线索处理台</h1>
            <p className="mt-1 text-xs text-gray-500">门店导入与 txt 生成</p>
          </div>
        </div>
      </div>

      <nav className="space-y-1 p-3" aria-label="主导航">
        {items.map((item) => {
          const Icon = item.icon;
          if (item.disabled) {
            return (
              <div
                key={item.href}
                className="flex items-center gap-3 rounded-md px-3 py-2.5 text-sm text-gray-400"
                aria-disabled="true"
              >
                <Icon className="h-4 w-4" />
                <span className="flex-1 truncate">{item.title}</span>
                <span className="rounded border border-gray-200 px-1.5 py-0.5 text-xs text-gray-400">预留</span>
              </div>
            );
          }
          return (
            <NavLink
              key={item.href}
              to={item.href}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition ${
                  isActive
                    ? 'border border-gray-200 bg-gray-100 text-gray-950'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-950'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              <span className="truncate">{item.title}</span>
            </NavLink>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-gray-200 p-4 text-xs leading-5 text-gray-500">
        文件将按识别门店保存到建银线索目录，并由后端白名单脚本生成 txt。
      </div>
    </aside>
  );
}

