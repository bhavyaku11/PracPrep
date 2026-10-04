import React, { useState, useEffect } from "react";
import { X, Edit2, AlertCircle, Save, FileText, BookOpen } from "lucide-react";
import type { ExperimentRecord, ExperimentStatus } from "../../types/experiment";

interface EditExperimentModalProps {
  experiment: ExperimentRecord | null;
  isOpen: boolean;
  initialTab?: "basic" | "content";
  onClose: () => void;
  onSave: (id: string, updates: Partial<ExperimentRecord>) => void;
}

interface EditExperimentFormProps {
  experiment: ExperimentRecord;
  initialTab?: "basic" | "content";
  onClose: () => void;
  onSave: (id: string, updates: Partial<ExperimentRecord>) => void;
}

const EditExperimentForm: React.FC<EditExperimentFormProps> = ({
  experiment,
  initialTab = "basic",
  onClose,
  onSave,
}) => {
  const [activeTab, setActiveTab] = useState<"basic" | "content">(initialTab);
  
  // Basic info fields
  const [title, setTitle] = useState(experiment.title);
  const [subject, setSubject] = useState(experiment.subject);
  const [experimentNumber, setExperimentNumber] = useState(experiment.experimentNumber || "");
  const [courseSemester, setCourseSemester] = useState(experiment.courseSemester || "");
  const [status, setStatus] = useState<ExperimentStatus>(experiment.status);
  const [description, setDescription] = useState(experiment.description || "");

  // Lab content fields
  const [objective, setObjective] = useState(experiment.objective || "");
  const [theory, setTheory] = useState(experiment.theory || "");
  const [apparatus, setApparatus] = useState(experiment.apparatus || "");
  const [procedure, setProcedure] = useState(experiment.procedure || "");
  const [observations, setObservations] = useState(experiment.observations || "");
  const [calculations, setCalculations] = useState(experiment.calculations || "");
  const [precautions, setPrecautions] = useState(experiment.precautions || "");

  const [errors, setErrors] = useState<{ title?: string; subject?: string }>({});

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const newErrors: { title?: string; subject?: string } = {};

    if (!title.trim()) {
      newErrors.title = "Experiment title is required.";
      setActiveTab("basic");
    }
    if (!subject.trim()) {
      newErrors.subject = "Subject or laboratory is required.";
      setActiveTab("basic");
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onSave(experiment.id, {
      title: title.trim(),
      subject: subject.trim(),
      experimentNumber: experimentNumber.trim() || undefined,
      courseSemester: courseSemester.trim() || undefined,
      status,
      description: description.trim() || undefined,
      objective: objective.trim() || undefined,
      theory: theory.trim() || undefined,
      apparatus: apparatus.trim() || undefined,
      procedure: procedure.trim() || undefined,
      observations: observations.trim() || undefined,
      calculations: calculations.trim() || undefined,
      precautions: precautions.trim() || undefined,
    });

    onClose();
  };

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4 pt-3">
      {/* Sub-tab Navigation */}
      <div className="flex border-b border-neutral-200 gap-1 pb-1">
        <button
          type="button"
          onClick={() => setActiveTab("basic")}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
            activeTab === "basic"
              ? "bg-neutral-900 text-white shadow-2xs"
              : "text-neutral-600 hover:bg-neutral-100"
          }`}
        >
          <FileText className="h-3.5 w-3.5" />
          <span>Basic Details</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("content")}
          className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${
            activeTab === "content"
              ? "bg-neutral-900 text-white shadow-2xs"
              : "text-neutral-600 hover:bg-neutral-100"
          }`}
        >
          <BookOpen className="h-3.5 w-3.5" />
          <span>Lab Content & Sections</span>
        </button>
      </div>

      <div className="max-h-[55vh] overflow-y-auto pr-1 space-y-3.5">
        {activeTab === "basic" ? (
          <>
            {/* Title */}
            <div>
              <label
                htmlFor="edit-title"
                className="block text-xs font-semibold text-neutral-800 mb-1"
              >
                Experiment Title <span className="text-red-500">*</span>
              </label>
              <input
                type="text"
                id="edit-title"
                value={title}
                onChange={(e) => {
                  setTitle(e.target.value);
                  if (errors.title) setErrors((prev) => ({ ...prev, title: undefined }));
                }}
                placeholder="e.g. Verification of Ohm's Law"
                className={`w-full rounded-lg border bg-neutral-50/50 px-3 py-2 text-xs sm:text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all ${
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

            {/* Subject & Experiment Number */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="edit-subject"
                  className="block text-xs font-semibold text-neutral-800 mb-1"
                >
                  Subject / Laboratory <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  id="edit-subject"
                  value={subject}
                  onChange={(e) => {
                    setSubject(e.target.value);
                    if (errors.subject) setErrors((prev) => ({ ...prev, subject: undefined }));
                  }}
                  placeholder="e.g. Physics Lab"
                  className={`w-full rounded-lg border bg-neutral-50/50 px-3 py-2 text-xs sm:text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all ${
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
                <label
                  htmlFor="edit-exp-number"
                  className="block text-xs font-semibold text-neutral-800 mb-1"
                >
                  Experiment Number <span className="text-neutral-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  id="edit-exp-number"
                  value={experimentNumber}
                  onChange={(e) => setExperimentNumber(e.target.value)}
                  placeholder="e.g. Exp 01"
                  className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs sm:text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30"
                />
              </div>
            </div>

            {/* Status & Course Semester */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="edit-status"
                  className="block text-xs font-semibold text-neutral-800 mb-1"
                >
                  Experiment Status
                </label>
                <select
                  id="edit-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as ExperimentStatus)}
                  className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs sm:text-sm text-neutral-900 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 cursor-pointer"
                >
                  <option value="ready">Ready / In Progress</option>
                  <option value="in-progress">In Progress</option>
                  <option value="completed">Completed</option>
                  <option value="draft">Draft</option>
                </select>
              </div>

              <div>
                <label
                  htmlFor="edit-semester"
                  className="block text-xs font-semibold text-neutral-800 mb-1"
                >
                  Course / Semester <span className="text-neutral-400 font-normal">(Optional)</span>
                </label>
                <input
                  type="text"
                  id="edit-semester"
                  value={courseSemester}
                  onChange={(e) => setCourseSemester(e.target.value)}
                  placeholder="e.g. Semester 2"
                  className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs sm:text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30"
                />
              </div>
            </div>

            {/* Notes / Description */}
            <div>
              <label
                htmlFor="edit-description"
                className="block text-xs font-semibold text-neutral-800 mb-1"
              >
                Summary / Notes <span className="text-neutral-400 font-normal">(Optional)</span>
              </label>
              <textarea
                id="edit-description"
                rows={2}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Overview, notes, or equipment constraints..."
                className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs sm:text-sm text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
              />
            </div>
          </>
        ) : (
          <>
            {/* Objective */}
            <div>
              <label
                htmlFor="edit-objective"
                className="block text-xs font-semibold text-neutral-800 mb-1"
              >
                Aim / Objective
              </label>
              <textarea
                id="edit-objective"
                rows={2}
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                placeholder="State the primary objective of this experiment..."
                className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
              />
            </div>

            {/* Theory */}
            <div>
              <label
                htmlFor="edit-theory"
                className="block text-xs font-semibold text-neutral-800 mb-1"
              >
                Theory & Governing Principles
              </label>
              <textarea
                id="edit-theory"
                rows={4}
                value={theory}
                onChange={(e) => setTheory(e.target.value)}
                placeholder="Key physical laws, working principles, equations, and derivations..."
                className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y font-mono text-[11px]"
              />
            </div>

            {/* Apparatus */}
            <div>
              <label
                htmlFor="edit-apparatus"
                className="block text-xs font-semibold text-neutral-800 mb-1"
              >
                Apparatus & Equipment
              </label>
              <textarea
                id="edit-apparatus"
                rows={3}
                value={apparatus}
                onChange={(e) => setApparatus(e.target.value)}
                placeholder="List instruments, components, specifications (one per line)..."
                className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
              />
            </div>

            {/* Procedure */}
            <div>
              <label
                htmlFor="edit-procedure"
                className="block text-xs font-semibold text-neutral-800 mb-1"
              >
                Procedure Steps
              </label>
              <textarea
                id="edit-procedure"
                rows={4}
                value={procedure}
                onChange={(e) => setProcedure(e.target.value)}
                placeholder="1. Connect the circuit...&#10;2. Set the initial voltage...&#10;3. Record the ammeter readings..."
                className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
              />
            </div>

            {/* Observations & Calculations */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label
                  htmlFor="edit-observations"
                  className="block text-xs font-semibold text-neutral-800 mb-1"
                >
                  Observations
                </label>
                <textarea
                  id="edit-observations"
                  rows={3}
                  value={observations}
                  onChange={(e) => setObservations(e.target.value)}
                  placeholder="Experimental values, tabular notes, parameters recorded..."
                  className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
                />
              </div>

              <div>
                <label
                  htmlFor="edit-calculations"
                  className="block text-xs font-semibold text-neutral-800 mb-1"
                >
                  Calculations & Formulas
                </label>
                <textarea
                  id="edit-calculations"
                  rows={3}
                  value={calculations}
                  onChange={(e) => setCalculations(e.target.value)}
                  placeholder="Mathematical relations, sample substitutions, final values..."
                  className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
                />
              </div>
            </div>

            {/* Precautions */}
            <div>
              <label
                htmlFor="edit-precautions"
                className="block text-xs font-semibold text-neutral-800 mb-1"
              >
                Precautions & Safety Guidelines
              </label>
              <textarea
                id="edit-precautions"
                rows={3}
                value={precautions}
                onChange={(e) => setPrecautions(e.target.value)}
                placeholder="Critical safety rules, equipment handling guidelines (one per line)..."
                className="w-full rounded-lg border border-neutral-300 bg-neutral-50/50 px-3 py-2 text-xs text-neutral-900 placeholder:text-neutral-400 outline-none transition-all focus:border-emerald-600 focus:bg-white focus:ring-1 focus:ring-emerald-600/30 resize-y"
              />
            </div>
          </>
        )}
      </div>

      {/* Action Buttons */}
      <div className="flex flex-col-reverse sm:flex-row items-center justify-end gap-2.5 pt-3 border-t border-neutral-100">
        <button
          type="button"
          onClick={onClose}
          className="w-full sm:w-auto inline-flex h-9 items-center justify-center rounded-lg border border-neutral-300 bg-white px-4 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          className="w-full sm:w-auto inline-flex h-9 items-center justify-center gap-1.5 rounded-lg bg-neutral-900 px-4 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
        >
          <Save className="h-3.5 w-3.5" />
          <span>Save Changes</span>
        </button>
      </div>
    </form>
  );
};

export const EditExperimentModal: React.FC<EditExperimentModalProps> = ({
  experiment,
  isOpen,
  initialTab = "basic",
  onClose,
  onSave,
}) => {
  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !experiment) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="edit-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-950/40 backdrop-blur-xs animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div
        className="w-full max-w-xl rounded-2xl border border-neutral-200 bg-white p-5 sm:p-6 shadow-2xl animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-3 border-b border-neutral-100">
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-neutral-100 text-neutral-800">
              <Edit2 className="h-4 w-4 text-emerald-700" />
            </div>
            <div>
              <h2
                id="edit-modal-title"
                className="font-jakarta text-base font-bold text-neutral-900"
              >
                Edit Experiment
              </h2>
              <p className="text-xs text-neutral-500">
                Update experiment details, theory, procedure, and notes.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-1.5 rounded-lg text-neutral-400 hover:text-neutral-700 hover:bg-neutral-100 transition-colors"
            aria-label="Close edit dialog"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Modal Form component with key={experiment.id} */}
        <EditExperimentForm
          key={`${experiment.id}-${initialTab}`}
          experiment={experiment}
          initialTab={initialTab}
          onClose={onClose}
          onSave={onSave}
        />
      </div>
    </div>
  );
};

export default EditExperimentModal;
