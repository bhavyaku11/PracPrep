import React, { useEffect, useState } from "react";
import { AuthenticateWithRedirectCallback, useAuth as useClerkAuth, useUser } from "@clerk/clerk-react";
import { Loader2, AlertCircle, ArrowLeft } from "lucide-react";
import BrandLogo from "../components/BrandLogo";
import { useAuth } from "../context/useAuth";
import { migrationService } from "../services/migrationService";

interface SSOCallbackPageProps {
  onNavigate: (path: string) => void;
}

export const SSOCallbackPage: React.FC<SSOCallbackPageProps> = ({ onNavigate }) => {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user: clerkUser } = useUser();
  const { syncClerkSession } = useAuth();
  const [syncError, setSyncError] = useState<string | null>(() => {
    if (typeof window !== "undefined") {
      const params = new URLSearchParams(window.location.search);
      const errorParam = params.get("error") || params.get("error_description");
      if (errorParam) {
        return errorParam === "access_denied"
          ? "Sign-in was cancelled or access was denied."
          : `Authentication provider error: ${errorParam}`;
      }
    }
    return null;
  });
  const [isProcessing, setIsProcessing] = useState(() => !syncError);

  useEffect(() => {
    if (syncError || !isLoaded) return;

    if (isSignedIn && clerkUser) {
      let isMounted = true;

      const performSync = async () => {
        try {
          const token = await getToken();
          if (!token) {
            throw new Error("Unable to retrieve session token from Clerk.");
          }

          const email = clerkUser.primaryEmailAddress?.emailAddress;
          const fullName = clerkUser.fullName || clerkUser.firstName || undefined;

          await syncClerkSession({
            clerkToken: token,
            email,
            fullName,
          });

          if (!isMounted) return;

          // Check if guest lab data exists to offer migration
          if (migrationService.checkHasGuestData()) {
            onNavigate("/login?migrate=true");
          } else {
            onNavigate("/dashboard");
          }
        } catch (err: unknown) {
          if (!isMounted) return;
          console.error("SSO Callback sync failed:", err);
          // If Clerk authentication succeeded, proceed to dashboard or migration rather than stranding the user
          if (clerkUser) {
            if (migrationService.checkHasGuestData()) {
              onNavigate("/login?migrate=true");
            } else {
              onNavigate("/dashboard");
            }
            return;
          }
          const message =
            err instanceof Error ? err.message : "Failed to synchronize your account session.";
          setSyncError(message);
          setIsProcessing(false);
        }
      };

      void performSync();

      return () => {
        isMounted = false;
      };
    }
  }, [isLoaded, isSignedIn, clerkUser, getToken, syncClerkSession, onNavigate, syncError]);

  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center bg-neutral-50 px-4 py-12 selection:bg-emerald-100 selection:text-emerald-900">
      {/* Background decorative gradient */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(ellipse_80%_80%_at_50%_-20%,rgba(16,185,129,0.1),rgba(255,255,255,0))]" />

      {/* Clerk internal redirect callback processor */}
      <div className="hidden" aria-hidden="true">
        <AuthenticateWithRedirectCallback />
      </div>

      <div className="w-full max-w-md rounded-2xl border border-neutral-200/80 bg-white p-8 shadow-xl shadow-neutral-900/5 text-center">
        <div className="mb-6 flex justify-center">
          <BrandLogo size="lg" />
        </div>

        {syncError ? (
          <div className="space-y-4">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600">
              <AlertCircle className="h-6 w-6" />
            </div>
            <h2 className="text-lg font-semibold text-neutral-900">Authentication Failed</h2>
            <p className="text-sm text-neutral-600">{syncError}</p>
            <div className="pt-2">
              <button
                type="button"
                onClick={() => onNavigate("/login")}
                className="inline-flex items-center justify-center gap-2 rounded-xl bg-neutral-900 px-5 py-2.5 text-sm font-medium text-white transition-colors hover:bg-neutral-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
              >
                <ArrowLeft className="h-4 w-4" />
                <span>Return to Sign In</span>
              </button>
            </div>
          </div>
        ) : (
          <div className="space-y-4 py-4">
            <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-50 text-emerald-600">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
            <h2 className="text-lg font-semibold text-neutral-900">
              {isProcessing ? "Authenticating with Google..." : "Finalizing session..."}
            </h2>
            <p className="text-xs text-neutral-500">
              Verifying your credentials and preparing your lab workspace. Please wait a moment.
            </p>
          </div>
        )}
      </div>
    </div>
  );
};

export default SSOCallbackPage;
