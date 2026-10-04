import React from "react";
import { AlertCircle } from "lucide-react";
import type { ExperimentFormData, FormValidationErrors } from "../../types/experiment";

interface ExperimentDetailsFormProps {
  formData: ExperimentFormData;
  errors: FormValidationErrors;
  onChange: (fields: Partial<ExperimentFormData>) => void;
  onClearError: (field: keyof FormValidationErrors) => void;
}

export const ExperimentDetailsForm: React.FC<ExperimentDetailsFormProps> = ({
  formData,
  errors,
  onChange,
  onClearError,
}) => {
  return (
    <div className="space-y-4 rounded-xl border border-neutral-200/90 bg-white p-5 shadow-2xs">
      <h3 className="font-jakarta text-sm font-bold text-neutral-900">
        Experiment Details
      </h3>

      <div className="space-y-3.5">
        {/* Title */}
        <div>
          <label htmlFor="exp-title" className="block text-xs font-semibold text-neutral-800 mb-1">
            Experiment Title <span className="text-red-500">*</span>
          </label>
          <input
            type="text"
            id="exp-title"
            value={formData.title}
            onChange={(e) => {
              onChange({ title: e.target.value });
              if (errors.title) onClearError("title");
            }}
            placeholder="e.g. Verification of Ohm's Law and Series-Parallel Resistance"
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

        {/* Subject & Number */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <div>
            <label htmlFor="exp-subject" className="block text-xs font-semibold text-neutral-800 mb-1">
              Subject / Laboratory <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              id="exp-subject"
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
            <label htmlFor="exp-number" className="block text-xs font-semibold text-neutral-800 mb-1">
              Experiment Number <span className="text-neutral-400 font-normal">(Optional)</span>
            </label>
            <input
              type="text"
              id="exp-number"
              value={formData.experimentNumber}
              onChange={(e) => onChange({ experimentNumber: e.target.value })}
              placeholder="e.g. Exp 01"
              className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30"
            />
          </div>
        </div>

        {/* Course / Semester */}
        <div>
          <label htmlFor="exp-semester" className="block text-xs font-semibold text-neutral-800 mb-1">
            Course / Semester <span className="text-neutral-400 font-normal">(Optional)</span>
          </label>
          <input
            type="text"
            id="exp-semester"
            value={formData.courseSemester}
            onChange={(e) => onChange({ courseSemester: e.target.value })}
            placeholder="e.g. Semester 2"
            className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30"
          />
        </div>

        {/* Short Notes */}
        <div>
          <label htmlFor="exp-desc" className="block text-xs font-semibold text-neutral-800 mb-1">
            Notes <span className="text-neutral-400 font-normal">(Optional)</span>
          </label>
          <textarea
            id="exp-desc"
            rows={2}
            value={formData.description}
            onChange={(e) => onChange({ description: e.target.value })}
            placeholder="Specific focus areas, apparatus constraints, or syllabus notes..."
            className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
          />
        </div>
      </div>
    </div>
  );
};

export default ExperimentDetailsForm;
