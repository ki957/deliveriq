import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { Link, Navigate, useNavigate, useParams, useSearchParams } from "react-router";
import { z } from "zod";

import { api, ApiError, isPortal, type Me, type Portal, unwrap } from "@/shared/api/client";
import { useSetMe } from "@/shared/auth/use-me";
import { Button } from "@/shared/ui/button";
import { Wordmark } from "@/shared/ui/wordmark";

const TITLES: Record<Portal, string> = {
  customer: "Customer",
  kitchen: "Kitchen",
  delivery: "Delivery",
  management: "Management",
};

// Client checks are for usability only; the backend validates everything (DDR-96).
const mobileSchema = z.object({
  mobile: z
    .string()
    .trim()
    .regex(/^[+\d\s()-]{10,20}$/, "Enter a 10-digit Indian mobile number"),
});
const codeSchema = z.object({
  code: z
    .string()
    .trim()
    .regex(/^\d{6}$/, "Enter the 6-digit code"),
  displayName: z.string().trim().max(80, "Use at most 80 characters").optional(),
  trustDevice: z.boolean(),
});
type MobileForm = z.infer<typeof mobileSchema>;
type CodeForm = z.infer<typeof codeSchema>;

export function messageFor(error: unknown): string {
  if (!(error instanceof ApiError)) return "Something went wrong. Try again.";
  switch (error.status) {
    case 400:
      return "That code is invalid or has expired. Request a new code.";
    case 422:
      return "Enter a valid Indian mobile number.";
    case 429:
      return `Too many attempts. Try again in ${error.retryAfter ?? 60} seconds.`;
    case 503:
      return "Sign-in is temporarily unavailable.";
    default:
      return "Something went wrong. Try again.";
  }
}

/** Only same-portal paths are accepted as a post-login target (no open redirect). */
export function safeNext(portal: Portal, next: string | null): string {
  return next && next.startsWith(`/${portal}`) && !next.startsWith("//") ? next : `/${portal}`;
}

export function LoginPage() {
  const params = useParams();
  if (!isPortal(params.portal)) return <Navigate to="/" replace />;
  return <LoginForm key={params.portal} portal={params.portal} />;
}

function LoginForm({ portal }: { portal: Portal }) {
  const [search] = useSearchParams();
  const navigate = useNavigate();
  const setMe = useSetMe();
  const [mobile, setMobile] = useState<string | null>(null);
  const [needName, setNeedName] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const triedTrusted = useRef(false);

  const target = safeNext(portal, search.get("next"));

  const mobileForm = useForm<MobileForm>({
    resolver: zodResolver(mobileSchema),
    defaultValues: { mobile: "" },
  });
  const codeForm = useForm<CodeForm>({
    resolver: zodResolver(codeSchema),
    defaultValues: { code: "", displayName: "", trustDevice: false },
  });

  function signedIn(me: Me) {
    setMe(me);
    navigate(target, { replace: true });
  }

  // A trusted device skips the code (DDR-98). Failure is silent: the form is shown.
  useEffect(() => {
    if (triedTrusted.current) return;
    triedTrusted.current = true;
    api.POST("/api/v1/auth/trusted-login", { body: { portal } }).then(({ data, response }) => {
      if (response.ok && data) signedIn(data);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once per mount
  }, [portal]);

  async function requestCode(values: MobileForm) {
    setError(null);
    try {
      unwrap(await api.POST("/api/v1/auth/otp/request", { body: { mobile: values.mobile, portal } }));
      setMobile(values.mobile);
    } catch (e) {
      setError(messageFor(e));
    }
  }

  async function verify(values: CodeForm) {
    setError(null);
    if (!mobile) return;
    if (needName && !values.displayName) {
      codeForm.setError("displayName", { message: "Enter your name to create your account" });
      return;
    }
    const result = await api.POST("/api/v1/auth/otp/verify", {
      body: {
        mobile,
        portal,
        code: values.code,
        trust_device: values.trustDevice,
        ...(values.displayName ? { display_name: values.displayName } : {}),
      },
    });
    if (result.response.status === 422 && portal === "customer" && !needName) {
      setNeedName(true); // new customer: same code, plus a name (DDR-97)
      return;
    }
    try {
      signedIn(unwrap(result));
    } catch (e) {
      setError(messageFor(e));
    }
  }

  return (
    <div
      data-portal={portal}
      className="flex min-h-screen items-center justify-center bg-background p-4 text-text"
    >
      <main className="w-full max-w-sm rounded-panel border border-border bg-surface p-6 shadow-sm">
        <Wordmark />
        <h1 className="mt-4 text-xl font-semibold">Sign in to {TITLES[portal]}</h1>

        {error ? (
          <p role="alert" className="mt-4 rounded-control border border-status-danger p-3 text-sm">
            {error}
          </p>
        ) : null}

        {mobile === null ? (
          <form className="mt-4 space-y-4" onSubmit={mobileForm.handleSubmit(requestCode)} noValidate>
            <div>
              <label htmlFor="mobile" className="block text-sm font-medium">
                Mobile number
              </label>
              <input
                id="mobile"
                type="tel"
                inputMode="tel"
                autoComplete="tel"
                className="mt-1 min-h-11 w-full rounded-control border border-border bg-surface px-3"
                aria-invalid={Boolean(mobileForm.formState.errors.mobile)}
                aria-describedby="mobile-hint mobile-error"
                {...mobileForm.register("mobile")}
              />
              <p id="mobile-hint" className="mt-1 text-xs text-text-muted">
                We'll send a 6-digit code to this number.
              </p>
              <p id="mobile-error" className="mt-1 text-sm">
                {mobileForm.formState.errors.mobile?.message}
              </p>
            </div>
            <Button type="submit" className="w-full" disabled={mobileForm.formState.isSubmitting}>
              Send code
            </Button>
          </form>
        ) : (
          <form className="mt-4 space-y-4" onSubmit={codeForm.handleSubmit(verify)} noValidate>
            <p className="text-sm text-text-muted">If this number can sign in here, we sent it a code.</p>
            <div>
              <label htmlFor="code" className="block text-sm font-medium">
                6-digit code
              </label>
              <input
                id="code"
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={6}
                className="mt-1 min-h-11 w-full rounded-control border border-border bg-surface px-3 tracking-widest"
                aria-invalid={Boolean(codeForm.formState.errors.code)}
                aria-describedby="code-error"
                {...codeForm.register("code")}
              />
              <p id="code-error" className="mt-1 text-sm">
                {codeForm.formState.errors.code?.message}
              </p>
            </div>
            {needName ? (
              <div>
                <label htmlFor="displayName" className="block text-sm font-medium">
                  Your name
                </label>
                <input
                  id="displayName"
                  autoComplete="name"
                  className="mt-1 min-h-11 w-full rounded-control border border-border bg-surface px-3"
                  aria-describedby="name-hint name-error"
                  {...codeForm.register("displayName")}
                />
                <p id="name-hint" className="mt-1 text-xs text-text-muted">
                  New number: enter your name to create your account.
                </p>
                <p id="name-error" className="mt-1 text-sm">
                  {codeForm.formState.errors.displayName?.message}
                </p>
              </div>
            ) : null}
            <label className="flex min-h-11 items-center gap-2 text-sm">
              <input type="checkbox" className="size-5" {...codeForm.register("trustDevice")} />
              Trust this device for 7 days
            </label>
            <Button type="submit" className="w-full" disabled={codeForm.formState.isSubmitting}>
              Sign in
            </Button>
            <Button variant="ghost" className="w-full" onClick={() => setMobile(null)}>
              Use a different number
            </Button>
          </form>
        )}

        <p className="mt-6 text-center text-sm">
          <Link to="/" className="underline">
            Choose a different portal
          </Link>
        </p>
      </main>
    </div>
  );
}
