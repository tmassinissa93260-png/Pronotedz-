-- Additive migration only.
--
-- `gamification` tracked badges and chapters_completed but never an actual
-- point total — the Phase 1 dashboard was deriving a fake XP number from
-- array lengths. This adds the real column and a SECURITY DEFINER RPC so
-- concurrent awards (two tabs, a fast double-click) can't race each other
-- with a client-side read-modify-write.

ALTER TABLE public.gamification
  ADD COLUMN IF NOT EXISTS xp integer NOT NULL DEFAULT 0;

CREATE OR REPLACE FUNCTION public.award_xp(_user uuid, _amount int)
RETURNS int
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  _new_xp int;
BEGIN
  IF _user <> auth.uid() THEN
    RAISE EXCEPTION 'Non autorisé';
  END IF;
  IF _amount <= 0 OR _amount > 200 THEN
    RAISE EXCEPTION 'Montant XP invalide';
  END IF;
  INSERT INTO public.gamification (student_id, xp)
    VALUES (_user, _amount)
    ON CONFLICT (student_id) DO UPDATE SET xp = public.gamification.xp + _amount, updated_at = now()
    RETURNING xp INTO _new_xp;
  RETURN _new_xp;
END;
$$;

GRANT EXECUTE ON FUNCTION public.award_xp(uuid, int) TO authenticated;

-- One-time: give existing accounts a fair starting XP total reflecting what
-- they'd already earned under the old derived formula, instead of resetting
-- everyone to 0.
UPDATE public.gamification
SET xp = COALESCE(jsonb_array_length(chapters_completed), 0) * 10 + COALESCE(jsonb_array_length(badges), 0) * 25
WHERE xp = 0;
