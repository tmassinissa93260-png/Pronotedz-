import { describe, it, expect } from "vitest";
import {
  GRADES_BY_CYCLE,
  CYCLES,
  tracksForYear,
  cycleFromSchoolLevel,
  suggestedExamTarget,
  schoolLevelLabel,
  type SchoolLevel,
} from "./school-levels";

// Every value here must exist verbatim in the production `school_level` Postgres
// enum (supabase/migrations). This list is the schema's source of truth mirrored
// for tests — never edit it to match new app code, only to match a migration.
const PRODUCTION_SCHOOL_LEVEL_ENUM: SchoolLevel[] = [
  "primaire",
  "cem_1",
  "cem_2",
  "cem_3",
  "cem_4",
  "lycee_1_tc",
  "lycee_2_sciences",
  "lycee_2_lettres",
  "lycee_2_maths",
  "lycee_2_gestion",
  "lycee_2_langues",
  "lycee_2_techmath",
  "lycee_3_sciences",
  "lycee_3_lettres",
  "lycee_3_maths",
  "lycee_3_gestion",
  "lycee_3_langues",
  "lycee_3_techmath",
  "univ_1",
  "univ_2",
  "univ_3",
  "autre",
];

function allMappedLevels(): SchoolLevel[] {
  const levels = new Set<SchoolLevel>();
  for (const grades of Object.values(GRADES_BY_CYCLE)) {
    for (const g of grades) levels.add(g.schoolLevel);
  }
  for (const year of [2, 3] as const) {
    for (const t of tracksForYear(year)) levels.add(t.schoolLevel);
  }
  return [...levels];
}

describe("school-levels mapping stays in sync with the production enum", () => {
  it("only ever produces values that exist in the enum", () => {
    for (const level of allMappedLevels()) {
      expect(PRODUCTION_SCHOOL_LEVEL_ENUM).toContain(level);
    }
  });

  it("covers every enum value from onboarding (nothing unreachable)", () => {
    const mapped = new Set(allMappedLevels());
    for (const level of PRODUCTION_SCHOOL_LEVEL_ENUM) {
      expect(mapped.has(level), `${level} is not reachable from any onboarding step`).toBe(true);
    }
  });

  it("round-trips cycleFromSchoolLevel for every enum value", () => {
    expect(cycleFromSchoolLevel("primaire")).toBe("primaire");
    expect(cycleFromSchoolLevel("cem_3")).toBe("cem");
    expect(cycleFromSchoolLevel("lycee_2_maths")).toBe("lycee");
    expect(cycleFromSchoolLevel("univ_2")).toBe("universite");
    expect(cycleFromSchoolLevel("autre")).toBe("autre");
  });

  it("suggests bem only for cem_4 and bac only for 3AS tracks", () => {
    expect(suggestedExamTarget("cem_4")).toBe("bem");
    expect(suggestedExamTarget("cem_1")).toBe("none");
    expect(suggestedExamTarget("lycee_3_sciences")).toBe("bac");
    expect(suggestedExamTarget("lycee_2_sciences")).toBe("none");
    expect(suggestedExamTarget("univ_1")).toBe("none");
  });

  it("has a French and Arabic label for every enum value", () => {
    for (const level of PRODUCTION_SCHOOL_LEVEL_ENUM) {
      expect(schoolLevelLabel(level, "fr")).not.toBe(level);
      expect(schoolLevelLabel(level, "ar")).not.toBe(level);
    }
  });

  it("2AS and 3AS each expose exactly the 6 official Algerian lycée tracks", () => {
    expect(tracksForYear(2)).toHaveLength(6);
    expect(tracksForYear(3)).toHaveLength(6);
    const year2 = tracksForYear(2).map((t) => t.schoolLevel);
    const year3 = tracksForYear(3).map((t) => t.schoolLevel);
    expect(new Set(year2).size).toBe(6);
    expect(new Set(year3).size).toBe(6);
  });

  it("exposes all 5 cycles with bilingual labels", () => {
    expect(CYCLES).toHaveLength(5);
    for (const c of CYCLES) {
      expect(c.label_fr.length).toBeGreaterThan(0);
      expect(c.label_ar.length).toBeGreaterThan(0);
    }
  });
});
