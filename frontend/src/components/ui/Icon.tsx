import type { SVGProps } from "react";

const PATHS = {
  check: "M5 12.5l4.5 4.5L19 7.5",
  x: "M6 6l12 12M18 6L6 18",
  alert: "M12 4l9 16H3L12 4z M12 10v4 M12 17.2v.1",
  lock: "M6 11h12v9H6z M8.5 11V8a3.5 3.5 0 017 0v3",
  upload: "M12 16V5 M7.5 9.5L12 5l4.5 4.5 M5 19h14",
  cpu: "M8 8h8v8H8z M10 3v3 M14 3v3 M10 18v3 M14 18v3 M3 10h3 M3 14h3 M18 10h3 M18 14h3",
  shield: "M12 3l7 3v5c0 5-3 8.5-7 10-4-1.5-7-5-7-10V6l7-3z M9 12l2 2 4-4",
  user: "M12 12a4 4 0 100-8 4 4 0 000 8z M4.5 20c.8-3.6 3.8-5.5 7.5-5.5s6.7 1.9 7.5 5.5",
  file: "M7 3h7l4 4v14H7z M14 3v4h4 M9.5 12h5 M9.5 15.5h5",
  layers: "M12 4l9 5-9 5-9-5 9-5z M3 14l9 5 9-5",
  search: "M11 18a7 7 0 100-14 7 7 0 000 14z M20 20l-4-4",
  eye: "M2 12s3.6-6.5 10-6.5S22 12 22 12s-3.6 6.5-10 6.5S2 12 2 12z M12 15a3 3 0 100-6 3 3 0 000 6z",
  activity: "M3 12h4l3-7 4 14 3-7h4",
  zoomIn: "M11 18a7 7 0 100-14 7 7 0 000 14z M20 20l-4-4 M11 8v6 M8 11h6",
  zoomOut: "M11 18a7 7 0 100-14 7 7 0 000 14z M20 20l-4-4 M8 11h6",
  fit: "M4 9V4h5 M20 9V4h-5 M4 15v5h5 M20 15v5h-5",
  reset: "M20 12a8 8 0 11-2.4-5.7 M20 4v5h-5",
  expand: "M14 4h6v6 M20 4l-7 7 M10 20H4v-6 M4 20l7-7",
  move: "M12 3v18 M3 12h18 M9 6l3-3 3 3 M9 18l3 3 3-3 M6 9l-3 3 3 3 M18 9l3 3-3 3",
  contrast: "M12 21a9 9 0 100-18 9 9 0 000 18z M12 3v18 M12 3a9 9 0 010 18z",
  arrowRight: "M5 12h14 M13 6l6 6-6 6",
  arrowDown: "M12 5v14 M6 13l6 6 6-6",
  plus: "M12 5v14 M5 12h14",
  database: "M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6 M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6",
  play: "M7 4.5v15l12-7.5-12-7.5z",
  clock: "M12 21a9 9 0 100-18 9 9 0 000 18z M12 7v5l3 2",
  printer: "M7 8V3h10v5 M7 17H4v-7h16v7h-3 M7 14h10v7H7z",
  chevron: "M6 9l6 6 6-6",
  cube: "M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z M12 12l8-4.5 M12 12v9 M12 12L4 7.5",
  dot: "M12 15a3 3 0 100-6 3 3 0 000 6z",
  refresh: "M20 12a8 8 0 11-2.4-5.7 M20 4v5h-5",
  home: "M4 11l8-7 8 7 M6 10v10h12V10",
  list: "M8 6h12 M8 12h12 M8 18h12 M4 6h.1 M4 12h.1 M4 18h.1",
  info: "M12 21a9 9 0 100-18 9 9 0 000 18z M12 11v5 M12 7.8v.1",
} as const;

export type IconName = keyof typeof PATHS;

export function Icon({
  name,
  size = 16,
  ...rest
}: { name: IconName; size?: number } & Omit<SVGProps<SVGSVGElement>, "name">) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
