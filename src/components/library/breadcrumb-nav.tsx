import { Link } from "@tanstack/react-router";
import { ChevronRight } from "lucide-react";
import { Fragment } from "react";

export type Crumb = { label: string; to?: string; params?: Record<string, string> };

export function BreadcrumbNav({ items }: { items: Crumb[] }) {
  return (
    <nav aria-label="Fil d'ariane" className="flex flex-wrap items-center gap-1.5 text-sm text-muted-foreground">
      {items.map((item, i) => (
        <Fragment key={i}>
          {i > 0 && <ChevronRight className="size-3.5 shrink-0" />}
          {item.to ? (
            <Link to={item.to} params={item.params} className="transition-colors hover:text-foreground">
              {item.label}
            </Link>
          ) : (
            <span className="font-medium text-foreground">{item.label}</span>
          )}
        </Fragment>
      ))}
    </nav>
  );
}
