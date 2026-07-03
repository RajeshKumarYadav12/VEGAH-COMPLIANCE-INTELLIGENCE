"use client";
import { useState, useCallback, useRef } from "react";
import { FiFile, FiDatabase } from "react-icons/fi";
import { UploadedFiles } from "@/types/rfp";
import { uploadCapabilities } from "@/lib/api";

interface UploadZoneProps {
  onFilesSelected: (files: UploadedFiles) => void;
  disabled?: boolean;
}

export function UploadZone({ onFilesSelected, disabled }: UploadZoneProps) {
  const [rfpFile, setRfpFile] = useState<File | null>(null);
  const [capFile, setCapFile] = useState<File | null>(null);
  const [isDraggingRfp, setIsDraggingRfp] = useState(false);
  const [isDraggingCap, setIsDraggingCap] = useState(false);
  const [uploadingCap, setUploadingCap] = useState(false);
  const [capUploadMsg, setCapUploadMsg] = useState<string>("");
  const rfpInputRef = useRef<HTMLInputElement>(null);
  const capInputRef = useRef<HTMLInputElement>(null);

  const handleRfpFile = useCallback(
    (file: File) => {
      if (!file.name.toLowerCase().endsWith(".pdf")) {
        alert("Please upload a PDF file for the RFP.");
        return;
      }
      setRfpFile(file);
      onFilesSelected({ rfpFile: file, capabilityFile: capFile });
    },
    [capFile, onFilesSelected],
  );

  const handleCapFile = useCallback(
    async (file: File) => {
      const ext = file.name.toLowerCase();
      if (!ext.endsWith(".csv") && !ext.endsWith(".json")) {
        alert("Please upload a CSV or JSON file for capabilities.");
        return;
      }
      setCapFile(file);
      onFilesSelected({ rfpFile: rfpFile, capabilityFile: file });

      // Auto-upload to backend
      try {
        setUploadingCap(true);
        setCapUploadMsg("Uploading & embedding capabilities...");
        const result = await uploadCapabilities(file);
        setCapUploadMsg(
          `✓ ${result.capabilities_parsed} capabilities embedded into knowledge base`,
        );
      } catch (err) {
        setCapUploadMsg(`⚠ Upload failed: ${(err as Error).message}`);
      } finally {
        setUploadingCap(false);
      }
    },
    [rfpFile, onFilesSelected],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLDivElement>, type: "rfp" | "cap") => {
      e.preventDefault();
      if (type === "rfp") setIsDraggingRfp(false);
      else setIsDraggingCap(false);
      const file = e.dataTransfer.files[0];
      if (!file) return;
      if (type === "rfp") handleRfpFile(file);
      else handleCapFile(file);
    },
    [handleRfpFile, handleCapFile],
  );

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="grid grid-cols-1 gap-20">
      {/* RFP PDF Upload */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDraggingRfp(true);
        }}
        onDragLeave={() => setIsDraggingRfp(false)}
        onDrop={(e) => onDrop(e, "rfp")}
        onClick={() => !disabled && rfpInputRef.current?.click()}
        className={`upload-zone ${isDraggingRfp ? "upload-zone--dragging" : ""} ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      >
        <input
          ref={rfpInputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) =>
            e.target.files?.[0] && handleRfpFile(e.target.files[0])
          }
          disabled={disabled}
        />
        <div className="upload-zone__icon">
          <FiFile size={32} />
        </div>
        {rfpFile ? (
          <div className="upload-zone__file-info">
            <span className="upload-zone__filename">{rfpFile.name}</span>
            <span className="upload-zone__meta">
              {formatSize(rfpFile.size)} · PDF
            </span>
            <span className="upload-zone__badge upload-zone__badge--success">
              ✓ Ready
            </span>
          </div>
        ) : (
          <>
            <p className="upload-zone__label">Drop RFP Document here</p>
            <p className="upload-zone__sublabel">PDF format · Up to 50MB</p>
          </>
        )}
      </div>

      {/* Capability Matrix Upload */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDraggingCap(true);
        }}
        onDragLeave={() => setIsDraggingCap(false)}
        onDrop={(e) => onDrop(e, "cap")}
        onClick={() => !disabled && capInputRef.current?.click()}
        className={`upload-zone upload-zone--secondary ${isDraggingCap ? "upload-zone--dragging" : ""} ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      >
        <input
          ref={capInputRef}
          type="file"
          accept=".csv,.json"
          className="hidden"
          onChange={(e) =>
            e.target.files?.[0] && handleCapFile(e.target.files[0])
          }
          disabled={disabled}
        />
        <div className="upload-zone__icon upload-zone__icon--secondary">
          <FiDatabase size={32} />
        </div>
        {uploadingCap ? (
          <div className="upload-zone__file-info">
            <div className="upload-zone__spinner" />
            <span className="upload-zone__sublabel">{capUploadMsg}</span>
          </div>
        ) : capFile ? (
          <div className="upload-zone__file-info">
            <span className="upload-zone__filename">{capFile.name}</span>
            <span className="upload-zone__meta">
              {formatSize(capFile.size)}
            </span>
            <span className="upload-zone__badge upload-zone__badge--secondary">
              {capUploadMsg || "✓ Uploaded"}
            </span>
          </div>
        ) : (
          <>
            <p className="upload-zone__label">Capability Matrix</p>
            <p className="upload-zone__sublabel">CSV or JSON · Optional</p>
            <p className="upload-zone__hint">Auto-embeds into knowledge base</p>
          </>
        )}
      </div>
    </div>
  );
}
