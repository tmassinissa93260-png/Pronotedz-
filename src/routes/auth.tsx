import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { supabase } from "@/lib/supabase/client";
import {
  signInWithPassword,
  signUpWithPassword,
  signInWithGoogle,
  resetPasswordForEmail,
} from "@/lib/auth/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { LanguageSwitcher } from "@/components/language-switcher";
import { FadeIn } from "@/components/motion/fade-in";
import { useT } from "@/lib/i18n";

type Search = { mode?: "signin" | "signup" | "reset"; ref?: string };

export const Route = createFileRoute("/auth")({
  validateSearch: (s: Record<string, unknown>): Search => ({
    mode: s.mode === "signup" ? "signup" : s.mode === "reset" ? "reset" : "signin",
    ref: typeof s.ref === "string" && s.ref.length >= 4 && s.ref.length <= 32 ? s.ref : undefined,
  }),
  component: AuthPage,
});

function AuthPage() {
  const { mode: initialMode, ref } = Route.useSearch();
  const navigate = useNavigate();
  const t = useT();
  const [mode, setMode] = useState<"signin" | "signup" | "reset">(ref ? "signup" : initialMode ?? "signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [awaitingConfirm, setAwaitingConfirm] = useState(false);
  const [resetSent, setResetSent] = useState(false);

  useEffect(() => {
    if (ref) window.localStorage.setItem("estadi_ref", ref);
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) navigate({ to: "/dashboard" });
    });
  }, [navigate, ref]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      if (mode === "reset") {
        await resetPasswordForEmail(email);
        setResetSent(true);
      } else if (mode === "signup") {
        const data = await signUpWithPassword(email, password, fullName);
        if (data.session) {
          toast.success(t("auth.accountCreated"));
          navigate({ to: "/onboarding" });
        } else {
          setAwaitingConfirm(true);
        }
      } else {
        await signInWithPassword(email, password);
        navigate({ to: "/dashboard" });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("auth.signInErrorGeneric"));
    } finally {
      setLoading(false);
    }
  }

  async function handleGoogle() {
    try {
      await signInWithGoogle();
    } catch {
      toast.error(t("auth.signInErrorGeneric"));
    }
  }

  return (
    <div className="min-h-screen bg-hero">
      <div className="mx-auto flex max-w-md justify-end px-4 pt-4">
        <LanguageSwitcher compact />
      </div>
      <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
        <Link to="/" className="mb-8 flex items-center gap-2.5">
          <div className="grid size-9 place-items-center rounded-xl bg-emerald-gradient font-display font-bold text-primary-foreground shadow-glow">
            أ
          </div>
          <span className="font-display text-lg font-bold">{t("common.appName")}</span>
        </Link>

        <FadeIn>
          <Card className="p-6">
            {awaitingConfirm ? (
              <ConfirmEmail email={email} onBack={() => { setAwaitingConfirm(false); setMode("signin"); }} />
            ) : mode === "reset" ? (
              resetSent ? (
                <ResetSent onBack={() => { setResetSent(false); setMode("signin"); }} />
              ) : (
                <ResetForm
                  email={email}
                  setEmail={setEmail}
                  loading={loading}
                  onSubmit={handleSubmit}
                  onBack={() => setMode("signin")}
                />
              )
            ) : (
              <>
                <h1 className="font-display text-2xl font-bold">
                  {mode === "signup" ? t("auth.createAccount") : t("auth.welcomeBack")}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {mode === "signup" ? t("auth.joinThousands") : t("auth.resumeLearning")}
                </p>

                <Button variant="outline" className="mt-6 w-full" onClick={handleGoogle} type="button">
                  {t("auth.continueWithGoogle")}
                </Button>

                <div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
                  <div className="h-px flex-1 bg-border" /> {t("auth.or")}{" "}
                  <div className="h-px flex-1 bg-border" />
                </div>

                <form onSubmit={handleSubmit} className="space-y-3">
                  {mode === "signup" && (
                    <div className="space-y-1.5">
                      <Label htmlFor="fullName">{t("auth.fullName")}</Label>
                      <Input
                        id="fullName"
                        required
                        value={fullName}
                        onChange={(e) => setFullName(e.target.value)}
                      />
                    </div>
                  )}
                  <div className="space-y-1.5">
                    <Label htmlFor="email">{t("auth.email")}</Label>
                    <Input
                      id="email"
                      required
                      type="email"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="password">{t("auth.password")}</Label>
                      {mode === "signin" && (
                        <button
                          type="button"
                          onClick={() => setMode("reset")}
                          className="text-xs font-medium text-primary hover:underline"
                        >
                          {t("auth.forgotPassword")}
                        </button>
                      )}
                    </div>
                    <Input
                      id="password"
                      required
                      type="password"
                      minLength={6}
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                    />
                  </div>
                  <Button type="submit" disabled={loading} className="w-full">
                    {loading ? t("common.loading") : mode === "signup" ? t("auth.submitSignUp") : t("auth.submitSignIn")}
                  </Button>
                </form>

                <p className="mt-5 text-center text-sm text-muted-foreground">
                  {mode === "signup" ? t("auth.haveAccount") : t("auth.noAccount")}{" "}
                  <button
                    onClick={() => setMode(mode === "signup" ? "signin" : "signup")}
                    className="font-medium text-primary hover:underline"
                  >
                    {mode === "signup" ? t("auth.signIn") : t("auth.signUp")}
                  </button>
                </p>
              </>
            )}
          </Card>
        </FadeIn>
      </div>
    </div>
  );
}

function ConfirmEmail({ email, onBack }: { email: string; onBack: () => void }) {
  const t = useT();
  return (
    <>
      <h1 className="font-display text-2xl font-bold">{t("auth.confirmEmailTitle")} 📩</h1>
      <p className="mt-2 text-sm text-muted-foreground">
        {t("auth.confirmEmailBody", { email })}
      </p>
      <Button onClick={onBack} className="mt-6 w-full">
        {t("auth.confirmedSignIn")}
      </Button>
    </>
  );
}

function ResetForm({
  email,
  setEmail,
  loading,
  onSubmit,
  onBack,
}: {
  email: string;
  setEmail: (v: string) => void;
  loading: boolean;
  onSubmit: (e: React.FormEvent) => void;
  onBack: () => void;
}) {
  const t = useT();
  return (
    <>
      <h1 className="font-display text-2xl font-bold">{t("auth.resetPassword")}</h1>
      <form onSubmit={onSubmit} className="mt-4 space-y-3">
        <div className="space-y-1.5">
          <Label htmlFor="reset-email">{t("auth.email")}</Label>
          <Input id="reset-email" required type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </div>
        <Button type="submit" disabled={loading} className="w-full">
          {loading ? t("common.loading") : t("auth.resetPassword")}
        </Button>
      </form>
      <button onClick={onBack} className="mt-4 text-sm font-medium text-primary hover:underline">
        {t("auth.backToSignIn")}
      </button>
    </>
  );
}

function ResetSent({ onBack }: { onBack: () => void }) {
  const t = useT();
  return (
    <>
      <h1 className="font-display text-2xl font-bold">{t("auth.resetPasswordSent")} 📬</h1>
      <p className="mt-2 text-sm text-muted-foreground">{t("auth.resetPasswordBody")}</p>
      <Button onClick={onBack} className="mt-6 w-full">
        {t("auth.backToSignIn")}
      </Button>
    </>
  );
}
