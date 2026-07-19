import { queryOptions } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase/client";
import type { Database } from "@/lib/supabase/types";

export type CommunityThread = Database["public"]["Tables"]["community_threads"]["Row"];
export type CommunityPost = Database["public"]["Tables"]["community_posts"]["Row"];
export type Profile = Database["public"]["Tables"]["profiles"]["Row"];

export type ThreadWithAuthor = CommunityThread & { author: Pick<Profile, "full_name" | "avatar_url"> | null };

async function fetchThreads(subjectFilter: string): Promise<ThreadWithAuthor[]> {
  let query = supabase
    .from("community_threads")
    .select("*, author:profiles(full_name, avatar_url)")
    .order("last_post_at", { ascending: false })
    .limit(50);
  if (subjectFilter.trim()) query = query.ilike("subject", `%${subjectFilter.trim()}%`);
  const { data, error } = await query;
  if (error) throw error;
  return (data ?? []) as unknown as ThreadWithAuthor[];
}

export function threadsQueryOptions(subjectFilter: string) {
  return queryOptions({
    queryKey: ["community", "threads", subjectFilter],
    queryFn: () => fetchThreads(subjectFilter),
    staleTime: 30_000,
  });
}

async function fetchThread(threadId: string): Promise<ThreadWithAuthor | null> {
  const { data, error } = await supabase
    .from("community_threads")
    .select("*, author:profiles(full_name, avatar_url)")
    .eq("id", threadId)
    .maybeSingle();
  if (error) throw error;
  return data as unknown as ThreadWithAuthor | null;
}

export function threadQueryOptions(threadId: string) {
  return queryOptions({
    queryKey: ["community", "thread", threadId],
    queryFn: () => fetchThread(threadId),
    staleTime: 15_000,
  });
}

export type PostWithAuthor = CommunityPost & { author: Pick<Profile, "full_name" | "avatar_url"> | null };

async function fetchPosts(threadId: string): Promise<PostWithAuthor[]> {
  const { data, error } = await supabase
    .from("community_posts")
    .select("*, author:profiles(full_name, avatar_url)")
    .eq("thread_id", threadId)
    .order("created_at");
  if (error) throw error;
  return (data ?? []) as unknown as PostWithAuthor[];
}

export function postsQueryOptions(threadId: string) {
  return queryOptions({
    queryKey: ["community", "posts", threadId],
    queryFn: () => fetchPosts(threadId),
    staleTime: 15_000,
  });
}

async function fetchMyLikes(postIds: string[], userId: string): Promise<Set<string>> {
  if (!postIds.length) return new Set();
  const { data, error } = await supabase
    .from("community_post_likes")
    .select("post_id")
    .eq("user_id", userId)
    .in("post_id", postIds);
  if (error) throw error;
  return new Set((data ?? []).map((l) => l.post_id));
}

export function myLikesQueryOptions(postIds: string[], userId: string | undefined) {
  return queryOptions({
    queryKey: ["community", "my-likes", postIds, userId],
    queryFn: () => fetchMyLikes(postIds, userId as string),
    enabled: Boolean(userId) && postIds.length > 0,
    staleTime: 15_000,
  });
}
