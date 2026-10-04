import React, { useEffect, useState, type FormEvent } from "react";
import {
  Mail,
  Lock,
  User,
  Eye,
  EyeOff,
  ArrowLeft,
  UserCheck,
  AlertCircle,
  Loader2,
  CheckCircle2,
  Database,
  Sparkles,
  ArrowRight,
  Trash2,
} from "lucide-react";
import BrandLogo from "../components/BrandLogo";
import { siteConfig } from "../config/site";
import { useAuth } from "../context/useAuth.ts";
import { authService } from "../services/authService.ts";
import { migrationService, type GuestDataSummary } from "../services/migrationService.ts";
import { ApiError } from "../lib/apiClient.ts";
import { useSignIn, useSignUp, useAuth as useClerkAuth, useUser, useClerk } from "@clerk/clerk-react";
import { isClerkConfigured } from "../lib/clerk.ts";

interface AuthPageProps {
  initialMode?: "signin" | "signup";
  onNavigate?: (path: string) => void;
  onGuestAccess?: () => void;
}

interface SignInErrors {
  email?: string;
  password?: string;
  general?: string;
}

interface SignUpErrors {
  name?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
  general?: string;
}

const GoogleIcon: React.FC<{ className?: string }> = ({ className = "h-4 w-4" }) => (
  <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
    <path
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
      fill="#4285F4"
    />
    <path
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      fill="#34A853"
    />
    <path
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      fill="#FBBC05"
    />
    <path
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      fill="#EA4335"
    />
  </svg>
);

export const AuthPage: React.FC<AuthPageProps> = ({
  initialMode = "signin",
  onNavigate,
  onGuestAccess,
}) => {
  const [isSignUp, setIsSignUp] = useState(initialMode === "signup");



  // Form states
  const [signInEmail, setSignInEmail] = useState("");
  const [signInPassword, setSignInPassword] = useState("");
  const [showSignInPassword, setShowSignInPassword] = useState(false);
  const [signInErrors, setSignInErrors] = useState<SignInErrors>({});
  const [isSignInSubmitting, setIsSignInSubmitting] = useState(false);
  const [signInSuccess, setSignInSuccess] = useState(false);

  const [signUpName, setSignUpName] = useState("");
  const [signUpEmail, setSignUpEmail] = useState("");
  const [signUpPassword, setSignUpPassword] = useState("");
  const [signUpConfirmPassword, setSignUpConfirmPassword] = useState("");
  const [showSignUpPassword, setShowSignUpPassword] = useState(false);
  const [showSignUpConfirmPassword, setShowSignUpConfirmPassword] = useState(false);
  const [signUpErrors, setSignUpErrors] = useState<SignUpErrors>({});
  const [isSignUpSubmitting, setIsSignUpSubmitting] = useState(false);
  const [signUpSuccess, setSignUpSuccess] = useState(false);

  // Guest Data Migration states
  const [showMigrationModal, setShowMigrationModal] = useState(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      return params.get("migrate") === "true" && migrationService.checkHasGuestData();
    }
    return false;
  });
  const [migrationSummary, setMigrationSummary] = useState<GuestDataSummary>(() => {
    return migrationService.getGuestDataSummary();
  });
  const [isMigrating, setIsMigrating] = useState(false);
  const [migrationSuccess, setMigrationSuccess] = useState(false);
  const [migrationSuccessMessage, setMigrationSuccessMessage] = useState("");
  const [migrationError, setMigrationError] = useState<string | null>(null);
  const [showDiscardConfirm, setShowDiscardConfirm] = useState(false);
  const [migrationIdempotencyKey] = useState(() => `mig-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`);

  const authContext = useAuth();
  const { signIn, isLoaded: isSignInLoaded } = useSignIn();
  const { signUp, isLoaded: isSignUpLoaded } = useSignUp();
  const { isSignedIn: isClerkSignedIn } = useClerkAuth();
  const { user: clerkUser } = useUser();
  const { signOut } = useClerk();
  const [isGoogleLoading, setIsGoogleLoading] = useState(false);
  const [googleError, setGoogleError] = useState<string | null>(null);

  // Check if returning from OAuth redirect with guest data or already authenticated
  useEffect(() => {
    if (authContext?.isAuthenticated || (isClerkSignedIn && clerkUser)) {
      if (migrationService.checkHasGuestData()) {
        const timer = setTimeout(() => setShowMigrationModal(true), 0);
        return () => clearTimeout(timer);
      } else {
        if (onNavigate) onNavigate(siteConfig.links.dashboard);
      }
    }
  }, [authContext?.isAuthenticated, isClerkSignedIn, clerkUser, onNavigate]);

  const handleGoogleAuth = async (mode: "signin" | "signup") => {
    if (isGoogleLoading || isSignInSubmitting || isSignUpSubmitting) return;

    if (!isClerkConfigured()) {
      setGoogleError(
        "Google Sign-In is unavailable. Clerk Publishable Key is missing or unconfigured."
      );
      return;
    }

    // If already signed into Clerk, proceed directly to workspace or migration
    if (isClerkSignedIn && clerkUser) {
      if (migrationService.checkHasGuestData()) {
        setShowMigrationModal(true);
      } else if (onNavigate) {
        onNavigate(siteConfig.links.dashboard);
      }
      return;
    }

    setIsGoogleLoading(true);
    setGoogleError(null);

    try {
      const callbackUrl =
        typeof window !== "undefined"
          ? `${window.location.origin}/sso-callback`
          : "/sso-callback";

      if (mode === "signup" && signUp) {
        await signUp.authenticateWithRedirect({
          strategy: "oauth_google",
          redirectUrl: callbackUrl,
          redirectUrlComplete: callbackUrl,
        });
      } else if (signIn) {
        await signIn.authenticateWithRedirect({
          strategy: "oauth_google",
          redirectUrl: callbackUrl,
          redirectUrlComplete: callbackUrl,
        });
      } else {
        throw new Error("Clerk authentication is initializing. Please try again.");
      }
    } catch (err: unknown) {
      setIsGoogleLoading(false);
      const isSessionExists =
        (typeof err === "object" &&
          err !== null &&
          "errors" in err &&
          Array.isArray((err as { errors: Array<{ code?: string; message?: string }> }).errors) &&
          (err as { errors: Array<{ code?: string; message?: string }> }).errors.some(
            (e) => e.code === "session_exists" || /already signed in/i.test(e.message || "")
          )) ||
        (err instanceof Error && /already signed in/i.test(err.message));

      if (isSessionExists) {
        // Clerk session already exists! Seamlessly navigate to dashboard or show migration
        if (migrationService.checkHasGuestData()) {
          setShowMigrationModal(true);
        } else if (onNavigate) {
          onNavigate(siteConfig.links.dashboard);
        }
        return;
      }

      const message =
        err && typeof err === "object" && "errors" in err && Array.isArray((err as { errors: unknown[] }).errors)
          ? ((err as { errors: Array<{ longMessage?: string; message?: string }> }).errors[0]?.longMessage ||
             (err as { errors: Array<{ longMessage?: string; message?: string }> }).errors[0]?.message ||
             "Failed to initiate Google authentication. Please try again.")
          : err instanceof Error
          ? err.message
          : "Failed to initiate Google authentication. Please try again.";
      setGoogleError(message);
    }
  };

  // Switch modes and update URL cleanly
  const handleModeSwitch = (toSignUp: boolean) => {
    setIsSignUp(toSignUp);
    setSignInErrors({});
    setSignUpErrors({});
    setGoogleError(null);
    if (onNavigate) {
      onNavigate(toSignUp ? siteConfig.links.signup : siteConfig.links.login);
    }
  };

  const handleGuestClick = (e: React.MouseEvent) => {
    e.preventDefault();
    if (authContext) {
      authContext.enterGuestMode();
    } else {
      authService.clearLocalSession();
      try {
        localStorage.setItem("pracprep_user", JSON.stringify({ isGuest: true }));
      } catch {}
    }
    if (onGuestAccess) {
      onGuestAccess();
    } else if (onNavigate) {
      onNavigate(siteConfig.links.guest);
    }
  };

  const handlePerformMigration = async () => {
    if (isMigrating) return;
    setIsMigrating(true);
    setMigrationError(null);

    try {
      const response = await migrationService.migrateGuestData(migrationIdempotencyKey);
      setIsMigrating(false);
      setMigrationSuccess(true);
      setMigrationSuccessMessage(
        `Successfully transferred ${response.experimentsMigrated} experiment(s) and ${response.vivaSessionsMigrated} viva session(s) to your account.`
      );
      setTimeout(() => {
        setShowMigrationModal(false);
        if (onNavigate) onNavigate(siteConfig.links.dashboard);
      }, 1500);
    } catch (err: unknown) {
      setIsMigrating(false);
      const msg =
        err instanceof ApiError
          ? err.message
          : "Migration failed. Your guest data is safely preserved on this device. Please try again.";
      setMigrationError(msg);
    }
  };

  const handleDiscardGuestData = () => {
    migrationService.discardGuestData();
    setShowMigrationModal(false);
    if (onNavigate) onNavigate(siteConfig.links.dashboard);
  };

  const handleSkipMigration = () => {
    setShowMigrationModal(false);
    if (onNavigate) onNavigate(siteConfig.links.dashboard);
  };

  const validateEmail = (email: string) => {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  };

  const handleSignInSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (isSignInSubmitting || signInSuccess) return;

    const errors: SignInErrors = {};

    if (!signInEmail.trim()) {
      errors.email = "Email address is required";
    } else if (!validateEmail(signInEmail)) {
      errors.email = "Please enter a valid academic or university email";
    }

    if (!signInPassword) {
      errors.password = "Password is required";
    }

    setSignInErrors(errors);

    if (Object.keys(errors).length === 0) {
      setIsSignInSubmitting(true);
      try {
        if (authContext) {
          await authContext.login({
            email: signInEmail.trim(),
            password: signInPassword,
          });
        } else {
          await authService.login({
            email: signInEmail.trim(),
            password: signInPassword,
          });
        }

        setIsSignInSubmitting(false);

        if (migrationService.checkHasGuestData()) {
          setMigrationSummary(migrationService.getGuestDataSummary());
          setShowMigrationModal(true);
        } else {
          setSignInSuccess(true);
          setTimeout(() => {
            if (onNavigate) onNavigate(siteConfig.links.dashboard);
          }, 1200);
        }
      } catch (err: unknown) {
        setIsSignInSubmitting(false);
        const message =
          err instanceof ApiError
            ? err.message
            : "Failed to sign in. Please verify your credentials.";
        setSignInErrors({ general: message });
      }
    }
  };

  const handleSignUpSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (isSignUpSubmitting || signUpSuccess) return;

    const errors: SignUpErrors = {};

    if (!signUpName.trim()) {
      errors.name = "Full name is required";
    } else if (signUpName.trim().length < 2) {
      errors.name = "Name must be at least 2 characters";
    }

    if (!signUpEmail.trim()) {
      errors.email = "Email address is required";
    } else if (!validateEmail(signUpEmail)) {
      errors.email = "Please enter a valid university or student email";
    }

    if (!signUpPassword) {
      errors.password = "Password is required";
    } else if (signUpPassword.length < 8) {
      errors.password = "Password must be at least 8 characters long";
    }

    if (!signUpConfirmPassword) {
      errors.confirmPassword = "Confirm password is required";
    } else if (signUpPassword !== signUpConfirmPassword) {
      errors.confirmPassword = "Passwords do not match";
    }

    setSignUpErrors(errors);

    if (Object.keys(errors).length === 0) {
      setIsSignUpSubmitting(true);
      try {
        if (authContext) {
          await authContext.register({
            email: signUpEmail.trim(),
            password: signUpPassword,
            full_name: signUpName.trim(),
          });
        } else {
          await authService.register({
            email: signUpEmail.trim(),
            password: signUpPassword,
            full_name: signUpName.trim(),
          });
        }

        setIsSignUpSubmitting(false);

        if (migrationService.checkHasGuestData()) {
          setMigrationSummary(migrationService.getGuestDataSummary());
          setShowMigrationModal(true);
        } else {
          setSignUpSuccess(true);
          setTimeout(() => {
            if (onNavigate) onNavigate(siteConfig.links.dashboard);
          }, 1200);
        }
      } catch (err: unknown) {
        setIsSignUpSubmitting(false);
        const message =
          err instanceof ApiError
            ? err.message
            : "Failed to create account. Please try again.";
        setSignUpErrors({ general: message });
      }
    }
  };

  return (
    <div className="pracprep-auth-wrapper min-h-screen w-full bg-neutral-50/70 flex flex-col justify-between py-6 px-4 sm:px-6 lg:px-8 selection:bg-emerald-100 selection:text-emerald-900 font-inter">
      {/* Top Header with Brand & Return Home */}
      <header className="mx-auto w-full max-w-7xl flex items-center justify-between py-2 mb-4 gap-2">
        <BrandLogo onClick={() => onNavigate && onNavigate("/")} />
        <a
          href="/"
          onClick={(e) => {
            e.preventDefault();
            if (onNavigate) onNavigate("/");
          }}
          className="inline-flex shrink-0 items-center gap-1.5 sm:gap-2 rounded-xl border border-neutral-300 bg-white px-2.5 sm:px-3.5 py-2 text-xs sm:text-sm font-medium text-neutral-700 shadow-2xs hover:bg-neutral-50 hover:text-neutral-950 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
        >
          <ArrowLeft className="h-4 w-4 text-neutral-500" />
          <span className="hidden sm:inline">Back to Landing Page</span>
          <span className="sm:hidden">Back</span>
        </a>
      </header>

      {/* Main Authentication Container */}
      <main className="flex-1 flex items-center justify-center w-full py-4">
        <div
          className={`auth-card-container relative w-full max-w-[1080px] min-h-[640px] bg-white rounded-3xl shadow-xl border border-neutral-200/90 overflow-hidden ${
            isSignUp ? "sign-up-mode" : ""
          }`}
        >
          {/* Internal Scoped CSS for the Split-Screen Curved Bubble Animation */}
          <style>{`
            .auth-card-container {
              position: relative;
              transition: all 0.3s ease;
            }

            .auth-card-container::before {
              content: "";
              position: absolute;
              height: 2200px;
              width: 2200px;
              top: -10%;
              right: 48%;
              transform: translateY(-50%);
              background: linear-gradient(135deg, #064e3b 0%, #047857 40%, #0f172a 100%);
              transition: 1.5s cubic-bezier(0.77, 0, 0.175, 1);
              border-radius: 50%;
              z-index: 6;
              box-shadow: 0 10px 40px rgba(6, 78, 59, 0.25);
            }

            .auth-card-container.sign-up-mode::before {
              transform: translate(100%, -50%);
              right: 52%;
            }

            .auth-forms-slider {
              position: absolute;
              top: 50%;
              transform: translate(-50%, -50%);
              left: 75%;
              width: 50%;
              transition: 1.1s 0.3s cubic-bezier(0.77, 0, 0.175, 1);
              display: grid;
              grid-template-columns: 1fr;
              z-index: 5;
            }

            .auth-card-container.sign-up-mode .auth-forms-slider {
              left: 25%;
            }

            .auth-form-panel {
              display: flex;
              flex-direction: column;
              justify-content: center;
              padding: 2.5rem 3.5rem;
              transition: opacity 0.3s 0.4s, transform 0.4s 0.3s;
              overflow-y: auto;
              max-height: 640px;
              grid-column: 1 / 2;
              grid-row: 1 / 2;
            }

            .auth-form-panel.sign-up-form {
              opacity: 0;
              pointer-events: none;
              z-index: 1;
              transform: scale(0.96);
            }

            .auth-form-panel.sign-in-form {
              opacity: 1;
              pointer-events: auto;
              z-index: 2;
              transform: scale(1);
            }

            .auth-card-container.sign-up-mode .auth-form-panel.sign-up-form {
              opacity: 1;
              pointer-events: auto;
              z-index: 2;
              transform: scale(1);
            }

            .auth-card-container.sign-up-mode .auth-form-panel.sign-in-form {
              opacity: 0;
              pointer-events: none;
              z-index: 1;
              transform: scale(0.96);
            }

            .auth-welcome-panels {
              position: absolute;
              height: 100%;
              width: 100%;
              top: 0;
              left: 0;
              display: grid;
              grid-template-columns: repeat(2, 1fr);
              pointer-events: none;
            }

            .welcome-panel {
              display: flex;
              flex-direction: column;
              align-items: center;
              justify-content: center;
              text-align: center;
              z-index: 6;
              padding: 3rem 14%;
            }

            .welcome-panel.left-panel {
              pointer-events: all;
            }

            .welcome-panel.right-panel {
              pointer-events: none;
            }

            .welcome-panel .panel-content {
              color: #ffffff;
              transition: transform 0.9s cubic-bezier(0.77, 0, 0.175, 1);
              transition-delay: 0.4s;
            }

            .welcome-panel.right-panel .panel-content {
              transform: translateX(800px);
            }

            .auth-card-container.sign-up-mode .welcome-panel.left-panel .panel-content {
              transform: translateX(-800px);
            }

            .auth-card-container.sign-up-mode .welcome-panel.right-panel .panel-content {
              transform: translateX(0%);
            }

            .auth-card-container.sign-up-mode .welcome-panel.left-panel {
              pointer-events: none;
            }

            .auth-card-container.sign-up-mode .welcome-panel.right-panel {
              pointer-events: all;
            }

            /* Responsive rules for Tablet & Mobile */
            @media (max-width: 900px) {
              .auth-card-container {
                min-height: 820px;
                height: auto;
              }

              .auth-card-container::before {
                width: 1600px;
                height: 1600px;
                transform: translateX(-50%);
                left: 50%;
                bottom: 68%;
                right: initial;
                top: initial;
                transition: 1.6s ease-in-out;
              }

              .auth-card-container.sign-up-mode::before {
                transform: translate(-50%, 100%);
                bottom: 30%;
                right: initial;
              }

              .auth-forms-slider {
                width: 100%;
                top: 96%;
                transform: translate(-50%, -100%);
                transition: 1s 0.5s ease-in-out;
                left: 50% !important;
              }

              .auth-card-container.sign-up-mode .auth-forms-slider {
                top: 8%;
                transform: translate(-50%, 0);
              }

              .auth-form-panel {
                padding: 1.5rem 2rem;
              }

              .auth-welcome-panels {
                grid-template-columns: 1fr;
                grid-template-rows: 1fr 2fr 1fr;
              }

              .welcome-panel {
                padding: 1.5rem 10%;
              }

              .welcome-panel.left-panel {
                grid-row: 1 / 2;
              }

              .welcome-panel.right-panel {
                grid-row: 3 / 4;
              }

              .welcome-panel.right-panel .panel-content {
                transform: translateY(300px);
              }

              .auth-card-container.sign-up-mode .welcome-panel.left-panel .panel-content {
                transform: translateY(-300px);
              }

              .auth-card-container.sign-up-mode .welcome-panel.right-panel .panel-content {
                transform: translateY(0);
              }
            }

            @media (max-width: 580px) {
              .auth-form-panel {
                padding: 1rem 1.25rem;
              }
              .welcome-panel {
                padding: 1rem;
              }
            }
          `}</style>

          {/* Forms Slider Container (Holds Sign In and Sign Up forms) */}
          <div className="auth-forms-slider">
            {/* 1. SIGN IN FORM */}
            <div className="auth-form-panel sign-in-form">
              <div className="w-full max-w-[380px] mx-auto">
                <div className="text-center sm:text-left mb-6">
                  <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900 font-jakarta">
                    Welcome Back
                  </h1>
                  <p className="mt-1 text-xs sm:text-sm text-neutral-500">
                    Continue your lab preparation journey.
                  </p>
                </div>

                {signInSuccess && (
                  <div className="mb-4 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-xs sm:text-sm text-emerald-800 animate-in fade-in">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    <span>Authentication successful! Directing to workspace...</span>
                  </div>
                )}

                {signInErrors.general && (
                  <div className="mb-4 flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 p-3 text-xs sm:text-sm text-red-800 animate-in fade-in">
                    <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />
                    <span>{signInErrors.general}</span>
                  </div>
                )}

                {isClerkSignedIn && clerkUser && (
                  <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50/90 p-3.5 text-xs text-emerald-900 shadow-2xs">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold truncate">
                          Signed in as {clerkUser.primaryEmailAddress?.emailAddress || clerkUser.fullName}
                        </p>
                        <p className="text-[11px] text-emerald-700">Google authentication is active.</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            if (migrationService.checkHasGuestData()) {
                              setShowMigrationModal(true);
                            } else if (onNavigate) {
                              onNavigate(siteConfig.links.dashboard);
                            }
                          }}
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-700 transition-colors"
                        >
                          Workspace
                        </button>
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              localStorage.removeItem("pracprep_user");
                            } catch {}
                            try {
                              await signOut();
                            } catch {}
                          }}
                          className="rounded-lg border border-emerald-300 bg-white px-2 py-1.5 font-medium text-emerald-800 hover:bg-emerald-100 transition-colors"
                        >
                          Sign Out
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <form onSubmit={handleSignInSubmit} noValidate className="space-y-4">
                  {/* Email Field */}
                  <div>
                    <div
                      className={`relative flex items-center rounded-xl bg-neutral-100/80 border transition-all ${
                        signInErrors.email
                          ? "border-red-400 bg-red-50/20 ring-2 ring-red-200"
                          : "border-neutral-200/90 focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20 focus-within:bg-white"
                      }`}
                    >
                      <div className="pl-3.5 pr-2 text-neutral-400">
                        <Mail className="h-4 w-4" />
                      </div>
                      <input
                        type="email"
                        id="signin-email"
                        value={signInEmail}
                        onChange={(e) => {
                          setSignInEmail(e.target.value);
                          if (signInErrors.email) setSignInErrors({ ...signInErrors, email: undefined });
                        }}
                        placeholder="Academic or Student Email"
                        autoComplete="email"
                        className="w-full bg-transparent py-3 pr-4 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none"
                        aria-invalid={!!signInErrors.email}
                        aria-describedby={signInErrors.email ? "signin-email-error" : undefined}
                      />
                    </div>
                    {signInErrors.email && (
                      <p id="signin-email-error" className="mt-1 flex items-center gap-1 text-xs text-red-600">
                        <AlertCircle className="h-3 w-3" />
                        <span>{signInErrors.email}</span>
                      </p>
                    )}
                  </div>

                  {/* Password Field */}
                  <div>
                    <div
                      className={`relative flex items-center rounded-xl bg-neutral-100/80 border transition-all ${
                        signInErrors.password
                          ? "border-red-400 bg-red-50/20 ring-2 ring-red-200"
                          : "border-neutral-200/90 focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20 focus-within:bg-white"
                      }`}
                    >
                      <div className="pl-3.5 pr-2 text-neutral-400">
                        <Lock className="h-4 w-4" />
                      </div>
                      <input
                        type={showSignInPassword ? "text" : "password"}
                        id="signin-password"
                        value={signInPassword}
                        onChange={(e) => {
                          setSignInPassword(e.target.value);
                          if (signInErrors.password) setSignInErrors({ ...signInErrors, password: undefined });
                        }}
                        placeholder="Password"
                        autoComplete="current-password"
                        className="w-full bg-transparent py-3 pr-10 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none"
                        aria-invalid={!!signInErrors.password}
                        aria-describedby={signInErrors.password ? "signin-password-error" : undefined}
                      />
                      <button
                        type="button"
                        onClick={() => setShowSignInPassword(!showSignInPassword)}
                        className="absolute right-3 text-neutral-400 hover:text-neutral-700 transition-colors"
                        aria-label={showSignInPassword ? "Hide password" : "Show password"}
                      >
                        {showSignInPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {signInErrors.password && (
                      <p id="signin-password-error" className="mt-1 flex items-center gap-1 text-xs text-red-600">
                        <AlertCircle className="h-3 w-3" />
                        <span>{signInErrors.password}</span>
                      </p>
                    )}
                  </div>

                  {/* Forgot Password Link */}
                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => alert("Password reset link will be sent to your university email address.")}
                      className="text-xs font-medium text-emerald-700 hover:text-emerald-800 hover:underline"
                    >
                      Forgot password?
                    </button>
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    disabled={isSignInSubmitting || signInSuccess}
                    className="w-full h-11 inline-flex items-center justify-center rounded-xl bg-neutral-900 px-4 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:bg-emerald-700 hover:shadow-md active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
                  >
                    {isSignInSubmitting ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Signing in...
                      </span>
                    ) : (
                      "Sign In"
                    )}
                  </button>

                  {/* Divider */}
                  <div className="relative my-4 flex items-center justify-center">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-neutral-200" />
                    </div>
                    <span className="relative bg-white px-3 text-[11px] font-medium uppercase tracking-wider text-neutral-400">
                      Or continue with
                    </span>
                  </div>

                  {/* Google Sign-in Button */}
                  {googleError && !isSignUp && (
                    <div className="mb-2 p-2.5 rounded-xl border border-red-200 bg-red-50 text-xs text-red-700 flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                      <span>{googleError}</span>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => handleGoogleAuth("signin")}
                    disabled={
                      isGoogleLoading ||
                      isSignInSubmitting ||
                      (!isSignInLoaded && isClerkConfigured())
                    }
                    aria-label="Continue with Google"
                    aria-busy={isGoogleLoading}
                    className="w-full h-11 inline-flex items-center justify-center gap-2.5 rounded-xl border border-neutral-200 bg-white px-4 text-sm font-medium text-neutral-700 shadow-2xs hover:bg-neutral-50 hover:border-neutral-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {isGoogleLoading && !isSignUp ? (
                      <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
                    ) : (
                      <GoogleIcon className="h-4 w-4" />
                    )}
                    <span>
                      {isGoogleLoading && !isSignUp
                        ? "Connecting to Google..."
                        : "Continue with Google"}
                    </span>
                  </button>

                  {/* Guest Access Highlight */}
                  <div className="pt-2">
                    <button
                      type="button"
                      onClick={handleGuestClick}
                      className="w-full rounded-xl border border-emerald-200 bg-emerald-50/60 p-2.5 text-center transition-all hover:bg-emerald-100/60 hover:border-emerald-300 group"
                    >
                      <div className="flex items-center justify-center gap-2 text-xs font-semibold text-emerald-800">
                        <UserCheck className="h-3.5 w-3.5 text-emerald-600" />
                        <span>Continue as Guest</span>
                        <span className="text-[10px] bg-white border border-emerald-200 rounded-full px-2 py-0.5 text-emerald-700">
                          Instant access
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-emerald-700/80">
                        Explore PracPrep without creating an account.
                      </p>
                    </button>
                  </div>

                  {/* Small Mobile Switch */}
                  <div className="pt-2 text-center">
                    <p className="text-xs text-neutral-500">
                      Don&apos;t have an account?{" "}
                      <button
                        type="button"
                        onClick={() => handleModeSwitch(true)}
                        className="font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                      >
                        Sign up
                      </button>
                    </p>
                  </div>
                </form>
              </div>
            </div>

            {/* 2. SIGN UP FORM */}
            <div className="auth-form-panel sign-up-form">
              <div className="w-full max-w-[380px] mx-auto">
                <div className="text-center sm:text-left mb-5">
                  <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-neutral-900 font-jakarta">
                    Create Account
                  </h1>
                  <p className="mt-1 text-xs sm:text-sm text-neutral-500">
                    Start preparing smarter for your laboratory sessions.
                  </p>
                </div>

                {signUpSuccess && (
                  <div className="mb-4 flex items-center gap-2 rounded-xl bg-emerald-50 border border-emerald-200 p-3 text-xs sm:text-sm text-emerald-800 animate-in fade-in">
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                    <span>Account created! Redirecting to workspace...</span>
                  </div>
                )}

                {signUpErrors.general && (
                  <div className="mb-4 flex items-center gap-2 rounded-xl bg-red-50 border border-red-200 p-3 text-xs sm:text-sm text-red-800 animate-in fade-in">
                    <AlertCircle className="h-4 w-4 text-red-600 shrink-0" />
                    <span>{signUpErrors.general}</span>
                  </div>
                )}

                {isClerkSignedIn && clerkUser && (
                  <div className="mb-4 rounded-xl border border-emerald-200 bg-emerald-50/90 p-3.5 text-xs text-emerald-900 shadow-2xs">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-semibold truncate">
                          Signed in as {clerkUser.primaryEmailAddress?.emailAddress || clerkUser.fullName}
                        </p>
                        <p className="text-[11px] text-emerald-700">Google authentication is active.</p>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          type="button"
                          onClick={() => {
                            if (migrationService.checkHasGuestData()) {
                              setShowMigrationModal(true);
                            } else if (onNavigate) {
                              onNavigate(siteConfig.links.dashboard);
                            }
                          }}
                          className="rounded-lg bg-emerald-600 px-3 py-1.5 font-semibold text-white hover:bg-emerald-700 transition-colors"
                        >
                          Workspace
                        </button>
                        <button
                          type="button"
                          onClick={async () => {
                            try {
                              localStorage.removeItem("pracprep_user");
                            } catch {}
                            try {
                              await signOut();
                            } catch {}
                          }}
                          className="rounded-lg border border-emerald-300 bg-white px-2 py-1.5 font-medium text-emerald-800 hover:bg-emerald-100 transition-colors"
                        >
                          Sign Out
                        </button>
                      </div>
                    </div>
                  </div>
                )}

                <form onSubmit={handleSignUpSubmit} noValidate className="space-y-3.5">
                  {/* Full Name */}
                  <div>
                    <div
                      className={`relative flex items-center rounded-xl bg-neutral-100/80 border transition-all ${
                        signUpErrors.name
                          ? "border-red-400 bg-red-50/20 ring-2 ring-red-200"
                          : "border-neutral-200/90 focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20 focus-within:bg-white"
                      }`}
                    >
                      <div className="pl-3.5 pr-2 text-neutral-400">
                        <User className="h-4 w-4" />
                      </div>
                      <input
                        type="text"
                        id="signup-name"
                        value={signUpName}
                        onChange={(e) => {
                          setSignUpName(e.target.value);
                          if (signUpErrors.name) setSignUpErrors({ ...signUpErrors, name: undefined });
                        }}
                        placeholder="Full Name (e.g. Alex Morgan)"
                        autoComplete="name"
                        className="w-full bg-transparent py-2.5 pr-4 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none"
                        aria-invalid={!!signUpErrors.name}
                        aria-describedby={signUpErrors.name ? "signup-name-error" : undefined}
                      />
                    </div>
                    {signUpErrors.name && (
                      <p id="signup-name-error" className="mt-1 flex items-center gap-1 text-xs text-red-600">
                        <AlertCircle className="h-3 w-3" />
                        <span>{signUpErrors.name}</span>
                      </p>
                    )}
                  </div>

                  {/* Email */}
                  <div>
                    <div
                      className={`relative flex items-center rounded-xl bg-neutral-100/80 border transition-all ${
                        signUpErrors.email
                          ? "border-red-400 bg-red-50/20 ring-2 ring-red-200"
                          : "border-neutral-200/90 focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20 focus-within:bg-white"
                      }`}
                    >
                      <div className="pl-3.5 pr-2 text-neutral-400">
                        <Mail className="h-4 w-4" />
                      </div>
                      <input
                        type="email"
                        id="signup-email"
                        value={signUpEmail}
                        onChange={(e) => {
                          setSignUpEmail(e.target.value);
                          if (signUpErrors.email) setSignUpErrors({ ...signUpErrors, email: undefined });
                        }}
                        placeholder="University Email Address"
                        autoComplete="email"
                        className="w-full bg-transparent py-2.5 pr-4 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none"
                        aria-invalid={!!signUpErrors.email}
                        aria-describedby={signUpErrors.email ? "signup-email-error" : undefined}
                      />
                    </div>
                    {signUpErrors.email && (
                      <p id="signup-email-error" className="mt-1 flex items-center gap-1 text-xs text-red-600">
                        <AlertCircle className="h-3 w-3" />
                        <span>{signUpErrors.email}</span>
                      </p>
                    )}
                  </div>

                  {/* Password */}
                  <div>
                    <div
                      className={`relative flex items-center rounded-xl bg-neutral-100/80 border transition-all ${
                        signUpErrors.password
                          ? "border-red-400 bg-red-50/20 ring-2 ring-red-200"
                          : "border-neutral-200/90 focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20 focus-within:bg-white"
                      }`}
                    >
                      <div className="pl-3.5 pr-2 text-neutral-400">
                        <Lock className="h-4 w-4" />
                      </div>
                      <input
                        type={showSignUpPassword ? "text" : "password"}
                        id="signup-password"
                        value={signUpPassword}
                        onChange={(e) => {
                          setSignUpPassword(e.target.value);
                          if (signUpErrors.password) setSignUpErrors({ ...signUpErrors, password: undefined });
                        }}
                        placeholder="Password (minimum 8 characters)"
                        autoComplete="new-password"
                        className="w-full bg-transparent py-2.5 pr-10 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none"
                        aria-invalid={!!signUpErrors.password}
                        aria-describedby={signUpErrors.password ? "signup-password-error" : undefined}
                      />
                      <button
                        type="button"
                        onClick={() => setShowSignUpPassword(!showSignUpPassword)}
                        className="absolute right-3 text-neutral-400 hover:text-neutral-700 transition-colors"
                        aria-label={showSignUpPassword ? "Hide password" : "Show password"}
                      >
                        {showSignUpPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {signUpErrors.password && (
                      <p id="signup-password-error" className="mt-1 flex items-center gap-1 text-xs text-red-600">
                        <AlertCircle className="h-3 w-3" />
                        <span>{signUpErrors.password}</span>
                      </p>
                    )}
                  </div>

                  {/* Confirm Password */}
                  <div>
                    <div
                      className={`relative flex items-center rounded-xl bg-neutral-100/80 border transition-all ${
                        signUpErrors.confirmPassword
                          ? "border-red-400 bg-red-50/20 ring-2 ring-red-200"
                          : "border-neutral-200/90 focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/20 focus-within:bg-white"
                      }`}
                    >
                      <div className="pl-3.5 pr-2 text-neutral-400">
                        <Lock className="h-4 w-4" />
                      </div>
                      <input
                        type={showSignUpConfirmPassword ? "text" : "password"}
                        id="signup-confirm-password"
                        value={signUpConfirmPassword}
                        onChange={(e) => {
                          setSignUpConfirmPassword(e.target.value);
                          if (signUpErrors.confirmPassword) setSignUpErrors({ ...signUpErrors, confirmPassword: undefined });
                        }}
                        placeholder="Confirm Password"
                        autoComplete="new-password"
                        className="w-full bg-transparent py-2.5 pr-10 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none"
                        aria-invalid={!!signUpErrors.confirmPassword}
                        aria-describedby={signUpErrors.confirmPassword ? "signup-confirm-error" : undefined}
                      />
                      <button
                        type="button"
                        onClick={() => setShowSignUpConfirmPassword(!showSignUpConfirmPassword)}
                        className="absolute right-3 text-neutral-400 hover:text-neutral-700 transition-colors"
                        aria-label={showSignUpConfirmPassword ? "Hide confirm password" : "Show confirm password"}
                      >
                        {showSignUpConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                    {signUpErrors.confirmPassword && (
                      <p id="signup-confirm-error" className="mt-1 flex items-center gap-1 text-xs text-red-600">
                        <AlertCircle className="h-3 w-3" />
                        <span>{signUpErrors.confirmPassword}</span>
                      </p>
                    )}
                  </div>

                  {/* Submit Button */}
                  <button
                    type="submit"
                    disabled={isSignUpSubmitting || signUpSuccess}
                    className="w-full h-11 inline-flex items-center justify-center rounded-xl bg-neutral-900 px-4 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:bg-emerald-700 hover:shadow-md active:scale-[0.98] disabled:opacity-60 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
                  >
                    {isSignUpSubmitting ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        Creating Account...
                      </span>
                    ) : (
                      "Create Account"
                    )}
                  </button>

                  {/* Divider */}
                  <div className="relative my-3 flex items-center justify-center">
                    <div className="absolute inset-0 flex items-center">
                      <div className="w-full border-t border-neutral-200" />
                    </div>
                    <span className="relative bg-white px-3 text-[11px] font-medium uppercase tracking-wider text-neutral-400">
                      Or sign up with
                    </span>
                  </div>

                  {/* Google Sign-up Button */}
                  {googleError && isSignUp && (
                    <div className="mb-2 p-2.5 rounded-xl border border-red-200 bg-red-50 text-xs text-red-700 flex items-start gap-2">
                      <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                      <span>{googleError}</span>
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => handleGoogleAuth("signup")}
                    disabled={
                      isGoogleLoading ||
                      isSignUpSubmitting ||
                      (!isSignUpLoaded && isClerkConfigured())
                    }
                    aria-label="Sign up with Google"
                    aria-busy={isGoogleLoading}
                    className="w-full h-11 inline-flex items-center justify-center gap-2.5 rounded-xl border border-neutral-200 bg-white px-4 text-sm font-medium text-neutral-700 shadow-2xs hover:bg-neutral-50 hover:border-neutral-300 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 disabled:opacity-60 disabled:cursor-not-allowed"
                  >
                    {isGoogleLoading && isSignUp ? (
                      <Loader2 className="h-4 w-4 animate-spin text-emerald-600" />
                    ) : (
                      <GoogleIcon className="h-4 w-4" />
                    )}
                    <span>
                      {isGoogleLoading && isSignUp
                        ? "Connecting to Google..."
                        : "Sign up with Google"}
                    </span>
                  </button>

                  {/* Guest Access Highlight */}
                  <div className="pt-1">
                    <button
                      type="button"
                      onClick={handleGuestClick}
                      className="w-full rounded-xl border border-emerald-200 bg-emerald-50/60 p-2 text-center transition-all hover:bg-emerald-100/60 hover:border-emerald-300"
                    >
                      <div className="flex items-center justify-center gap-2 text-xs font-semibold text-emerald-800">
                        <UserCheck className="h-3.5 w-3.5 text-emerald-600" />
                        <span>Continue as Guest</span>
                        <span className="text-[10px] bg-white border border-emerald-200 rounded-full px-2 py-0.5 text-emerald-700">
                          Instant access
                        </span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-emerald-700/80">
                        Explore PracPrep without creating an account.
                      </p>
                    </button>
                  </div>

                  {/* Small Mobile Switch */}
                  <div className="pt-1 text-center">
                    <p className="text-xs text-neutral-500">
                      Already have an account?{" "}
                      <button
                        type="button"
                        onClick={() => handleModeSwitch(false)}
                        className="font-semibold text-emerald-700 hover:text-emerald-800 hover:underline"
                      >
                        Sign in
                      </button>
                    </p>
                  </div>
                </form>
              </div>
            </div>
          </div>

          {/* Dynamic Welcome Panels on the Curved Animated Shape */}
          <div className="auth-welcome-panels">
            {/* Left Welcome Panel (Visible during Sign In mode to prompt Sign Up) */}
            <div className="welcome-panel left-panel">
              <div className="panel-content max-w-sm">
                <span className="inline-block rounded-full bg-emerald-400/20 px-3 py-1 text-xs font-semibold text-emerald-200 uppercase tracking-widest mb-3 backdrop-blur-xs">
                  PracPrep Companion
                </span>
                <h2 className="text-3xl font-bold tracking-tight mb-3 font-jakarta">
                  New here?
                </h2>
                <p className="text-sm text-emerald-100/90 leading-relaxed mb-8">
                  Join PracPrep and turn your lab manuals into confident preparation.
                </p>
                <button
                  type="button"
                  onClick={() => handleModeSwitch(true)}
                  className="inline-flex h-11 items-center justify-center rounded-full border-2 border-white/90 bg-transparent px-8 text-sm font-semibold text-white tracking-wide transition-all duration-200 hover:bg-white hover:text-emerald-950 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-emerald-900"
                >
                  Create Account
                </button>
              </div>
            </div>

            {/* Right Welcome Panel (Visible during Sign Up mode to prompt Sign In) */}
            <div className="welcome-panel right-panel">
              <div className="panel-content max-w-sm">
                <span className="inline-block rounded-full bg-emerald-400/20 px-3 py-1 text-xs font-semibold text-emerald-200 uppercase tracking-widest mb-3 backdrop-blur-xs">
                  Welcome Back
                </span>
                <h2 className="text-3xl font-bold tracking-tight mb-3 font-jakarta">
                  Already with us?
                </h2>
                <p className="text-sm text-emerald-100/90 leading-relaxed mb-8">
                  Welcome back. Continue learning, practicing, and tracking your progress.
                </p>
                <button
                  type="button"
                  onClick={() => handleModeSwitch(false)}
                  className="inline-flex h-11 items-center justify-center rounded-full border-2 border-white/90 bg-transparent px-8 text-sm font-semibold text-white tracking-wide transition-all duration-200 hover:bg-white hover:text-emerald-950 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-emerald-900"
                >
                  Sign In
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="text-center text-xs text-neutral-400 py-3">
        PracPrep — From Lab Manual to Lab-Ready &copy; 2026. All rights reserved.
      </footer>

      {/* Guest Data Migration Modal */}
      {showMigrationModal && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="migration-dialog-title"
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-900/60 backdrop-blur-sm animate-in fade-in duration-200"
        >
          <div className="w-full max-w-lg bg-white rounded-2xl shadow-2xl border border-neutral-200/90 p-6 sm:p-8 space-y-6">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-emerald-50 text-emerald-600 rounded-xl flex-shrink-0 border border-emerald-100">
                <Database className="h-6 w-6" aria-hidden="true" />
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold bg-emerald-100 text-emerald-800">
                    Account Ready
                  </span>
                </div>
                <h2
                  id="migration-dialog-title"
                  className="text-xl font-bold text-neutral-900 mt-1"
                >
                  Transfer Your Guest Lab Data
                </h2>
                <p className="text-sm text-neutral-600 mt-1">
                  We found experiments and practice sessions from your guest browsing session on this browser.
                </p>
              </div>
            </div>

            {/* Data Summary Card */}
            <div className="bg-neutral-50 rounded-xl p-4 border border-neutral-200/80 space-y-3">
              <div className="text-xs font-semibold text-neutral-500 uppercase tracking-wider">
                Records Ready for Migration
              </div>
              <div className="grid grid-cols-2 gap-3 text-center">
                <div className="bg-white p-3 rounded-lg border border-neutral-200/60 shadow-sm">
                  <div className="text-2xl font-bold text-neutral-900">
                    {migrationSummary.experimentCount}
                  </div>
                  <div className="text-xs text-neutral-500 font-medium">
                    Experiment{migrationSummary.experimentCount === 1 ? "" : "s"} & Checklists
                  </div>
                </div>
                <div className="bg-white p-3 rounded-lg border border-neutral-200/60 shadow-sm">
                  <div className="text-2xl font-bold text-neutral-900">
                    {migrationSummary.vivaSessionCount}
                  </div>
                  <div className="text-xs text-neutral-500 font-medium">
                    Viva Session{migrationSummary.vivaSessionCount === 1 ? "" : "s"} & AI Feedback
                  </div>
                </div>
              </div>
            </div>

            {/* Success state */}
            {migrationSuccess && (
              <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-900 flex items-start gap-3">
                <CheckCircle2 className="h-5 w-5 text-emerald-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm">
                  <div className="font-semibold text-emerald-900">Migration Confirmed!</div>
                  <div className="text-emerald-700 text-xs mt-0.5">
                    {migrationSuccessMessage} Loading your dashboard...
                  </div>
                </div>
              </div>
            )}

            {/* Error state */}
            {migrationError && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-red-900 flex items-start gap-3">
                <AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div className="text-sm">
                  <div className="font-semibold text-red-900">Migration Incomplete</div>
                  <div className="text-red-700 text-xs mt-0.5">{migrationError}</div>
                  <div className="text-xs text-neutral-600 mt-1 font-medium">
                    Your guest data was preserved locally. You can safely retry.
                  </div>
                </div>
              </div>
            )}

            {/* Safety guarantee */}
            {!migrationSuccess && (
              <div className="p-3 bg-neutral-50 rounded-xl border border-neutral-200/60 text-xs text-neutral-600 flex items-start gap-2">
                <Sparkles className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span>
                  <strong>Data Safety:</strong> Guest data is only cleared from this device after confirmed receipt by the server.
                </span>
              </div>
            )}

            {/* Discard confirmation warning */}
            {showDiscardConfirm && !migrationSuccess && (
              <div className="p-4 bg-amber-50 border border-amber-200 rounded-xl text-amber-900 space-y-3">
                <div className="flex items-start gap-2 text-xs">
                  <AlertCircle className="h-4 w-4 text-amber-600 flex-shrink-0 mt-0.5" />
                  <span>
                    Are you sure? Discarding will permanently remove these guest experiments from this browser without adding them to your account.
                  </span>
                </div>
                <div className="flex items-center gap-2 justify-end">
                  <button
                    type="button"
                    onClick={() => setShowDiscardConfirm(false)}
                    className="px-3 py-1.5 text-xs font-medium text-neutral-700 hover:bg-neutral-100 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    id="confirm-discard-btn"
                    onClick={handleDiscardGuestData}
                    className="px-3 py-1.5 text-xs font-semibold text-white bg-red-600 hover:bg-red-700 rounded-lg shadow-sm transition-colors"
                  >
                    Yes, Discard Data
                  </button>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            {!migrationSuccess && !showDiscardConfirm && (
              <div className="space-y-3 pt-2">
                <button
                  type="button"
                  id="migrate-guest-data-btn"
                  onClick={handlePerformMigration}
                  disabled={isMigrating}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl text-sm font-semibold text-white bg-emerald-600 hover:bg-emerald-700 active:bg-emerald-800 disabled:opacity-60 shadow-md shadow-emerald-700/10 transition-all focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
                >
                  {isMigrating ? (
                    <>
                      <Loader2 className="h-4 w-4 animate-spin" />
                      Migrating Records...
                    </>
                  ) : (
                    <>
                      <ArrowRight className="h-4 w-4" />
                      {migrationError ? "Retry Migration" : "Migrate to My Account"}
                    </>
                  )}
                </button>

                <div className="flex items-center justify-between gap-3 pt-1">
                  <button
                    type="button"
                    id="discard-guest-data-btn"
                    onClick={() => setShowDiscardConfirm(true)}
                    disabled={isMigrating}
                    className="text-xs font-medium text-neutral-500 hover:text-red-600 transition-colors flex items-center gap-1.5 p-1 disabled:opacity-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    Discard Guest Data
                  </button>

                  <button
                    type="button"
                    id="skip-migration-btn"
                    onClick={handleSkipMigration}
                    disabled={isMigrating}
                    className="text-xs font-medium text-neutral-500 hover:text-neutral-800 transition-colors p-1 disabled:opacity-50"
                  >
                    Skip for Now
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default AuthPage;
