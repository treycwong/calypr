/** The Calypr "C" glyph. Inline SVG rather than an <img> so it inherits `currentColor` from
 *  whatever tile it sits in — the canvas header paints it black on the cyan chip, and anywhere
 *  else it just follows the text colour. */
export function CalyprMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      <path
        d="M9.864 19.464C3.528 19.464 0 14.784 0 9.768C0 4.704 3.624 0 10.392 0C13.704 0 16.776 1.128 19.032 3.36C18.84 4.56 18.096 5.616 16.752 5.616C15.504 5.616 14.928 4.68 14.4 3.648C13.632 2.304 12.408 0.600001 10.392 0.600001C7.248 0.600001 5.304 4.104 5.304 8.208C5.304 14.112 8.688 17.16 12.384 17.16C15.624 17.16 18.504 14.808 19.104 10.752H19.608C18.936 16.584 14.4 19.464 9.864 19.464Z"
        fill="currentColor"
      />
    </svg>
  );
}
