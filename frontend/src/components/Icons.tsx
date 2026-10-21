import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement> & { size?: number }

function base({ size = 18, ...rest }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.8,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    ...rest,
  }
}

export const IconHome = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 10.5 12 3.5l8 7V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z" />
  </svg>
)

export const IconCourt = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3.4" y="5.6" width="17.2" height="12.8" rx="1.8" />
    <path d="M12 5.6v12.8" />
    <path d="M3.4 12h17.2" />
  </svg>
)

/** Badminton shuttlecock — used for brand marks. */
export const IconShuttle = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M8.4 4.6 15.6 4.6 13.8 14.4 10.2 14.4z" />
    <circle cx="12" cy="17.4" r="3.1" />
    <path d="M10.4 5.2 10.9 14M12 4.7v9.6M13.6 5.2 13.1 14" />
  </svg>
)

export const IconList = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="5" y="3.5" width="14" height="17" rx="2.5" />
    <path d="M9 8.5h6M9 12h6M9 15.5h3.5" />
  </svg>
)

export const IconClock = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 7.5V12l3 1.8" />
  </svg>
)

export const IconSettings = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 14.5a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1 1.55V21a2 2 0 1 1-4 0v-.11a1.7 1.7 0 0 0-1.1-1.55 1.7 1.7 0 0 0-1.88.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.55-1H3a2 2 0 1 1 0-4h.11a1.7 1.7 0 0 0 1.55-1.1 1.7 1.7 0 0 0-.34-1.88l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9a1.7 1.7 0 0 0 1-1.55V3a2 2 0 1 1 4 0v.11a1.7 1.7 0 0 0 1 1.55 1.7 1.7 0 0 0 1.88-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87V9a1.7 1.7 0 0 0 1.55 1H21a2 2 0 1 1 0 4h-.11a1.7 1.7 0 0 0-1.49 1z" />
  </svg>
)

export const IconCheck = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="m5 12.5 4.5 4.5L19 7" />
  </svg>
)

export const IconX = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </svg>
)

export const IconRefresh = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M20 11a8 8 0 1 0-2.6 5.9" />
    <path d="M20 4.5V11h-6.2" />
  </svg>
)

export const IconUpload = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 16V4.5M8 8l4-4 4 4" />
    <path d="M4.5 15v3.5A1.5 1.5 0 0 0 6 20h12a1.5 1.5 0 0 0 1.5-1.5V15" />
  </svg>
)

export const IconTrash = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 7h16M9.5 7V4.8A1.3 1.3 0 0 1 10.8 3.5h2.4a1.3 1.3 0 0 1 1.3 1.3V7" />
    <path d="M6.5 7l.8 12.2A1.5 1.5 0 0 0 8.8 20.5h6.4a1.5 1.5 0 0 0 1.5-1.3L17.5 7" />
    <path d="M10.5 11v5.5M13.5 11v5.5" />
  </svg>
)

export const IconAlert = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 4.5 21 19.5H3z" />
    <path d="M12 10v4M12 16.6v.4" />
  </svg>
)

export const IconInfo = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5.5M12 8.2v.3" />
  </svg>
)

export const IconBolt = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M13.5 3 6 13.2h4.6L9.8 21l7.6-10.4h-4.7z" />
  </svg>
)

export const IconChevron = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="m9.5 6 6 6-6 6" />
  </svg>
)

export const IconPlus = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 5.5v13M5.5 12h13" />
  </svg>
)

export const IconShield = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3.2 19 6v5.4c0 4.3-2.9 7.6-7 9.4-4.1-1.8-7-5.1-7-9.4V6z" />
    <path d="m9.2 12 2 2 3.6-3.8" />
  </svg>
)

export const IconCalendar = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3.8" y="5.2" width="16.4" height="15" rx="2.4" />
    <path d="M3.8 9.6h16.4M8.4 3.4v3.2M15.6 3.4v3.2" />
  </svg>
)

export const IconUser = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="8.4" r="3.6" />
    <path d="M4.8 20c.9-3.5 3.8-5.4 7.2-5.4S18.3 16.5 19.2 20" />
  </svg>
)

export const IconLogout = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M15 8V5.5A1.5 1.5 0 0 0 13.5 4H6a1.5 1.5 0 0 0-1.5 1.5v13A1.5 1.5 0 0 0 6 20h7.5a1.5 1.5 0 0 0 1.5-1.5V16" />
    <path d="M10.5 12H21m0 0-3.2-3.2M21 12l-3.2 3.2" />
  </svg>
)
