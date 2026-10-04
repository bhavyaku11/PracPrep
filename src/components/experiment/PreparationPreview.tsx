import React from "react";
import { FolderKanban, BookOpenCheck, HelpCircle } from "lucide-react";

export const PreparationPreview: React.FC = () => {
  const steps = [
    {
      step: "1",
      title: "Organize",
      description: "Your experiment details are prepared in a structured workspace.",
      icon: FolderKanban,
    },
    {
      step: "2",
      title: "Study",
      description: "Review the objective, theory, apparatus, and procedure clearly.",
      icon: BookOpenCheck,
    },
    {
      step: "3",
      title: "Practice",
      description: "Prepare for your viva with experiment-specific questions.",
      icon: HelpCircle,
    },
  ];

  return (
    <section
      aria-labelledby="what-happens-next-heading"
      className="rounded-2xl border border-neutral-200/80 bg-neutral-50/60 p-4 sm:p-5"
    >
      <div className="mb-3">
        <h3
          id="what-happens-next-heading"
          className="font-jakarta text-xs font-semibold text-neutral-800 uppercase tracking-wider"
        >
          What happens next?
        </h3>
        <p className="text-[11px] text-neutral-500">
          How PracPrep processes your experiment setup
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {steps.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.step}
              className="flex items-start gap-2.5 rounded-xl border border-neutral-200/70 bg-white p-3 shadow-2xs"
            >
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-neutral-100 text-neutral-700 font-bold text-xs">
                {item.step}
              </div>
              <div className="space-y-0.5">
                <div className="flex items-center gap-1.5">
                  <Icon className="h-3.5 w-3.5 text-emerald-700" />
                  <span className="font-semibold text-xs text-neutral-900">{item.title}</span>
                </div>
                <p className="text-[11px] text-neutral-500 leading-snug">
                  {item.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default PreparationPreview;
