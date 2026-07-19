import { useMemo, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { GraduationCap, Users, Sparkles, Upload, ShieldCheck, Check } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { FadeIn } from "@/components/motion/fade-in";
import { cn } from "@/lib/utils";
import { useT, useI18n, type Lang } from "@/lib/i18n";
import { useOnboardingSubmit } from "@/hooks/use-onboarding-submit";
import {
  CYCLES,
  GRADES_BY_CYCLE,
  tracksForYear,
  suggestedExamTarget,
  type Cycle,
  type SchoolLevel,
  type ExamTarget,
  type GradeOption,
} from "@/lib/curriculum/school-levels";
import type { Role } from "@/lib/onboarding/submit";

type StepId = "role" | "cycle" | "grade" | "track" | "exam" | "wilaya" | "language" | "teacher";

export function OnboardingWizard({ userId }: { userId: string }) {
  const t = useT();
  const { lang, setLang } = useI18n();
  const navigate = useNavigate();
  const submit = useOnboardingSubmit();

  const [step, setStep] = useState(0);
  const [role, setRole] = useState<Role>("student");
  const [cycle, setCycle] = useState<Cycle>("lycee");
  const [grade, setGrade] = useState<GradeOption>(GRADES_BY_CYCLE.lycee[2]);
  const [year, setYear] = useState<2 | 3>(3);
  const [track, setTrack] = useState<SchoolLevel | null>(null);
  const [exam, setExam] = useState<ExamTarget>("bac");
  const [wilaya, setWilaya] = useState("");
  const [selectedLang, setSelectedLang] = useState<Lang>(lang);
  const [subjects, setSubjects] = useState("");
  const [hourlyRate, setHourlyRate] = useState(1500);
  const [idDoc, setIdDoc] = useState<File | null>(null);
  const [diploma, setDiploma] = useState<File | null>(null);

  const needsTrack = cycle === "lycee" && grade.hasTrack;

  const steps = useMemo<StepId[]>(() => {
    const s: StepId[] = ["role", "cycle", "grade"];
    if (needsTrack) s.push("track");
    s.push("exam", "wilaya", "language");
    if (role === "teacher") s.push("teacher");
    return s;
  }, [needsTrack, role]);

  const current = steps[step];
  const finalSchoolLevel: SchoolLevel = needsTrack ? track ?? grade.schoolLevel : grade.schoolLevel;

  function selectGrade(g: GradeOption) {
    setGrade(g);
    setTrack(null);
    setExam(suggestedExamTarget(g.hasTrack ? (year === 2 ? "lycee_2_sciences" : "lycee_3_sciences") : g.schoolLevel));
  }

  function selectYear(y: 2 | 3) {
    setYear(y);
    const g = GRADES_BY_CYCLE.lycee[y === 2 ? 1 : 2];
    setGrade(g);
    setTrack(null);
    setExam(y === 3 ? "bac" : "none");
  }

  function canAdvance(): boolean {
    if (current === "track") return track !== null;
    return true;
  }

  async function handleFinish() {
    try {
      const result = await submit.mutateAsync({
        userId,
        role,
        schoolLevel: finalSchoolLevel,
        examTarget: exam,
        wilaya,
        language: selectedLang,
        teacher:
          role === "teacher"
            ? {
                subjects: subjects.split(",").map((s) => s.trim()).filter(Boolean),
                hourlyRate,
                idDocFile: idDoc,
                diplomaFile: diploma,
              }
            : undefined,
      });
      setLang(selectedLang);
      navigate({ to: result.redirectTo as "/dashboard" | "/teacher" });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("common.somethingWrong"));
    }
  }

  function next() {
    if (step === steps.length - 1) {
      void handleFinish();
    } else {
      setStep((s) => s + 1);
    }
  }

  return (
    <div className="min-h-screen bg-hero">
      <div className="mx-auto max-w-xl px-4 py-10 sm:py-16">
        <FadeIn>
          <h1 className="font-display text-3xl font-bold tracking-tight">{t("onboarding.welcome")}</h1>
          <p className="mt-2 text-muted-foreground">{t("onboarding.subtitle")}</p>
        </FadeIn>

        <div className="mt-6 flex items-center gap-3">
          <Progress value={((step + 1) / steps.length) * 100} className="flex-1" />
          <span className="shrink-0 text-xs font-medium text-muted-foreground">
            {t("onboarding.stepOf", { current: step + 1, total: steps.length })}
          </span>
        </div>

        <FadeIn key={current} className="mt-8 min-h-[280px]">
          {current === "role" && (
            <RoleStep role={role} onChange={setRole} />
          )}
          {current === "cycle" && (
            <CycleStep
              role={role}
              cycle={cycle}
              onChange={(c) => {
                setCycle(c);
                const g = GRADES_BY_CYCLE[c][0];
                selectGrade(g);
              }}
            />
          )}
          {current === "grade" && (
            <GradeStep
              cycle={cycle}
              grade={grade}
              year={year}
              onSelectGrade={selectGrade}
              onSelectYear={selectYear}
            />
          )}
          {current === "track" && <TrackStep year={year} track={track} onChange={setTrack} />}
          {current === "exam" && <ExamStep exam={exam} onChange={setExam} />}
          {current === "wilaya" && <WilayaStep wilaya={wilaya} onChange={setWilaya} />}
          {current === "language" && <LanguageStep lang={selectedLang} onChange={setSelectedLang} />}
          {current === "teacher" && (
            <TeacherStep
              subjects={subjects}
              onSubjects={setSubjects}
              hourlyRate={hourlyRate}
              onHourlyRate={setHourlyRate}
              idDoc={idDoc}
              onIdDoc={setIdDoc}
              diploma={diploma}
              onDiploma={setDiploma}
            />
          )}
        </FadeIn>

        <div className="mt-8 flex items-center gap-3">
          {step > 0 && (
            <Button variant="outline" onClick={() => setStep((s) => s - 1)} disabled={submit.isPending}>
              {t("common.back")}
            </Button>
          )}
          <Button
            onClick={next}
            disabled={!canAdvance() || submit.isPending}
            className="flex-1"
            size="lg"
          >
            {submit.isPending
              ? t("onboarding.savingProfile")
              : step === steps.length - 1
                ? t("common.finish")
                : t("common.continue")}
          </Button>
        </div>
      </div>
    </div>
  );
}

function OptionCard({
  active,
  onClick,
  icon: Icon,
  label,
  sublabel,
}: {
  active: boolean;
  onClick: () => void;
  icon?: React.ComponentType<{ className?: string }>;
  label: string;
  sublabel?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "hover-lift relative flex flex-col items-start gap-2 rounded-2xl border p-4 text-left transition-colors",
        active ? "border-primary bg-primary/8" : "border-border bg-card hover:bg-secondary/40",
      )}
    >
      {active && (
        <span className="absolute right-3 top-3 grid size-5 place-items-center rounded-full bg-primary text-primary-foreground">
          <Check className="size-3" />
        </span>
      )}
      {Icon && <Icon className="size-5 text-primary" />}
      <div>
        <div className="text-sm font-semibold">{label}</div>
        {sublabel && <div className="text-xs text-muted-foreground">{sublabel}</div>}
      </div>
    </button>
  );
}

function RoleStep({ role, onChange }: { role: Role; onChange: (r: Role) => void }) {
  const t = useT();
  const options: { v: Role; icon: typeof GraduationCap; label: string }[] = [
    { v: "student", icon: GraduationCap, label: t("onboarding.roleStudent") },
    { v: "teacher", icon: Sparkles, label: t("onboarding.roleTeacher") },
    { v: "parent", icon: Users, label: t("onboarding.roleParent") },
  ];
  return (
    <section>
      <Label className="text-base">{t("onboarding.roleQuestion")}</Label>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {options.map((o) => (
          <OptionCard key={o.v} active={role === o.v} onClick={() => onChange(o.v)} icon={o.icon} label={o.label} />
        ))}
      </div>
    </section>
  );
}

function CycleStep({ role, cycle, onChange }: { role: Role; cycle: Cycle; onChange: (c: Cycle) => void }) {
  const t = useT();
  const { lang } = useI18n();
  const question =
    role === "parent"
      ? t("onboarding.cycleQuestionParent")
      : role === "teacher"
        ? t("onboarding.cycleQuestionTeacher")
        : t("onboarding.cycleQuestion");
  return (
    <section>
      <Label className="text-base">{question}</Label>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {CYCLES.map((c) => (
          <OptionCard
            key={c.value}
            active={cycle === c.value}
            onClick={() => onChange(c.value)}
            label={lang === "ar" ? c.label_ar : c.label_fr}
          />
        ))}
      </div>
    </section>
  );
}

function GradeStep({
  cycle,
  grade,
  year,
  onSelectGrade,
  onSelectYear,
}: {
  cycle: Cycle;
  grade: GradeOption;
  year: 2 | 3;
  onSelectGrade: (g: GradeOption) => void;
  onSelectYear: (y: 2 | 3) => void;
}) {
  const t = useT();
  const { lang } = useI18n();
  const grades = GRADES_BY_CYCLE[cycle];

  return (
    <section>
      <Label className="text-base">{t("onboarding.gradeQuestion")}</Label>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {grades.map((g) => {
          const isLyceeYearGrade = cycle === "lycee" && g.hasTrack;
          const active = isLyceeYearGrade ? grade.hasTrack && year === (g === grades[1] ? 2 : 3) : grade.schoolLevel === g.schoolLevel;
          return (
            <OptionCard
              key={g.schoolLevel + g.label_fr}
              active={active}
              onClick={() => (isLyceeYearGrade ? onSelectYear(g === grades[1] ? 2 : 3) : onSelectGrade(g))}
              label={lang === "ar" ? g.label_ar : g.label_fr}
            />
          );
        })}
      </div>
    </section>
  );
}

function TrackStep({
  year,
  track,
  onChange,
}: {
  year: 2 | 3;
  track: SchoolLevel | null;
  onChange: (t: SchoolLevel) => void;
}) {
  const t = useT();
  const { lang } = useI18n();
  const tracks = tracksForYear(year);
  return (
    <section>
      <Label className="text-base">{t("onboarding.trackQuestion")}</Label>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        {tracks.map((tr) => (
          <OptionCard
            key={tr.schoolLevel}
            active={track === tr.schoolLevel}
            onClick={() => onChange(tr.schoolLevel)}
            label={lang === "ar" ? tr.label_ar : tr.label_fr}
          />
        ))}
      </div>
    </section>
  );
}

function ExamStep({ exam, onChange }: { exam: ExamTarget; onChange: (e: ExamTarget) => void }) {
  const t = useT();
  const options: { v: ExamTarget; label: string }[] = [
    { v: "none", label: t("onboarding.examNone") },
    { v: "bem", label: t("onboarding.examBem") },
    { v: "bac", label: t("onboarding.examBac") },
  ];
  return (
    <section>
      <Label className="text-base">{t("onboarding.examQuestion")}</Label>
      <div className="mt-3 flex gap-3">
        {options.map((o) => (
          <OptionCard key={o.v} active={exam === o.v} onClick={() => onChange(o.v)} label={o.label} />
        ))}
      </div>
    </section>
  );
}

function WilayaStep({ wilaya, onChange }: { wilaya: string; onChange: (v: string) => void }) {
  const t = useT();
  return (
    <section>
      <Label htmlFor="wilaya" className="text-base">
        {t("onboarding.wilayaQuestion")}{" "}
        <span className="font-normal text-muted-foreground">({t("common.optional")})</span>
      </Label>
      <Input
        id="wilaya"
        className="mt-3"
        value={wilaya}
        onChange={(e) => onChange(e.target.value)}
        placeholder={t("onboarding.wilayaPlaceholder")}
      />
    </section>
  );
}

function LanguageStep({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  const t = useT();
  return (
    <section>
      <Label className="text-base">{t("onboarding.languageQuestion")}</Label>
      <div className="mt-3 grid grid-cols-2 gap-3">
        <OptionCard active={lang === "fr"} onClick={() => onChange("fr")} label="🇫🇷 Français" />
        <OptionCard active={lang === "ar"} onClick={() => onChange("ar")} label="🇩🇿 العربية" />
      </div>
    </section>
  );
}

function TeacherStep({
  subjects,
  onSubjects,
  hourlyRate,
  onHourlyRate,
  idDoc,
  onIdDoc,
  diploma,
  onDiploma,
}: {
  subjects: string;
  onSubjects: (v: string) => void;
  hourlyRate: number;
  onHourlyRate: (v: number) => void;
  idDoc: File | null;
  onIdDoc: (f: File | null) => void;
  diploma: File | null;
  onDiploma: (f: File | null) => void;
}) {
  const t = useT();
  return (
    <section className="space-y-6">
      <div>
        <Label htmlFor="subjects" className="text-base">
          {t("onboarding.teacherSubjects")}
        </Label>
        <Input
          id="subjects"
          className="mt-3"
          value={subjects}
          onChange={(e) => onSubjects(e.target.value)}
          placeholder={t("onboarding.teacherSubjectsPlaceholder")}
        />
      </div>
      <div>
        <Label htmlFor="rate" className="text-base">
          {t("onboarding.teacherRate")}
        </Label>
        <Input
          id="rate"
          type="number"
          min={0}
          className="mt-3"
          value={hourlyRate}
          onChange={(e) => onHourlyRate(Number(e.target.value))}
        />
      </div>
      <div className="rounded-2xl border border-primary/25 bg-primary/5 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-primary">
          <ShieldCheck className="size-4" /> {t("onboarding.teacherVerification")}
        </div>
        <p className="mt-1 text-xs text-muted-foreground">{t("onboarding.teacherVerificationBody")}</p>
        <div className="mt-3 space-y-2">
          <DocInput label={t("onboarding.teacherIdDoc")} file={idDoc} onChange={onIdDoc} chooseLabel={t("onboarding.chooseFile")} />
          <DocInput label={t("onboarding.teacherDiploma")} file={diploma} onChange={onDiploma} chooseLabel={t("onboarding.chooseFile")} />
        </div>
      </div>
    </section>
  );
}

function DocInput({
  label,
  file,
  onChange,
  chooseLabel,
}: {
  label: string;
  file: File | null;
  onChange: (f: File | null) => void;
  chooseLabel: string;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-3 rounded-xl border border-dashed border-border bg-background px-3 py-2.5 text-sm hover:bg-secondary/40">
      <Upload className="size-4 text-primary" />
      <div className="flex-1">
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="font-medium">{file?.name ?? chooseLabel}</div>
      </div>
      <input
        type="file"
        accept="image/*,application/pdf"
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </label>
  );
}
