import * as Calendar from 'expo-calendar';
import { Platform } from 'react-native';

const CALENDAR_NAME = 'Compagnon TDAH';

async function ensurePermission(): Promise<boolean> {
  const { status } = await Calendar.requestCalendarPermissionsAsync();
  return status === 'granted';
}

async function getOrCreateCalendarId(): Promise<string> {
  const calendars = await Calendar.getCalendarsAsync(Calendar.EntityTypes.EVENT);
  const existing = calendars.find((c) => c.title === CALENDAR_NAME);
  if (existing) return existing.id;

  const defaultCalendarSource =
    Platform.OS === 'ios'
      ? (await Calendar.getDefaultCalendarAsync()).source
      : { isLocalAccount: true, name: CALENDAR_NAME, type: Calendar.SourceType.LOCAL };

  return Calendar.createCalendarAsync({
    title: CALENDAR_NAME,
    color: '#5B6EE8',
    entityType: Calendar.EntityTypes.EVENT,
    source: defaultCalendarSource,
    name: CALENDAR_NAME,
    ownerAccount: 'compagnon-tdah',
    accessLevel: Calendar.CalendarAccessLevel.OWNER,
  });
}

type TaskForCalendar = {
  id: string;
  titre: string;
  date_prevue: string; // YYYY-MM-DD
  estimation_minutes: number | null;
};

// Un seul événement calendrier par tâche, ré-identifiable via son titre +
// date pour éviter les doublons si on synchronise plusieurs fois.
export async function syncTaskToCalendar(task: TaskForCalendar): Promise<boolean> {
  const granted = await ensurePermission();
  if (!granted) return false;

  const calendarId = await getOrCreateCalendarId();
  const start = new Date(`${task.date_prevue}T09:00:00`);
  const durationMinutes = task.estimation_minutes ?? 30;
  const end = new Date(start.getTime() + durationMinutes * 60 * 1000);

  await Calendar.createEventAsync(calendarId, {
    title: task.titre,
    startDate: start,
    endDate: end,
    notes: 'Ajouté depuis Compagnon TDAH',
  });

  return true;
}
