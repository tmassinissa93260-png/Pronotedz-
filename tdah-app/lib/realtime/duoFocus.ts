import type { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from '../supabase/client';

// Body doubling à deux humains (façon Focusmate) — pas de vidéo/audio (ça
// demanderait un SDK natif + un build EAS qu'on n'a pas encore), mais le vrai
// mécanisme qui fait marcher Focusmate n'est pas la vidéo, c'est la présence
// mutuelle engagée : deux personnes qui savent que l'autre est vraiment là,
// au même moment, avec un minuteur partagé. On le fait via Supabase Realtime
// (presence + broadcast), sans table dédiée : la "salle" est juste le nom du
// channel, comme un code de partie.

export type DuoEvent =
  | { type: 'start'; targetMinutes: number | null; startedAt: number }
  | { type: 'encourage'; emoji: string; from: string }
  | { type: 'end' };

const CODE_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'; // sans caractères ambigus (0/O, 1/I)

export function generateRoomCode(): string {
  let code = '';
  for (let i = 0; i < 6; i++) code += CODE_CHARS[Math.floor(Math.random() * CODE_CHARS.length)];
  return code;
}

export function joinDuoRoom(
  code: string,
  userId: string,
  handlers: {
    onPeerIds: (ids: string[]) => void;
    onEvent: (event: DuoEvent) => void;
  }
): RealtimeChannel {
  const channel = supabase.channel(`duo-focus-${code.toUpperCase()}`, {
    config: { presence: { key: userId } },
  });

  channel.on('presence', { event: 'sync' }, () => {
    const state = channel.presenceState();
    handlers.onPeerIds(Object.keys(state).filter((id) => id !== userId));
  });

  channel.on('broadcast', { event: 'duo-event' }, ({ payload }) => {
    handlers.onEvent(payload as DuoEvent);
  });

  channel.subscribe(async (status) => {
    if (status === 'SUBSCRIBED') {
      await channel.track({ online_at: new Date().toISOString() });
    }
  });

  return channel;
}

export function sendDuoEvent(channel: RealtimeChannel, event: DuoEvent) {
  channel.send({ type: 'broadcast', event: 'duo-event', payload: event });
}

export function leaveDuoRoom(channel: RealtimeChannel) {
  supabase.removeChannel(channel);
}

// Matching automatique : au lieu de partager un code avec quelqu'un qu'on
// connaît déjà (Focusmate n'a même pas ça — juste de l'IA), une salle
// d'attente commune où deux inconnus disponibles en même temps se
// retrouvent appairés automatiquement. Élection déterministe par tri des
// ids présents : seul le premier de la paire diffuse le code de la salle,
// pour que les deux ne créent pas chacun un salon différent.
export function joinLobby(
  userId: string,
  handlers: {
    onMatched: (roomCode: string) => void;
    onWaitingCountChange: (count: number) => void;
  }
): RealtimeChannel {
  const channel = supabase.channel('duo-focus-lobby', {
    config: { presence: { key: userId } },
  });
  let hasTriggeredMatch = false;

  channel.on('presence', { event: 'sync' }, () => {
    const ids = Object.keys(channel.presenceState()).sort();
    handlers.onWaitingCountChange(ids.length);

    if (ids.length >= 2 && !hasTriggeredMatch && userId === ids[0]) {
      hasTriggeredMatch = true;
      const pair = [ids[0], ids[1]];
      const code = generateRoomCode();
      channel.send({ type: 'broadcast', event: 'lobby-match', payload: { pair, code } });
    }
  });

  channel.on('broadcast', { event: 'lobby-match' }, ({ payload }) => {
    const { pair, code } = payload as { pair: string[]; code: string };
    if (pair.includes(userId)) handlers.onMatched(code);
  });

  channel.subscribe(async (status) => {
    if (status === 'SUBSCRIBED') {
      await channel.track({ online_at: new Date().toISOString() });
    }
  });

  return channel;
}

export function leaveLobby(channel: RealtimeChannel) {
  supabase.removeChannel(channel);
}
