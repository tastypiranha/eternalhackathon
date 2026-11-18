import type { ReactNode } from "react";

export type IconName =
  | "map"
  | "truck"
  | "chart"
  | "heart"
  | "store"
  | "tag"
  | "download"
  | "door"
  | "snow"
  | "leaf"
  | "grid"
  | "box"
  | "route"
  | "activity"
  | "settings"
  | "help"
  | "chevron"
  | "arrow"
  | "bell"
  | "search"
  | "temp"
  | "drop"
  | "milk"
  | "chicken"
  | "play"
  | "pause"
  | "heat"
  | "shock"
  | "reset"
  | "check"
  | "close"
  | "list"
  | "clock"
  | "warehouse"
  | "external";
export function Icon({
  name,
  size = 20,
  ...props
}: {
  name: IconName;
  size?: number;
  className?: string;
}) {
  const paths: Record<IconName, ReactNode> = {
    map: (
      <>
        <path d="m3 5 6-3 6 3 6-3v17l-6 3-6-3-6 3V5ZM9 2v17M15 5v17" />
      </>
    ),
    truck: (
      <>
        <path d="M2 5h12v12H2V5Zm12 4h4l4 5v3h-8" />
        <circle cx="6" cy="18" r="2" />
        <circle cx="18" cy="18" r="2" />
      </>
    ),
    chart: (
      <>
        <path d="M4 3v18h17M8 16v-5m5 5V6m5 10V9" />
      </>
    ),
    heart: <path d="M20 5c-3-3-7-1-8 1-2-3-6-4-9-1-4 5 3 10 9 16 6-6 13-11 8-16Z" />,
    store: (
      <>
        <path d="M3 10h18l-2-7H5l-2 7Zm1 0v11h16V10M9 21v-7h6v7M3 10c0 4 5 4 6 0 0 4 6 4 6 0 1 4 6 4 6 0" />
      </>
    ),
    tag: (
      <>
        <path d="M3 3h9l9 9-9 9-9-9V3Z" />
        <circle cx="8" cy="8" r="1.5" />
      </>
    ),
    download: (
      <>
        <path d="M12 3v12m-5-5 5 5 5-5M4 16v5h16v-5" />
      </>
    ),
    door: (
      <>
        <path d="M4 21h16M6 21V3h12v18M6 3l9 3v15M11 12h.01" />
      </>
    ),
    snow: (
      <>
        <path d="M12 2v20M3 7l18 10M3 17 21 7M8 4l4 4 4-4M8 20l4-4 4 4" />
      </>
    ),
    leaf: (
      <>
        <path d="M20 3C9 2 3 6 4 13c1 6 10 7 13 1 2-3 2-7 3-11Z" />
        <path d="M3 21 15 9M8 16v-5m0 5h5" />
      </>
    ),
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1.5" />
        <rect x="14" y="3" width="7" height="7" rx="1.5" />
        <rect x="3" y="14" width="7" height="7" rx="1.5" />
        <rect x="14" y="14" width="7" height="7" rx="1.5" />
      </>
    ),
    box: (
      <>
        <path d="m3 7 9-5 9 5v10l-9 5-9-5V7Zm0 0 9 5 9-5M12 12v10M7 5l10 5" />
      </>
    ),
    route: (
      <>
        <circle cx="6" cy="5" r="3" />
        <circle cx="18" cy="19" r="3" />
        <path d="M9 5h7a4 4 0 0 1 0 8H8a3 3 0 0 0 0 6h7" />
      </>
    ),
    activity: <path d="M2 12h5l3-8 4 16 3-8h5" />,
    settings: (
      <>
        <path d="m10 3-1 3-3 1-3 3 2 3v4l4 1 3 3 3-2 4-1v-4l2-3-3-3-3-1-2-3Z" />
        <circle cx="12" cy="12" r="3" />
      </>
    ),
    help: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3m0 3h.01" />
      </>
    ),
    chevron: <path d="m9 5 7 7-7 7" />,
    arrow: <path d="M4 12h16m-6-6 6 6-6 6" />,
    bell: (
      <>
        <path d="M5 9a7 7 0 0 1 14 0v6l2 3H3l2-3V9Zm4 12h6" />
      </>
    ),
    search: (
      <>
        <circle cx="10" cy="10" r="6" />
        <path d="m15 15 5 5" />
      </>
    ),
    temp: (
      <>
        <path d="M9 14V5a3 3 0 0 1 6 0v9a5 5 0 1 1-6 0Z" />
        <path d="M12 8v10m6-13h3m-3 4h2" />
      </>
    ),
    drop: <path d="M12 3C10 7 5 11 5 15a7 7 0 0 0 14 0c0-4-5-8-7-12Z" />,
    milk: (
      <>
        <path d="M8 3h8v5l3 4v9H5v-9l3-4V3Zm0 5h8M5 12h14M9 3v5" />
      </>
    ),
    chicken: (
      <>
        <path d="M10 15c-7-4-4-12 2-12 7-1 11 7 5 11-2 2-4 2-7 1Zm0 0-4 4" />
        <path d="M6 19c-3-4-6 1-2 2 1 4 6 1 2-2Z" />
      </>
    ),
    play: <path d="m8 4 12 8-12 8V4Z" />,
    pause: (
      <>
        <path d="M8 5v14M16 5v14" />
      </>
    ),
    heat: (
      <>
        <path d="M13 2c1 6-5 6-3 11-3-1-3-3-3-3-6 8 1 13 6 12 9-2 7-10 4-13 0 4-3 4-3 4s3-7-1-11Z" />
      </>
    ),
    shock: <path d="m13 2-9 12h7l-1 8 10-13h-7l1-7Z" />,
    reset: (
      <>
        <path d="M3 10a9 9 0 1 1 2 8M3 4v6h6" />
      </>
    ),
    check: <path d="m5 12 4 4L19 6" />,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    list: <path d="M8 5h13M8 12h13M8 19h13M3 5h.01M3 12h.01M3 19h.01" />,
    clock: (
      <>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 6v6l4 2" />
      </>
    ),
    warehouse: (
      <>
        <path d="m3 9 9-6 9 6v12H3V9Zm5 12V11h8v10M8 15h8m-8 3h8" />
      </>
    ),
    external: (
      <>
        <path d="M14 3h7v7m0-7L10 14M10 3H3v18h18v-7" />
      </>
    ),
  };
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.65"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}
