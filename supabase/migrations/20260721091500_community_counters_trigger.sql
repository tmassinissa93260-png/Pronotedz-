-- Additive migration only.
--
-- Same gap as courses.enrolled_count: community_threads.posts_count/
-- last_post_at and community_posts.likes_count existed but nothing kept them
-- in sync. Triggers now do, with a one-time backfill.

CREATE OR REPLACE FUNCTION public.sync_thread_post_counters()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE public.community_threads
    SET posts_count = posts_count + 1, last_post_at = NEW.created_at
    WHERE id = NEW.thread_id;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE public.community_threads SET posts_count = GREATEST(0, posts_count - 1) WHERE id = OLD.thread_id;
  END IF;
  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_community_posts_counters ON public.community_posts;
CREATE TRIGGER trg_community_posts_counters
  AFTER INSERT OR DELETE ON public.community_posts
  FOR EACH ROW EXECUTE FUNCTION public.sync_thread_post_counters();

CREATE OR REPLACE FUNCTION public.sync_post_like_counter()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE public.community_posts SET likes_count = likes_count + 1 WHERE id = NEW.post_id;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE public.community_posts SET likes_count = GREATEST(0, likes_count - 1) WHERE id = OLD.post_id;
  END IF;
  RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS trg_community_post_likes_counter ON public.community_post_likes;
CREATE TRIGGER trg_community_post_likes_counter
  AFTER INSERT OR DELETE ON public.community_post_likes
  FOR EACH ROW EXECUTE FUNCTION public.sync_post_like_counter();

UPDATE public.community_threads t
SET posts_count = COALESCE(c.n, 0), last_post_at = COALESCE(c.last_at, t.created_at)
FROM (
  SELECT thread_id, COUNT(*) AS n, MAX(created_at) AS last_at FROM public.community_posts GROUP BY thread_id
) c
WHERE c.thread_id = t.id AND t.posts_count IS DISTINCT FROM c.n;

UPDATE public.community_posts p
SET likes_count = COALESCE(c.n, 0)
FROM (
  SELECT post_id, COUNT(*) AS n FROM public.community_post_likes GROUP BY post_id
) c
WHERE c.post_id = p.id AND p.likes_count IS DISTINCT FROM c.n;
