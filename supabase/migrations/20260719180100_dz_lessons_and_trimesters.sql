-- Additive migration only.
--
-- 2) Trimester on chapters: the official Algerian programmes are published
--    per trimestre (1/2/3), and the library navigation the product now needs
--    is cycle -> niveau -> trimestre -> chapitre -> leçon. `trimester` is
--    nullable so none of the existing 1164 `edu_chapters` rows are touched;
--    they simply show as "non classé" until curated.
--
-- 3) `edu_lessons`: each chapter is broken down into leçons. Content is
--    generated on demand (never in bulk — cost discipline from the product
--    brief) by the `curriculum-ai` edge function and cached here:
--      lesson_content -> the AI's explanation of the leçon
--      exercises      -> array of { question, correction, difficulty }
--      sujet          -> a single exam-style question with its correction
--    Same public-read / admin-write RLS shape as edu_chapters. Direct writes
--    are admin-only; the edge function writes with the service role.

ALTER TABLE public.edu_chapters
  ADD COLUMN IF NOT EXISTS trimester smallint;

ALTER TABLE public.edu_chapters
  DROP CONSTRAINT IF EXISTS edu_chapters_trimester_check;
ALTER TABLE public.edu_chapters
  ADD CONSTRAINT edu_chapters_trimester_check CHECK (trimester IS NULL OR trimester IN (1, 2, 3));

CREATE TABLE IF NOT EXISTS public.edu_lessons (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chapter_id uuid NOT NULL REFERENCES public.edu_chapters(id) ON DELETE CASCADE,
  title_fr text NOT NULL,
  title_ar text NOT NULL,
  order_index int NOT NULL DEFAULT 0,
  lesson_content jsonb,
  exercises jsonb,
  sujet jsonb,
  ai_generated_at timestamptz,
  ai_model text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

GRANT SELECT ON public.edu_lessons TO anon, authenticated;
GRANT ALL ON public.edu_lessons TO service_role;
ALTER TABLE public.edu_lessons ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Public read edu_lessons" ON public.edu_lessons;
CREATE POLICY "Public read edu_lessons" ON public.edu_lessons FOR SELECT USING (true);

DROP POLICY IF EXISTS "Admins manage edu_lessons" ON public.edu_lessons;
CREATE POLICY "Admins manage edu_lessons" ON public.edu_lessons FOR ALL
  USING (public.has_role(auth.uid(), 'admin')) WITH CHECK (public.has_role(auth.uid(), 'admin'));

CREATE TRIGGER trg_edu_lessons_updated
  BEFORE UPDATE ON public.edu_lessons
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

CREATE INDEX IF NOT EXISTS idx_edu_lessons_chapter ON public.edu_lessons(chapter_id, order_index);
CREATE INDEX IF NOT EXISTS idx_edu_chapters_trimester ON public.edu_chapters(subject_id, trimester, order_index);
