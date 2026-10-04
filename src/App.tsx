import { useState, useEffect } from "react";
import { ClerkProvider } from "@clerk/clerk-react";
import Navbar from "./components/Navbar";
import HeroSection from "./components/HeroSection";
import { NotFound } from "./components/ui/ghost-404-page";
import AuthPage from "./pages/AuthPage";
import SSOCallbackPage from "./pages/SSOCallbackPage";
import DashboardLayout from "./components/dashboard/DashboardLayout";
import { settingsStorage } from "./services/settingsStorage";
import { AuthProvider } from "./context/AuthContext.tsx";
import { ClerkSessionBridge } from "./components/auth/ClerkSessionBridge.tsx";
import { getClerkPublishableKey, getClerkConfigurationError } from "./lib/clerk.ts";

const DASHBOARD_ROUTES = [
  "/dashboard",
  "/guest",
  "/experiments",
  "/create-experiment",
  "/viva-practice",
  "/progress",
  "/settings",
];

function AppRouter() {
  const [currentPath, setCurrentPath] = useState<string>(() => {
    if (typeof window !== "undefined") {
      return window.location.pathname || "/";
    }
    return "/";
  });

  useEffect(() => {
    settingsStorage.initTheme();
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname || "/");
    };

    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  const handleNavigate = (path: string) => {
    if (typeof window !== "undefined") {
      window.history.pushState({}, "", path);
      setCurrentPath(path);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  useEffect(() => {
    if (currentPath === "/" || currentPath === "") {
      document.documentElement.style.overflow = "hidden";
      document.body.style.overflow = "hidden";
    } else {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
    }
    return () => {
      document.documentElement.style.overflow = "";
      document.body.style.overflow = "";
    };
  }, [currentPath]);

  // Render SSOCallbackPage for OAuth callback flow
  if (currentPath === "/sso-callback") {
    return <SSOCallbackPage onNavigate={handleNavigate} />;
  }

  // Render AuthPage for /login and /signup routes
  if (currentPath === "/login" || currentPath === "/signup") {
    return (
      <AuthPage
        key={currentPath}
        initialMode={currentPath === "/signup" ? "signup" : "signin"}
        onNavigate={handleNavigate}
        onGuestAccess={() => handleNavigate("/guest")}
      />
    );
  }

  // Render DashboardLayout for /dashboard, /guest, and student workspace routes
  const isDashboardRoute =
    DASHBOARD_ROUTES.includes(currentPath) ||
    currentPath.startsWith("/experiments/");

  if (isDashboardRoute) {
    return (
      <DashboardLayout
        currentPath={currentPath}
        onNavigate={handleNavigate}
      />
    );
  }

  // Render custom 404 Ghost page for /404 and all unknown non-root routes
  if (currentPath === "/404" || (currentPath !== "/" && currentPath !== "")) {
    return (
      <NotFound
        currentPath={currentPath}
        onNavigate={handleNavigate}
      />
    );
  }

  // Render PracPrep Landing Page - Hero Section
  return (
    <div className="relative h-screen h-[100dvh] max-h-[100dvh] w-full overflow-hidden bg-white text-neutral-900 selection:bg-emerald-100 selection:text-emerald-900">
      <Navbar onNavigate={handleNavigate} currentPath={currentPath} />
      <main id="main-content" className="h-full w-full overflow-hidden">
        <HeroSection onNavigate={handleNavigate} />
      </main>
    </div>
  );
}

export function App() {
  const publishableKey = getClerkPublishableKey();
  const configError = getClerkConfigurationError();

  if (configError) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-neutral-50 p-6 selection:bg-emerald-100 selection:text-emerald-900">
        <div className="w-full max-w-md rounded-2xl border border-amber-200 bg-white p-6 shadow-xl shadow-neutral-900/5">
          <div className="flex items-center gap-3 text-amber-700 font-semibold text-base mb-2">
            <svg className="h-5 w-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>Clerk Configuration Required</span>
          </div>
          <p className="text-sm text-neutral-600 mb-4">{configError}</p>
          <p className="text-xs text-neutral-500">
            Ensure <code className="font-mono bg-neutral-100 px-1 py-0.5 rounded text-neutral-800">VITE_CLERK_PUBLISHABLE_KEY</code> is set in your root <code className="font-mono bg-neutral-100 px-1 py-0.5 rounded text-neutral-800">.env.local</code> file and restart the development server.
          </p>
        </div>
      </div>
    );
  }

  return (
    <ClerkProvider publishableKey={publishableKey}>
      <AuthProvider>
        <ClerkSessionBridge />
        <AppRouter />
      </AuthProvider>
    </ClerkProvider>
  );
}

export default App;
