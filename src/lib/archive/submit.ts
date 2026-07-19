import { supabase } from "@/lib/supabase/client";
import type { ExamType } from "@/lib/queries/archive";

export type SubmitArchivePayload = {
  examType: ExamType;
  year: number;
  subject: string;
  filiere: string | null;
  session: "normale" | "rattrapage" | null;
  title: string;
  pdfFile: File;
  correctionFile: File | null;
};

async function uploadArchiveFile(file: File): Promise<string> {
  const ext = file.name.split(".").pop()?.replace(/[^a-zA-Z0-9]/g, "") || "pdf";
  const path = `${new Date().getFullYear()}/${crypto.randomUUID()}.${ext}`;
  const { error } = await supabase.storage.from("exam-archive").upload(path, file);
  if (error) throw error;
  return path;
}

/**
 * Submits a candidate annale. RLS + a BEFORE INSERT trigger force `status`
 * to 'pending' for anyone who isn't an admin, no matter what's sent here —
 * this function never claims to publish anything.
 */
export async function submitArchiveEntry(payload: SubmitArchivePayload): Promise<void> {
  const pdfPath = await uploadArchiveFile(payload.pdfFile);
  const correctionPath = payload.correctionFile ? await uploadArchiveFile(payload.correctionFile) : null;

  const { error } = await supabase.from("exam_archive").insert({
    exam_type: payload.examType,
    year: payload.year,
    subject: payload.subject.trim().toLowerCase().replace(/\s+/g, "_"),
    filiere: payload.filiere ? payload.filiere.trim().toLowerCase().replace(/\s+/g, "_") : null,
    session: payload.session,
    title: payload.title.trim(),
    pdf_url: pdfPath,
    correction_url: correctionPath,
  });
  if (error) throw error;
}
