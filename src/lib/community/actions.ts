import { supabase } from "@/lib/supabase/client";

export async function createThread(authorId: string, title: string, body: string, subject: string, level: string): Promise<{ id: string }> {
  const { data, error } = await supabase
    .from("community_threads")
    .insert({ author_id: authorId, title: title.trim(), body: body.trim(), subject: subject.trim(), level: level.trim() })
    .select("id")
    .single();
  if (error) throw error;
  return { id: data.id };
}

export async function createPost(threadId: string, authorId: string, body: string): Promise<void> {
  const { error } = await supabase.from("community_posts").insert({ thread_id: threadId, author_id: authorId, body: body.trim() });
  if (error) throw error;
}

export async function toggleLike(postId: string, userId: string, currentlyLiked: boolean): Promise<void> {
  if (currentlyLiked) {
    const { error } = await supabase.from("community_post_likes").delete().eq("post_id", postId).eq("user_id", userId);
    if (error) throw error;
  } else {
    const { error } = await supabase.from("community_post_likes").insert({ post_id: postId, user_id: userId });
    if (error) throw error;
  }
}

export async function reportContent(reporterId: string, targetType: "thread" | "post", targetId: string, reason: string): Promise<void> {
  const { error } = await supabase
    .from("post_reports")
    .insert({ reporter_id: reporterId, target_type: targetType, target_id: targetId, reason: reason.trim() });
  if (error) throw error;
}
