import { test, describe } from "node:test";
import assert from "node:assert/strict";
import {
  parseNaiveDateTime,
  parseNaiveDate,
  isWithinBusinessHours,
  isInThePast,
  naiveToEpochMs,
} from "../agent/datetime";

describe("parseNaiveDateTime", () => {
  test("accepte un format ISO local valide", () => {
    const parsed = parseNaiveDateTime("2026-07-25T10:30:00");
    assert.deepEqual(parsed, { y: 2026, mo: 7, d: 25, h: 10, mi: 30, s: 0 });
  });

  test("rejette une date calendaire invalide (30 fevrier)", () => {
    assert.equal(parseNaiveDateTime("2026-02-30T10:00:00"), null);
  });

  test("rejette une heure invalide", () => {
    assert.equal(parseNaiveDateTime("2026-07-25T25:00:00"), null);
  });

  test("rejette un format non conforme", () => {
    assert.equal(parseNaiveDateTime("demain a 10h"), null);
    assert.equal(parseNaiveDateTime(""), null);
    assert.equal(parseNaiveDateTime(undefined), null);
    assert.equal(parseNaiveDateTime(12345 as any), null);
  });
});

describe("parseNaiveDate", () => {
  test("accepte YYYY-MM-DD", () => {
    assert.deepEqual(parseNaiveDate("2026-07-25"), { y: 2026, mo: 7, d: 25 });
  });
  test("rejette un jour hors calendrier", () => {
    assert.equal(parseNaiveDate("2026-04-31"), null);
  });
});

describe("isWithinBusinessHours", () => {
  test("accepte un creneau dans les horaires", () => {
    const dt = parseNaiveDateTime("2026-07-25T10:00:00")!;
    assert.equal(isWithinBusinessHours(dt, 9, 19, 30), true);
  });
  test("refuse un creneau qui deborde apres la fermeture", () => {
    const dt = parseNaiveDateTime("2026-07-25T18:45:00")!;
    assert.equal(isWithinBusinessHours(dt, 9, 19, 30), false);
  });
  test("refuse un creneau avant l'ouverture", () => {
    const dt = parseNaiveDateTime("2026-07-25T07:00:00")!;
    assert.equal(isWithinBusinessHours(dt, 9, 19, 30), false);
  });
});

describe("isInThePast + fuseau horaire du commerce", () => {
  test("une date lointaine dans le futur n'est jamais consideree passee", () => {
    const dt = parseNaiveDateTime("2099-01-01T10:00:00")!;
    assert.equal(isInThePast(dt, "Africa/Algiers"), false);
  });
  test("une date lointaine dans le passe est bien detectee", () => {
    const dt = parseNaiveDateTime("2000-01-01T10:00:00")!;
    assert.equal(isInThePast(dt, "Africa/Algiers"), true);
  });
  test("le calcul est independant du fuseau horaire du PROCESSUS node (pas de new Date() implicite)", () => {
    // naiveToEpochMs doit etre purement deterministe a partir des composantes,
    // sans dependre de process.env.TZ.
    const dt = parseNaiveDateTime("2026-07-25T10:30:00")!;
    const epoch1 = naiveToEpochMs(dt);
    const epoch2 = naiveToEpochMs(dt);
    assert.equal(epoch1, epoch2);
    assert.equal(epoch1, Date.UTC(2026, 6, 25, 10, 30, 0));
  });
});
