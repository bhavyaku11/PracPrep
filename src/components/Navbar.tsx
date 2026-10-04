import React, { useState, useEffect } from "react";
import { Menu, X, ArrowUpRight, UserCheck } from "lucide-react";
import BrandLogo from "./BrandLogo";
import { siteConfig } from "../config/site";

interface NavbarProps {
  onNavigate?: (path: string) => void;
  currentPath?: string;
}

const GithubIcon: React.FC<{ className?: string }> = ({ className = "h-4 w-4" }) => (
  <svg
    viewBox="0 0 24 24"
    fill="currentColor"
    className={className}
    aria-hidden="true"
  >
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
    />
  </svg>
);

export const Navbar: React.FC<NavbarProps> = ({ onNavigate, currentPath = "/" }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setScrolled(window.scrollY > 12);
    };
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // Close mobile menu on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && mobileMenuOpen) {
        setMobileMenuOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [mobileMenuOpen]);

  const handleLinkClick = (path: string, e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onNavigate) {
      e.preventDefault();
      onNavigate(path);
      setMobileMenuOpen(false);
    }
  };

  return (
    <header
      className={`fixed top-0 left-0 right-0 z-50 transition-all duration-200 ${
        scrolled
          ? "bg-white/90 backdrop-blur-md border-b border-neutral-200/80 shadow-xs"
          : "bg-transparent border-b border-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        {/* Left: Website Identity */}
        <BrandLogo onClick={() => onNavigate && onNavigate("/")} />

        {/* Right: Desktop Navigation Actions */}
        <nav
          className="hidden md:flex items-center gap-2 lg:gap-3"
          aria-label="Main Navigation"
        >
          {/* GitHub link */}
          <a
            href={siteConfig.links.github}
            target="_blank"
            rel="noopener noreferrer"
            aria-label="PracPrep on GitHub (opens in new tab)"
            className="inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium text-neutral-600 hover:text-neutral-950 hover:bg-neutral-100 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
          >
            <GithubIcon className="h-4 w-4" />
            <span>GitHub</span>
            <ArrowUpRight className="h-3 w-3 text-neutral-400" aria-hidden="true" />
          </a>

          {/* Continue as Guest */}
          <a
            href={siteConfig.links.guest}
            onClick={(e) => handleLinkClick(siteConfig.links.guest, e)}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 ${
              currentPath === siteConfig.links.guest
                ? "bg-emerald-50 text-emerald-800"
                : "text-neutral-700 hover:text-emerald-700 hover:bg-emerald-50"
            }`}
          >
            <UserCheck className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            <span>Continue as Guest</span>
          </a>

          {/* Log in */}
          <a
            href={siteConfig.links.login}
            onClick={(e) => handleLinkClick(siteConfig.links.login, e)}
            className={`rounded-lg px-3.5 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2 ${
              currentPath === siteConfig.links.login
                ? "bg-neutral-100 text-neutral-950"
                : "text-neutral-700 hover:text-neutral-950 hover:bg-neutral-100"
            }`}
          >
            Log in
          </a>

          {/* Get Started Button */}
          <a
            href={siteConfig.links.signup}
            onClick={(e) => handleLinkClick(siteConfig.links.signup, e)}
            className="inline-flex items-center justify-center rounded-lg bg-neutral-900 px-4 py-2 text-sm font-semibold text-white shadow-sm transition-all duration-200 hover:bg-emerald-700 hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
          >
            Get Started
          </a>
        </nav>

        {/* Mobile menu button */}
        <div className="flex md:hidden items-center gap-2">
          <a
            href={siteConfig.links.guest}
            onClick={(e) => handleLinkClick(siteConfig.links.guest, e)}
            className="inline-flex items-center justify-center rounded-md border border-neutral-300 px-2.5 py-1.5 text-xs font-semibold text-neutral-800 hover:bg-neutral-50"
          >
            Guest
          </a>
          <button
            type="button"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="inline-flex h-10 w-10 items-center justify-center rounded-lg text-neutral-700 hover:bg-neutral-100 hover:text-neutral-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
            aria-expanded={mobileMenuOpen}
            aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
          >
            {mobileMenuOpen ? (
              <X className="h-5 w-5" aria-hidden="true" />
            ) : (
              <Menu className="h-5 w-5" aria-hidden="true" />
            )}
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div
          className="md:hidden border-b border-neutral-200 bg-white/95 backdrop-blur-md px-4 pt-2 pb-6 shadow-lg animate-in slide-in-from-top duration-200"
          id="mobile-navigation"
        >
          <div className="flex flex-col space-y-1.5 pt-2">
            <a
              href={siteConfig.links.guest}
              onClick={(e) => handleLinkClick(siteConfig.links.guest, e)}
              className="flex h-11 items-center justify-between rounded-lg px-3 text-sm font-medium text-neutral-800 hover:bg-emerald-50 hover:text-emerald-800 transition-colors"
            >
              <span className="flex items-center gap-2">
                <UserCheck className="h-4 w-4 text-emerald-600" />
                Continue as Guest
              </span>
              <span className="text-xs bg-emerald-100 text-emerald-800 font-semibold px-2 py-0.5 rounded-full">
                Instant Access
              </span>
            </a>

            <a
              href={siteConfig.links.login}
              onClick={(e) => handleLinkClick(siteConfig.links.login, e)}
              className="flex h-11 items-center rounded-lg px-3 text-sm font-medium text-neutral-800 hover:bg-neutral-100 hover:text-neutral-950 transition-colors"
            >
              Log in
            </a>

            <a
              href={siteConfig.links.github}
              target="_blank"
              rel="noopener noreferrer"
              className="flex h-11 items-center justify-between rounded-lg px-3 text-sm font-medium text-neutral-700 hover:bg-neutral-100 hover:text-neutral-950 transition-colors"
            >
              <span className="flex items-center gap-2">
                <GithubIcon className="h-4 w-4" />
                GitHub Repository
              </span>
              <ArrowUpRight className="h-4 w-4 text-neutral-400" />
            </a>

            <div className="pt-3">
              <a
                href={siteConfig.links.signup}
                onClick={(e) => handleLinkClick(siteConfig.links.signup, e)}
                className="flex h-11 w-full items-center justify-center rounded-lg bg-neutral-900 px-4 text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
              >
                Get Started
              </a>
            </div>
          </div>
        </div>
      )}
    </header>
  );
};

export default Navbar;
