import { Compass, LogOut } from "lucide-react";
import { useEffect } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { hasSeenTour, useTour } from "@/components/tour/GuidedTour";
import { Badge } from "@/components/ui/badge";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

const NAV = [
  {
    to: "/console",
    label: "Console",
    tour: "nav-console",
    roles: ["operator_admin", "operator_analyst", "platform_admin"],
  },
  {
    to: "/portfolio",
    label: "Portfolio",
    tour: "nav-portfolio",
    roles: ["operator_admin", "operator_analyst", "platform_admin"],
  },
  {
    to: "/upload",
    label: "Upload data",
    tour: "nav-upload",
    roles: ["operator_admin", "operator_analyst", "platform_admin"],
  },
  {
    to: "/lender",
    label: "Lender analytics",
    tour: "nav-lender",
    roles: ["lender_viewer", "platform_admin"],
  },
  { to: "/admin", label: "Admin", tour: "nav-admin", roles: ["platform_admin"] },
];

export function AppShell() {
  const { user, logout } = useAuth();
  const { start } = useTour();
  const nav = NAV.filter((item) => !user || item.roles.includes(user.role));

  // Auto-launch the tour once for first-time visitors (after the nav is painted).
  useEffect(() => {
    if (user && !hasSeenTour()) start();
  }, [user, start]);

  return (
    <div className="min-h-dvh bg-background">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2 font-mono text-sm font-semibold">
              <img src="/grid.svg" alt="" className="h-6 w-6" />
              GridScore<span className="text-primary">AI</span>
            </div>
            <nav className="flex items-center gap-1">
              {nav.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  data-tour={item.tour}
                  className={({ isActive }) =>
                    cn(
                      "rounded-md px-3 py-1.5 text-sm transition-colors",
                      isActive
                        ? "bg-secondary text-foreground"
                        : "text-muted-foreground hover:text-foreground",
                    )
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {user && (
              <>
                <Badge variant="muted">{user.role}</Badge>
                <span className="hidden sm:inline">{user.email ?? user.kind}</span>
              </>
            )}
            <button
              onClick={start}
              data-tour="launch"
              aria-label="Take the product tour"
              className="flex items-center gap-1 rounded-md px-2 py-1 hover:text-foreground"
            >
              <Compass className="h-3.5 w-3.5" /> Tour
            </button>
            <button
              onClick={logout}
              className="flex items-center gap-1 rounded-md px-2 py-1 hover:text-foreground"
            >
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-6">
        <Outlet />
      </main>
    </div>
  );
}
