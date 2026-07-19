import type { Database } from "@/lib/supabase/types";

/**
 * Single source of truth for the Algerian school hierarchy used in onboarding.
 * Values MUST match the `school_level` Postgres enum exactly — it is production
 * schema we never break. See supabase/migrations for the enum definition.
 */
export type SchoolLevel = Database["public"]["Enums"]["school_level"];
export type ExamTarget = Database["public"]["Enums"]["exam_target"];

export type Cycle = "primaire" | "cem" | "lycee" | "universite" | "autre";

export const CYCLES: { value: Cycle; label_fr: string; label_ar: string }[] = [
  { value: "primaire", label_fr: "Primaire", label_ar: "الابتدائي" },
  { value: "cem", label_fr: "CEM (Moyen)", label_ar: "المتوسط" },
  { value: "lycee", label_fr: "Lycée", label_ar: "الثانوي" },
  { value: "universite", label_fr: "Université", label_ar: "الجامعة" },
  { value: "autre", label_fr: "Autre", label_ar: "أخرى" },
];

export type GradeOption = {
  schoolLevel: SchoolLevel;
  label_fr: string;
  label_ar: string;
  /** true when this grade requires a filière (track) selection */
  hasTrack: boolean;
};

export type TrackOption = {
  schoolLevel: SchoolLevel;
  label_fr: string;
  label_ar: string;
};

const LYCEE_2_TRACKS: TrackOption[] = [
  { schoolLevel: "lycee_2_sciences", label_fr: "Sciences expérimentales", label_ar: "علوم تجريبية" },
  { schoolLevel: "lycee_2_maths", label_fr: "Mathématiques", label_ar: "رياضيات" },
  { schoolLevel: "lycee_2_techmath", label_fr: "Technique-Math", label_ar: "تقني رياضي" },
  { schoolLevel: "lycee_2_gestion", label_fr: "Gestion & économie", label_ar: "تسيير واقتصاد" },
  { schoolLevel: "lycee_2_langues", label_fr: "Langues étrangères", label_ar: "لغات أجنبية" },
  { schoolLevel: "lycee_2_lettres", label_fr: "Lettres & philosophie", label_ar: "آداب وفلسفة" },
  { schoolLevel: "lycee_2_arts", label_fr: "Arts", label_ar: "فنون" },
];

const LYCEE_3_TRACKS: TrackOption[] = [
  { schoolLevel: "lycee_3_sciences", label_fr: "Sciences expérimentales", label_ar: "علوم تجريبية" },
  { schoolLevel: "lycee_3_maths", label_fr: "Mathématiques", label_ar: "رياضيات" },
  { schoolLevel: "lycee_3_techmath", label_fr: "Technique-Math", label_ar: "تقني رياضي" },
  { schoolLevel: "lycee_3_gestion", label_fr: "Gestion & économie", label_ar: "تسيير واقتصاد" },
  { schoolLevel: "lycee_3_langues", label_fr: "Langues étrangères", label_ar: "لغات أجنبية" },
  { schoolLevel: "lycee_3_lettres", label_fr: "Lettres & philosophie", label_ar: "آداب وفلسفة" },
  { schoolLevel: "lycee_3_arts", label_fr: "Arts", label_ar: "فنون" },
];

/**
 * Grades available for a cycle. Lycée 2AS/3AS resolve through `tracksForGrade`.
 * 1AS is genuinely two tronc-commun tracks in the real system (sciences /
 * lettres), not one — index order here (0,1 = 1AS; 2 = 2AS; 3 = 3AS) is
 * relied on by the onboarding wizard's year selection.
 */
export const GRADES_BY_CYCLE: Record<Cycle, GradeOption[]> = {
  primaire: [{ schoolLevel: "primaire", label_fr: "Primaire", label_ar: "الابتدائي", hasTrack: false }],
  cem: [
    { schoolLevel: "cem_1", label_fr: "1ère année moyenne (1AM)", label_ar: "السنة الأولى متوسط", hasTrack: false },
    { schoolLevel: "cem_2", label_fr: "2e année moyenne (2AM)", label_ar: "السنة الثانية متوسط", hasTrack: false },
    { schoolLevel: "cem_3", label_fr: "3e année moyenne (3AM)", label_ar: "السنة الثالثة متوسط", hasTrack: false },
    { schoolLevel: "cem_4", label_fr: "4e année moyenne — BEM (4AM)", label_ar: "السنة الرابعة متوسط (شهادة التعليم المتوسط)", hasTrack: false },
  ],
  lycee: [
    { schoolLevel: "lycee_1_tc_sciences", label_fr: "1ère année secondaire — tronc commun sciences (1AS)", label_ar: "السنة الأولى ثانوي (جذع مشترك علوم)", hasTrack: false },
    { schoolLevel: "lycee_1_tc_lettres", label_fr: "1ère année secondaire — tronc commun lettres (1AS)", label_ar: "السنة الأولى ثانوي (جذع مشترك آداب)", hasTrack: false },
    { schoolLevel: "lycee_2_sciences", label_fr: "2e année secondaire (2AS)", label_ar: "السنة الثانية ثانوي", hasTrack: true },
    { schoolLevel: "lycee_3_sciences", label_fr: "3e année secondaire — BAC (3AS)", label_ar: "السنة الثالثة ثانوي (بكالوريا)", hasTrack: true },
  ],
  universite: [
    { schoolLevel: "univ_1", label_fr: "Licence 1 (L1)", label_ar: "السنة الأولى جامعي", hasTrack: false },
    { schoolLevel: "univ_2", label_fr: "Licence 2 (L2)", label_ar: "السنة الثانية جامعي", hasTrack: false },
    { schoolLevel: "univ_3", label_fr: "Licence 3 (L3)", label_ar: "السنة الثالثة جامعي", hasTrack: false },
  ],
  autre: [{ schoolLevel: "autre", label_fr: "Autre", label_ar: "أخرى", hasTrack: false }],
};

export function tracksForGrade(cycle: Cycle, grade: GradeOption): TrackOption[] {
  if (cycle !== "lycee" || !grade.hasTrack) return [];
  return grade.schoolLevel.startsWith("lycee_2") || grade.label_fr.includes("2e")
    ? LYCEE_2_TRACKS
    : LYCEE_3_TRACKS;
}

/** 2AS / 3AS grade rows are placeholders (default to sciences); pick the right track list by year. */
export function tracksForYear(year: 2 | 3): TrackOption[] {
  return year === 2 ? LYCEE_2_TRACKS : LYCEE_3_TRACKS;
}

export function cycleFromSchoolLevel(level: SchoolLevel): Cycle {
  if (level === "primaire") return "primaire";
  if (level.startsWith("cem_")) return "cem";
  if (level.startsWith("lycee_")) return "lycee";
  if (level.startsWith("univ_")) return "universite";
  return "autre";
}

export function suggestedExamTarget(level: SchoolLevel): ExamTarget {
  if (level === "cem_4") return "bem";
  if (level.startsWith("lycee_3")) return "bac";
  return "none";
}

export function schoolLevelLabel(level: SchoolLevel, lang: "fr" | "ar" = "fr"): string {
  for (const grades of Object.values(GRADES_BY_CYCLE)) {
    const grade = grades.find((g) => g.schoolLevel === level);
    if (grade) return lang === "ar" ? grade.label_ar : grade.label_fr;
  }
  for (const track of [...LYCEE_2_TRACKS, ...LYCEE_3_TRACKS]) {
    if (track.schoolLevel === level) return lang === "ar" ? track.label_ar : track.label_fr;
  }
  return level;
}
