/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // ── Vivid accent palette (kept as literals — pops on both themes) ──
        "secondary": "#d7ffc5",
        "on-secondary": "#053900",
        "surface-tint": "#47d6ff",
        "tertiary-fixed-dim": "#ffb59c",
        "on-primary": "#003543",
        "on-primary-container": "#00566a",
        "tertiary-container": "#ffad92",
        "on-error": "#690005",
        "on-secondary-fixed": "#022100",
        "inverse-primary": "#00677f",
        "secondary-fixed-dim": "#2ae500",
        "primary-fixed": "#b6ebff",
        "primary-container": "#00d2ff",
        "error": "#ffb4ab",
        "on-error-container": "#ffdad6",
        "on-tertiary-container": "#902c00",
        "primary-fixed-dim": "#47d6ff",
        "tertiary-fixed": "#ffdbcf",
        "on-tertiary": "#5c1900",
        "secondary-container": "#2ff801",
        "on-secondary-container": "#0f6d00",
        "on-secondary-fixed-variant": "#095300",
        "secondary-fixed": "#79ff5b",
        "tertiary": "#ffd3c6",
        "on-tertiary-fixed": "#390c00",
        "on-primary-fixed": "#001f28",
        "on-tertiary-fixed-variant": "#832700",
        "on-primary-fixed-variant": "#004e60",
        "error-container": "#93000a",
        "border-active": "#00E5FF33",
        "accent-green": "#39FF14",
        "accent-amber": "#F59E0B",
        "accent-red": "#EF4444",

        // ── Themed neutrals → CSS variables. Dark values are the EXACT originals (see
        //    index.css :root), so dark mode is pixel-identical; `html.light` overrides them. ──
        "background":  "rgb(var(--c-bg) / <alpha-value>)",
        "surface":     "rgb(var(--c-bg) / <alpha-value>)",
        "surface-dim": "rgb(var(--c-bg) / <alpha-value>)",
        "on-background":     "rgb(var(--c-text) / <alpha-value>)",
        "on-surface":        "rgb(var(--c-text) / <alpha-value>)",
        "inverse-surface":   "rgb(var(--c-text) / <alpha-value>)",
        "on-surface-variant":"rgb(var(--c-text-muted) / <alpha-value>)",
        "inverse-on-surface":"rgb(var(--c-inverse-on-surface) / <alpha-value>)",
        "surface-variant":          "rgb(var(--c-surface-highest) / <alpha-value>)",
        "surface-bright":           "rgb(var(--c-surface-bright) / <alpha-value>)",
        "surface-container-low":    "rgb(var(--c-surface-low) / <alpha-value>)",
        "surface-container":        "rgb(var(--c-surface-mid) / <alpha-value>)",
        "surface-container-high":   "rgb(var(--c-surface-high) / <alpha-value>)",
        "surface-container-highest":"rgb(var(--c-surface-highest) / <alpha-value>)",
        "surface-container-lowest": "rgb(var(--c-surface-lowest) / <alpha-value>)",
        "outline":         "rgb(var(--c-outline) / <alpha-value>)",
        "outline-variant": "rgb(var(--c-outline-variant) / <alpha-value>)",
        "primary":         "rgb(var(--c-primary) / <alpha-value>)",

        // Phase 2 tokens → variables
        "app-bg":      "rgb(var(--c-bg-deep) / <alpha-value>)",
        card:          "rgb(var(--c-surface) / <alpha-value>)",
        "card-hover":  "rgb(var(--c-surface-hover) / <alpha-value>)",
        input:         "rgb(var(--c-input) / <alpha-value>)",
        border:        "rgb(var(--c-border) / <alpha-value>)",
        "accent-cyan": "rgb(var(--c-accent-cyan) / <alpha-value>)",
        "text-primary":   "rgb(var(--c-text-strong) / <alpha-value>)",
        "text-secondary": "rgb(var(--c-text-secondary) / <alpha-value>)",
        "text-hint":      "rgb(var(--c-text-hint) / <alpha-value>)",

        // `white` becomes a theme-aware OVERLAY so the 300+ `white/[0.0x]` borders/fills flip
        // dark↔light automatically (white overlay on dark → dark overlay on light).
        "white": "rgb(var(--c-overlay) / <alpha-value>)",
        // `black` (used for recessed panels like bg-black/40) → a themed panel-shade: black in
        // dark, a soft warm tint in light (so it reads as a clean nested section, not a gray box).
        "black": "rgb(var(--c-black) / <alpha-value>)",
      },
      borderRadius: {
        DEFAULT: "0.125rem",
        lg: "0.25rem",
        xl: "0.5rem",
        full: "0.75rem",
        input: "6px",
        btn: "6px",
        card: "8px",
        pill: "100px",
      },
      spacing: {
        xs: "4px",
        "container-margin": "32px",
        md: "16px",
        xl: "48px",
        gutter: "16px",
        lg: "24px",
        sm: "8px",
        unit: "4px"
      },
      fontFamily: {
        "body-lg": ["Inter"],
        "display-lg": ["Inter"],
        "mono-log": ["JetBrains Mono"],
        "body-md": ["Inter"],
        "headline-md": ["Inter"],
        "headline-sm": ["Inter"],
        "headline-md-mobile": ["Inter"],
        "mono-label": ["JetBrains Mono"],

        // Preserved Phase 2 fonts
        display: ["'Space Grotesk'", "sans-serif"],
        body: ["Inter", "sans-serif"],
        mono: ["'JetBrains Mono'", "monospace"],
      },
      fontSize: {
        "body-lg": ["16px", {"lineHeight": "1.6", "fontWeight": "400"}],
        "display-lg": ["48px", {"lineHeight": "1.1", "letterSpacing": "-0.04em", "fontWeight": "800"}],
        "mono-log": ["13px", {"lineHeight": "1.6", "fontWeight": "400"}],
        "body-md": ["14px", {"lineHeight": "1.5", "fontWeight": "400"}],
        "headline-md": ["32px", {"lineHeight": "1.2", "letterSpacing": "-0.02em", "fontWeight": "700"}],
        "headline-sm": ["20px", {"lineHeight": "1.4", "fontWeight": "600"}],
        "headline-md-mobile": ["28px", {"lineHeight": "1.2", "fontWeight": "700"}],
        "mono-label": ["12px", {"lineHeight": "1.2", "letterSpacing": "0.05em", "fontWeight": "500"}],

        // Preserved Phase 2 sizes
        "11px": ["11px", { lineHeight: "1.4" }],
        "12px": ["12px", { lineHeight: "1.4" }],
        "13px": ["13px", { lineHeight: "1.5" }],
        "14px": ["14px", { lineHeight: "1.5" }],
        "16px": ["16px", { lineHeight: "1.5" }],
        "18px": ["18px", { lineHeight: "1.2" }],
        "24px": ["24px", { lineHeight: "1.2" }],
        "32px": ["32px", { lineHeight: "1.1" }],
        "48px": ["48px", { lineHeight: "1.1" }],
      },
      boxShadow: {
        "active-card": "0 0 0 1px #00E5FF33, 0 4px 24px #00E5FF11",
      },
      textShadow: {
        "cyan-glow": "0 0 20px #00E5FF66",
      }
    }
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries')
  ],
}
