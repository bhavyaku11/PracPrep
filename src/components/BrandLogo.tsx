import React from "react";

interface BrandLogoProps {
  className?: string;
  onClick?: () => void;
  size?: "sm" | "md" | "lg";
}

export const BrandLogo: React.FC<BrandLogoProps> = ({ className = "", onClick, size = "md" }) => {
  const isSmall = size === "sm";
  const isLarge = size === "lg";

  return (
    <a
      href="/"
      onClick={(e) => {
        if (onClick) {
          e.preventDefault();
          onClick();
        }
      }}
      className={`group inline-flex items-center gap-2.5 outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 focus-visible:ring-offset-2 rounded-lg p-1 transition-colors ${className}`}
      aria-label="PracPrep Home"
    >
      <div className={`relative flex items-center justify-center rounded-xl bg-neutral-900 dark:bg-neutral-800 text-white shadow-sm transition-transform duration-200 group-hover:scale-105 group-hover:bg-neutral-800 dark:group-hover:bg-neutral-700 ${
        isSmall ? "h-7 w-7" : isLarge ? "h-11 w-11" : "h-9 w-9"
      }`}>
        {/* Custom Laboratory Flask Icon */}
        <svg
          viewBox="0 0 24 24"
          className="h-5 w-5 fill-none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          {/* Flask neck and rim */}
          <path d="M10 2h4" />
          <path d="M10 2v4.5L5.2 17.5A2.5 2.5 0 0 0 7.5 21h9a2.5 2.5 0 0 0 2.3-3.5L14 6.5V2" />
          {/* Green liquid meniscus */}
          <path
            d="M6.8 15.5c1.2-.8 2.8.4 4.4-.2 1.6-.6 2.8.4 4.2.2l.9 2a1.5 1.5 0 0 1-1.3 2H7.2a1.5 1.5 0 0 1-1.4-2l1-2Z"
            className="fill-emerald-500 stroke-none"
          />
          {/* Sparkle bubble */}
          <circle cx="12" cy="10" r="0.75" className="fill-emerald-300 stroke-none" />
        </svg>
      </div>

      <div className="flex flex-col">
        <div className="flex items-center gap-1.5 leading-none">
          <span className="font-jakarta text-xl font-bold tracking-tight text-neutral-900 dark:text-white">
            Prac<span className="text-emerald-700 dark:text-emerald-400">Prep</span>
          </span>
          <span className="rounded-full bg-emerald-100 dark:bg-emerald-950 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-800 dark:text-emerald-300 tracking-wide uppercase">
            Lab
          </span>
        </div>
        <span className="text-[10px] font-medium text-neutral-500 dark:text-neutral-400 tracking-wider">
          AI Lab Companion
        </span>
      </div>
    </a>
  );
};

export default BrandLogo;
