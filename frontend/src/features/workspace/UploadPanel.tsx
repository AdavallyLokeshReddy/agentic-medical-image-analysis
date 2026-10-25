"use client";

import { useCallback, useRef, useState, type DragEvent } from "react";
import { ApiError } from "@/api/client";
import { api } from "@/api/endpoints";
import { Icon } from "@/components/ui/Icon";
import { Panel } from "@/components/ui/Panel";
import { StateBlock } from "@/components/ui/StateBlock";
import type { UploadResult } from "@/types/api";
import { cn, formatBytes, shortUid } from "@/utils/format";

export type UploadPhase = "idle" | "uploading" | "processing" | "done" | "error";

export interface UploadProgress {
  phase: UploadPhase;
  /** 0..1 of request-body bytes sent. */
  fraction: number;
}

function isLikelyDicom(f: File) {
  // DICOM files often have no extension; only drop obvious junk.
  return !f.name.startsWith(".");
}

export function UploadPanel({
  caseId,
  onUploaded,
  onProgress,
}: {
  caseId: string;
  onUploaded: () => void;
  onProgress: (p: UploadProgress) => void;
}) {
  const [files, setFiles] = useState<File[]>([]);
  const [phase, setPhase] = useState<UploadPhase>("idle");
  const [fraction, setFraction] = useState(0);
  const [loaded, setLoaded] = useState(0);
  const [total, setTotal] = useState(0);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [over, setOver] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const abort = useRef<AbortController | null>(null);

  const set = useCallback(
    (p: UploadPhase, f: number) => {
      setPhase(p);
      setFraction(f);
      onProgress({ phase: p, fraction: f });
    },
    [onProgress],
  );

  const accept = (list: FileList | File[] | null) => {
    if (!list) return;
    const picked = Array.from(list).filter(isLikelyDicom);
    setFiles(picked);
    setResult(null);
    setError(null);
    if (phase !== "idle") set("idle", 0);
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setOver(false);
    accept(e.dataTransfer.files);
  };

  async function start() {
    if (files.length === 0) return;
    const controller = new AbortController();
    abort.current = controller;
    setError(null);
    setResult(null);
    setLoaded(0);
    setTotal(files.reduce((n, f) => n + f.size, 0));
    set("uploading", 0);
    try {
      const res = await api.uploadSeries(
        caseId,
        files,
        (l, t) => {
          setLoaded(l);
          setTotal(t);
          const frac = t > 0 ? l / t : 0;
          // Once every byte is sent the backend is still validating and storing.
          if (frac >= 1) set("processing", 1);
          else set("uploading", frac);
        },
        controller.signal,
      );
      setResult(res);
      setFiles([]);
      set("done", 1);
      onUploaded();
    } catch (e) {
      if (e instanceof DOMException && e.name === "AbortError") {
        set("idle", 0);
        return;
      }
      setError(e instanceof ApiError ? e : null);
      set("error", 0);
    } finally {
      abort.current = null;
    }
  }

  const busy = phase === "uploading" || phase === "processing";
  const totalBytes = files.reduce((n, f) => n + f.size, 0);
  const pct = Math.round(fraction * 100);

  return (
    <Panel title="Input · DICOM upload">
      <div className="space-y-3 p-4">
        <div
          onDragOver={(e) => {
            e.preventDefault();
            setOver(true);
          }}
          onDragLeave={() => setOver(false)}
          onDrop={onDrop}
          className={cn(
            "rounded-xl border border-dashed px-4 py-5 text-center transition-colors",
            over ? "border-accent bg-accent/10" : "border-line2 bg-black/20",
            busy && "pointer-events-none opacity-60",
          )}
        >
          <Icon name="upload" size={22} className="mx-auto text-accent" />
          <p className="mt-2 text-[13px] font-medium">Drop a CT series here</p>
          <p className="mt-0.5 text-xs text-faint">Multiple .dcm slices of one series</p>
          <div className="mt-3 flex flex-wrap justify-center gap-2">
            <button type="button" className="btn" onClick={() => fileInput.current?.click()} disabled={busy}>
              Choose files
            </button>
            <button type="button" className="btn" onClick={() => folderInput.current?.click()} disabled={busy}>
              Choose folder
            </button>
          </div>
          <input
            ref={fileInput}
            type="file"
            multiple
            className="sr-only"
            aria-label="Choose DICOM files"
            onChange={(e) => {
              accept(e.target.files);
              e.target.value = "";
            }}
          />
          <input
            ref={(el) => {
              folderInput.current = el;
              if (el) el.setAttribute("webkitdirectory", "");
            }}
            type="file"
            className="sr-only"
            aria-label="Choose a folder of DICOM files"
            onChange={(e) => {
              accept(e.target.files);
              e.target.value = "";
            }}
          />
        </div>

        {files.length > 0 && !busy && (
          <div className="flex items-center justify-between gap-2 rounded-lg border border-line bg-white/[0.03] px-3 py-2 text-xs">
            <span className="num">
              {files.length} file{files.length === 1 ? "" : "s"} · {formatBytes(totalBytes)}
            </span>
            <button type="button" className="text-faint hover:text-ink" onClick={() => setFiles([])}>
              Clear
            </button>
          </div>
        )}

        {busy && (
          <div role="status" aria-live="polite" className="space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-ink">
                {phase === "uploading" ? "Uploading DICOM series…" : "Validating imaging series…"}
              </span>
              <span className="num text-dim">
                {phase === "uploading" ? `${pct}% · ${formatBytes(loaded)} / ${formatBytes(total)}` : "server-side"}
              </span>
            </div>
            <div
              className="relative h-1.5 overflow-hidden rounded-full bg-white/10"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={phase === "uploading" ? pct : 100}
              aria-label="Upload progress"
            >
              <div
                className="h-full rounded-full bg-accent transition-[width] duration-150 ease-out"
                style={{ width: `${phase === "uploading" ? pct : 100}%` }}
              />
              {phase === "processing" && (
                <div className="anim-scan absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-white/50 to-transparent" />
              )}
            </div>
            <button type="button" className="text-xs text-faint hover:text-ink" onClick={() => abort.current?.abort()}>
              Cancel upload
            </button>
          </div>
        )}

        {!busy && (
          <button type="button" className="btn btn-primary w-full" disabled={files.length === 0} onClick={start}>
            <Icon name="upload" size={15} />
            Upload to {caseId}
          </button>
        )}

        {phase === "error" && <StateBlock compact kind="error" title="Upload failed" error={error} />}

        {result && phase === "done" && (
          <div className="anim-rise rounded-lg border border-live/30 bg-live/[0.06] p-3 text-xs">
            <p className="flex items-center gap-1.5 font-medium text-live">
              <Icon name="check" size={13} /> Series received by the backend
            </p>
            <dl className="num mt-2 space-y-0.5 text-dim">
              <div className="flex justify-between gap-3">
                <dt>Files stored</dt>
                <dd className="text-ink">{result.uploaded_count}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Series files</dt>
                <dd className="text-ink">{result.series_file_count}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Modality</dt>
                <dd className="text-ink">{result.modality}</dd>
              </div>
              <div className="flex justify-between gap-3">
                <dt>Series UID</dt>
                <dd className="text-ink" title={result.series_instance_uid}>
                  {shortUid(result.series_instance_uid, 6)}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </div>
    </Panel>
  );
}
