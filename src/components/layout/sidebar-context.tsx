import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type SidebarCtx = {
  collapsed: boolean;
  toggle: () => void;
  mobileOpen: boolean;
  setMobileOpen: (v: boolean) => void;
};

const Ctx = createContext<SidebarCtx | null>(null);
const STORAGE_KEY = "estadi_sidebar_collapsed";

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(() =>
    typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) === "1" : false,
  );
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  return (
    <Ctx.Provider value={{ collapsed, toggle: () => setCollapsed((c) => !c), mobileOpen, setMobileOpen }}>
      {children}
    </Ctx.Provider>
  );
}

export function useSidebar(): SidebarCtx {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useSidebar must be used inside <SidebarProvider>");
  return ctx;
}
