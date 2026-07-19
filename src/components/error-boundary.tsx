import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

type Props = { children: ReactNode };
type State = { error: Error | null };

function Fallback({ error, onRetry }: { error: Error; onRetry: () => void }) {
  const t = useT();
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="grid size-14 place-items-center rounded-2xl bg-destructive/10 text-destructive">
        <AlertTriangle className="size-6" />
      </div>
      <div>
        <h2 className="font-display text-lg font-semibold">{t("common.somethingWrong")}</h2>
        <p className="mt-1 max-w-sm text-sm text-muted-foreground">{error.message}</p>
      </div>
      <Button onClick={onRetry}>{t("common.retry")}</Button>
    </div>
  );
}

/** Top-level React error boundary. Catches render errors anywhere below it. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return <Fallback error={this.state.error} onRetry={() => this.setState({ error: null })} />;
    }
    return this.props.children;
  }
}
