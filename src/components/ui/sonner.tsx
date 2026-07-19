import { Toaster as Sonner, type ToasterProps } from "sonner";

function Toaster(props: ToasterProps) {
  return (
    <Sonner
      className="toaster group"
      position="top-center"
      richColors
      toastOptions={{
        classNames: {
          toast:
            "group toast rounded-xl border border-border bg-card text-card-foreground shadow-lift",
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
