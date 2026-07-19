import { Link, useRouterState } from "@tanstack/react-router";
import { LogOut } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetClose } from "@/components/ui/sheet";
import { cn } from "@/lib/utils";
import { primaryNav, communityNav, teacherNavItem, adminNavItem } from "@/lib/nav-config";
import { useSidebar } from "./sidebar-context";
import { useT } from "@/lib/i18n";

export function MobileNavSheet({
  isTeacher,
  isAdmin,
  onSignOut,
}: {
  isTeacher: boolean;
  isAdmin: boolean;
  onSignOut: () => void;
}) {
  const { mobileOpen, setMobileOpen } = useSidebar();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const t = useT();
  const isActive = (url: string) => pathname === url || pathname.startsWith(url + "/");

  const items = [
    ...primaryNav,
    ...communityNav,
    ...(isTeacher ? [teacherNavItem] : []),
    ...(isAdmin ? [adminNavItem] : []),
  ];

  return (
    <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>{t("common.appName")}</SheetTitle>
        </SheetHeader>
        <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-3">
          {items.map((item) => (
            <SheetClose asChild key={item.url}>
              <Link
                to={item.url}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive(item.url)
                    ? "bg-primary/12 text-primary"
                    : "text-sidebar-foreground/80 hover:bg-sidebar-accent",
                )}
              >
                <item.icon className="size-4 shrink-0" />
                {t(item.titleKey)}
              </Link>
            </SheetClose>
          ))}
        </nav>
        <div className="border-t border-sidebar-border p-3">
          <button
            onClick={onSignOut}
            className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-sidebar-accent"
          >
            <LogOut className="size-4" />
            {t("common.signOut")}
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
