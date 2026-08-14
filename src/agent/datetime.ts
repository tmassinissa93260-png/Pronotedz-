// Toutes les datetimes du systeme sont des chaines "naives" (sans offset,
// ex: "2026-07-25T10:30:00") representant l'heure LOCALE du commerce, pas UTC
// et pas l'heure locale du serveur. On evite volontairement `new Date(str)` /
// `new Date(y,m,d,h,mi)` pour l'arithmetique de creneaux car leur
// interpretation depend du fuseau horaire du PROCESSUS NODE, ce qui produit
// des reservations decalees d'heure quand le serveur ne tourne pas dans le
// meme fuseau que le commerce (typique en conteneur, TZ=UTC par defaut).
// On utilise Date.UTC(...) uniquement comme espace arithmetique neutre.

export interface NaiveDateTime {
  y: number;
  mo: number; // 1-12
  d: number;
  h: number;
  mi: number;
  s: number;
}

const DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2}))?$/;
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

function isValidCalendarDate(y: number, mo: number, d: number): boolean {
  if (mo < 1 || mo > 12 || d < 1 || d > 31) return false;
  const ms = Date.UTC(y, mo - 1, d);
  const check = new Date(ms);
  return check.getUTCFullYear() === y && check.getUTCMonth() === mo - 1 && check.getUTCDate() === d;
}

export function parseNaiveDateTime(input: unknown): NaiveDateTime | null {
  if (typeof input !== "string") return null;
  const m = DATETIME_RE.exec(input.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const h = Number(m[4]);
  const mi = Number(m[5]);
  const s = m[6] ? Number(m[6]) : 0;
  if (!isValidCalendarDate(y, mo, d)) return null;
  if (h > 23 || mi > 59 || s > 59) return null;
  return { y, mo, d, h, mi, s };
}

export function parseNaiveDate(input: unknown): { y: number; mo: number; d: number } | null {
  if (typeof input !== "string") return null;
  const m = DATE_RE.exec(input.trim());
  if (!m) return null;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  if (!isValidCalendarDate(y, mo, d)) return null;
  return { y, mo, d };
}

export function naiveToEpochMs(dt: NaiveDateTime): number {
  return Date.UTC(dt.y, dt.mo - 1, dt.d, dt.h, dt.mi, dt.s);
}

export function formatNaive(y: number, mo: number, d: number, h: number, mi: number, s = 0): string {
  const p2 = (n: number) => String(n).padStart(2, "0");
  return `${y}-${p2(mo)}-${p2(d)}T${p2(h)}:${p2(mi)}:${p2(s)}`;
}

export function naiveDateKey(dt: NaiveDateTime): string {
  const p2 = (n: number) => String(n).padStart(2, "0");
  return `${dt.y}-${p2(dt.mo)}-${p2(dt.d)}`;
}

// Heure "actuelle" exprimee comme datetime naive dans le fuseau du commerce,
// via l'API Intl (pas de dependance externe, gere correctement les regles DST/IANA).
export function nowInTimezone(timezone: string): NaiveDateTime {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: timezone,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).formatToParts(new Date());

  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? "0");
  return {
    y: get("year"),
    mo: get("month"),
    d: get("day"),
    h: get("hour") === 24 ? 0 : get("hour"),
    mi: get("minute"),
    s: get("second"),
  };
}

export function isWithinBusinessHours(dt: NaiveDateTime, openHour: number, closeHour: number, durationMinutes: number): boolean {
  const startMinutes = dt.h * 60 + dt.mi;
  const endMinutes = startMinutes + durationMinutes;
  return startMinutes >= openHour * 60 && endMinutes <= closeHour * 60;
}

export function isInThePast(dt: NaiveDateTime, timezone: string): boolean {
  return naiveToEpochMs(dt) < naiveToEpochMs(nowInTimezone(timezone));
}
