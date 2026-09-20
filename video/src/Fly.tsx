export function Fly({
  className = "",
  small = false,
}: {
  className?: string;
  small?: boolean;
}) {
  return (
    <svg
      className={className}
      viewBox="0 0 220 170"
      fill="none"
      role="img"
      aria-label="FLIH, a very determined fly on four wheels"
    >
      <g
        stroke="#2d2d2d"
        strokeWidth="3.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {!small && (
          <>
            <path d="M22 96l-13-3m15 15-17 2m23 9-12 6" />
            <path d="M179 28l5-10m3 19 12-4" stroke="#ff4d4d" />
          </>
        )}
        <ellipse
          cx="80"
          cy="69"
          rx="24"
          ry="43"
          transform="rotate(-45 80 69)"
          fill="#fdfbf7"
        />
        <path d="M53 43l46 47m-33-40 9 23" stroke="#a7a39c" strokeWidth="2" />
        <ellipse
          cx="128"
          cy="54"
          rx="23"
          ry="39"
          transform="rotate(28 128 54)"
          fill="#fdfbf7"
        />
        <path d="M142 24l-29 56m21-41 1 20" stroke="#a7a39c" strokeWidth="2" />
        <ellipse cx="65" cy="138" rx="13" ry="17" fill="#2d2d2d" />
        <ellipse cx="169" cy="134" rx="13" ry="17" fill="#2d2d2d" />
        <path d="M47 109l108-9 31 20-14 25-108 6-22-22z" fill="#fff2a6" />
        <path d="M43 126l112-8 30 2m-29 0 2 29" />
        <ellipse cx="76" cy="148" rx="13" ry="16" fill="#2d2d2d" />
        <ellipse cx="169" cy="145" rx="13" ry="16" fill="#2d2d2d" />
        <path d="M76 142v11m93-14v11" stroke="#fdfbf7" />
        <ellipse
          cx="102"
          cy="93"
          rx="43"
          ry="29"
          transform="rotate(-9 102 93)"
          fill="#44443f"
        />
        <path d="M72 74q-9 18 3 38m9-43q-9 25 4 47" stroke="#727169" />
        <path d="M131 68l1-17 10-9m9 27 11-15 11 1" />
        <circle cx="143" cy="83" r="24" fill="#fff9c4" />
        <ellipse cx="138" cy="77" rx="10" ry="14" fill="white" />
        <ellipse cx="156" cy="77" rx="9" ry="13" fill="white" />
        <circle cx="141" cy="80" r="3" fill="#2d2d2d" />
        <circle cx="158" cy="79" r="3" fill="#2d2d2d" />
        <path d="M143 95q7 4 12-2m-47 20-5 11m24-18 10 13" />
        <path d="M62 119v-13h15v12" fill="#ff4d4d" />
        <path d="M98 133h24" strokeWidth="2" />
      </g>
    </svg>
  );
}
