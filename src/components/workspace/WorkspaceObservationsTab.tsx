import React from "react";
import { Table, Calculator, Edit2, FileSpreadsheet } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";

interface WorkspaceObservationsTabProps {
  experiment: ExperimentRecord;
  onEdit: () => void;
}

export const WorkspaceObservationsTab: React.FC<WorkspaceObservationsTabProps> = ({
  experiment,
  onEdit,
}) => {
  const hasObservations = Boolean(
    experiment.observations && experiment.observations.trim().length > 0
  );
  const hasCalculations = Boolean(
    experiment.calculations && experiment.calculations.trim().length > 0
  );
  const hasAnyData = hasObservations || hasCalculations;

  return (
    <div className="space-y-4">
      {/* Header Row */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-neutral-200">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-emerald-50 text-emerald-800">
            <Table className="h-4 w-4" />
          </div>
          <div>
            <h2 className="font-jakarta text-base font-bold text-neutral-900">
              Observations, Data & Calculations
            </h2>
            <p className="text-xs text-neutral-500">
              Record experimental readings, tabular parameters, and mathematical calculations.
            </p>
          </div>
        </div>

        <button
          type="button"
          onClick={onEdit}
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded-lg border border-neutral-300 bg-white px-3 text-xs font-semibold text-neutral-700 hover:bg-neutral-50 transition-colors shadow-2xs self-start sm:self-auto"
        >
          <Edit2 className="h-3.5 w-3.5" />
          <span>Edit Observations</span>
        </button>
      </div>

      {/* Content or Empty State */}
      {hasAnyData ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Observations Box */}
          <div className="rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-2xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-neutral-100">
              <div className="flex items-center gap-2">
                <Table className="h-4 w-4 text-emerald-700" />
                <h3 className="font-jakarta text-sm font-bold text-neutral-900">
                  Observation Readings & Tables
                </h3>
              </div>
            </div>

            {hasObservations ? (
              <div className="bg-neutral-50/70 p-4 rounded-xl border border-neutral-100 text-xs sm:text-sm text-neutral-800 font-mono whitespace-pre-wrap leading-relaxed overflow-x-auto">
                {experiment.observations}
              </div>
            ) : (
              <p className="text-xs text-neutral-400 italic py-4">
                No observations recorded yet.
              </p>
            )}
          </div>

          {/* Calculations Box */}
          <div className="rounded-2xl border border-neutral-200/90 bg-white p-5 sm:p-6 shadow-2xs space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-neutral-100">
              <div className="flex items-center gap-2">
                <Calculator className="h-4 w-4 text-emerald-700" />
                <h3 className="font-jakarta text-sm font-bold text-neutral-900">
                  Formulas & Calculation Notes
                </h3>
              </div>
            </div>

            {hasCalculations ? (
              <div className="bg-neutral-50/70 p-4 rounded-xl border border-neutral-100 text-xs sm:text-sm text-neutral-800 font-mono whitespace-pre-wrap leading-relaxed overflow-x-auto">
                {experiment.calculations}
              </div>
            ) : (
              <p className="text-xs text-neutral-400 italic py-4">
                No calculation formulas or notes recorded yet.
              </p>
            )}
          </div>
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center rounded-2xl border-2 border-dashed border-neutral-200 bg-white py-14 px-4 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-neutral-100 text-neutral-500 mb-3">
            <FileSpreadsheet className="h-6 w-6" />
          </div>
          <h3 className="font-jakarta text-sm sm:text-base font-bold text-neutral-900 mb-1">
            No observations recorded.
          </h3>
          <p className="max-w-md text-xs text-neutral-500 leading-relaxed mb-5">
            Use this section to organize experimental readings and calculations during your lab session.
          </p>
          <button
            type="button"
            onClick={onEdit}
            className="inline-flex h-9 items-center justify-center gap-2 rounded-xl bg-neutral-900 px-4 text-xs font-semibold text-white shadow-2xs hover:bg-emerald-700 transition-colors"
          >
            <Edit2 className="h-3.5 w-3.5" />
            <span>Edit Experiment</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default WorkspaceObservationsTab;
