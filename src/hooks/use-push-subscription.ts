import { useEffect, useState } from "react";
import { isPushSupported, getExistingPushSubscription, subscribeToPush, unsubscribeFromPush } from "@/lib/push/subscribe";

export function usePushSubscription(userId: string) {
  const [supported] = useState(isPushSupported);
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!supported) return;
    getExistingPushSubscription().then((sub) => setSubscribed(Boolean(sub)));
  }, [supported]);

  async function toggle(): Promise<boolean> {
    setLoading(true);
    try {
      const next = !subscribed;
      if (next) {
        await subscribeToPush(userId);
      } else {
        await unsubscribeFromPush();
      }
      setSubscribed(next);
      return next;
    } finally {
      setLoading(false);
    }
  }

  return { supported, subscribed, loading, toggle };
}
