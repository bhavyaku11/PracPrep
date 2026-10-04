import React from "react";
import {
  Info,
  ExternalLink,
  Code2,
  FlaskConical,
  MessageSquareCode,
  Cpu,
} from "lucide-react";
import { siteConfig } from "../../config/site";
import BrandLogo from "../BrandLogo";

interface AboutSettingsSectionProps {
  onNavigate: (path: string) => void;
}

export const AboutSettingsSection: React.FC<AboutSettingsSectionProps> = ({
  onNavigate,
}) => {
  return (
    <div className="bg-white dark:bg-neutral-900 border border-neutral-200 dark:border-neutral-800 rounded-2xl p-6 sm:p-7 shadow-xs space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-neutral-100 dark:border-neutral-800">
        <div>
          <h2 className="text-base font-bold text-neutral-900 dark:text-white flex items-center gap-2">
            <Info className="w-5 h-5 text-emerald-600 dark:text-emerald-400" />
            About PracPrep
          </h2>
          <p className="text-xs text-neutral-500 dark:text-neutral-400 mt-0.5">
            Application specifications, architecture overview, and platform details.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="px-2.5 py-1 rounded-lg text-[11px] font-mono font-medium bg-neutral-100 dark:bg-neutral-800 text-neutral-700 dark:text-neutral-300 border border-neutral-200 dark:border-neutral-700">
            v0.0.0-preview
          </span>
        </div>
      </div>

      {/* Product Banner */}
      <div className="p-5 rounded-2xl bg-neutral-50 dark:bg-neutral-800/40 border border-neutral-200 dark:border-neutral-800 flex flex-col sm:flex-row sm:items-center gap-4">
        <div className="p-3 bg-white dark:bg-neutral-900 rounded-xl border border-neutral-200 dark:border-neutral-800 shadow-2xs shrink-0 self-start sm:self-center">
          <BrandLogo size="md" />
        </div>
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-bold text-neutral-900 dark:text-white">
              {siteConfig.name}
            </h3>
            <span className="text-[11px] text-emerald-600 dark:text-emerald-400 font-medium">
              — {siteConfig.tagline}
            </span>
          </div>
          <p className="text-xs text-neutral-600 dark:text-neutral-400 leading-relaxed">
            {siteConfig.description}
          </p>
        </div>
      </div>

      {/* Architectural Pillars */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3.5 pt-1">
        <div className="p-4 rounded-xl border border-neutral-200/80 dark:border-neutral-800 bg-white dark:bg-neutral-900/60 space-y-1.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <FlaskConical className="w-4 h-4" />
          </div>
          <h4 className="text-xs font-bold text-neutral-900 dark:text-white">
            Lab Manual Ingestion
          </h4>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-normal">
            Automated structuring of experiments, apparatus, formulas, and safety checklists.
          </p>
        </div>

        <div className="p-4 rounded-xl border border-neutral-200/80 dark:border-neutral-800 bg-white dark:bg-neutral-900/60 space-y-1.5">
          <div className="w-8 h-8 rounded-lg bg-emerald-50 dark:bg-emerald-950/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center">
            <MessageSquareCode className="w-4 h-4" />
          </div>
          <h4 className="text-xs font-bold text-neutral-900 dark:text-white">
            Viva Simulator Engine
          </h4>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-normal">
            Interactive oral viva questioning across Theory, Procedure, and Calculations.
          </p>
        </div>

        <div className="p-4 rounded-xl border border-neutral-200/80 dark:border-neutral-800 bg-white dark:bg-neutral-900/60 space-y-1.5">
          <div className="w-8 h-8 rounded-lg bg-amber-50 dark:bg-amber-950/60 text-amber-600 dark:text-amber-400 flex items-center justify-center">
            <Cpu className="w-4 h-4" />
          </div>
          <h4 className="text-xs font-bold text-neutral-900 dark:text-white">
            Local-First Privacy
          </h4>
          <p className="text-[11px] text-neutral-500 dark:text-neutral-400 leading-normal">
            Session-scoped encrypted storage with full student export and zero third-party tracking.
          </p>
        </div>
      </div>

      {/* Links & Quick Actions */}
      <div className="pt-2 border-t border-neutral-100 dark:border-neutral-800 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-4 text-neutral-500 dark:text-neutral-400">
          <button
            type="button"
            onClick={() => onNavigate("/experiments")}
            className="hover:text-neutral-900 dark:hover:text-white transition-colors"
          >
            My Experiments
          </button>
          <span>•</span>
          <button
            type="button"
            onClick={() => onNavigate("/viva-practice")}
            className="hover:text-neutral-900 dark:hover:text-white transition-colors"
          >
            Viva Hub
          </button>
          <span>•</span>
          <button
            type="button"
            onClick={() => onNavigate("/progress")}
            className="hover:text-neutral-900 dark:hover:text-white transition-colors"
          >
            Progress Analytics
          </button>
        </div>

        {siteConfig.links.github && (
          <a
            href={siteConfig.links.github}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 font-medium text-neutral-700 dark:text-neutral-300 hover:text-neutral-900 dark:hover:text-white transition-colors"
          >
            <Code2 className="w-3.5 h-3.5 text-neutral-400" />
            <span>GitHub Repository</span>
            <ExternalLink className="w-3 h-3 text-neutral-400" />
          </a>
        )}
      </div>
    </div>
  );
};

export default AboutSettingsSection;
