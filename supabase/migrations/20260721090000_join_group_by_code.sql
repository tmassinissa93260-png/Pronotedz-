-- Additive migration only.
--
-- Joining a study group by invite code needs to look the group up by code
-- *before* the caller is a member — which "Members see their groups" (SELECT
-- USING is_group_member OR owner_id = self) deliberately never allows for a
-- stranger. A SECURITY DEFINER RPC is the standard escape hatch for exactly
-- this, same pattern as is_group_member/is_group_owner already in this schema.

CREATE OR REPLACE FUNCTION public.join_group_by_code(_code text)
RETURNS TABLE(group_id uuid, group_name text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS $$
DECLARE
  _group record;
  _member_count int;
BEGIN
  SELECT id, name, max_members INTO _group
  FROM public.study_groups
  WHERE upper(invite_code) = upper(_code);

  IF _group.id IS NULL THEN
    RAISE EXCEPTION 'Code invalide';
  END IF;

  IF EXISTS(SELECT 1 FROM public.group_members WHERE group_members.group_id = _group.id AND user_id = auth.uid()) THEN
    RETURN QUERY SELECT _group.id, _group.name;
    RETURN;
  END IF;

  SELECT count(*) INTO _member_count FROM public.group_members WHERE group_members.group_id = _group.id;
  IF _member_count >= _group.max_members THEN
    RAISE EXCEPTION 'Ce groupe est complet';
  END IF;

  INSERT INTO public.group_members (group_id, user_id) VALUES (_group.id, auth.uid());
  RETURN QUERY SELECT _group.id, _group.name;
END;
$$;

GRANT EXECUTE ON FUNCTION public.join_group_by_code(text) TO authenticated;
