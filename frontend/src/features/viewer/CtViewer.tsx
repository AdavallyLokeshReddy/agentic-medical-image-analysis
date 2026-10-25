"use client";

import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { Icon, type IconName } from "@/components/ui/Icon";
import { ProvenanceBadge } from "@/components/ui/ProvenanceBadge";
import { StateBlock } from "@/components/ui/StateBlock";
import type { AsyncResult } from "@/hooks/useAsync";
import type { ImageInfo, PreviewResult, SeriesInfo } from "@/types/api";
import { cn, formatBytes, shortUid } from "@/utils/format";

const MIN_SCALE = 0.1;
const MAX_SCALE = 24;

interface View {
  s: number;
  x: number;
  y: number;
}

function ToolButton({
  icon,
  label,
  onClick,
  active,
}: {
  icon: IconName;
  label: string;
  onClick: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      className={cn("btn btn-icon", active && "border-accent/60 bg-accent/10 text-accent")}
      onClick={onClick}
      aria-label={label}
      aria-pressed={active}
      title={label}
    >
      <Icon name={icon} size={15} />
    </button>
  );
}

export function CtViewer({
  caseId,
  hasSeries,
  preview,
  imageInfo,
  seriesInfo,
}: {
  caseId: string;
  hasSeries: boolean;
  preview: AsyncResult<PreviewResult>;
  imageInfo: AsyncResult<ImageInfo>;
  seriesInfo: AsyncResult<SeriesInfo>;
}) {
  const frameRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<HTMLDivElement>(null);
  const imgRef = useRef<HTMLImageElement>(null);
  const userAdjusted = useRef(false);
  const drag = useRef<{ px: number; py: number; vx: number; vy: number } | null>(null);

  const [view, setView] = useState<View>({ s: 1, x: 0, y: 0 });
  const [brightness, setBrightness] = useState(1);
  const [contrast, setContrast] = useState(1);
  const [fullscreen, setFullscreen] = useState(false);
  const [dragging, setDragging] = useState(false);

  const src = preview.data?.src ?? null;

  const fit = useCallback(() => {
    const stage = stageRef.current;
    const img = imgRef.current;
    if (!stage || !img || !img.naturalWidth) return;
    const { width: cw, height: ch } = stage.getBoundingClientRect();
    const s = Math.min(cw / img.naturalWidth, ch / img.naturalHeight) * 0.94;
    setView({ s, x: (cw - img.naturalWidth * s) / 2, y: (ch - img.naturalHeight * s) / 2 });
  }, []);

  const actualSize = useCallback(() => {
    const stage = stageRef.current;
    const img = imgRef.current;
    if (!stage || !img) return;
    const { width: cw, height: ch } = stage.getBoundingClientRect();
    userAdjusted.current = true;
    setView({ s: 1, x: (cw - img.naturalWidth) / 2, y: (ch - img.naturalHeight) / 2 });
  }, []);

  const zoomAt = useCallback((factor: number, cx?: number, cy?: number) => {
    const stage = stageRef.current;
    if (!stage) return;
    const rect = stage.getBoundingClientRect();
    const px = cx ?? rect.width / 2;
    const py = cy ?? rect.height / 2;
    userAdjusted.current = true;
    setView((v) => {
      const s = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.s * factor));
      const k = s / v.s;
      return { s, x: px - (px - v.x) * k, y: py - (py - v.y) * k };
    });
  }, []);

  const resetAll = useCallback(() => {
    userAdjusted.current = false;
    setBrightness(1);
    setContrast(1);
    fit();
  }, [fit]);

  // Wheel zoom needs a non-passive listener so the page does not scroll.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !src) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = stage.getBoundingClientRect();
      zoomAt(Math.exp(-e.deltaY * 0.0015), e.clientX - rect.left, e.clientY - rect.top);
    };
    stage.addEventListener("wheel", onWheel, { passive: false });
    return () => stage.removeEventListener("wheel", onWheel);
  }, [src, zoomAt]);

  // Keep the image fitted on resize until the user takes manual control.
  useEffect(() => {
    const stage = stageRef.current;
    if (!stage || !src) return;
    const ro = new ResizeObserver(() => {
      if (!userAdjusted.current) fit();
    });
    ro.observe(stage);
    return () => ro.disconnect();
  }, [src, fit]);

  useEffect(() => {
    const onChange = () => setFullscreen(document.fullscreenElement === frameRef.current);
    document.addEventListener("fullscreenchange", onChange);
    return () => document.removeEventListener("fullscreenchange", onChange);
  }, []);

  const toggleFullscreen = useCallback(() => {
    const el = frameRef.current;
    if (!el) return;
    if (document.fullscreenElement) void document.exitFullscreen();
    else void el.requestFullscreen?.();
  }, []);

  const onPointerDown = (e: PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    drag.current = { px: e.clientX, py: e.clientY, vx: view.x, vy: view.y };
    userAdjusted.current = true;
    setDragging(true);
  };
  const onPointerMove = (e: PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d) return;
    setView((v) => ({ ...v, x: d.vx + (e.clientX - d.px), y: d.vy + (e.clientY - d.py) }));
  };
  const endDrag = () => {
    drag.current = null;
    setDragging(false);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const step = 40;
    switch (e.key) {
      case "+":
      case "=":
        zoomAt(1.25);
        break;
      case "-":
        zoomAt(0.8);
        break;
      case "0":
        userAdjusted.current = false;
        fit();
        break;
      case "1":
        actualSize();
        break;
      case "f":
      case "F":
        toggleFullscreen();
        break;
      case "ArrowLeft":
        userAdjusted.current = true;
        setView((v) => ({ ...v, x: v.x + step }));
        break;
      case "ArrowRight":
        userAdjusted.current = true;
        setView((v) => ({ ...v, x: v.x - step }));
        break;
      case "ArrowUp":
        userAdjusted.current = true;
        setView((v) => ({ ...v, y: v.y + step }));
        break;
      case "ArrowDown":
        userAdjusted.current = true;
        setView((v) => ({ ...v, y: v.y - step }));
        break;
      default:
        return;
    }
    e.preventDefault();
  };

  const info = imageInfo.data;
  const series = seriesInfo.data;
  const pv = preview.data;

  return (
    <div
      ref={frameRef}
      className={cn(
        "panel flex min-h-0 flex-col overflow-hidden",
        fullscreen && "!rounded-none !border-0 bg-bg",
      )}
    >
      {/* toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-3 py-2">
        <div className="flex items-center gap-2">
          <h2 className="panel-title">CT viewer</h2>
          {preview.status === "success" && <ProvenanceBadge kind="live" label="Live preview" />}
          {preview.status === "loading" && hasSeries && <ProvenanceBadge kind="pending" label="Rendering" />}
        </div>
        <div className="flex items-center gap-1" role="toolbar" aria-label="Viewer tools">
          <ToolButton icon="zoomOut" label="Zoom out (−)" onClick={() => zoomAt(0.8)} />
          <ToolButton icon="zoomIn" label="Zoom in (+)" onClick={() => zoomAt(1.25)} />
          <ToolButton
            icon="fit"
            label="Fit to view (0)"
            onClick={() => {
              userAdjusted.current = false;
              fit();
            }}
          />
          <button type="button" className="btn btn-icon num !text-[11px]" onClick={actualSize} title="Actual pixels (1)" aria-label="Actual pixels (1)">
            1:1
          </button>
          <ToolButton icon="reset" label="Reset view and display adjustments" onClick={resetAll} />
          <ToolButton icon="expand" label={fullscreen ? "Exit fullscreen (F)" : "Fullscreen (F)"} onClick={toggleFullscreen} active={fullscreen} />
        </div>
      </div>

      {/* stage */}
      <div className={cn("relative min-h-[380px] flex-1 bg-black", fullscreen && "min-h-0")}>
        {!hasSeries ? (
          <StateBlock
            kind="empty"
            title="No imaging data yet"
            message="Upload a CT series (.dcm files) to this case to see it here."
          />
        ) : preview.status === "error" ? (
          <StateBlock kind="error" title="Preview unavailable" error={preview.error} onRetry={preview.reload} />
        ) : !src ? (
          <div className="absolute inset-0 grid place-items-center">
            <div className="relative w-64 overflow-hidden rounded-full">
              <div className="h-1 w-full bg-white/10" />
              <div className="anim-scan absolute inset-y-0 left-0 w-1/3 bg-gradient-to-r from-transparent via-accent to-transparent" />
            </div>
            <p className="absolute mt-10 text-xs text-dim" role="status">
              Preprocessing volume and rendering preview…
            </p>
          </div>
        ) : (
          <div
            ref={stageRef}
            tabIndex={0}
            role="application"
            aria-label={`CT slice viewer for ${caseId}. Plus and minus zoom, arrow keys pan, zero fits, F toggles fullscreen.`}
            className={cn(
              "absolute inset-0 select-none overflow-hidden outline-offset-[-2px]",
              dragging ? "cursor-grabbing" : "cursor-grab",
            )}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={endDrag}
            onPointerCancel={endDrag}
            onKeyDown={onKeyDown}
            onDoubleClick={() => {
              userAdjusted.current = false;
              fit();
            }}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- data URL from the backend; next/image adds nothing here */}
            <img
              ref={imgRef}
              src={src}
              alt={`Axial CT preview slice${pv?.sliceIndex !== null && pv?.sliceIndex !== undefined ? ` ${pv.sliceIndex + 1}` : ""} for ${caseId}`}
              draggable={false}
              onLoad={fit}
              className="pointer-events-none absolute left-0 top-0 max-w-none origin-top-left"
              style={{
                transform: `translate(${view.x}px, ${view.y}px) scale(${view.s})`,
                imageRendering: view.s >= 2 ? "pixelated" : "auto",
                filter: `brightness(${brightness}) contrast(${contrast})`,
              }}
            />

            {/* overlays */}
            <div className="num pointer-events-none absolute left-3 top-3 space-y-0.5 text-[11px] text-white/80 [text-shadow:0_1px_2px_#000]">
              <div>{caseId}</div>
              <div className="text-white/55">{shortUid(pv?.seriesUid ?? series?.series_instance_uid, 6)}</div>
            </div>
            <div className="num pointer-events-none absolute right-3 top-3 text-right text-[11px] text-white/80 [text-shadow:0_1px_2px_#000]">
              {pv?.sliceIndex !== null && pv?.sliceCount !== null && pv ? (
                <div>
                  Slice {(pv.sliceIndex ?? 0) + 1} / {pv.sliceCount}
                </div>
              ) : null}
              <div className="text-white/55">Window 40 / 80 HU</div>
            </div>
            <div className="num pointer-events-none absolute bottom-3 left-3 text-[11px] text-white/70 [text-shadow:0_1px_2px_#000]">
              {view.s.toFixed(2)}×
            </div>
            <div className="num pointer-events-none absolute bottom-3 right-3 text-[11px] text-white/70 [text-shadow:0_1px_2px_#000]">
              {info ? `${info.columns} × ${info.rows}` : ""}
              {pv ? ` · ${formatBytes(pv.bytes)}` : ""}
            </div>
          </div>
        )}
      </div>

      {/* display adjustments + honest capability notes */}
      <div className="grid gap-3 border-t border-line px-3 py-3 md:grid-cols-[1fr_auto]">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          <label className="flex items-center gap-2 text-xs text-dim">
            <Icon name="contrast" size={14} className="text-faint" />
            Brightness
            <input
              type="range"
              min={0.5}
              max={1.8}
              step={0.05}
              value={brightness}
              onChange={(e) => setBrightness(Number(e.target.value))}
              disabled={!src}
              className="w-28 accent-[var(--accent)]"
              aria-label="Display brightness"
            />
            <span className="num w-9 text-faint">{brightness.toFixed(2)}</span>
          </label>
          <label className="flex items-center gap-2 text-xs text-dim">
            Contrast
            <input
              type="range"
              min={0.5}
              max={2.5}
              step={0.05}
              value={contrast}
              onChange={(e) => setContrast(Number(e.target.value))}
              disabled={!src}
              className="w-28 accent-[var(--accent)]"
              aria-label="Display contrast"
            />
            <span className="num w-9 text-faint">{contrast.toFixed(2)}</span>
          </label>
        </div>
        <ul className="flex flex-wrap items-center gap-1.5 text-[11px]">
          <li className="chip border-line2 text-faint" title="Brightness and contrast act on the 8-bit preview image only. They do not change Hounsfield windowing or any model input.">
            Display-only adjustments
          </li>
          <li className="chip border-dashed border-line2 text-faint" title="GET /cases/{id}/preview returns the middle slice at a fixed 40/80 HU window. It has no slice or window parameters.">
            <Icon name="lock" size={11} /> Slice scrolling &amp; HU window: not exposed
          </li>
        </ul>
      </div>
    </div>
  );
}
