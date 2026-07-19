-- Additive migration only.
--
-- Phase 6 (task planner, group pomodoro, group AI quiz, real payments, push
-- notifications) uses six tables that already exist in the schema but have
-- no application code touching them yet, so their RLS policies were never
-- exercised or written from this rewrite's side: student_tasks,
-- task_reminder_log, group_pomodoro_sessions, group_exam_alerts, payments,
-- push_subscriptions, teacher_earnings. This adds owner/group-member scoped
-- policies following the exact patterns already used elsewhere in this
-- schema (is_group_member, has_role). Policy names are distinct from
-- anything used before, so this is safe to apply even if some of these
-- tables already carry other policies.

ALTER TABLE public.student_tasks ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.task_reminder_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_pomodoro_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.group_exam_alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.push_subscriptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.teacher_earnings ENABLE ROW LEVEL SECURITY;

-- student_tasks: the student owns their planner; a task can optionally be
-- shared read-only with their study group.
CREATE POLICY "student_tasks owner all" ON public.student_tasks FOR ALL TO authenticated
  USING (student_id = auth.uid()) WITH CHECK (student_id = auth.uid());
CREATE POLICY "student_tasks group shared read" ON public.student_tasks FOR SELECT TO authenticated
  USING (share_with_group AND group_id IS NOT NULL AND public.is_group_member(group_id, auth.uid()));

-- task_reminder_log: written only by the reminder edge function (service
-- role, bypasses RLS); students can read their own log.
CREATE POLICY "task_reminder_log owner read" ON public.task_reminder_log FOR SELECT TO authenticated
  USING (student_id = auth.uid());

-- group_pomodoro_sessions: any member can see/start/advance the group's
-- synced timer.
CREATE POLICY "group_pomodoro select members" ON public.group_pomodoro_sessions FOR SELECT TO authenticated
  USING (public.is_group_member(group_id, auth.uid()));
CREATE POLICY "group_pomodoro insert members" ON public.group_pomodoro_sessions FOR INSERT TO authenticated
  WITH CHECK (public.is_group_member(group_id, auth.uid()) AND started_by = auth.uid());
CREATE POLICY "group_pomodoro update members" ON public.group_pomodoro_sessions FOR UPDATE TO authenticated
  USING (public.is_group_member(group_id, auth.uid())) WITH CHECK (public.is_group_member(group_id, auth.uid()));

-- group_exam_alerts: any member can see them; creating one requires
-- membership and self-attribution; only the creator or the group owner can
-- remove one.
CREATE POLICY "group_exam_alerts select members" ON public.group_exam_alerts FOR SELECT TO authenticated
  USING (public.is_group_member(group_id, auth.uid()));
CREATE POLICY "group_exam_alerts insert members" ON public.group_exam_alerts FOR INSERT TO authenticated
  WITH CHECK (public.is_group_member(group_id, auth.uid()) AND created_by = auth.uid());
CREATE POLICY "group_exam_alerts delete creator" ON public.group_exam_alerts FOR DELETE TO authenticated
  USING (created_by = auth.uid() OR public.is_group_owner(group_id, auth.uid()));

-- payments: rows are created and transitioned exclusively by the checkout
-- and webhook edge functions (service role); the buyer only needs to read
-- their own payment history/status from the client.
CREATE POLICY "payments select own" ON public.payments FOR SELECT TO authenticated
  USING (user_id = auth.uid());

-- push_subscriptions: a user manages their own device registrations.
CREATE POLICY "push_subscriptions owner all" ON public.push_subscriptions FOR ALL TO authenticated
  USING (user_id = auth.uid()) WITH CHECK (user_id = auth.uid());

-- teacher_earnings: a teacher reads their own earnings; rows are created by
-- the payment webhook (service role).
CREATE POLICY "teacher_earnings select own" ON public.teacher_earnings FOR SELECT TO authenticated
  USING (teacher_id = auth.uid());
