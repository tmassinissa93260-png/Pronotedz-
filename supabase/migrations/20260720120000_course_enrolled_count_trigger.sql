-- Additive migration only.
--
-- `courses.enrolled_count` already existed but nothing kept it in sync —
-- new enrollments never incremented it. Backfills existing counts once,
-- then keeps them correct going forward.

CREATE OR REPLACE FUNCTION public.sync_course_enrolled_count()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE public.courses SET enrolled_count = enrolled_count + 1 WHERE id = NEW.course_id;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE public.courses SET enrolled_count = GREATEST(0, enrolled_count - 1) WHERE id = OLD.course_id;
  END IF;
  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_course_enrollments_count ON public.course_enrollments;
CREATE TRIGGER trg_course_enrollments_count
  AFTER INSERT OR DELETE ON public.course_enrollments
  FOR EACH ROW EXECUTE FUNCTION public.sync_course_enrolled_count();

UPDATE public.courses c
SET enrolled_count = COALESCE(counts.n, 0)
FROM (
  SELECT course_id, COUNT(*) AS n FROM public.course_enrollments GROUP BY course_id
) counts
WHERE counts.course_id = c.id AND c.enrolled_count IS DISTINCT FROM counts.n;
