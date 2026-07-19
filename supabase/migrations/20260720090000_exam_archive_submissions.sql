-- Additive migration only.
--
-- The "internal solution" to not being able to crawl the ministry's site for
-- annales: turn sourcing into a first-class in-app workflow instead of a
-- one-off scrape. Any authenticated user can submit a candidate annale;
-- it lands as `status = 'pending'` and is invisible to normal browsing until
-- an admin reviews it. Admin-authored entries publish immediately, exactly
-- like before this migration — nothing about the existing 315 rows changes
-- (they all default to 'published').
--
-- `session` (session normale / session de rattrapage) is a real, well-known
-- distinction in the Algerian BEM/BAC and was simply missing before.

ALTER TABLE public.exam_archive
  ADD COLUMN IF NOT EXISTS session text,
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'published';

ALTER TABLE public.exam_archive
  DROP CONSTRAINT IF EXISTS exam_archive_session_check;
ALTER TABLE public.exam_archive
  ADD CONSTRAINT exam_archive_session_check CHECK (session IS NULL OR session IN ('normale', 'rattrapage'));

ALTER TABLE public.exam_archive
  DROP CONSTRAINT IF EXISTS exam_archive_status_check;
ALTER TABLE public.exam_archive
  ADD CONSTRAINT exam_archive_status_check CHECK (status IN ('pending', 'published', 'rejected'));

-- Backfill: rows that predate this column were curated by an admin, so they
-- are already trustworthy — default above already covers new rows, this
-- covers any NULLs from a race with the ADD COLUMN itself.
UPDATE public.exam_archive SET status = 'published' WHERE status IS NULL;

-- A non-admin should never be able to self-publish by passing status
-- directly — force it server-side based on who's inserting.
CREATE OR REPLACE FUNCTION public.enforce_exam_archive_submission_status()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF public.has_role(auth.uid(), 'admin') THEN
    NEW.status := COALESCE(NEW.status, 'published');
  ELSE
    NEW.status := 'pending';
  END IF;
  NEW.uploaded_by := auth.uid();
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_exam_archive_submission_status ON public.exam_archive;
CREATE TRIGGER trg_exam_archive_submission_status
  BEFORE INSERT ON public.exam_archive
  FOR EACH ROW EXECUTE FUNCTION public.enforce_exam_archive_submission_status();

-- Public read: published only. Admins keep full visibility via the existing
-- "Admins manage exam_archive" ALL policy, so this SELECT policy only needs
-- to add the "everyone can read what's published" case.
DROP POLICY IF EXISTS "exam_archive public read" ON public.exam_archive;
CREATE POLICY "exam_archive public read published" ON public.exam_archive
  FOR SELECT USING (status = 'published' OR public.has_role(auth.uid(), 'admin'));

-- Any authenticated user may submit a candidate annale; the trigger above
-- makes sure it always lands as 'pending' unless they're an admin. Additive
-- alongside the existing "exam_archive admin insert" policy (RLS policies
-- for the same command are OR'd together).
DROP POLICY IF EXISTS "exam_archive authenticated submit" ON public.exam_archive;
CREATE POLICY "exam_archive authenticated submit" ON public.exam_archive
  FOR INSERT TO authenticated WITH CHECK (true);

-- Storage: let any authenticated user upload a candidate file. Visibility of
-- the *table row* pointing at it is what actually gates exposure, exactly
-- like the pending/published split above.
DROP POLICY IF EXISTS "exam-archive authenticated insert" ON storage.objects;
CREATE POLICY "exam-archive authenticated insert" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'exam-archive');
