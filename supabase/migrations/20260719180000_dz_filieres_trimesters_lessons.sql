-- Additive migration only. Nothing here drops, renames, or narrows an existing
-- column/type/policy — it only extends what's already in production.
--
-- 1) Two Algerian curriculum gaps found by research (see chat for sources):
--    - "Arts" is a real 7th BAC filière (théâtre / cinéma / arts plastiques /
--      musique), introduced 2022-2023, first session 2024. Not previously
--      represented in `school_level`.
--    - 1AS ("tronc commun") actually splits into "tronc commun sciences" and
--      "tronc commun lettres" — previously collapsed into one generic
--      `lycee_1_tc` value. That value is kept (existing rows keep working);
--      the two more precise values are additive siblings.
--
-- Enum additions must not run in the same transaction as statements that use
-- the new values, so this file does nothing else.

ALTER TYPE public.school_level ADD VALUE IF NOT EXISTS 'lycee_2_arts';
ALTER TYPE public.school_level ADD VALUE IF NOT EXISTS 'lycee_3_arts';
ALTER TYPE public.school_level ADD VALUE IF NOT EXISTS 'lycee_1_tc_sciences';
ALTER TYPE public.school_level ADD VALUE IF NOT EXISTS 'lycee_1_tc_lettres';
