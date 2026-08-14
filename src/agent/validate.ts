// Validation stricte des arguments d'outils. Le schema JSON envoye a Claude
// (input_schema) ne fait que GUIDER la generation du modele : rien ne garantit
// qu'un input recu respecte les types/bornes attendus (hallucination, valeur
// manquante, type incorrect...). La sortie du modele n'est jamais une source
// de verite : chaque champ est revalide ici avant de toucher la base.

export type ValidationResult<T> = { ok: true; value: T } | { ok: false; error: string };

function ok<T>(value: T): ValidationResult<T> {
  return { ok: true, value };
}
function fail<T>(error: string): ValidationResult<T> {
  return { ok: false, error };
}

const PHONE_RE = /^[+0-9][0-9 .-]{5,19}$/;
const ID_RE = /^[A-Za-z0-9_-]{1,64}$/;

export function requireNonEmptyString(value: unknown, field: string, maxLen = 200): ValidationResult<string> {
  if (typeof value !== "string") return fail(`${field} doit etre une chaine de caracteres.`);
  const trimmed = value.trim();
  if (trimmed.length === 0) return fail(`${field} est requis.`);
  if (trimmed.length > maxLen) return fail(`${field} est trop long (max ${maxLen} caracteres).`);
  return ok(trimmed);
}

export function requireId(value: unknown, field: string): ValidationResult<string> {
  if (typeof value !== "string" || !ID_RE.test(value)) return fail(`${field} est invalide.`);
  return ok(value);
}

export function requirePhone(value: unknown, field = "customer_phone"): ValidationResult<string> {
  if (typeof value !== "string" || !PHONE_RE.test(value.trim())) {
    return fail(`${field} doit etre un numero de telephone valide.`);
  }
  return ok(value.trim());
}

export function requireEnum<T extends string>(value: unknown, allowed: readonly T[], field: string): ValidationResult<T> {
  if (typeof value !== "string" || !(allowed as readonly string[]).includes(value)) {
    return fail(`${field} doit etre l'un de: ${allowed.join(", ")}.`);
  }
  return ok(value as T);
}

export function requirePositiveInt(value: unknown, field: string, max: number): ValidationResult<number> {
  if (typeof value !== "number" || !Number.isInteger(value) || value < 1 || value > max) {
    return fail(`${field} doit etre un entier entre 1 et ${max}.`);
  }
  return ok(value);
}

export function requireItemsArray(
  value: unknown,
  maxItems = 30
): ValidationResult<{ menu_item_id: unknown; quantity: unknown }[]> {
  if (!Array.isArray(value) || value.length === 0) return fail("items doit etre une liste non vide.");
  if (value.length > maxItems) return fail(`items ne peut pas depasser ${maxItems} lignes.`);
  return ok(value);
}
