import { useMemo, useState } from "react";

import { registerModel, uploadDataset, withApiError } from "../api/client";

function Upload({ onModelRegistered }) {
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [datasetInfo, setDatasetInfo] = useState(null);
  const [selectedAttributes, setSelectedAttributes] = useState([]);
  const [modelName, setModelName] = useState("LoanApprovalModel");
  const [isUploading, setIsUploading] = useState(false);
  const [isRegistering, setIsRegistering] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [successMessage, setSuccessMessage] = useState("");

  const sortedColumns = useMemo(() => datasetInfo?.columns || [], [datasetInfo]);

  const handleFileSelection = (selectedFile) => {
    if (!selectedFile) {
      return;
    }
    setFile(selectedFile);
    setDatasetInfo(null);
    setSelectedAttributes([]);
    setSuccessMessage("");
    setErrorMessage("");
  };

  const handleAnalyzeDataset = async () => {
    if (!file) {
      setErrorMessage("Select a CSV file first.");
      return;
    }

    setIsUploading(true);
    try {
      const result = await uploadDataset(file);
      setDatasetInfo(result);
      setSelectedAttributes(result.suggested_sensitive_attributes || []);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to upload dataset."));
    } finally {
      setIsUploading(false);
    }
  };

  const toggleAttribute = (attribute) => {
    setSelectedAttributes((previous) => {
      if (previous.includes(attribute)) {
        return previous.filter((item) => item !== attribute);
      }
      return [...previous, attribute];
    });
  };

  const handleRegisterModel = async () => {
    if (!modelName.trim()) {
      setErrorMessage("Please provide a model name.");
      return;
    }

    setIsRegistering(true);
    try {
      const created = await registerModel({
        name: modelName.trim(),
        sensitive_attributes: selectedAttributes,
      });

      setSuccessMessage(`Model registered successfully. Model ID: ${created.id}`);
      setErrorMessage("");
      if (onModelRegistered) {
        await onModelRegistered(created.id);
      }
    } catch (error) {
      setErrorMessage(withApiError(error, "Failed to register model."));
    } finally {
      setIsRegistering(false);
    }
  };

  return (
    <section className="space-y-4">
      <div className="glass-panel rounded-2xl p-6">
        <h2 className="font-heading text-2xl font-bold">Upload Dataset and Register Model</h2>
        <p className="mt-1 text-sm text-slate-600">
          Drag and drop a CSV, review detected sensitive columns, then register a model for monitoring.
        </p>

        <div
          className={`mt-5 rounded-2xl border-2 border-dashed p-6 text-center transition ${
            isDragging ? "border-fair-green bg-emerald-50" : "border-slate-300 bg-white/70"
          }`}
          onDragOver={(event) => {
            event.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={(event) => {
            event.preventDefault();
            setIsDragging(false);
            handleFileSelection(event.dataTransfer.files?.[0]);
          }}
        >
          <p className="text-sm text-slate-600">Drop CSV file here or choose a file.</p>
          <input
            className="mt-3 block w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
            type="file"
            accept=".csv"
            onChange={(event) => handleFileSelection(event.target.files?.[0])}
          />
          {file && <p className="mt-2 text-xs font-mono text-slate-600">Selected: {file.name}</p>}
          <button
            type="button"
            className="mt-4 rounded-xl bg-fair-ink px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            onClick={handleAnalyzeDataset}
            disabled={!file || isUploading}
          >
            {isUploading ? "Analyzing CSV..." : "Upload and Detect Sensitive Columns"}
          </button>
        </div>
      </div>

      {datasetInfo && (
        <div className="glass-panel rounded-2xl p-6">
          <h3 className="font-heading text-lg font-bold">Detected Columns</h3>
          <p className="mt-1 text-sm text-slate-600">Suggested sensitive attributes are pre-selected.</p>

          <div className="mt-4 flex flex-wrap gap-2">
            {sortedColumns.map((column) => {
              const suggested = (datasetInfo.suggested_sensitive_attributes || []).includes(column);
              return (
                <span
                  key={column}
                  className={`rounded-full px-3 py-1 text-xs font-semibold ${
                    suggested ? "bg-amber-100 text-amber-900" : "bg-slate-100 text-slate-700"
                  }`}
                >
                  {column}
                </span>
              );
            })}
          </div>

          <div className="mt-5">
            <h4 className="text-sm font-semibold text-slate-700">Confirm Sensitive Attributes</h4>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {sortedColumns.map((column) => (
                <label key={column} className="flex items-center gap-2 rounded-lg bg-white/80 px-3 py-2 text-sm">
                  <input
                    type="checkbox"
                    checked={selectedAttributes.includes(column)}
                    onChange={() => toggleAttribute(column)}
                  />
                  <span>{column}</span>
                </label>
              ))}
            </div>
          </div>

          <div className="mt-5 grid gap-3 sm:grid-cols-[1fr_auto] sm:items-end">
            <div>
              <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-500" htmlFor="model-name">
                Model Name
              </label>
              <input
                id="model-name"
                className="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-sm"
                value={modelName}
                onChange={(event) => setModelName(event.target.value)}
                placeholder="LoanApprovalModel"
              />
            </div>

            <button
              type="button"
              className="rounded-xl bg-fair-green px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              onClick={handleRegisterModel}
              disabled={isRegistering || !modelName.trim()}
            >
              {isRegistering ? "Registering..." : "Register Model"}
            </button>
          </div>
        </div>
      )}

      {errorMessage && (
        <div className="rounded-xl border border-fair-red/30 bg-fair-red/10 px-4 py-3 text-sm text-fair-red">{errorMessage}</div>
      )}

      {successMessage && (
        <div className="rounded-xl border border-fair-green/30 bg-emerald-100 px-4 py-3 text-sm font-semibold text-emerald-900">
          {successMessage}
        </div>
      )}
    </section>
  );
}

export default Upload;
