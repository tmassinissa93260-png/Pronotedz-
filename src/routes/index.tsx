import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { ArrowRight, Sparkles, Video, Library, Users } from "lucide-react";
import { supabase } from "@/lib/supabase/client";
import { Button } from "@/components/ui/button";
import { FadeIn } from "@/components/motion/fade-in";
import { StaggerGroup, StaggerItem } from "@/components/motion/stagger";
import { LanguageSwitcher } from "@/components/language-switcher";
import { ThemeToggle } from "@/components/theme-toggle";
import { useT } from "@/lib/i18n";

export const Route = createFileRoute("/")({
  component: Landing,
});

const FEATURES = [
  {
    icon: Sparkles,
    title: "Tuteur IA 24/7",
    body: "Explications chapitre par chapitre, exercices corrigés et fiches de révision générées sur ton programme.",
  },
  {
    icon: Library,
    title: "Programme officiel",
    body: "Toute la bibliothèque BEM et BAC : cours, résumés, flashcards, quiz et exercices par matière.",
  },
  {
    icon: Video,
    title: "Profs en direct",
    body: "Réserve une session 1-à-1 en visio avec un professeur vérifié, sur le créneau qui t'arrange.",
  },
  {
    icon: Users,
    title: "Communauté & groupes",
    body: "Rejoins des groupes d'étude, pose tes questions et progresse avec d'autres élèves algériens.",
  },
];

function Landing() {
  const navigate = useNavigate();
  const t = useT();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) navigate({ to: "/dashboard" });
    });
  }, [navigate]);

  return (
    <div className="min-h-screen bg-hero">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-4 py-5 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-emerald-gradient font-display text-lg font-bold text-primary-foreground shadow-glow">
            أ
          </div>
          <span className="font-display text-lg font-bold tracking-tight">{t("common.appName")}</span>
        </div>
        <div className="flex items-center gap-1 sm:gap-1.5">
          <LanguageSwitcher compact />
          <ThemeToggle />
          <Button variant="ghost" asChild className="hidden sm:inline-flex">
            <Link to="/auth" search={{ mode: "signin" }}>
              {t("auth.signIn")}
            </Link>
          </Button>
          <Button asChild size="sm" className="sm:h-10 sm:px-4 sm:text-sm">
            <Link to="/auth" search={{ mode: "signup" }}>
              {t("auth.signUp")}
            </Link>
          </Button>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 pb-24 pt-12 sm:pt-20">
        <FadeIn className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-primary/25 bg-primary/10 px-3.5 py-1.5 text-xs font-semibold text-primary">
            <Sparkles className="size-3.5" /> Aligné sur le programme algérien BEM · BAC
          </span>
          <h1 className="mt-6 font-display text-4xl font-extrabold tracking-tight sm:text-6xl">
            Réussis ton année avec un{" "}
            <span className="bg-emerald-gradient bg-clip-text text-transparent">
              compagnon scolaire
            </span>{" "}
            qui s'adapte à toi.
          </h1>
          <p className="mx-auto mt-5 max-w-xl text-balance text-base text-muted-foreground sm:text-lg">
            Cours, tuteur IA, profs en direct et communauté — tout pour préparer ton BEM ou ton BAC,
            en français ou en arabe.
          </p>
          <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
            <Button size="lg" asChild>
              <Link to="/auth" search={{ mode: "signup" }}>
                Commencer gratuitement <ArrowRight className="size-4" />
              </Link>
            </Button>
            <Button size="lg" variant="outline" asChild>
              <Link to="/auth" search={{ mode: "signin" }}>
                J'ai déjà un compte
              </Link>
            </Button>
          </div>
        </FadeIn>

        <StaggerGroup className="mx-auto mt-20 grid max-w-5xl gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {FEATURES.map((f) => (
            <StaggerItem
              key={f.title}
              className="hover-lift rounded-2xl border border-border bg-card/70 p-5 backdrop-blur-xl"
            >
              <div className="grid size-10 place-items-center rounded-xl bg-primary/10 text-primary">
                <f.icon className="size-5" />
              </div>
              <h3 className="mt-4 font-display text-sm font-semibold">{f.title}</h3>
              <p className="mt-1.5 text-sm text-muted-foreground">{f.body}</p>
            </StaggerItem>
          ))}
        </StaggerGroup>
      </main>
    </div>
  );
}
