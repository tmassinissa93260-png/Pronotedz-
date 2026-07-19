-- Additive migration only.
--
-- teacher_profiles already lets admins update verification_status (tp3), but
-- the teacher-docs storage bucket only ever let the owning teacher read their
-- own uploaded ID/diploma ("teacher-docs owner all") — there was no way for
-- an admin to actually look at the documents before approving anyone. That
-- meant no teacher could ever reach 'verified' through a real review. This
-- adds the missing read path, admin-only, alongside the existing owner policy.

CREATE POLICY "teacher-docs admin read" ON storage.objects FOR SELECT TO authenticated
  USING (bucket_id = 'teacher-docs' AND public.has_role(auth.uid(), 'admin'));
