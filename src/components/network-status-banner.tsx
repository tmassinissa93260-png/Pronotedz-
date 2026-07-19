import { WifiOff } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useOnlineStatus } from "@/hooks/use-online-status";
import { useT } from "@/lib/i18n";

/** Persistent banner when offline; auto-refetches every query the moment connectivity returns. */
export function NetworkStatusBanner() {
  const online = useOnlineStatus();
  const queryClient = useQueryClient();
  const wasOffline = useRef(false);
  const t = useT();

  useEffect(() => {
    if (!online) {
      wasOffline.current = true;
    } else if (wasOffline.current) {
      wasOffline.current = false;
      queryClient.invalidateQueries();
    }
  }, [online, queryClient]);

  return (
    <AnimatePresence>
      {!online && (
        <motion.div
          initial={{ y: -40, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          exit={{ y: -40, opacity: 0 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="fixed inset-x-0 top-0 z-50 flex items-center justify-center gap-2 bg-destructive px-4 py-2 text-sm font-medium text-destructive-foreground"
          role="status"
        >
          <WifiOff className="size-4" />
          {t("common.networkError")}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
