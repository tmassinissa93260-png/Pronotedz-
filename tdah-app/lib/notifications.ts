import * as Notifications from 'expo-notifications';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Rappels locaux (pas de push distant — juste des notifications programmées
// sur l'appareil, ça marche encore dans Expo Go contrairement au push
// distant qui a été retiré côté Android depuis le SDK 53). Répond au point
// le plus cité dans la checklist "bonne app" du fondateur : des rappels
// pour respecter les horaires sans avoir à y penser.

const STORAGE_PREFIX = 'notif:';
const MINUTES_BEFORE = 5;

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function requestNotificationPermission(): Promise<boolean> {
  const current = await Notifications.getPermissionsAsync();
  if (current.granted) return true;
  const requested = await Notifications.requestPermissionsAsync();
  return requested.granted;
}

// Programme un rappel N minutes avant l'heure de début d'une tâche. Annule
// d'abord tout rappel précédent pour cette tâche pour éviter les doublons
// si l'heure est modifiée.
export async function scheduleTaskReminder(taskId: string, titre: string, dateISO: string, heureDebut: string) {
  await cancelTaskReminder(taskId);

  const [h, m] = heureDebut.split(':').map(Number);
  const target = new Date(`${dateISO}T00:00:00`);
  target.setHours(h, m - MINUTES_BEFORE, 0, 0);
  if (target.getTime() <= Date.now()) return;

  const granted = await requestNotificationPermission();
  if (!granted) return;

  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title: `Dans ${MINUTES_BEFORE} min : ${titre}`,
      body: `Prévu à ${heureDebut.slice(0, 5)}`,
    },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: target },
  });
  await AsyncStorage.setItem(`${STORAGE_PREFIX}${taskId}`, id);
}

export async function cancelTaskReminder(taskId: string) {
  const id = await AsyncStorage.getItem(`${STORAGE_PREFIX}${taskId}`);
  if (!id) return;
  await Notifications.cancelScheduledNotificationAsync(id).catch(() => {});
  await AsyncStorage.removeItem(`${STORAGE_PREFIX}${taskId}`);
}
