import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

type SchoolLevel = Database["public"]["Enums"]["school_level"];
type SessionType = Database["public"]["Enums"]["session_type"];

export type CreateSlotPayload = {
  teacherId: string;
  title: string | null;
  subject: string;
  level: SchoolLevel;
  scheduledAt: Date;
  durationMin: number;
  sessionType: SessionType;
  maxStudents: number;
  pricePerStudent: number;
};

export async function createSessionSlot(payload: CreateSlotPayload): Promise<{ id: string }> {
  if (payload.scheduledAt.getTime() < Date.now()) {
    throw new Error("Choisis une date future.");
  }
  const maxStudents = payload.sessionType === "solo" ? 1 : payload.maxStudents;
  const { data, error } = await supabase
    .from("live_sessions")
    .insert({
      teacher_id: payload.teacherId,
      title: payload.title,
      subject: payload.subject,
      level: payload.level,
      scheduled_at: payload.scheduledAt.toISOString(),
      duration_min: payload.durationMin,
      session_type: payload.sessionType,
      max_students: maxStudents,
      price_per_student: payload.pricePerStudent,
      status: "scheduled",
    })
    .select("id")
    .single();
  if (error) throw error;
  return { id: data.id };
}

export async function bookSession(sessionId: string, studentId: string): Promise<{ alreadyBooked: boolean }> {
  const { data: session, error: sessionError } = await supabase
    .from("live_sessions")
    .select("id, max_students, session_type, scheduled_at, status")
    .eq("id", sessionId)
    .maybeSingle();
  if (sessionError) throw sessionError;
  if (!session) throw new Error("Session introuvable.");
  if (session.status === "cancelled" || session.status === "completed") {
    throw new Error("Cette session n'est plus disponible.");
  }
  if (new Date(session.scheduled_at).getTime() < Date.now()) {
    throw new Error("Ce créneau est déjà passé.");
  }

  const { count } = await supabase
    .from("session_bookings")
    .select("id", { count: "exact", head: true })
    .eq("session_id", sessionId)
    .in("status", ["booked", "attended"]);
  if ((count ?? 0) >= session.max_students) {
    throw new Error("Cette session est complète.");
  }

  const { data: existing } = await supabase
    .from("session_bookings")
    .select("id, status")
    .eq("session_id", sessionId)
    .eq("student_id", studentId)
    .maybeSingle();
  if (existing && existing.status !== "cancelled") {
    return { alreadyBooked: true };
  }

  const mode = session.session_type === "group" ? "group" : "solo";
  const { error } = existing
    ? await supabase.from("session_bookings").update({ status: "booked", mode }).eq("id", existing.id)
    : await supabase.from("session_bookings").insert({ session_id: sessionId, student_id: studentId, status: "booked", mode });
  if (error) throw error;
  return { alreadyBooked: false };
}

export async function cancelBooking(bookingId: string): Promise<void> {
  const { error } = await supabase.from("session_bookings").update({ status: "cancelled" }).eq("id", bookingId);
  if (error) throw error;
}

export type AvailabilitySlot = {
  id?: string;
  teacherId: string;
  dayOfWeek: number;
  startTime: string;
  endTime: string;
  recurring: boolean;
};

export async function upsertAvailability(slot: AvailabilitySlot): Promise<void> {
  if (slot.startTime >= slot.endTime) throw new Error("L'heure de fin doit être après l'heure de début.");
  const { error } = await supabase.from("teacher_availability").insert({
    teacher_id: slot.teacherId,
    day_of_week: slot.dayOfWeek,
    start_time: slot.startTime,
    end_time: slot.endTime,
    recurring: slot.recurring,
  });
  if (error) throw error;
}

export async function deleteAvailability(id: string): Promise<void> {
  const { error } = await supabase.from("teacher_availability").delete().eq("id", id);
  if (error) throw error;
}
