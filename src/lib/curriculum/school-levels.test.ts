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
// enum (supabase/migrations, including 20260719180000_dz_filieres_trimesters_lessons.sql).
// This list is the schema's source of truth mirrored for tests — never edit it
// to match new app code, only to match a migration.
const PRODUCTION_SCHOOL_LEVEL_ENUM: SchoolLevel[] = [
  "primaire",
  "cem_1",
  "cem_2",
  "cem_3",
  "cem_4",
  "lycee_1_tc",
  "lycee_1_tc_sciences",
  "lycee_1_tc_lettres",
  "lycee_2_sciences",
  "lycee_2_lettres",
  "lycee_2_maths",
  "lycee_2_gestion",
  "lycee_2_langues",
  "lycee_2_techmath",
  "lycee_2_arts",
  "lycee_3_sciences",
  "lycee_3_lettres",
  "lycee_3_maths",
  "lycee_3_gestion",
  "lycee_3_langues",
  "lycee_3_techmath",
  "lycee_3_arts",
  "univ_1",
  "univ_2",
  "univ_3",
  "autre",
];

// `lycee_1_tc` predates the sciences/lettres split and is kept only so old
// rows stay valid — onboarding no longer offers it, by design.
const LEGACY_UNREACHABLE: SchoolLevel[] = ["lycee_1_tc"];

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

  it("covers every current enum value from onboarding (nothing unreachable)", () => {
    const mapped = new Set(allMappedLevels());
    for (const level of PRODUCTION_SCHOOL_LEVEL_ENUM) {
      if (LEGACY_UNREACHABLE.includes(level)) continue;
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

  it("has a French and Arabic label for every reachable enum value", () => {
    for (const level of PRODUCTION_SCHOOL_LEVEL_ENUM) {
      if (LEGACY_UNREACHABLE.includes(level)) continue;
      expect(schoolLevelLabel(level, "fr")).not.toBe(level);
      expect(schoolLevelLabel(level, "ar")).not.toBe(level);
    }
  });

  it("2AS and 3AS each expose exactly the 7 official Algerian lycée filières (incl. Arts)", () => {
    expect(tracksForYear(2)).toHaveLength(7);
    expect(tracksForYear(3)).toHaveLength(7);
    const year2 = tracksForYear(2).map((t) => t.schoolLevel);
    const year3 = tracksForYear(3).map((t) => t.schoolLevel);
    expect(new Set(year2).size).toBe(7);
    expect(new Set(year3).size).toBe(7);
    expect(year2).toContain("lycee_2_arts");
    expect(year3).toContain("lycee_3_arts");
  });

  it("1AS is a real sciences/lettres split, not a single generic tronc commun", () => {
    const oneAS = GRADES_BY_CYCLE.lycee.filter((g) => g.schoolLevel.startsWith("lycee_1"));
    expect(oneAS.map((g) => g.schoolLevel)).toEqual(["lycee_1_tc_sciences", "lycee_1_tc_lettres"]);
  });

  it("exposes all 5 cycles with bilingual labels", () => {
    expect(CYCLES).toHaveLength(5);
    for (const c of CYCLES) {
      expect(c.label_fr.length).toBeGreaterThan(0);
      expect(c.label_ar.length).toBeGreaterThan(0);
    }
  });
});
