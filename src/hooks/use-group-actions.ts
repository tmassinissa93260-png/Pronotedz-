import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createGroup,
  joinGroupByCode,
  leaveGroup,
  sendGroupMessage,
  createGroupEvent,
  deleteGroupEvent,
  uploadGroupResource,
  deleteGroupResource,
  startPomodoro,
  createGroupExamAlert,
  deleteGroupExamAlert,
  type CreateGroupPayload,
} from "@/lib/groups/actions";

export function useCreateGroup(ownerId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<CreateGroupPayload, "ownerId">) => createGroup({ ...payload, ownerId }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "mine", ownerId] }),
  });
}

export function useJoinGroupByCode(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (code: string) => joinGroupByCode(code),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "mine", userId] }),
  });
}

export function useLeaveGroup(userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (groupId: string) => leaveGroup(groupId, userId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups"] }),
  });
}

export function useSendGroupMessage(groupId: string, authorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => sendGroupMessage(groupId, authorId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "messages", groupId] }),
  });
}

export function useCreateGroupEvent(groupId: string, createdBy: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ title, description, eventAt }: { title: string; description: string | null; eventAt: Date }) =>
      createGroupEvent(groupId, createdBy, title, description, eventAt),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "events", groupId] }),
  });
}

export function useDeleteGroupEvent(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (eventId: string) => deleteGroupEvent(eventId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "events", groupId] }),
  });
}

export function useUploadGroupResource(groupId: string, uploaderId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, title }: { file: File; title: string }) => uploadGroupResource(groupId, uploaderId, file, title),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "resources", groupId] }),
  });
}

export function useDeleteGroupResource(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, path }: { id: string; path: string }) => deleteGroupResource(id, path),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "resources", groupId] }),
  });
}

export function useStartPomodoro(groupId: string, startedBy: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { phase: "focus" | "break"; durationMin: number }) =>
      startPomodoro(groupId, startedBy, input.phase, input.durationMin),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "pomodoro", groupId] }),
  });
}

export function useCreateGroupExamAlert(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createGroupExamAlert,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "exam-alerts", groupId] }),
  });
}

export function useDeleteGroupExamAlert(groupId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteGroupExamAlert(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["groups", "exam-alerts", groupId] }),
  });
}
