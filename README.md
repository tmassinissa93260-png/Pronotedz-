# Estadi

Plateforme de soutien scolaire algérienne (BEM/BAC) — cours en ligne, tuteur IA,
profs en direct, communauté. Réécriture complète : React + TypeScript + Vite,
TanStack Router, Supabase, Tailwind v4 + shadcn/ui, Framer Motion.

Le projet se branche sur le **même projet Supabase de production** que
l'ancienne app (mêmes tables, mêmes données : 1164 chapitres, 315 annales,
utilisateurs réels). Le schéma existant est la source de vérité — toute
migration future doit être additive.

## Démarrer

```bash
npm install
cp .env.example .env   # renseigne VITE_SUPABASE_URL / VITE_SUPABASE_PUBLISHABLE_KEY
npm run dev            # http://localhost:8080
```

## Scripts

- `npm run dev` — serveur de dev
- `npm run build` — type-check (`tsc -b`) puis build de production
- `npm run lint` — ESLint
- `npm test` — tests unitaires (Vitest)

## Structure

```
src/
  routes/              # TanStack Router (file-based), routeTree.gen.ts auto-généré
  components/
    ui/                # primitives shadcn/ui (Radix + Tailwind)
    layout/             # sidebar, header, tab bar mobile, shell authentifié
    motion/             # wrappers Framer Motion (FadeIn, Stagger, PageTransition)
    onboarding/         # wizard d'onboarding
  lib/
    supabase/           # client + types générés (schéma prod)
    i18n/               # dictionnaires FR/AR typés + provider RTL
    curriculum/         # mapping cycle/niveau/filière ↔ enum school_level (prod)
    auth/                # actions Supabase Auth
    onboarding/          # logique de soumission (écrit dans le schéma existant)
    queries/              # options TanStack Query (profil, dashboard)
  hooks/                # hooks réutilisables (session, current user, dashboard…)
```

## Phase 1 — ce qui est livré

Socle : design system, auth, onboarding, layout/navigation. Voir le résumé
donné en fin de session pour le détail et comment tester chaque écran.
