import { createRootRouteWithContext, Outlet, Link } from "@tanstack/react-router";
import type { QueryClient } from "@tanstack/react-query";
import { PageTransition } from "@/components/motion/page-transition";
import { Button } from "@/components/ui/button";

export const Route = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  component: RootComponent,
  notFoundComponent: NotFound,
});

function RootComponent() {
  return (
    <PageTransition>
      <Outlet />
    </PageTransition>
  );
}

function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      <span className="font-display text-7xl font-bold text-primary">404</span>
      <div>
        <h1 className="font-display text-xl font-semibold">Page introuvable</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Cette page n'existe pas ou a été déplacée.
        </p>
      </div>
      <Button asChild>
        <Link to="/">Retour à l'accueil</Link>
      </Button>
    </div>
  );
}
