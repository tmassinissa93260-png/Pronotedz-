import { Link, useRouterState } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";
import { mobileTabs } from "@/lib/nav-config";
import { useSidebar } from "./sidebar-context";
import { useT } from "@/lib/i18n";

export function MobileTabBar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { setMobileOpen } = useSidebar();
  const t = useT();
  const isActive = (url: string) => pathname === url || pathname.startsWith(url + "/");

  return (
    <nav
      className="glass fixed inset-x-0 bottom-0 z-40 md:hidden"
      style={{ paddingBottom: "env(safe-area-inset-bottom)" }}
      aria-label="Navigation principale"
    >
      <ul className="mx-auto grid max-w-md grid-cols-5">
        {mobileTabs.map((tab) => {
          const active = isActive(tab.url);
          return (
            <li key={tab.url} className="flex">
              <Link
                to={tab.url}
                className={cn(
                  "flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium transition-colors",
                  active ? "text-primary" : "text-muted-foreground",
                )}
              >
                <span
                  className={cn(
                    "grid h-8 w-12 place-items-center rounded-xl transition-colors",
                    active && "bg-primary/15",
                  )}
                >
                  <tab.icon className="size-[18px]" />
                </span>
                <span>{t(tab.titleKey)}</span>
              </Link>
            </li>
          );
        })}
        <li className="flex">
          <button
            onClick={() => setMobileOpen(true)}
            className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[10px] font-medium text-muted-foreground"
            aria-label={t("nav.more")}
          >
            <span className="grid h-8 w-12 place-items-center rounded-xl">
              <Menu className="size-[18px]" />
            </span>
            <span>{t("nav.more")}</span>
          </button>
        </li>
      </ul>
    </nav>
  );
}
