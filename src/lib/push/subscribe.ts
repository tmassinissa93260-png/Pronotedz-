import { supabase } from "@/lib/supabase/client";

const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY as string | undefined;

function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const b64 = (base64 + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(b64);
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export function isPushSupported(): boolean {
  return typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && Boolean(VAPID_PUBLIC_KEY);
}

export async function getExistingPushSubscription(): Promise<PushSubscription | null> {
  if (!isPushSupported()) return null;
  const registration = await navigator.serviceWorker.getRegistration();
  if (!registration) return null;
  return registration.pushManager.getSubscription();
}

export async function subscribeToPush(userId: string): Promise<void> {
  if (!isPushSupported()) throw new Error("Les notifications push ne sont pas disponibles sur cet appareil.");
  const permission = await Notification.requestPermission();
  if (permission !== "granted") throw new Error("Autorisation refusée.");

  const registration = await navigator.serviceWorker.register("/sw.js");
  await navigator.serviceWorker.ready;

  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY as string) as BufferSource,
  });

  const json = subscription.toJSON();
  const row = {
    user_id: userId,
    endpoint: json.endpoint!,
    p256dh: json.keys!.p256dh,
    auth_key: json.keys!.auth,
    user_agent: navigator.userAgent,
  };

  const { data: existing } = await supabase
    .from("push_subscriptions")
    .select("id")
    .eq("endpoint", row.endpoint)
    .maybeSingle();

  const { error } = existing
    ? await supabase.from("push_subscriptions").update(row).eq("id", existing.id)
    : await supabase.from("push_subscriptions").insert(row);
  if (error) throw error;
}

export async function unsubscribeFromPush(): Promise<void> {
  const subscription = await getExistingPushSubscription();
  if (!subscription) return;
  const endpoint = subscription.endpoint;
  await subscription.unsubscribe();
  await supabase.from("push_subscriptions").delete().eq("endpoint", endpoint);
}
