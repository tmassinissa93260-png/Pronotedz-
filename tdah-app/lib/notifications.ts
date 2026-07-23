import * as Notifications from 'expo-notifications';
import AsyncStorage from '@react-native-async-storage/async-storage';

// Rappels locaux (pas de push distant — juste des notifications programmées
// sur l'appareil, ça marche encore dans Expo Go contrairement au push
// distant qui a été retiré côté Android depuis le SDK 53). Répond au point
// le plus cité dans la checklist "bonne app" du fondateur : des rappels
// pour respecter les horaires sans avoir à y penser.

const STORAGE_PREFIX = 'notif:';
const MINUTES_BEFORE = 5;
// TickTick a un "rappel constant" qui sonne en boucle tant que la tâche
// n'est pas traitée — on fait volontairement plus doux : un seul rappel de
// relance, pas une alarme qui insiste. Une notif qui harcèle irait à
// l'encontre du "discrète et non intrusive" qu'on vise.
const FOLLOWUP_AFTER_MINUTES = 10;

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

// Programme un rappel N minutes avant l'heure de début d'une tâche, plus une
// relance douce si elle n'a toujours pas été traitée un peu après. Annule
// d'abord tout rappel précédent pour cette tâche pour éviter les doublons
// si l'heure est modifiée.
export async function scheduleTaskReminder(taskId: string, titre: string, dateISO: string, heureDebut: string) {
  await cancelTaskReminder(taskId);

  const [h, m] = heureDebut.split(':').map(Number);
  const reminderAt = new Date(`${dateISO}T00:00:00`);
  reminderAt.setHours(h, m - MINUTES_BEFORE, 0, 0);
  const followUpAt = new Date(`${dateISO}T00:00:00`);
  followUpAt.setHours(h, m + FOLLOWUP_AFTER_MINUTES, 0, 0);

  const granted = await requestNotificationPermission();
  if (!granted) return;

  const ids: string[] = [];

  if (reminderAt.getTime() > Date.now()) {
    ids.push(
      await Notifications.scheduleNotificationAsync({
        content: {
          title: `Dans ${MINUTES_BEFORE} min : ${titre}`,
          body: `Prévu à ${heureDebut.slice(0, 5)}`,
        },
        trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: reminderAt },
      })
    );
  }

  if (followUpAt.getTime() > Date.now()) {
    ids.push(
      await Notifications.scheduleNotificationAsync({
        content: {
          title: `Toujours partant pour "${titre}" ?`,
          body: 'Pas de souci si ce n’est pas encore fait — juste un petit rappel.',
        },
        trigger: { type: Notifications.SchedulableTriggerInputTypes.DATE, date: followUpAt },
      })
    );
  }

  if (ids.length > 0) {
    await AsyncStorage.setItem(`${STORAGE_PREFIX}${taskId}`, JSON.stringify(ids));
  }
}

export async function cancelTaskReminder(taskId: string) {
  const raw = await AsyncStorage.getItem(`${STORAGE_PREFIX}${taskId}`);
  if (!raw) return;
  const ids: string[] = JSON.parse(raw);
  await Promise.all(ids.map((id) => Notifications.cancelScheduledNotificationAsync(id).catch(() => {})));
  await AsyncStorage.removeItem(`${STORAGE_PREFIX}${taskId}`);
}

const LIGHT_REMINDER_KEY = 'notif:lumiere-matin';

// Rappel lumière du matin : complément direct à la chronothérapie sommeil —
// la lumière matinale est le levier le mieux documenté pour avancer une
// horloge biologique en retard de phase, très fréquent en TDAH (jusqu'à 75%
// des adultes selon la littérature sur les rythmes circadiens et le TDAH).
export async function scheduleLightReminder(hour: number, minute: number) {
  await cancelLightReminder();
  const granted = await requestNotificationPermission();
  if (!granted) return;
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title: '☀️ Lumière du matin',
      body: '10 minutes de lumière (fenêtre, dehors) aident ton horloge biologique à se recaler.',
    },
    trigger: { type: Notifications.SchedulableTriggerInputTypes.DAILY, hour, minute },
  });
  await AsyncStorage.setItem(LIGHT_REMINDER_KEY, id);
}

export async function cancelLightReminder() {
  const id = await AsyncStorage.getItem(LIGHT_REMINDER_KEY);
  if (!id) return;
  await Notifications.cancelScheduledNotificationAsync(id).catch(() => {});
  await AsyncStorage.removeItem(LIGHT_REMINDER_KEY);
}

export async function isLightReminderScheduled(): Promise<boolean> {
  return (await AsyncStorage.getItem(LIGHT_REMINDER_KEY)) != null;
}
