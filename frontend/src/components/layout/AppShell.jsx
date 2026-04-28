import { BarChart3, Clock3, LogOut, Settings2 } from 'lucide-react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';

import { useAuthStore } from '../../store/authStore';
import { cn } from '../../lib/utils';

const navItems = [
  { to: '/dashboard', label: 'Dashboard', icon: BarChart3 },
  { to: '/dashboard/history', label: 'Interview History', icon: Clock3 },
  { to: '/dashboard/settings', label: 'Settings', icon: Settings2 },
];

export function AppShell() {
  const navigate = useNavigate();
  const logout = useAuthStore((state) => state.logout);

  const onLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  return (
    <div className="min-h-screen bg-app text-on-surface">
      <div className="mx-auto grid min-h-screen max-w-[1600px] grid-cols-[260px_1fr]">
        <aside className="border-r border-outline-variant/60 bg-surface-container-low/40 p-6 backdrop-blur-xl">
          <div className="mb-12">
            <p className="font-code text-xs uppercase tracking-[0.14em] text-primary">IntervAI</p>
            <h1 className="mt-2 font-headline text-2xl font-bold">Technical Platform</h1>
          </div>

          <nav className="space-y-2">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-3 rounded-md px-3 py-2 text-sm transition',
                    isActive
                      ? 'bg-primary-container/20 text-primary shadow-glow'
                      : 'text-on-surface-variant hover:bg-surface-container-high/60 hover:text-on-surface',
                  )
                }
              >
                <Icon size={16} />
                <span>{label}</span>
              </NavLink>
            ))}
          </nav>

          <button
            type="button"
            onClick={onLogout}
            className="mt-12 flex w-full items-center gap-3 rounded-md border border-outline-variant/70 px-3 py-2 text-sm text-on-surface-variant transition hover:bg-surface-container-high/70 hover:text-on-surface"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </aside>

        <main className="p-6 md:p-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
