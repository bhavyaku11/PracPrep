import React from "react";
import { AlertCircle } from "lucide-react";
import type { ExperimentFormData, FormValidationErrors } from "../../types/experiment";

interface ManualExperimentFormProps {
  formData: ExperimentFormData;
  errors: FormValidationErrors;
  onChange: (fields: Partial<ExperimentFormData>) => void;
  onClearError: (field: keyof FormValidationErrors) => void;
}

export const ManualExperimentForm: React.FC<ManualExperimentFormProps> = ({
  formData,
  errors,
  onChange,
  onClearError,
}) => {
  return (
    <div className="space-y-4">
      {/* 1. Basic Info */}
      <div className="rounded-xl border border-neutral-200/90 bg-white p-5 shadow-2xs space-y-3.5">
        <h3 className="font-jakarta text-sm font-bold text-neutral-900">
          Basic Information
        </h3>

        <div className="space-y-3">
          <div>
            <label htmlFor="manual-exp-title" className="block text-xs font-semibold text-neutral-800 mb-1">
              Experiment Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="manual-exp-title"
              value={formData.title}
              onChange={(e) => {
                onChange({ title: e.target.value });
                if (errors.title) onClearError("title");
              }}
              placeholder="e.g. Determination of Wavelength of Sodium Light"
              className={`w-full rounded-lg border bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all ${
                errors.title
                  ? "border-red-400 bg-red-50/20 ring-1 ring-red-200"
                  : "border-neutral-300 focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30"
              }`}
            />
            {errors.title && (
              <p className="mt-1 flex items-center gap-1 text-xs text-red-600">
                <AlertCircle className="h-3 w-3" />
                <span>{errors.title}</span>
              </p>
            )}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label htmlFor="manual-exp-subject" className="block text-xs font-semibold text-neutral-800 mb-1">
                Subject / Laboratory <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="manual-exp-subject"
                value={formData.subject}
                onChange={(e) => {
                  onChange({ subject: e.target.value });
                  if (errors.subject) onClearError("subject");
                }}
                placeholder="e.g. Physics Lab"
                className={`w-full rounded-lg border bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all ${
                  errors.subject
                    ? "border-red-400 bg-red-50/20 ring-1 ring-red-200"
                    : "border-neutral-300 focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30"
                }`}
              />
              {errors.subject && (
                <p className="mt-1 flex items-center gap-1 text-xs text-red-600">
                  <AlertCircle className="h-3 w-3" />
                  <span>{errors.subject}</span>
                </p>
              )}
            </div>

            <div>
              <label htmlFor="manual-exp-number" className="block text-xs font-semibold text-neutral-800 mb-1">
                Experiment Number <span className="text-neutral-400 font-normal">(Optional)</span>
              </label>
              <input
                type="text"
                id="manual-exp-number"
                value={formData.experimentNumber}
                onChange={(e) => onChange({ experimentNumber: e.target.value })}
                placeholder="e.g. Exp 02"
                className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30"
              />
            </div>
          </div>
        </div>
      </div>

      {/* 2. Objective & Theory */}
      <div className="rounded-xl border border-neutral-200/90 bg-white p-5 shadow-2xs space-y-3.5">
        <h3 className="font-jakarta text-sm font-bold text-neutral-900">
          Objective & Theory
        </h3>

        <div className="space-y-3">
          <div>
            <label htmlFor="manual-objective" className="block text-xs font-semibold text-neutral-800 mb-1">
              Aim / Objective
            </label>
            <textarea
              id="manual-objective"
              rows={2}
              value={formData.objective}
              onChange={(e) => onChange({ objective: e.target.value })}
              placeholder="Primary aim or expected result..."
              className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
            />
          </div>

          <div>
            <label htmlFor="manual-theory" className="block text-xs font-semibold text-neutral-800 mb-1">
              Theory & Formulas
            </label>
            <textarea
              id="manual-theory"
              rows={3}
              value={formData.theory}
              onChange={(e) => onChange({ theory: e.target.value })}
              placeholder="Underlying scientific law, working principle, or formulas..."
              className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
            />
          </div>
        </div>
      </div>

      {/* 3. Setup & Procedure */}
      <div className="rounded-xl border border-neutral-200/90 bg-white p-5 shadow-2xs space-y-3.5">
        <h3 className="font-jakarta text-sm font-bold text-neutral-900">
          Apparatus & Procedure
        </h3>

        <div className="space-y-3">
          <div>
            <label htmlFor="manual-apparatus" className="block text-xs font-semibold text-neutral-800 mb-1">
              Apparatus Required
            </label>
            <textarea
              id="manual-apparatus"
              rows={2}
              value={formData.apparatus}
              onChange={(e) => onChange({ apparatus: e.target.value })}
              placeholder="Components, equipment, measuring instruments..."
              className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
            />
          </div>

          <div>
            <label htmlFor="manual-procedure" className="block text-xs font-semibold text-neutral-800 mb-1">
              Procedure Steps
            </label>
            <textarea
              id="manual-procedure"
              rows={3}
              value={formData.procedure}
              onChange={(e) => onChange({ procedure: e.target.value })}
              placeholder="1. Set up apparatus... 2. Take observations..."
              className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ManualExperimentForm;
