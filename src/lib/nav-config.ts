import {
  LayoutDashboard,
  Sparkles,
  Library,
  BookOpen,
  Video,
  Wrench,
  ListTodo,
  Users,
  MessageSquare,
  Archive,
  GraduationCap,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";
import type { TranslationKey } from "@/lib/i18n";

export type NavItem = {
  titleKey: TranslationKey;
  url: string;
  icon: LucideIcon;
};

export const primaryNav: NavItem[] = [
  { titleKey: "nav.dashboard", url: "/dashboard", icon: LayoutDashboard },
  { titleKey: "nav.aiTutor", url: "/ai", icon: Sparkles },
  { titleKey: "nav.library", url: "/library", icon: Library },
  { titleKey: "nav.courses", url: "/courses", icon: BookOpen },
  { titleKey: "nav.teachers", url: "/teachers", icon: Video },
  { titleKey: "nav.tools", url: "/tools", icon: Wrench },
  { titleKey: "nav.tasks", url: "/tasks", icon: ListTodo },
];

export const communityNav: NavItem[] = [
  { titleKey: "nav.groups", url: "/groups", icon: Users },
  { titleKey: "nav.community", url: "/community", icon: MessageSquare },
  { titleKey: "nav.archive", url: "/archive", icon: Archive },
];

export const mobileTabs: NavItem[] = [
  { titleKey: "nav.dashboard", url: "/dashboard", icon: LayoutDashboard },
  { titleKey: "nav.aiTutor", url: "/ai", icon: Sparkles },
  { titleKey: "nav.library", url: "/library", icon: Library },
  { titleKey: "nav.teachers", url: "/teachers", icon: Video },
];

export const teacherNavItem: NavItem = { titleKey: "nav.teacherSpace", url: "/teacher", icon: GraduationCap };
export const adminNavItem: NavItem = { titleKey: "nav.admin", url: "/admin", icon: ShieldCheck };
