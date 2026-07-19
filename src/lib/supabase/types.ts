export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      ai_conversations: {
        Row: {
          chapter: string | null
          created_at: string
          id: string
          level: string | null
          mode: Database["public"]["Enums"]["ai_conversation_mode"]
          student_id: string
          subject: string | null
          title: string
          updated_at: string
        }
        Insert: {
          chapter?: string | null
          created_at?: string
          id?: string
          level?: string | null
          mode?: Database["public"]["Enums"]["ai_conversation_mode"]
          student_id: string
          subject?: string | null
          title?: string
          updated_at?: string
        }
        Update: {
          chapter?: string | null
          created_at?: string
          id?: string
          level?: string | null
          mode?: Database["public"]["Enums"]["ai_conversation_mode"]
          student_id?: string
          subject?: string | null
          title?: string
          updated_at?: string
        }
        Relationships: []
      }
      ai_exams: {
        Row: {
          answers: Json | null
          chapter: string | null
          created_at: string
          duration_min: number
          finished_at: string | null
          grading: Json | null
          id: string
          level: string | null
          questions: Json
          score: number | null
          started_at: string
          student_id: string
          subject: string
        }
        Insert: {
          answers?: Json | null
          chapter?: string | null
          created_at?: string
          duration_min?: number
          finished_at?: string | null
          grading?: Json | null
          id?: string
          level?: string | null
          questions: Json
          score?: number | null
          started_at?: string
          student_id: string
          subject: string
        }
        Update: {
          answers?: Json | null
          chapter?: string | null
          created_at?: string
          duration_min?: number
          finished_at?: string | null
          grading?: Json | null
          id?: string
          level?: string | null
          questions?: Json
          score?: number | null
          started_at?: string
          student_id?: string
          subject?: string
        }
        Relationships: []
      }
      ai_exercises: {
        Row: {
          created_at: string
          difficulty: number
          generated_exercise: Json
          id: string
          level: Database["public"]["Enums"]["school_level"]
          source_content: string | null
          source_type: Database["public"]["Enums"]["ai_source_type"]
          student_id: string
          subject: string
        }
        Insert: {
          created_at?: string
          difficulty?: number
          generated_exercise: Json
          id?: string
          level: Database["public"]["Enums"]["school_level"]
          source_content?: string | null
          source_type?: Database["public"]["Enums"]["ai_source_type"]
          student_id: string
          subject: string
        }
        Update: {
          created_at?: string
          difficulty?: number
          generated_exercise?: Json
          id?: string
          level?: Database["public"]["Enums"]["school_level"]
          source_content?: string | null
          source_type?: Database["public"]["Enums"]["ai_source_type"]
          student_id?: string
          subject?: string
        }
        Relationships: []
      }
      ai_messages: {
        Row: {
          content: string
          conversation_id: string
          created_at: string
          hint_level: number | null
          id: string
          image_url: string | null
          parts: Json | null
          role: string
        }
        Insert: {
          content: string
          conversation_id: string
          created_at?: string
          hint_level?: number | null
          id?: string
          image_url?: string | null
          parts?: Json | null
          role: string
        }
        Update: {
          content?: string
          conversation_id?: string
          created_at?: string
          hint_level?: number | null
          id?: string
          image_url?: string | null
          parts?: Json | null
          role?: string
        }
        Relationships: [
          {
            foreignKeyName: "ai_messages_conversation_id_fkey"
            columns: ["conversation_id"]
            isOneToOne: false
            referencedRelation: "ai_conversations"
            referencedColumns: ["id"]
          },
        ]
      }
      ai_quizzes: {
        Row: {
          chapter: string | null
          completed_at: string | null
          created_at: string
          id: string
          level: Database["public"]["Enums"]["school_level"]
          questions: Json
          score: number | null
          student_id: string
          subject: string
        }
        Insert: {
          chapter?: string | null
          completed_at?: string | null
          created_at?: string
          id?: string
          level: Database["public"]["Enums"]["school_level"]
          questions: Json
          score?: number | null
          student_id: string
          subject: string
        }
        Update: {
          chapter?: string | null
          completed_at?: string | null
          created_at?: string
          id?: string
          level?: Database["public"]["Enums"]["school_level"]
          questions?: Json
          score?: number | null
          student_id?: string
          subject?: string
        }
        Relationships: []
      }
      ai_revision_sheets: {
        Row: {
          chapter: string | null
          content_markdown: string
          conversation_id: string | null
          created_at: string
          id: string
          student_id: string
          subject: string | null
          title: string
        }
        Insert: {
          chapter?: string | null
          content_markdown: string
          conversation_id?: string | null
          created_at?: string
          id?: string
          student_id: string
          subject?: string | null
          title: string
        }
        Update: {
          chapter?: string | null
          content_markdown?: string
          conversation_id?: string | null
          created_at?: string
          id?: string
          student_id?: string
          subject?: string | null
          title?: string
        }
        Relationships: [
          {
            foreignKeyName: "ai_revision_sheets_conversation_id_fkey"
            columns: ["conversation_id"]
            isOneToOne: false
            referencedRelation: "ai_conversations"
            referencedColumns: ["id"]
          },
        ]
      }
      ai_submissions: {
        Row: {
          ai_feedback: string | null
          exercise_id: string
          id: string
          is_correct: boolean | null
          score: number | null
          student_answer: string
          student_id: string
          submitted_at: string
        }
        Insert: {
          ai_feedback?: string | null
          exercise_id: string
          id?: string
          is_correct?: boolean | null
          score?: number | null
          student_answer: string
          student_id: string
          submitted_at?: string
        }
        Update: {
          ai_feedback?: string | null
          exercise_id?: string
          id?: string
          is_correct?: boolean | null
          score?: number | null
          student_answer?: string
          student_id?: string
          submitted_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "ai_submissions_exercise_id_fkey"
            columns: ["exercise_id"]
            isOneToOne: false
            referencedRelation: "ai_exercises"
            referencedColumns: ["id"]
          },
        ]
      }
      ai_usage: {
        Row: {
          conversation_id: string | null
          cost_eur: number
          created_at: string
          id: string
          input_tokens: number
          mode: string | null
          model: string
          output_tokens: number
          user_id: string | null
        }
        Insert: {
          conversation_id?: string | null
          cost_eur?: number
          created_at?: string
          id?: string
          input_tokens?: number
          mode?: string | null
          model: string
          output_tokens?: number
          user_id?: string | null
        }
        Update: {
          conversation_id?: string | null
          cost_eur?: number
          created_at?: string
          id?: string
          input_tokens?: number
          mode?: string | null
          model?: string
          output_tokens?: number
          user_id?: string | null
        }
        Relationships: []
      }
      community_bans: {
        Row: {
          banned_until: string
          created_at: string
          reason: string | null
          user_id: string
        }
        Insert: {
          banned_until: string
          created_at?: string
          reason?: string | null
          user_id: string
        }
        Update: {
          banned_until?: string
          created_at?: string
          reason?: string | null
          user_id?: string
        }
        Relationships: []
      }
      community_post_likes: {
        Row: {
          created_at: string
          post_id: string
          user_id: string
        }
        Insert: {
          created_at?: string
          post_id: string
          user_id: string
        }
        Update: {
          created_at?: string
          post_id?: string
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "community_post_likes_post_id_fkey"
            columns: ["post_id"]
            isOneToOne: false
            referencedRelation: "community_posts"
            referencedColumns: ["id"]
          },
        ]
      }
      community_posts: {
        Row: {
          author_id: string
          body: string
          created_at: string
          hidden: boolean
          id: string
          likes_count: number
          thread_id: string
        }
        Insert: {
          author_id: string
          body: string
          created_at?: string
          hidden?: boolean
          id?: string
          likes_count?: number
          thread_id: string
        }
        Update: {
          author_id?: string
          body?: string
          created_at?: string
          hidden?: boolean
          id?: string
          likes_count?: number
          thread_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "community_posts_thread_id_fkey"
            columns: ["thread_id"]
            isOneToOne: false
            referencedRelation: "community_threads"
            referencedColumns: ["id"]
          },
        ]
      }
      community_threads: {
        Row: {
          author_id: string
          body: string
          created_at: string
          hidden: boolean
          id: string
          last_post_at: string
          level: string
          posts_count: number
          subject: string
          title: string
          updated_at: string
        }
        Insert: {
          author_id: string
          body: string
          created_at?: string
          hidden?: boolean
          id?: string
          last_post_at?: string
          level: string
          posts_count?: number
          subject: string
          title: string
          updated_at?: string
        }
        Update: {
          author_id?: string
          body?: string
          created_at?: string
          hidden?: boolean
          id?: string
          last_post_at?: string
          level?: string
          posts_count?: number
          subject?: string
          title?: string
          updated_at?: string
        }
        Relationships: []
      }
      course_enrollments: {
        Row: {
          course_id: string
          enrolled_at: string
          id: string
          payment_id: string | null
          progress_pct: number
          student_id: string
        }
        Insert: {
          course_id: string
          enrolled_at?: string
          id?: string
          payment_id?: string | null
          progress_pct?: number
          student_id: string
        }
        Update: {
          course_id?: string
          enrolled_at?: string
          id?: string
          payment_id?: string | null
          progress_pct?: number
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "course_enrollments_course_id_fkey"
            columns: ["course_id"]
            isOneToOne: false
            referencedRelation: "courses"
            referencedColumns: ["id"]
          },
        ]
      }
      course_reviews: {
        Row: {
          comment: string | null
          course_id: string
          created_at: string
          id: string
          rating: number
          student_id: string
        }
        Insert: {
          comment?: string | null
          course_id: string
          created_at?: string
          id?: string
          rating: number
          student_id: string
        }
        Update: {
          comment?: string | null
          course_id?: string
          created_at?: string
          id?: string
          rating?: number
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "course_reviews_course_id_fkey"
            columns: ["course_id"]
            isOneToOne: false
            referencedRelation: "courses"
            referencedColumns: ["id"]
          },
        ]
      }
      course_videos: {
        Row: {
          course_id: string
          created_at: string
          duration_sec: number | null
          id: string
          is_free_preview: boolean
          order_index: number
          title: string
          video_url: string
        }
        Insert: {
          course_id: string
          created_at?: string
          duration_sec?: number | null
          id?: string
          is_free_preview?: boolean
          order_index?: number
          title: string
          video_url: string
        }
        Update: {
          course_id?: string
          created_at?: string
          duration_sec?: number | null
          id?: string
          is_free_preview?: boolean
          order_index?: number
          title?: string
          video_url?: string
        }
        Relationships: [
          {
            foreignKeyName: "course_videos_course_id_fkey"
            columns: ["course_id"]
            isOneToOne: false
            referencedRelation: "courses"
            referencedColumns: ["id"]
          },
        ]
      }
      courses: {
        Row: {
          created_at: string
          description: string | null
          enrolled_count: number
          id: string
          language: Database["public"]["Enums"]["language_code"]
          level: Database["public"]["Enums"]["school_level"]
          price: number
          price_type: Database["public"]["Enums"]["price_type"]
          rating_avg: number
          status: Database["public"]["Enums"]["course_status"]
          subject: string
          teacher_id: string
          thumbnail_url: string | null
          title: string
          trailer_video_url: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          enrolled_count?: number
          id?: string
          language?: Database["public"]["Enums"]["language_code"]
          level: Database["public"]["Enums"]["school_level"]
          price?: number
          price_type?: Database["public"]["Enums"]["price_type"]
          rating_avg?: number
          status?: Database["public"]["Enums"]["course_status"]
          subject: string
          teacher_id: string
          thumbnail_url?: string | null
          title: string
          trailer_video_url: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          description?: string | null
          enrolled_count?: number
          id?: string
          language?: Database["public"]["Enums"]["language_code"]
          level?: Database["public"]["Enums"]["school_level"]
          price?: number
          price_type?: Database["public"]["Enums"]["price_type"]
          rating_avg?: number
          status?: Database["public"]["Enums"]["course_status"]
          subject?: string
          teacher_id?: string
          thumbnail_url?: string | null
          title?: string
          trailer_video_url?: string
          updated_at?: string
        }
        Relationships: []
      }
      curriculum: {
        Row: {
          chapter_order: number
          chapter_title_ar: string | null
          chapter_title_fr: string
          created_at: string
          filiere: string | null
          id: string
          keywords: string[]
          level: string
          notes: string | null
          subject: string
        }
        Insert: {
          chapter_order: number
          chapter_title_ar?: string | null
          chapter_title_fr: string
          created_at?: string
          filiere?: string | null
          id?: string
          keywords?: string[]
          level: string
          notes?: string | null
          subject: string
        }
        Update: {
          chapter_order?: number
          chapter_title_ar?: string | null
          chapter_title_fr?: string
          created_at?: string
          filiere?: string | null
          id?: string
          keywords?: string[]
          level?: string
          notes?: string | null
          subject?: string
        }
        Relationships: []
      }
      edu_chapters: {
        Row: {
          ai_content: Json | null
          ai_generated_at: string | null
          created_at: string
          id: string
          order_index: number
          subject_id: string
          summary_ar: string | null
          summary_fr: string | null
          title_ar: string
          title_fr: string
          updated_at: string
        }
        Insert: {
          ai_content?: Json | null
          ai_generated_at?: string | null
          created_at?: string
          id?: string
          order_index?: number
          subject_id: string
          summary_ar?: string | null
          summary_fr?: string | null
          title_ar: string
          title_fr: string
          updated_at?: string
        }
        Update: {
          ai_content?: Json | null
          ai_generated_at?: string | null
          created_at?: string
          id?: string
          order_index?: number
          subject_id?: string
          summary_ar?: string | null
          summary_fr?: string | null
          title_ar?: string
          title_fr?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "edu_chapters_subject_id_fkey"
            columns: ["subject_id"]
            isOneToOne: false
            referencedRelation: "edu_subjects"
            referencedColumns: ["id"]
          },
        ]
      }
      edu_levels: {
        Row: {
          created_at: string
          cycle: string
          grade: string
          id: string
          label_ar: string
          label_fr: string
          order_index: number
          slug: string
          track: string | null
          updated_at: string
        }
        Insert: {
          created_at?: string
          cycle: string
          grade: string
          id?: string
          label_ar: string
          label_fr: string
          order_index?: number
          slug: string
          track?: string | null
          updated_at?: string
        }
        Update: {
          created_at?: string
          cycle?: string
          grade?: string
          id?: string
          label_ar?: string
          label_fr?: string
          order_index?: number
          slug?: string
          track?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      edu_subjects: {
        Row: {
          color: string | null
          created_at: string
          icon: string | null
          id: string
          level_id: string
          name_ar: string
          name_fr: string
          order_index: number
          slug: string
          updated_at: string
        }
        Insert: {
          color?: string | null
          created_at?: string
          icon?: string | null
          id?: string
          level_id: string
          name_ar: string
          name_fr: string
          order_index?: number
          slug: string
          updated_at?: string
        }
        Update: {
          color?: string | null
          created_at?: string
          icon?: string | null
          id?: string
          level_id?: string
          name_ar?: string
          name_fr?: string
          order_index?: number
          slug?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "edu_subjects_level_id_fkey"
            columns: ["level_id"]
            isOneToOne: false
            referencedRelation: "edu_levels"
            referencedColumns: ["id"]
          },
        ]
      }
      exam_archive: {
        Row: {
          correction_url: string | null
          created_at: string
          exam_type: Database["public"]["Enums"]["exam_target"]
          filiere: string | null
          id: string
          pdf_url: string
          subject: string
          title: string
          updated_at: string
          uploaded_by: string | null
          year: number
        }
        Insert: {
          correction_url?: string | null
          created_at?: string
          exam_type: Database["public"]["Enums"]["exam_target"]
          filiere?: string | null
          id?: string
          pdf_url: string
          subject: string
          title: string
          updated_at?: string
          uploaded_by?: string | null
          year: number
        }
        Update: {
          correction_url?: string | null
          created_at?: string
          exam_type?: Database["public"]["Enums"]["exam_target"]
          filiere?: string | null
          id?: string
          pdf_url?: string
          subject?: string
          title?: string
          updated_at?: string
          uploaded_by?: string | null
          year?: number
        }
        Relationships: []
      }
      exam_countdowns: {
        Row: {
          exam: Database["public"]["Enums"]["exam_target"]
          exam_date: string
          id: string
          year: number
        }
        Insert: {
          exam: Database["public"]["Enums"]["exam_target"]
          exam_date: string
          id?: string
          year: number
        }
        Update: {
          exam?: Database["public"]["Enums"]["exam_target"]
          exam_date?: string
          id?: string
          year?: number
        }
        Relationships: []
      }
      gamification: {
        Row: {
          badges: Json
          chapters_completed: Json
          last_practice_date: string | null
          student_id: string
          updated_at: string
        }
        Insert: {
          badges?: Json
          chapters_completed?: Json
          last_practice_date?: string | null
          student_id: string
          updated_at?: string
        }
        Update: {
          badges?: Json
          chapters_completed?: Json
          last_practice_date?: string | null
          student_id?: string
          updated_at?: string
        }
        Relationships: []
      }
      group_events: {
        Row: {
          created_at: string
          created_by: string
          description: string | null
          event_at: string
          group_id: string
          id: string
          title: string
        }
        Insert: {
          created_at?: string
          created_by: string
          description?: string | null
          event_at: string
          group_id: string
          id?: string
          title: string
        }
        Update: {
          created_at?: string
          created_by?: string
          description?: string | null
          event_at?: string
          group_id?: string
          id?: string
          title?: string
        }
        Relationships: [
          {
            foreignKeyName: "group_events_group_id_fkey"
            columns: ["group_id"]
            isOneToOne: false
            referencedRelation: "study_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      group_exam_alerts: {
        Row: {
          chapters: string[]
          checklist: Json
          created_at: string
          created_by: string
          exam_date: string
          group_id: string
          id: string
          quiz: Json
          subject: string
        }
        Insert: {
          chapters?: string[]
          checklist?: Json
          created_at?: string
          created_by: string
          exam_date: string
          group_id: string
          id?: string
          quiz?: Json
          subject: string
        }
        Update: {
          chapters?: string[]
          checklist?: Json
          created_at?: string
          created_by?: string
          exam_date?: string
          group_id?: string
          id?: string
          quiz?: Json
          subject?: string
        }
        Relationships: [
          {
            foreignKeyName: "group_exam_alerts_group_id_fkey"
            columns: ["group_id"]
            isOneToOne: false
            referencedRelation: "study_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      group_members: {
        Row: {
          group_id: string
          id: string
          joined_at: string
          role: Database["public"]["Enums"]["group_member_role"]
          user_id: string
        }
        Insert: {
          group_id: string
          id?: string
          joined_at?: string
          role?: Database["public"]["Enums"]["group_member_role"]
          user_id: string
        }
        Update: {
          group_id?: string
          id?: string
          joined_at?: string
          role?: Database["public"]["Enums"]["group_member_role"]
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "group_members_group_id_fkey"
            columns: ["group_id"]
            isOneToOne: false
            referencedRelation: "study_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      group_messages: {
        Row: {
          author_id: string
          body: string
          created_at: string
          group_id: string
          id: string
        }
        Insert: {
          author_id: string
          body: string
          created_at?: string
          group_id: string
          id?: string
        }
        Update: {
          author_id?: string
          body?: string
          created_at?: string
          group_id?: string
          id?: string
        }
        Relationships: [
          {
            foreignKeyName: "group_messages_group_id_fkey"
            columns: ["group_id"]
            isOneToOne: false
            referencedRelation: "study_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      group_pomodoro_sessions: {
        Row: {
          created_at: string
          ends_at: string
          group_id: string
          id: string
          phase: string
          started_at: string
          started_by: string
        }
        Insert: {
          created_at?: string
          ends_at: string
          group_id: string
          id?: string
          phase: string
          started_at?: string
          started_by: string
        }
        Update: {
          created_at?: string
          ends_at?: string
          group_id?: string
          id?: string
          phase?: string
          started_at?: string
          started_by?: string
        }
        Relationships: [
          {
            foreignKeyName: "group_pomodoro_sessions_group_id_fkey"
            columns: ["group_id"]
            isOneToOne: false
            referencedRelation: "study_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      group_resources: {
        Row: {
          created_at: string
          group_id: string
          id: string
          mime_type: string | null
          size_bytes: number | null
          storage_path: string
          title: string
          uploader_id: string
        }
        Insert: {
          created_at?: string
          group_id: string
          id?: string
          mime_type?: string | null
          size_bytes?: number | null
          storage_path: string
          title: string
          uploader_id: string
        }
        Update: {
          created_at?: string
          group_id?: string
          id?: string
          mime_type?: string | null
          size_bytes?: number | null
          storage_path?: string
          title?: string
          uploader_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "group_resources_group_id_fkey"
            columns: ["group_id"]
            isOneToOne: false
            referencedRelation: "study_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      live_sessions: {
        Row: {
          allow_recording: boolean
          created_at: string
          daily_room_url: string | null
          duration_min: number
          id: string
          level: Database["public"]["Enums"]["school_level"]
          max_students: number
          price_per_student: number
          recording_url: string | null
          scheduled_at: string
          session_type: Database["public"]["Enums"]["session_type"]
          status: Database["public"]["Enums"]["session_status"]
          subject: string
          teacher_id: string
          title: string | null
          updated_at: string
        }
        Insert: {
          allow_recording?: boolean
          created_at?: string
          daily_room_url?: string | null
          duration_min?: number
          id?: string
          level: Database["public"]["Enums"]["school_level"]
          max_students?: number
          price_per_student: number
          recording_url?: string | null
          scheduled_at: string
          session_type?: Database["public"]["Enums"]["session_type"]
          status?: Database["public"]["Enums"]["session_status"]
          subject: string
          teacher_id: string
          title?: string | null
          updated_at?: string
        }
        Update: {
          allow_recording?: boolean
          created_at?: string
          daily_room_url?: string | null
          duration_min?: number
          id?: string
          level?: Database["public"]["Enums"]["school_level"]
          max_students?: number
          price_per_student?: number
          recording_url?: string | null
          scheduled_at?: string
          session_type?: Database["public"]["Enums"]["session_type"]
          status?: Database["public"]["Enums"]["session_status"]
          subject?: string
          teacher_id?: string
          title?: string | null
          updated_at?: string
        }
        Relationships: []
      }
      memo_progress: {
        Row: {
          attempts: number
          block_index: number
          created_at: string
          id: string
          mastered_at: string | null
          next_review_at: string | null
          quiz_score: number | null
          sheet_id: string
          student_id: string
          updated_at: string
        }
        Insert: {
          attempts?: number
          block_index: number
          created_at?: string
          id?: string
          mastered_at?: string | null
          next_review_at?: string | null
          quiz_score?: number | null
          sheet_id: string
          student_id: string
          updated_at?: string
        }
        Update: {
          attempts?: number
          block_index?: number
          created_at?: string
          id?: string
          mastered_at?: string | null
          next_review_at?: string | null
          quiz_score?: number | null
          sheet_id?: string
          student_id?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "memo_progress_sheet_id_fkey"
            columns: ["sheet_id"]
            isOneToOne: false
            referencedRelation: "memo_sheets"
            referencedColumns: ["id"]
          },
        ]
      }
      memo_sheets: {
        Row: {
          blocks: Json
          chapter: string | null
          created_at: string
          formats: Json
          id: string
          level: string | null
          source_kind: string
          source_text: string | null
          student_id: string
          subject: string | null
          title: string
          updated_at: string
        }
        Insert: {
          blocks?: Json
          chapter?: string | null
          created_at?: string
          formats?: Json
          id?: string
          level?: string | null
          source_kind?: string
          source_text?: string | null
          student_id: string
          subject?: string | null
          title: string
          updated_at?: string
        }
        Update: {
          blocks?: Json
          chapter?: string | null
          created_at?: string
          formats?: Json
          id?: string
          level?: string | null
          source_kind?: string
          source_text?: string | null
          student_id?: string
          subject?: string | null
          title?: string
          updated_at?: string
        }
        Relationships: []
      }
      notifications: {
        Row: {
          body: string | null
          created_at: string
          id: string
          link: string | null
          read_at: string | null
          title: string
          type: string
          user_id: string
        }
        Insert: {
          body?: string | null
          created_at?: string
          id?: string
          link?: string | null
          read_at?: string | null
          title: string
          type: string
          user_id: string
        }
        Update: {
          body?: string | null
          created_at?: string
          id?: string
          link?: string | null
          read_at?: string | null
          title?: string
          type?: string
          user_id?: string
        }
        Relationships: []
      }
      parent_child_links: {
        Row: {
          created_at: string
          id: string
          parent_id: string
          status: Database["public"]["Enums"]["link_status"]
          student_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          parent_id: string
          status?: Database["public"]["Enums"]["link_status"]
          student_id: string
        }
        Update: {
          created_at?: string
          id?: string
          parent_id?: string
          status?: Database["public"]["Enums"]["link_status"]
          student_id?: string
        }
        Relationships: []
      }
      payments: {
        Row: {
          amount: number
          chargily_checkout_id: string | null
          chargily_payment_url: string | null
          created_at: string
          currency: string
          id: string
          item_id: string
          item_type: Database["public"]["Enums"]["item_type"]
          paid_at: string | null
          status: Database["public"]["Enums"]["payment_status"]
          user_id: string
        }
        Insert: {
          amount: number
          chargily_checkout_id?: string | null
          chargily_payment_url?: string | null
          created_at?: string
          currency?: string
          id?: string
          item_id: string
          item_type: Database["public"]["Enums"]["item_type"]
          paid_at?: string | null
          status?: Database["public"]["Enums"]["payment_status"]
          user_id: string
        }
        Update: {
          amount?: number
          chargily_checkout_id?: string | null
          chargily_payment_url?: string | null
          created_at?: string
          currency?: string
          id?: string
          item_id?: string
          item_type?: Database["public"]["Enums"]["item_type"]
          paid_at?: string | null
          status?: Database["public"]["Enums"]["payment_status"]
          user_id?: string
        }
        Relationships: []
      }
      payouts: {
        Row: {
          amount: number
          id: string
          method: string | null
          paid_at: string | null
          requested_at: string
          status: string
          teacher_id: string
        }
        Insert: {
          amount: number
          id?: string
          method?: string | null
          paid_at?: string | null
          requested_at?: string
          status?: string
          teacher_id: string
        }
        Update: {
          amount?: number
          id?: string
          method?: string | null
          paid_at?: string | null
          requested_at?: string
          status?: string
          teacher_id?: string
        }
        Relationships: []
      }
      post_reports: {
        Row: {
          created_at: string
          id: string
          reason: string
          reporter_id: string
          resolved_at: string | null
          status: string
          target_id: string
          target_type: string
        }
        Insert: {
          created_at?: string
          id?: string
          reason: string
          reporter_id: string
          resolved_at?: string | null
          status?: string
          target_id: string
          target_type: string
        }
        Update: {
          created_at?: string
          id?: string
          reason?: string
          reporter_id?: string
          resolved_at?: string | null
          status?: string
          target_id?: string
          target_type?: string
        }
        Relationships: []
      }
      profiles: {
        Row: {
          avatar_url: string | null
          created_at: string
          full_name: string | null
          id: string
          language: Database["public"]["Enums"]["language_code"]
          phone: string | null
          updated_at: string
          wilaya: string | null
        }
        Insert: {
          avatar_url?: string | null
          created_at?: string
          full_name?: string | null
          id: string
          language?: Database["public"]["Enums"]["language_code"]
          phone?: string | null
          updated_at?: string
          wilaya?: string | null
        }
        Update: {
          avatar_url?: string | null
          created_at?: string
          full_name?: string | null
          id?: string
          language?: Database["public"]["Enums"]["language_code"]
          phone?: string | null
          updated_at?: string
          wilaya?: string | null
        }
        Relationships: []
      }
      push_subscriptions: {
        Row: {
          auth_key: string
          created_at: string
          endpoint: string
          id: string
          p256dh: string
          user_agent: string | null
          user_id: string
        }
        Insert: {
          auth_key: string
          created_at?: string
          endpoint: string
          id?: string
          p256dh: string
          user_agent?: string | null
          user_id: string
        }
        Update: {
          auth_key?: string
          created_at?: string
          endpoint?: string
          id?: string
          p256dh?: string
          user_agent?: string | null
          user_id?: string
        }
        Relationships: []
      }
      quiz_responses: {
        Row: {
          answer: string
          id: string
          is_correct: boolean
          quiz_id: string
          student_id: string
          submitted_at: string
        }
        Insert: {
          answer: string
          id?: string
          is_correct?: boolean
          quiz_id: string
          student_id: string
          submitted_at?: string
        }
        Update: {
          answer?: string
          id?: string
          is_correct?: boolean
          quiz_id?: string
          student_id?: string
          submitted_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "quiz_responses_quiz_id_fkey"
            columns: ["quiz_id"]
            isOneToOne: false
            referencedRelation: "session_quizzes"
            referencedColumns: ["id"]
          },
        ]
      }
      referrals: {
        Row: {
          created_at: string
          credit_amount: number
          id: string
          referred_id: string
          referrer_id: string
          status: string
        }
        Insert: {
          created_at?: string
          credit_amount?: number
          id?: string
          referred_id: string
          referrer_id: string
          status?: string
        }
        Update: {
          created_at?: string
          credit_amount?: number
          id?: string
          referred_id?: string
          referrer_id?: string
          status?: string
        }
        Relationships: []
      }
      reports: {
        Row: {
          created_at: string
          description: string | null
          id: string
          reason: string
          reported_user_id: string
          reporter_id: string
          session_id: string | null
          status: Database["public"]["Enums"]["report_status"]
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          reason: string
          reported_user_id: string
          reporter_id: string
          session_id?: string | null
          status?: Database["public"]["Enums"]["report_status"]
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          reason?: string
          reported_user_id?: string
          reporter_id?: string
          session_id?: string | null
          status?: Database["public"]["Enums"]["report_status"]
        }
        Relationships: [
          {
            foreignKeyName: "reports_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "live_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      session_bookings: {
        Row: {
          created_at: string
          id: string
          joined_at: string | null
          left_at: string | null
          mode: string
          payment_id: string | null
          session_id: string
          status: Database["public"]["Enums"]["booking_status"]
          student_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          joined_at?: string | null
          left_at?: string | null
          mode?: string
          payment_id?: string | null
          session_id: string
          status?: Database["public"]["Enums"]["booking_status"]
          student_id: string
        }
        Update: {
          created_at?: string
          id?: string
          joined_at?: string | null
          left_at?: string | null
          mode?: string
          payment_id?: string | null
          session_id?: string
          status?: Database["public"]["Enums"]["booking_status"]
          student_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "session_bookings_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "live_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      session_quizzes: {
        Row: {
          closed_at: string | null
          correct_answer: string
          id: string
          options: Json
          question: string
          sent_at: string
          session_id: string
        }
        Insert: {
          closed_at?: string | null
          correct_answer: string
          id?: string
          options: Json
          question: string
          sent_at?: string
          session_id: string
        }
        Update: {
          closed_at?: string | null
          correct_answer?: string
          id?: string
          options?: Json
          question?: string
          sent_at?: string
          session_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "session_quizzes_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "live_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      session_reviews: {
        Row: {
          comment: string | null
          created_at: string
          id: string
          rating: number
          session_id: string
          student_id: string
          teacher_id: string
        }
        Insert: {
          comment?: string | null
          created_at?: string
          id?: string
          rating: number
          session_id: string
          student_id: string
          teacher_id: string
        }
        Update: {
          comment?: string | null
          created_at?: string
          id?: string
          rating?: number
          session_id?: string
          student_id?: string
          teacher_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "session_reviews_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "live_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      session_summaries: {
        Row: {
          created_at: string
          id: string
          per_student: Json
          session_id: string
          stats: Json
          summary_markdown: string
        }
        Insert: {
          created_at?: string
          id?: string
          per_student?: Json
          session_id: string
          stats?: Json
          summary_markdown: string
        }
        Update: {
          created_at?: string
          id?: string
          per_student?: Json
          session_id?: string
          stats?: Json
          summary_markdown?: string
        }
        Relationships: [
          {
            foreignKeyName: "session_summaries_session_id_fkey"
            columns: ["session_id"]
            isOneToOne: false
            referencedRelation: "live_sessions"
            referencedColumns: ["id"]
          },
        ]
      }
      session_waitlist: {
        Row: {
          created_at: string
          id: string
          notified_at: string | null
          preferred_slots: Json | null
          student_id: string
          subject: string | null
          teacher_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          notified_at?: string | null
          preferred_slots?: Json | null
          student_id: string
          subject?: string | null
          teacher_id: string
        }
        Update: {
          created_at?: string
          id?: string
          notified_at?: string | null
          preferred_slots?: Json | null
          student_id?: string
          subject?: string | null
          teacher_id?: string
        }
        Relationships: []
      }
      student_profiles: {
        Row: {
          created_at: string
          credits: number
          exam_target: Database["public"]["Enums"]["exam_target"]
          perk_unlocked_until: string | null
          preferred_language: string
          referral_code: string | null
          school_level: Database["public"]["Enums"]["school_level"] | null
          streak_days: number
          updated_at: string
          user_id: string
        }
        Insert: {
          created_at?: string
          credits?: number
          exam_target?: Database["public"]["Enums"]["exam_target"]
          perk_unlocked_until?: string | null
          preferred_language?: string
          referral_code?: string | null
          school_level?: Database["public"]["Enums"]["school_level"] | null
          streak_days?: number
          updated_at?: string
          user_id: string
        }
        Update: {
          created_at?: string
          credits?: number
          exam_target?: Database["public"]["Enums"]["exam_target"]
          perk_unlocked_until?: string | null
          preferred_language?: string
          referral_code?: string | null
          school_level?: Database["public"]["Enums"]["school_level"] | null
          streak_days?: number
          updated_at?: string
          user_id?: string
        }
        Relationships: []
      }
      student_tasks: {
        Row: {
          actual_minutes: number | null
          ai_analysis: Json | null
          channels: string[]
          chapter: string | null
          completed_at: string | null
          created_at: string
          difficulty: number
          due_at: string | null
          estimated_minutes: number
          group_id: string | null
          id: string
          level: string | null
          notes: string | null
          priority_score: number
          reminder_at: string | null
          self_grade: number | null
          share_with_group: boolean
          source_content: string | null
          source_type: string
          status: string
          student_id: string
          subject: string | null
          title: string
          updated_at: string
        }
        Insert: {
          actual_minutes?: number | null
          ai_analysis?: Json | null
          channels?: string[]
          chapter?: string | null
          completed_at?: string | null
          created_at?: string
          difficulty?: number
          due_at?: string | null
          estimated_minutes?: number
          group_id?: string | null
          id?: string
          level?: string | null
          notes?: string | null
          priority_score?: number
          reminder_at?: string | null
          self_grade?: number | null
          share_with_group?: boolean
          source_content?: string | null
          source_type?: string
          status?: string
          student_id: string
          subject?: string | null
          title: string
          updated_at?: string
        }
        Update: {
          actual_minutes?: number | null
          ai_analysis?: Json | null
          channels?: string[]
          chapter?: string | null
          completed_at?: string | null
          created_at?: string
          difficulty?: number
          due_at?: string | null
          estimated_minutes?: number
          group_id?: string | null
          id?: string
          level?: string | null
          notes?: string | null
          priority_score?: number
          reminder_at?: string | null
          self_grade?: number | null
          share_with_group?: boolean
          source_content?: string | null
          source_type?: string
          status?: string
          student_id?: string
          subject?: string | null
          title?: string
          updated_at?: string
        }
        Relationships: [
          {
            foreignKeyName: "student_tasks_group_id_fkey"
            columns: ["group_id"]
            isOneToOne: false
            referencedRelation: "study_groups"
            referencedColumns: ["id"]
          },
        ]
      }
      study_groups: {
        Row: {
          created_at: string
          description: string | null
          id: string
          invite_code: string
          level: string
          max_members: number
          name: string
          owner_id: string
          subject: string
          updated_at: string
        }
        Insert: {
          created_at?: string
          description?: string | null
          id?: string
          invite_code: string
          level: string
          max_members?: number
          name: string
          owner_id: string
          subject: string
          updated_at?: string
        }
        Update: {
          created_at?: string
          description?: string | null
          id?: string
          invite_code?: string
          level?: string
          max_members?: number
          name?: string
          owner_id?: string
          subject?: string
          updated_at?: string
        }
        Relationships: []
      }
      task_reminder_log: {
        Row: {
          channel: string
          id: string
          sent_at: string
          student_id: string
          task_id: string
          tier: string
        }
        Insert: {
          channel: string
          id?: string
          sent_at?: string
          student_id: string
          task_id: string
          tier: string
        }
        Update: {
          channel?: string
          id?: string
          sent_at?: string
          student_id?: string
          task_id?: string
          tier?: string
        }
        Relationships: [
          {
            foreignKeyName: "task_reminder_log_task_id_fkey"
            columns: ["task_id"]
            isOneToOne: false
            referencedRelation: "student_tasks"
            referencedColumns: ["id"]
          },
        ]
      }
      teacher_availability: {
        Row: {
          created_at: string
          day_of_week: number
          end_time: string
          id: string
          recurring: boolean
          start_time: string
          teacher_id: string
        }
        Insert: {
          created_at?: string
          day_of_week: number
          end_time: string
          id?: string
          recurring?: boolean
          start_time: string
          teacher_id: string
        }
        Update: {
          created_at?: string
          day_of_week?: number
          end_time?: string
          id?: string
          recurring?: boolean
          start_time?: string
          teacher_id?: string
        }
        Relationships: []
      }
      teacher_earnings: {
        Row: {
          amount: number
          created_at: string
          id: string
          net_amount: number
          payment_id: string
          platform_fee: number
          released_at: string | null
          status: Database["public"]["Enums"]["earning_status"]
          teacher_id: string
        }
        Insert: {
          amount: number
          created_at?: string
          id?: string
          net_amount: number
          payment_id: string
          platform_fee?: number
          released_at?: string | null
          status?: Database["public"]["Enums"]["earning_status"]
          teacher_id: string
        }
        Update: {
          amount?: number
          created_at?: string
          id?: string
          net_amount?: number
          payment_id?: string
          platform_fee?: number
          released_at?: string | null
          status?: Database["public"]["Enums"]["earning_status"]
          teacher_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "teacher_earnings_payment_id_fkey"
            columns: ["payment_id"]
            isOneToOne: false
            referencedRelation: "payments"
            referencedColumns: ["id"]
          },
        ]
      }
      teacher_profiles: {
        Row: {
          allow_recording: boolean
          bio: string | null
          created_at: string
          diploma_url: string | null
          hourly_rate: number | null
          id_document_url: string | null
          levels: Database["public"]["Enums"]["school_level"][]
          rating_avg: number
          subjects: string[]
          total_students: number
          updated_at: string
          user_id: string
          verification_status: Database["public"]["Enums"]["verification_status"]
        }
        Insert: {
          allow_recording?: boolean
          bio?: string | null
          created_at?: string
          diploma_url?: string | null
          hourly_rate?: number | null
          id_document_url?: string | null
          levels?: Database["public"]["Enums"]["school_level"][]
          rating_avg?: number
          subjects?: string[]
          total_students?: number
          updated_at?: string
          user_id: string
          verification_status?: Database["public"]["Enums"]["verification_status"]
        }
        Update: {
          allow_recording?: boolean
          bio?: string | null
          created_at?: string
          diploma_url?: string | null
          hourly_rate?: number | null
          id_document_url?: string | null
          levels?: Database["public"]["Enums"]["school_level"][]
          rating_avg?: number
          subjects?: string[]
          total_students?: number
          updated_at?: string
          user_id?: string
          verification_status?: Database["public"]["Enums"]["verification_status"]
        }
        Relationships: []
      }
      user_roles: {
        Row: {
          created_at: string
          id: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Insert: {
          created_at?: string
          id?: string
          role: Database["public"]["Enums"]["app_role"]
          user_id: string
        }
        Update: {
          created_at?: string
          id?: string
          role?: Database["public"]["Enums"]["app_role"]
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      has_role: {
        Args: {
          _role: Database["public"]["Enums"]["app_role"]
          _user_id: string
        }
        Returns: boolean
      }
      is_community_banned: { Args: { _user: string }; Returns: boolean }
      is_group_member: {
        Args: { _group: string; _user: string }
        Returns: boolean
      }
      is_group_owner: {
        Args: { _group: string; _user: string }
        Returns: boolean
      }
      is_parent_of: {
        Args: { _parent: string; _student: string }
        Returns: boolean
      }
      ping_streak: {
        Args: { _user: string }
        Returns: {
          last_practice_date: string
          streak_days: number
        }[]
      }
      redeem_referral_code: {
        Args: { _code: string; _new_user: string }
        Returns: undefined
      }
    }
    Enums: {
      ai_conversation_mode: "chat" | "exam"
      ai_source_type: "generated" | "from_photo" | "from_text"
      app_role: "student" | "teacher" | "parent" | "admin"
      booking_status: "booked" | "attended" | "no_show" | "cancelled"
      course_status: "draft" | "published" | "archived"
      earning_status: "pending" | "released" | "refunded"
      exam_target: "none" | "bem" | "bac"
      group_member_role: "owner" | "member"
      item_type: "course" | "session"
      language_code: "fr" | "ar"
      link_status: "pending" | "accepted" | "rejected"
      payment_status: "pending" | "paid" | "failed" | "refunded"
      price_type: "series" | "per_session"
      report_status: "open" | "reviewed" | "resolved"
      school_level:
        | "primaire"
        | "cem_1"
        | "cem_2"
        | "cem_3"
        | "cem_4"
        | "lycee_1_tc"
        | "lycee_2_sciences"
        | "lycee_2_lettres"
        | "lycee_2_maths"
        | "lycee_2_gestion"
        | "lycee_2_langues"
        | "lycee_2_techmath"
        | "lycee_3_sciences"
        | "lycee_3_lettres"
        | "lycee_3_maths"
        | "lycee_3_gestion"
        | "lycee_3_langues"
        | "lycee_3_techmath"
        | "univ_1"
        | "univ_2"
        | "univ_3"
        | "autre"
      session_status: "scheduled" | "live" | "completed" | "cancelled"
      session_type: "solo" | "group"
      verification_status: "pending" | "verified" | "rejected"
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {
      ai_conversation_mode: ["chat", "exam"],
      ai_source_type: ["generated", "from_photo", "from_text"],
      app_role: ["student", "teacher", "parent", "admin"],
      booking_status: ["booked", "attended", "no_show", "cancelled"],
      course_status: ["draft", "published", "archived"],
      earning_status: ["pending", "released", "refunded"],
      exam_target: ["none", "bem", "bac"],
      group_member_role: ["owner", "member"],
      item_type: ["course", "session"],
      language_code: ["fr", "ar"],
      link_status: ["pending", "accepted", "rejected"],
      payment_status: ["pending", "paid", "failed", "refunded"],
      price_type: ["series", "per_session"],
      report_status: ["open", "reviewed", "resolved"],
      school_level: [
        "primaire",
        "cem_1",
        "cem_2",
        "cem_3",
        "cem_4",
        "lycee_1_tc",
        "lycee_2_sciences",
        "lycee_2_lettres",
        "lycee_2_maths",
        "lycee_2_gestion",
        "lycee_2_langues",
        "lycee_2_techmath",
        "lycee_3_sciences",
        "lycee_3_lettres",
        "lycee_3_maths",
        "lycee_3_gestion",
        "lycee_3_langues",
        "lycee_3_techmath",
        "univ_1",
        "univ_2",
        "univ_3",
        "autre",
      ],
      session_status: ["scheduled", "live", "completed", "cancelled"],
      session_type: ["solo", "group"],
      verification_status: ["pending", "verified", "rejected"],
    },
  },
} as const
