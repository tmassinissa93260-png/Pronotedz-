import { Link, useRouterState } from "@tanstack/react-router";
import { motion } from "framer-motion";
import { ChevronsLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { primaryNav, communityNav, teacherNavItem, adminNavItem, type NavItem } from "@/lib/nav-config";
import { useSidebar } from "./sidebar-context";
import { useT } from "@/lib/i18n";

function NavLink({ item, collapsed, active }: { item: NavItem; collapsed: boolean; active: boolean }) {
  const t = useT();
  return (
    <Link
      to={item.url}
      className={cn(
        "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
        active
          ? "bg-primary/12 text-primary"
          : "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-foreground",
      )}
      title={collapsed ? t(item.titleKey) : undefined}
    >
      <item.icon className="size-4 shrink-0" />
      {!collapsed && <span className="truncate">{t(item.titleKey)}</span>}
    </Link>
  );
}

export function AppSidebar({ isTeacher, isAdmin }: { isTeacher: boolean; isAdmin: boolean }) {
  const { collapsed, toggle } = useSidebar();
  const t = useT();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const isActive = (url: string) => pathname === url || pathname.startsWith(url + "/");

  return (
    <motion.aside
      animate={{ width: collapsed ? 76 : 264 }}
      transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
      className="sticky top-0 hidden h-screen shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex"
    >
      <div className="flex h-14 items-center gap-2.5 border-b border-sidebar-border px-4">
        <Link to="/dashboard" className="flex items-center gap-2.5 overflow-hidden">
          <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-emerald-gradient font-display font-bold text-primary-foreground shadow-glow">
            أ
          </div>
          {!collapsed && (
            <div className="flex flex-col leading-tight">
              <span className="font-display text-base font-bold tracking-tight">
                {t("common.appName")}
              </span>
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                {t("common.tagline")}
              </span>
            </div>
          )}
        </Link>
      </div>

      <nav className="flex flex-1 flex-col gap-4 overflow-y-auto px-3 py-4">
        <div className="flex flex-col gap-1">
          {!collapsed && (
            <span className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {t("nav.learn")}
            </span>
          )}
          {primaryNav.map((item) => (
            <NavLink key={item.url} item={item} collapsed={collapsed} active={isActive(item.url)} />
          ))}
        </div>

        <div className="flex flex-col gap-1">
          {!collapsed && (
            <span className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              {t("nav.communitySection")}
            </span>
          )}
          {communityNav.map((item) => (
            <NavLink key={item.url} item={item} collapsed={collapsed} active={isActive(item.url)} />
          ))}
        </div>

        {(isTeacher || isAdmin) && (
          <div className="flex flex-col gap-1">
            {!collapsed && (
              <span className="px-3 pb-1 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                {t("nav.proSpaces")}
              </span>
            )}
            {isTeacher && (
              <NavLink item={teacherNavItem} collapsed={collapsed} active={isActive(teacherNavItem.url)} />
            )}
            {isAdmin && (
              <NavLink item={adminNavItem} collapsed={collapsed} active={isActive(adminNavItem.url)} />
            )}
          </div>
        )}
      </nav>

      <div className="border-t border-sidebar-border p-3">
        <button
          onClick={toggle}
          className="flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
        >
          <ChevronsLeft className={cn("size-4 transition-transform", collapsed && "rotate-180")} />
          {!collapsed && <span>Réduire</span>}
        </button>
      </div>
    </motion.aside>
  );
}
