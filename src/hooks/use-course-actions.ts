import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  createCourse,
  setCourseStatus,
  addCourseVideo,
  deleteCourseVideo,
  enrollInCourse,
  type CreateCoursePayload,
  type AddVideoPayload,
} from "@/lib/courses/actions";

export function useCreateCourse(teacherId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<CreateCoursePayload, "teacherId">) => createCourse({ ...payload, teacherId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["courses", "teacher", teacherId] });
    },
  });
}

export function useSetCourseStatus(teacherId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ courseId, status }: { courseId: string; status: "draft" | "published" | "archived" }) =>
      setCourseStatus(courseId, status),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["courses", "teacher", teacherId] });
      queryClient.invalidateQueries({ queryKey: ["courses", "published"] });
    },
  });
}

export function useAddCourseVideo(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: Omit<AddVideoPayload, "courseId">) => addCourseVideo({ ...payload, courseId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["courses", "videos", courseId] });
    },
  });
}

export function useDeleteCourseVideo(courseId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (videoId: string) => deleteCourseVideo(videoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["courses", "videos", courseId] });
    },
  });
}

export function useEnrollInCourse(courseId: string, studentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => enrollInCourse(courseId, studentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["courses", "my-enrollment", courseId, studentId] });
      queryClient.invalidateQueries({ queryKey: ["courses", "detail", courseId] });
    },
  });
}
