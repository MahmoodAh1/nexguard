export function Logo({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden>
      <defs>
        <linearGradient id="nx-shield" x1="4" y1="2" x2="28" y2="30" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4f8cff" />
          <stop offset="1" stopColor="#22d3ee" />
        </linearGradient>
      </defs>
      <path
        d="M16 2.5 27 6.5v8.2c0 6.8-4.4 11.9-11 14.8-6.6-2.9-11-8-11-14.8V6.5L16 2.5Z"
        stroke="url(#nx-shield)"
        strokeWidth="1.8"
        strokeLinejoin="round"
        fill="rgba(79,140,255,0.08)"
      />
      <path
        d="M9.5 16.5h3l2-4.5 3 8 2-3.5h3"
        stroke="url(#nx-shield)"
        strokeWidth="1.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
