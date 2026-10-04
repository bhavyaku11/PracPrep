import React, { useRef, useState } from "react";
import { UploadCloud, FileText, CheckCircle2, AlertCircle, X } from "lucide-react";
import type { UploadedFileMeta } from "../../types/experiment";

interface LabManualUploaderProps {
  file: UploadedFileMeta | null;
  onFileSelect: (fileMeta: UploadedFileMeta) => void;
  onFileRemove: () => void;
  error?: string;
}

const MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB
const ACCEPTED_EXTENSIONS = [".pdf", ".docx", ".doc", ".txt", ".md"];
const ACCEPTED_MIME_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "application/msword",
  "text/plain",
  "text/markdown",
];

export const LabManualUploader: React.FC<LabManualUploaderProps> = ({
  file,
  onFileSelect,
  onFileRemove,
  error,
}) => {
  const [isDragOver, setIsDragOver] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const validateAndProcessFile = (selectedFile: File) => {
    setValidationError(null);

    if (selectedFile.size > MAX_FILE_SIZE_BYTES) {
      setValidationError("File exceeds maximum allowed size (25 MB).");
      return;
    }

    const extension = `.${selectedFile.name.split(".").pop()?.toLowerCase()}`;
    const isValidExtension = ACCEPTED_EXTENSIONS.includes(extension);
    const isValidMime = ACCEPTED_MIME_TYPES.includes(selectedFile.type);

    if (!isValidExtension && !isValidMime) {
      setValidationError("Unsupported format. Please upload a PDF, Word document, or text file.");
      return;
    }

    const fileMeta: UploadedFileMeta = {
      file: selectedFile,
      name: selectedFile.name,
      size: selectedFile.size,
      type: selectedFile.type || extension,
      formattedSize: formatFileSize(selectedFile.size),
      uploadedAt: new Date(),
    };

    onFileSelect(fileMeta);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      validateAndProcessFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndProcessFile(e.target.files[0]);
    }
  };

  const handleBrowseClick = () => {
    fileInputRef.current?.click();
  };

  const handleRemove = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setValidationError(null);
    onFileRemove();
  };

  const displayError = validationError || error;

  return (
    <div className="space-y-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.doc,.txt,.md"
        onChange={handleFileInputChange}
        className="sr-only"
        aria-label="Upload laboratory manual file"
      />

      {file ? (
        /* Clean Selected File Card */
        <div className="flex items-center justify-between rounded-xl border border-neutral-200/90 bg-white p-3.5 shadow-2xs">
          <div className="flex items-center gap-3 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700">
              <FileText className="h-4 w-4" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <p className="truncate text-sm font-semibold text-neutral-900" title={file.name}>
                  {file.name}
                </p>
                <span className="inline-flex shrink-0 items-center gap-1 rounded bg-emerald-100 px-1.5 py-0.2 text-[10px] font-bold text-emerald-800">
                  <CheckCircle2 className="h-3 w-3" />
                  Attached
                </span>
              </div>
              <p className="text-xs text-neutral-400 mt-0.5">{file.formattedSize}</p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <button
              type="button"
              onClick={handleBrowseClick}
              className="rounded-lg border border-neutral-200 px-2.5 py-1 text-xs font-medium text-neutral-700 hover:bg-neutral-50 transition-colors"
            >
              Replace
            </button>
            <button
              type="button"
              onClick={handleRemove}
              className="p-1 rounded-lg text-neutral-400 hover:text-red-600 hover:bg-red-50 transition-colors"
              aria-label="Remove file"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      ) : (
        /* Minimalist Dropzone */
        <div
          onClick={handleBrowseClick}
          onDragEnter={handleDragEnter}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              handleBrowseClick();
            }
          }}
          className={`group flex flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center cursor-pointer transition-all outline-none focus-visible:ring-2 focus-visible:ring-emerald-600 ${
            isDragOver
              ? "border-emerald-600 bg-emerald-50/50"
              : displayError
              ? "border-red-300 bg-red-50/20"
              : "border-neutral-300 bg-neutral-50/30 hover:border-neutral-400 hover:bg-neutral-50/70"
          }`}
        >
          <UploadCloud className="h-7 w-7 text-neutral-400 group-hover:text-emerald-700 transition-colors mb-2" />
          <p className="text-sm font-semibold text-neutral-900">
            Drop lab manual here, or <span className="text-emerald-700 underline">browse</span>
          </p>
          <p className="mt-1 text-xs text-neutral-400">PDF, DOCX, or TXT up to 25MB</p>
        </div>
      )}

      {displayError && (
        <div className="flex items-center gap-1.5 text-xs text-red-600 pt-1">
          <AlertCircle className="h-3.5 w-3.5 shrink-0" />
          <span>{displayError}</span>
        </div>
      )}
    </div>
  );
};

export default LabManualUploader;
