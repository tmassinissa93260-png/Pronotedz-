import { Languages } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n";

export function LanguageSwitcher({ compact = false }: { compact?: boolean }) {
  const { lang, setLang } = useI18n();

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size={compact ? "icon" : "default"} aria-label="Changer de langue">
          <Languages className="size-4" />
          {!compact && <span>{lang === "fr" ? "Français" : "العربية"}</span>}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onSelect={() => setLang("fr")} data-active={lang === "fr"}>
          🇫🇷 Français
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => setLang("ar")} data-active={lang === "ar"}>
          🇩🇿 العربية
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
