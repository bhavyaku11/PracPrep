import React, { useState } from "react";
import {
  Sparkles,
  ArrowLeft,
  BookOpen,
  CheckCircle2,
  AlertTriangle,
  Play,
  Sliders,
  ShieldCheck,
  Wrench,
  ListOrdered,
  Table,
} from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";
import type {
  VivaSessionConfig,
  VivaTopic,
  VivaDifficulty,
} from "../../types/viva";
import { settingsStorage } from "../../services/settingsStorage";

interface VivaSetupScreenProps {
  experiment: ExperimentRecord;
  onStartSession: (config: VivaSessionConfig) => void;
  onBack: () => void;
}

export const VivaSetupScreen: React.FC<VivaSetupScreenProps> = ({
  experiment,
  onStartSession,
  onBack,
}) => {
  const [questionCount, setQuestionCount] = useState<5 | 10 | 15>(() => {
    return settingsStorage.getSettings().studyPreferences.defaultQuestionCount || 5;
  });
  const [difficulty, setDifficulty] = useState<VivaDifficulty>(() => {
    return settingsStorage.getSettings().studyPreferences.defaultDifficulty || "mixed";
  });
  const [focus, setFocus] = useState<VivaTopic>(() => {
    return settingsStorage.getSettings().studyPreferences.preferredFocus || "mixed";
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onStartSession({
      questionCount,
      difficulty,
      focus,
    });
  };

  // Check section availability in experiment
  const contentAvailability = [
    { label: "Theory", hasContent: Boolean(experiment.theory?.trim()), key: "theory" as VivaTopic },
    { label: "Apparatus", hasContent: Boolean(experiment.apparatus?.trim()), key: "apparatus" as VivaTopic },
    { label: "Procedure", hasContent: Boolean(experiment.procedure?.trim()), key: "procedure" as VivaTopic },
    {
      label: "Observations",
      hasContent: Boolean(experiment.observations?.trim() || experiment.calculations?.trim()),
      key: "observations" as VivaTopic,
    },
    { label: "Precautions", hasContent: Boolean(experiment.precautions?.trim()), key: "precautions" as VivaTopic },
  ];

  const selectedTopicHasContent =
    focus === "mixed" ||
    contentAvailability.find((c) => c.key === focus)?.hasContent;

  return (
    <div className="w-full max-w-4xl mx-auto space-y-6 pb-12">
      {/* 1. Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs text-neutral-500">
        <button
          type="button"
          onClick={onBack}
          className="inline-flex items-center gap-1 font-medium text-neutral-600 hover:text-emerald-800 transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          <span>Back to Workspace</span>
        </button>
        <span className="text-neutral-300">/</span>
        <span className="text-neutral-900 font-semibold truncate max-w-xs sm:max-w-md">
          {experiment.title}
        </span>
        <span className="text-neutral-300">/</span>
        <span className="text-emerald-800 font-medium">Viva Simulator Setup</span>
      </div>

      {/* 2. Setup Header Card */}
      <div className="rounded-2xl border border-neutral-200/90 bg-white p-6 sm:p-7 shadow-2xs space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1.5 flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
                <Sparkles className="h-3.5 w-3.5 text-emerald-700" />
                <span>AI Viva Voce Simulator</span>
              </span>
              <span className="text-xs font-semibold text-neutral-700 bg-neutral-100 px-2.5 py-0.5 rounded-full">
                {experiment.subject}
              </span>
              {experiment.experimentNumber && (
                <span className="font-mono text-xs font-semibold text-neutral-600 bg-neutral-100 px-2 py-0.5 rounded-md">
                  {experiment.experimentNumber}
                </span>
              )}
            </div>

            <h1 className="font-jakarta text-xl sm:text-2xl font-bold tracking-tight text-neutral-900">
              Configure Viva Session: {experiment.title}
            </h1>

            {experiment.objective ? (
              <p className="text-xs sm:text-sm text-neutral-600 leading-relaxed max-w-2xl pt-1">
                <span className="font-semibold text-neutral-800">Aim: </span>
                {experiment.objective}
              </p>
            ) : (
              <p className="text-xs text-neutral-500">
                Practice oral examination questions derived from this experiment's manual content.
              </p>
            )}
          </div>
        </div>

        {/* Content Coverage Summary */}
        <div className="pt-3 border-t border-neutral-100">
          <span className="block text-[11px] font-semibold uppercase tracking-wider text-neutral-400 mb-2">
            Available Experiment Grounding Material
          </span>
          <div className="flex flex-wrap gap-2">
            {contentAvailability.map((item) => (
              <span
                key={item.label}
                className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-lg border font-medium ${
                  item.hasContent
                    ? "bg-emerald-50/60 border-emerald-200 text-emerald-800"
                    : "bg-neutral-50 border-neutral-200 text-neutral-400"
                }`}
              >
                {item.hasContent ? (
                  <CheckCircle2 className="h-3 w-3 text-emerald-700" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-neutral-300" />
                )}
                <span>{item.label}</span>
                <span className="text-[10px] text-neutral-400">
                  {item.hasContent ? "Ready" : "Empty"}
                </span>
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* 3. Session Configuration Form */}
      <form onSubmit={handleSubmit} className="space-y-5">
        <div className="rounded-2xl border border-neutral-200/90 bg-white p-6 sm:p-7 shadow-2xs space-y-6">
          <div className="flex items-center gap-2 pb-2 border-b border-neutral-100">
            <Sliders className="h-4 w-4 text-emerald-700" />
            <h2 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900">
              Session Parameters
            </h2>
          </div>

          {/* Option 1: Question Count */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-neutral-800">
              Number of Questions
            </label>
            <div className="grid grid-cols-3 gap-3">
              {([5, 10, 15] as const).map((cnt) => (
                <button
                  key={cnt}
                  type="button"
                  onClick={() => setQuestionCount(cnt)}
                  className={`flex flex-col items-center justify-center p-3.5 rounded-xl border text-center transition-all ${
                    questionCount === cnt
                      ? "border-emerald-600 bg-emerald-50/50 text-emerald-950 font-bold ring-1 ring-emerald-600/30 shadow-2xs"
                      : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 hover:bg-neutral-50"
                  }`}
                >
                  <span className="text-base font-jakarta">{cnt} Questions</span>
                  <span className="text-[11px] text-neutral-500 font-normal">
                    {cnt === 5 ? "~5-8 mins" : cnt === 10 ? "~10-15 mins" : "~20 mins"}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Option 2: Difficulty Level */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-neutral-800">
              Examination Difficulty
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { id: "beginner", title: "Beginner", desc: "Basic definitions, apparatus & aim" },
                { id: "intermediate", title: "Intermediate", desc: "Formulas, steps & relations" },
                { id: "advanced", title: "Advanced", desc: "Troubleshooting, limits & derivations" },
                { id: "mixed", title: "Mixed", desc: "Adaptive progressive mix" },
              ].map((diff) => (
                <button
                  key={diff.id}
                  type="button"
                  onClick={() => setDifficulty(diff.id as VivaDifficulty)}
                  className={`flex flex-col items-start p-3 rounded-xl border text-left transition-all ${
                    difficulty === diff.id
                      ? "border-emerald-600 bg-emerald-50/50 text-emerald-950 ring-1 ring-emerald-600/30 shadow-2xs"
                      : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 hover:bg-neutral-50"
                  }`}
                >
                  <span className="text-xs font-bold font-jakarta">
                    {diff.title}
                  </span>
                  <span className="text-[10px] text-neutral-500 leading-tight mt-1">
                    {diff.desc}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Option 3: Question Focus */}
          <div className="space-y-2">
            <label className="block text-xs font-semibold text-neutral-800">
              Question Focus
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
              {[
                { id: "mixed", label: "Mixed Topics", icon: Sparkles },
                { id: "theory", label: "Theory & Laws", icon: BookOpen },
                { id: "procedure", label: "Procedure & Steps", icon: ListOrdered },
                { id: "apparatus", label: "Apparatus & Meters", icon: Wrench },
                { id: "observations", label: "Observations & Calc", icon: Table },
                { id: "precautions", label: "Precautions & Safety", icon: ShieldCheck },
              ].map((item) => {
                const Icon = item.icon;
                const isSelected = focus === item.id;
                return (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setFocus(item.id as VivaTopic)}
                    className={`flex items-center gap-2.5 p-3 rounded-xl border text-left transition-all ${
                      isSelected
                        ? "border-emerald-600 bg-emerald-50/50 text-emerald-950 ring-1 ring-emerald-600/30 font-semibold shadow-2xs"
                        : "border-neutral-200 bg-white text-neutral-700 hover:border-neutral-300 hover:bg-neutral-50"
                    }`}
                  >
                    <Icon className={`h-4 w-4 shrink-0 ${isSelected ? "text-emerald-700" : "text-neutral-400"}`} />
                    <span className="text-xs truncate">{item.label}</span>
                  </button>
                );
              })}
            </div>

            {/* Advisory note if selected focus has empty material */}
            {!selectedTopicHasContent && (
              <div className="flex items-center gap-2 p-3 rounded-xl bg-amber-50 border border-amber-200 text-xs text-amber-900 mt-2">
                <AlertTriangle className="h-4 w-4 text-amber-700 shrink-0" />
                <span>
                  Notice: Your experiment has not added details for this section yet. Questions will adapt using available manual context.
                </span>
              </div>
            )}
          </div>
        </div>

        {/* Engine Transparency Notice */}
        <div className="rounded-xl border border-neutral-200/80 bg-neutral-50/70 p-3.5 text-xs text-neutral-600 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 rounded-full bg-emerald-600 shrink-0" />
            <span>
              Evaluation engine: <span className="font-semibold text-neutral-800">Academic Demonstration Engine</span>. Questions and reference answers are grounded directly in your saved experiment text.
            </span>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col-reverse sm:flex-row items-center justify-between gap-3 pt-2">
          <button
            type="button"
            onClick={onBack}
            className="w-full sm:w-auto inline-flex h-10 items-center justify-center rounded-xl border border-neutral-300 bg-white px-5 text-xs sm:text-sm font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
          >
            Cancel
          </button>

          <button
            type="submit"
            className="w-full sm:w-auto inline-flex h-10 items-center justify-center gap-2 rounded-xl bg-neutral-900 px-6 text-xs sm:text-sm font-semibold text-white shadow-sm hover:bg-emerald-700 active:scale-[0.98] transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
          >
            <Play className="h-4 w-4 fill-white" />
            <span>Start Viva</span>
          </button>
        </div>
      </form>
    </div>
  );
};

export default VivaSetupScreen;
