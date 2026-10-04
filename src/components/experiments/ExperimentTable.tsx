import React from "react";
import { Edit2, Trash2, FileText, ArrowRight } from "lucide-react";
import type { ExperimentRecord } from "../../types/experiment";
import ExperimentStatusBadge from "./ExperimentStatusBadge";

interface ExperimentTableProps {
  experiments: ExperimentRecord[];
  onOpen: (id: string) => void;
  onEdit: (experiment: ExperimentRecord) => void;
  onDelete: (experiment: ExperimentRecord) => void;
}

export const ExperimentTable: React.FC<ExperimentTableProps> = ({
  experiments,
  onOpen,
  onEdit,
  onDelete,
}) => {
  return (
    <div className="rounded-xl border border-neutral-200/90 bg-white shadow-2xs overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse text-xs sm:text-sm">
          <thead>
            <tr className="border-b border-neutral-200 bg-neutral-50/80 text-[11px] font-semibold text-neutral-500 uppercase tracking-wider">
              <th scope="col" className="py-3 px-4 sm:px-5">
                Experiment
              </th>
              <th scope="col" className="py-3 px-4">
                Subject
              </th>
              <th scope="col" className="py-3 px-4">
                Status
              </th>
              <th scope="col" className="py-3 px-4">
                Last Updated
              </th>
              <th scope="col" className="py-3 px-4 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-100">
            {experiments.map((exp) => (
              <tr
                key={exp.id}
                className="group transition-colors hover:bg-neutral-50/70 focus-within:bg-neutral-50/70"
              >
                {/* Column 1: Title & Experiment Number */}
                <td className="py-3.5 px-4 sm:px-5">
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 transition-colors group-hover:bg-emerald-100/80">
                      <FileText className="h-4 w-4" />
                    </div>
                    <div className="min-w-0 max-w-xs xl:max-w-md">
                      <button
                        type="button"
                        onClick={() => onOpen(exp.id)}
                        className="text-left font-semibold text-neutral-900 hover:text-emerald-700 hover:underline transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 rounded truncate block max-w-full"
                        title={exp.title}
                      >
                        {exp.title}
                      </button>
                      <div className="flex items-center gap-2 mt-0.5 text-xs text-neutral-500">
                        {exp.experimentNumber && (
                          <span className="font-mono text-[11px] font-semibold text-neutral-600 bg-neutral-100 px-1.5 py-0.2 rounded">
                            {exp.experimentNumber}
                          </span>
                        )}
                        {exp.courseSemester && (
                          <span className="text-[11px] text-neutral-400">
                            {exp.courseSemester}
                          </span>
                        )}
                        <span className="text-[11px] text-neutral-400">
                          • {exp.createdAt}
                        </span>
                        {exp.hasManualFile && (
                          <span className="text-[11px] text-neutral-400">
                            • Manual
                          </span>
                        )}
                      </div>
                    </div>
                  </div>
                </td>

                {/* Column 2: Subject */}
                <td className="py-3.5 px-4 font-medium text-neutral-700">
                  <span className="inline-block max-w-[160px] truncate" title={exp.subject}>
                    {exp.subject}
                  </span>
                </td>

                {/* Column 3: Status Badge */}
                <td className="py-3.5 px-4">
                  <ExperimentStatusBadge status={exp.status} />
                </td>

                {/* Column 4: Last Updated */}
                <td className="py-3.5 px-4 text-xs text-neutral-500 whitespace-nowrap">
                  {exp.updatedAt}
                </td>

                {/* Column 5: Actions */}
                <td className="py-3.5 px-4 text-right whitespace-nowrap">
                  <div className="flex items-center justify-end gap-1.5">
                    {/* Open action */}
                    <button
                      type="button"
                      onClick={() => onOpen(exp.id)}
                      className="inline-flex h-8 items-center gap-1 rounded-lg bg-neutral-900 px-3 text-xs font-semibold text-white shadow-2xs transition-colors hover:bg-emerald-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
                      aria-label={`Open experiment ${exp.title}`}
                    >
                      <span>Open</span>
                      <ArrowRight className="h-3 w-3" />
                    </button>

                    {/* Edit action */}
                    <button
                      type="button"
                      onClick={() => onEdit(exp)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 bg-white text-neutral-600 shadow-2xs transition-colors hover:border-neutral-300 hover:bg-neutral-50 hover:text-neutral-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-600"
                      aria-label={`Edit metadata for ${exp.title}`}
                      title="Edit experiment"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                    </button>

                    {/* Delete action */}
                    <button
                      type="button"
                      onClick={() => onDelete(exp)}
                      className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-neutral-200 bg-white text-neutral-400 shadow-2xs transition-colors hover:border-red-200 hover:bg-red-50 hover:text-red-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-600"
                      aria-label={`Delete experiment ${exp.title}`}
                      title="Delete experiment"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default ExperimentTable;
