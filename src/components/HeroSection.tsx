import React from "react";
import { ArrowRight, Sparkles } from "lucide-react";
import { CrowdCanvas } from "./ui/skiper39";
import { siteConfig } from "../config/site";

interface HeroSectionProps {
  onNavigate?: (path: string) => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ onNavigate }) => {
  const handleCtaClick = (path: string, e: React.MouseEvent<HTMLAnchorElement>) => {
    if (onNavigate) {
      e.preventDefault();
      onNavigate(path);
    }
  };

  return (
    <section
      aria-label="Hero Section"
      className="relative flex h-screen h-[100dvh] max-h-[100dvh] w-full flex-col justify-between overflow-hidden bg-white"
    >
      {/* Top spacing under fixed navbar + Central Hero Content */}
      <div className="relative z-20 mx-auto flex w-full max-w-4xl flex-col items-center px-4 pt-20 sm:pt-22 md:pt-24 text-center sm:px-6 lg:px-8 shrink-0">
        {/* Main headline */}
        <h1 className="max-w-3xl font-jakarta text-3xl font-bold tracking-tight text-neutral-950 sm:text-5xl md:text-6xl leading-[1.1] sm:leading-[1.1]">
          From Lab Manual to{" "}
          <span className="relative inline-block text-neutral-950">
            Lab-Ready
            <span
              className="absolute -bottom-1 left-0 right-0 h-1.5 bg-emerald-500/25 rounded-full"
              aria-hidden="true"
            />
          </span>
          .
        </h1>

        {/* Supporting text */}
        <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-neutral-600 sm:mt-4 sm:text-base md:text-lg">
          {siteConfig.description}
        </p>

        {/* Hero CTAs */}
        <div className="mt-5 flex w-full flex-col sm:flex-row items-center justify-center gap-3 sm:mt-6 sm:w-auto sm:gap-4">
          {/* Primary CTA */}
          <a
            href={siteConfig.links.guest}
            onClick={(e) => handleCtaClick(siteConfig.links.guest, e)}
            className="group inline-flex h-11 sm:h-12 w-full sm:w-auto items-center justify-center gap-2 rounded-xl bg-neutral-900 px-5 sm:px-6 text-sm sm:text-base font-semibold text-white shadow-sm transition-all duration-200 hover:bg-emerald-700 hover:shadow-md active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
          >
            <span>Start Preparing</span>
            <ArrowRight
              className="h-4 w-4 transition-transform duration-200 group-hover:translate-x-1"
              aria-hidden="true"
            />
          </a>

          {/* Secondary CTA */}
          <a
            href={siteConfig.links.dashboard}
            onClick={(e) => handleCtaClick(siteConfig.links.dashboard, e)}
            className="inline-flex h-11 sm:h-12 w-full sm:w-auto items-center justify-center gap-2 rounded-xl border border-neutral-300 bg-white px-5 sm:px-6 text-sm sm:text-base font-semibold text-neutral-800 shadow-2xs transition-all duration-200 hover:border-neutral-900 hover:bg-neutral-50 active:scale-[0.98] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 focus-visible:ring-offset-2"
          >
            <Sparkles className="h-4 w-4 text-emerald-600" aria-hidden="true" />
            <span>Explore PracPrep</span>
          </a>
        </div>
      </div>

      {/* Skiper 39 Crowd Canvas Animation at bottom */}
      <div
        className="relative z-10 flex-1 min-h-[160px] w-full overflow-hidden pointer-events-none"
        aria-hidden="true"
      >
        {/* Subtle top blend for clean integration with white background */}
        <div
          className="absolute inset-x-0 top-0 h-10 bg-gradient-to-b from-white to-transparent pointer-events-none z-1"
          aria-hidden="true"
        />

        <CrowdCanvas
          src="/assets/peeps-sprite.png"
          rows={15}
          cols={7}
          className="absolute bottom-0 h-full w-full pointer-events-none"
        />
      </div>
    </section>
  );
};

export default HeroSection;
