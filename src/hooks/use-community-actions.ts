import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createThread, createPost, toggleLike, reportContent } from "@/lib/community/actions";

export function useCreateThread(authorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ title, body, subject, level }: { title: string; body: string; subject: string; level: string }) =>
      createThread(authorId, title, body, subject, level),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["community", "threads"] }),
  });
}

export function useCreatePost(threadId: string, authorId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => createPost(threadId, authorId, body),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["community", "posts", threadId] });
      queryClient.invalidateQueries({ queryKey: ["community", "thread", threadId] });
    },
  });
}

export function useToggleLike(threadId: string, userId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ postId, currentlyLiked }: { postId: string; currentlyLiked: boolean }) =>
      toggleLike(postId, userId, currentlyLiked),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["community", "posts", threadId] });
      queryClient.invalidateQueries({ queryKey: ["community", "my-likes"] });
    },
  });
}

export function useReportContent(reporterId: string) {
  return useMutation({
    mutationFn: ({ targetType, targetId, reason }: { targetType: "thread" | "post"; targetId: string; reason: string }) =>
      reportContent(reporterId, targetType, targetId, reason),
  });
}
