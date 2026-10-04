import React, { useEffect, useRef } from "react";
import { useAuth as useClerkAuth, useUser } from "@clerk/clerk-react";
import { useAuth } from "../../context/useAuth";
import { tokenManager } from "../../lib/apiClient";
import { notifyUserUpdate } from "../../services/settingsStorage";

/**
 * ClerkSessionBridge
 *
 * Automatically synchronizes an active Clerk authentication session with the
 * PracPrep FastAPI backend, provisioning or linking user identities and storing
 * native JWT tokens without duplicating state or causing render loops.
 */
export const ClerkSessionBridge: React.FC = () => {
  const { isLoaded, isSignedIn, getToken } = useClerkAuth();
  const { user: clerkUser } = useUser();
  const { syncClerkSession } = useAuth();
  const hasSyncedRef = useRef(false);
  const isSyncingRef = useRef(false);

  useEffect(() => {
    if (!isLoaded) return;

    if (isSignedIn && clerkUser) {
      const email = clerkUser.primaryEmailAddress?.emailAddress;
      const fullName = clerkUser.fullName || clerkUser.firstName || undefined;

      // Ensure local session storage is populated immediately for synchronous UI components
      if (typeof window !== "undefined") {
        try {
          const stored = window.localStorage.getItem("pracprep_user");
          const parsed = stored ? JSON.parse(stored) : null;
          if (!parsed || parsed.isGuest) {
            window.localStorage.setItem(
              "pracprep_user",
              JSON.stringify({
                isGuest: false,
                name: fullName || "Student",
                email: email || "student@university.edu",
                avatar: clerkUser.imageUrl,
              })
            );
            notifyUserUpdate();
          }
        } catch {
          // Safe fallback
        }
      }

      const hasPracPrepToken = tokenManager.hasAccessToken();

      // Only initiate sync if not already syncing and either hasn't synced yet or token is missing
      if (!isSyncingRef.current && (!hasSyncedRef.current || !hasPracPrepToken)) {
        isSyncingRef.current = true;

        getToken()
          .then(async (clerkToken: string | null) => {
            if (clerkToken) {
              await syncClerkSession({
                clerkToken,
                email,
                fullName,
              });
              hasSyncedRef.current = true;
            }
          })
          .catch((err: unknown) => {
            console.error("ClerkSessionBridge: Synchronization failed:", err);
          })
          .finally(() => {
            isSyncingRef.current = false;
          });
      }
    } else if (!isSignedIn) {
      hasSyncedRef.current = false;
      isSyncingRef.current = false;
    }
  }, [isLoaded, isSignedIn, clerkUser, getToken, syncClerkSession]);

  return null;
};

export default ClerkSessionBridge;
