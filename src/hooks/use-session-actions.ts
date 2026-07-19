import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createSessionSlot,
  bookSession,
  cancelBooking,
  upsertAvailability,
  deleteAvailability,
  type CreateSlotPayload,
  type AvailabilitySlot,
} from "@/lib/sessions/actions";

export function useCreateSessionSlot(teacherId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<CreateSlotPayload, "teacherId">) => createSessionSlot({ ...payload, teacherId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teachers", "open-slots", teacherId] });
      queryClient.invalidateQueries({ queryKey: ["sessions", "teacher-schedule", teacherId] });
    },
  });
}

export function useBookSession(sessionId: string, studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => bookSession(sessionId, studentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions", "my-booked-ids", studentId] });
      queryClient.invalidateQueries({ queryKey: ["teachers", "open-slots"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", studentId] });
    },
  });
}

export function useCancelBooking() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (bookingId: string) => cancelBooking(bookingId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}

export function useUpsertAvailability(teacherId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (slot: Omit<AvailabilitySlot, "teacherId">) => upsertAvailability({ ...slot, teacherId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teachers", "availability", teacherId] });
    },
  });
}

export function useDeleteAvailability(teacherId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteAvailability(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["teachers", "availability", teacherId] });
    },
  });
}
