import React, { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence, useReducedMotion } from "framer-motion";
import { HelpCircle, X, Home } from "lucide-react";

export interface NotFoundProps {
  onNavigate?: (path: string) => void;
  currentPath?: string;
}

export function NotFound({ onNavigate, currentPath }: NotFoundProps) {
  const [showExplanation, setShowExplanation] = useState(false);
  const systemReducedMotion = useReducedMotion();
  const [isReducedMotion, setIsReducedMotion] = useState(Boolean(systemReducedMotion));

  useEffect(() => {
    const checkReducedMotion = () => {
      const dataAttr = document.documentElement.getAttribute("data-reduced-motion");
      if (dataAttr === "true") {
        setIsReducedMotion(true);
      } else if (systemReducedMotion) {
        setIsReducedMotion(true);
      } else {
        setIsReducedMotion(false);
      }
    };
    checkReducedMotion();
  }, [systemReducedMotion]);

  // Handle escape key to close explanation modal
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && showExplanation) {
        setShowExplanation(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [showExplanation]);

  const handleNavigateHome = useCallback(
    (e?: React.MouseEvent) => {
      if (e) e.preventDefault();
      if (onNavigate) {
        onNavigate("/");
      } else if (typeof window !== "undefined") {
        window.history.pushState({}, "", "/");
        window.dispatchEvent(new PopStateEvent("popstate"));
      }
    },
    [onNavigate]
  );

  const containerVariants = {
    hidden: {
      opacity: 0,
      y: isReducedMotion ? 0 : 30,
    },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: isReducedMotion ? 0.1 : 0.7,
        ease: [0.43, 0.13, 0.23, 0.96] as const,
        delayChildren: isReducedMotion ? 0 : 0.1,
        staggerChildren: isReducedMotion ? 0 : 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: {
      opacity: 0,
      y: isReducedMotion ? 0 : 20,
    },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: isReducedMotion ? 0.1 : 0.6,
        ease: [0.43, 0.13, 0.23, 0.96] as const,
      },
    },
  };

  const numberVariants = {
    hidden: (direction: number) => ({
      opacity: 0,
      x: isReducedMotion ? 0 : direction * 40,
      y: isReducedMotion ? 0 : 15,
      rotate: isReducedMotion ? 0 : direction * 5,
    }),
    visible: {
      opacity: 0.7,
      x: 0,
      y: 0,
      rotate: 0,
      transition: {
        duration: isReducedMotion ? 0.1 : 0.8,
        ease: [0.43, 0.13, 0.23, 0.96] as const,
      },
    },
  };

  const ghostVariants = {
    hidden: {
      scale: isReducedMotion ? 1 : 0.8,
      opacity: 0,
      y: isReducedMotion ? 0 : 15,
      rotate: isReducedMotion ? 0 : -5,
    },
    visible: {
      scale: 1,
      opacity: 1,
      y: 0,
      rotate: 0,
      transition: {
        duration: isReducedMotion ? 0.1 : 0.6,
        ease: [0.43, 0.13, 0.23, 0.96] as const,
      },
    },
    hover: isReducedMotion
      ? {}
      : {
          scale: 1.1,
          y: -10,
          rotate: [0, -5, 5, -5, 0],
          transition: {
            duration: 0.8,
            ease: "easeInOut" as const,
            rotate: {
              duration: 2,
              ease: "linear" as const,
              repeat: Infinity,
              repeatType: "reverse" as const,
            },
          },
        },
    floating: isReducedMotion
      ? {}
      : {
          y: [-5, 5],
          transition: {
            y: {
              duration: 2,
              ease: "easeInOut" as const,
              repeat: Infinity,
              repeatType: "reverse" as const,
            },
          },
        },
  };

  return (
    <main
      role="main"
      aria-label="404 Page Not Found"
      className="min-h-screen w-full flex flex-col items-center justify-center bg-white px-4 py-12 selection:bg-emerald-100 selection:text-emerald-900"
    >
      <AnimatePresence mode="wait">
        <motion.div
          className="w-full max-w-lg mx-auto text-center"
          variants={containerVariants}
          initial="hidden"
          animate="visible"
          exit="hidden"
        >
          {/* 4 [Ghost] 4 Composition */}
          <div className="flex items-center justify-center gap-4 md:gap-6 mb-8 md:mb-12">
            <motion.span
              className="text-[80px] md:text-[120px] font-bold text-[#222222] opacity-70 font-signika select-none leading-none tracking-tighter"
              variants={numberVariants}
              custom={-1}
            >
              4
            </motion.span>

            <motion.div
              variants={ghostVariants}
              whileHover="hover"
              animate={isReducedMotion ? "visible" : ["visible", "floating"]}
              className="relative flex items-center justify-center"
            >
              <img
                src="/ghost-404.png"
                alt="Ghost"
                width={120}
                height={120}
                className="w-[80px] h-[80px] md:w-[120px] md:h-[120px] object-contain select-none"
                draggable={false}
                onError={(e) => {
                  const target = e.currentTarget;
                  if (!target.src.includes("cdn.21st.dev")) {
                    target.src =
                      "https://cdn.21st.dev/assets/mirror/88/8848c4fd858052c49c5a5d7267489c02b021c6cf3e31bfec02787e16f1ab7d0e.png";
                  }
                }}
              />
            </motion.div>

            <motion.span
              className="text-[80px] md:text-[120px] font-bold text-[#222222] opacity-70 font-signika select-none leading-none tracking-tighter"
              variants={numberVariants}
              custom={1}
            >
              4
            </motion.span>
          </div>

          {/* Headline */}
          <motion.h1
            className="text-3xl md:text-5xl font-bold text-[#222222] mb-4 md:mb-6 opacity-70 font-dm-sans select-none tracking-tight"
            variants={itemVariants}
          >
            Boo! Page missing!
          </motion.h1>

          {/* Subtext */}
          <motion.p
            className="text-base sm:text-lg md:text-xl text-[#222222] mb-8 md:mb-12 opacity-50 font-dm-sans select-none max-w-sm sm:max-w-md mx-auto leading-relaxed"
            variants={itemVariants}
          >
            Whoops! This page must be a ghost - it&apos;s not here!
          </motion.p>

          {/* Primary Action Button */}
          <motion.div
            variants={itemVariants}
            whileHover={
              isReducedMotion
                ? {}
                : {
                    scale: 1.05,
                    transition: {
                      duration: 0.3,
                      ease: [0.43, 0.13, 0.23, 0.96] as const,
                    },
                  }
            }
          >
            <button
              type="button"
              onClick={handleNavigateHome}
              className="inline-flex items-center justify-center gap-2 bg-[#222222] text-white px-8 py-3.5 rounded-full text-base sm:text-lg font-medium hover:bg-black transition-colors font-dm-sans select-none shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900 focus-visible:ring-offset-2 cursor-pointer"
            >
              <Home className="w-4 h-4 sm:w-5 sm:h-5 opacity-90" />
              <span>Find shelter</span>
            </button>
          </motion.div>

          {/* Secondary Action: "What means 404?" */}
          <motion.div className="mt-10 sm:mt-12" variants={itemVariants}>
            <button
              type="button"
              onClick={() => setShowExplanation(true)}
              aria-haspopup="dialog"
              aria-expanded={showExplanation}
              className="text-[#222222] opacity-50 hover:opacity-70 transition-opacity underline font-dm-sans select-none text-sm sm:text-base cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900 rounded"
            >
              What means 404?
            </button>
          </motion.div>
        </motion.div>
      </AnimatePresence>

      {/* Accessible "What means 404?" Explanation Dialog */}
      <AnimatePresence>
        {showExplanation && (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="404-explanation-title"
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/40 backdrop-blur-xs"
            onClick={() => setShowExplanation(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 10 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2 }}
              onClick={(e) => e.stopPropagation()}
              className="relative w-full max-w-md rounded-2xl border border-neutral-200 bg-white p-6 sm:p-7 shadow-2xl text-left"
            >
              <button
                type="button"
                onClick={() => setShowExplanation(false)}
                className="absolute top-4 right-4 rounded-lg p-1.5 text-neutral-400 hover:text-neutral-600 hover:bg-neutral-100 transition-colors cursor-pointer"
                aria-label="Close explanation dialog"
              >
                <X className="w-4 h-4" />
              </button>

              <div className="flex items-center gap-3 mb-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-50 text-amber-600 border border-amber-200">
                  <HelpCircle className="w-5 h-5" />
                </div>
                <div>
                  <h2
                    id="404-explanation-title"
                    className="text-base sm:text-lg font-bold text-neutral-900 font-dm-sans"
                  >
                    HTTP 404 Not Found
                  </h2>
                  <p className="text-xs text-neutral-500 font-mono">
                    Status Code: 404
                  </p>
                </div>
              </div>

              <p className="text-xs sm:text-sm text-neutral-600 leading-relaxed font-dm-sans mb-4">
                A 404 error means the application or server could not locate the laboratory manual, workspace section, or resource you requested. The URL may have a typo, or the experiment route may have been relocated.
              </p>

              {currentPath && currentPath !== "/404" && (
                <div className="rounded-xl bg-neutral-50 border border-neutral-200/80 p-3 text-xs text-neutral-600 font-mono mb-5 truncate">
                  <span className="font-semibold text-neutral-500 mr-1.5">Attempted:</span>
                  {currentPath}
                </div>
              )}

              <div className="flex flex-col sm:flex-row items-center gap-2 pt-2 border-t border-neutral-100">
                <button
                  type="button"
                  onClick={handleNavigateHome}
                  className="w-full inline-flex items-center justify-center gap-2 rounded-xl bg-neutral-900 px-4 py-2.5 text-xs sm:text-sm font-semibold text-white hover:bg-neutral-800 transition-colors cursor-pointer"
                >
                  <Home className="w-3.5 h-3.5" />
                  <span>Return to Landing Page</span>
                </button>
                <button
                  type="button"
                  onClick={() => setShowExplanation(false)}
                  className="w-full sm:w-auto inline-flex items-center justify-center rounded-xl border border-neutral-200 px-4 py-2.5 text-xs sm:text-sm font-medium text-neutral-700 hover:bg-neutral-50 transition-colors cursor-pointer"
                >
                  Got it
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </main>
  );
}

export default NotFound;
