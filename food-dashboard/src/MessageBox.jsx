import { useEffect, useRef, useState } from "react";

/**
 * The message a resident is about to send, shown in full.
 *
 * Copying silently to the clipboard asks people to trust text they have not
 * seen, and fails outright in some webviews and on plain http. So the text is
 * shown, already selected, with a copy button; when the clipboard works the
 * status says so, and when it does not the text is still right there.
 */
export default function MessageBox({ title, text, copied = null, onClose }) {
  const areaRef = useRef(null);
  const [status, setStatus] = useState(
    copied === true ? "Copied to your clipboard." : copied === false ? "Select the text and copy it." : ""
  );

  useEffect(() => {
    const el = areaRef.current;
    if (el) {
      el.focus();
      el.select();
    }
    const onKey = (e) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setStatus("Copied to your clipboard.");
    } catch {
      areaRef.current?.select();
      setStatus("Your browser blocked the clipboard. The text is selected; press Ctrl+C or Cmd+C.");
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="message-title"
      className="print-hide fixed inset-0 z-[80] flex items-start justify-center overflow-y-auto bg-ink/40 p-3 sm:items-center sm:p-8"
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div className="my-auto w-full max-w-[40rem] border border-rule-strong bg-paper">
        <div className="flex items-center justify-between border-b border-rule-strong px-5 py-3">
          <p id="message-title" className="label">{title}</p>
          <button onClick={onClose} aria-label="Close" className="-mr-1 text-[22px] leading-none text-ink-3 hover:text-ink">
            ×
          </button>
        </div>
        <textarea
          ref={areaRef}
          readOnly
          value={text}
          rows={16}
          aria-label={title}
          className="block w-full resize-y border-0 bg-paper px-5 py-4 font-mono text-[12.5px] leading-[1.55] text-ink focus:outline-none"
        />
        <div className="flex flex-wrap items-center justify-between gap-3 border-t border-rule-strong px-5 py-3">
          <p className="text-[12px] text-ink-2" aria-live="polite">{status}</p>
          <div className="flex items-center gap-4">
            <button onClick={copy} className="bg-ink px-4 py-2 text-[13px] font-semibold text-paper hover:bg-ink-2">
              Copy
            </button>
            <button onClick={onClose} className="border-b border-ink/25 text-[12px] text-ink-2 hover:border-ink hover:text-ink">
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
