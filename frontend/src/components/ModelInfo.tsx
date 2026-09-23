import { useEffect, useRef } from 'react';
import { Check, Command, Info, RotateCcw, X } from 'lucide-react';

export function ModelInfo({ onClose, onReset }: { onClose: () => void; onReset: () => void }) {
  const infoDialog = useRef<HTMLElement>(null);
  useEffect(() => {
    const previousFocus = document.activeElement as HTMLElement | null;
    const dialog = infoDialog.current;
    dialog?.querySelector<HTMLButtonElement>('button')?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
      if (event.key !== 'Tab' || !dialog) return;
      const focusable = [...dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href]')];
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      }
      if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previousFocus?.focus();
    };
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <section
        ref={infoDialog}
        className="info-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="model-title"
        onClick={(event) => event.stopPropagation()}
      >
        <button
          className="modal-close icon-button"
          aria-label="Close model information"
          onClick={onClose}
        >
          <X size={19} />
        </button>
        <div className="eyebrow">SIMULATION MODEL</div>
        <h2 id="model-title">Real physics. Clear boundaries.</h2>
        <p>
          Metis connects orbital motion, sunlight, electrical loads and stored battery energy in a
          deterministic synthetic mission.
        </p>
        <ul>
          <li>
            <Check size={16} /> Backend J2 gravity model and Earth-fixed positions
          </li>
          <li>
            <Check size={16} /> Solar-disk eclipse geometry and ideal Sun-tracking panels
          </li>
          <li>
            <Check size={16} /> Bounded battery energy and accountable power balance
          </li>
        </ul>
        <div className="model-note">
          <Info size={17} />
          <p>
            This is an engineering simulation, not a flight-certified model. Visual lighting is
            approximate; measured eclipse and power always come from the backend. Satellite markers
            use symbolic size. The orbit preview contains positions only; no future power or health
            is predicted.
          </p>
        </div>
        <p className="credit-copy">
          Earth texture:{' '}
          <a
            href="https://github.com/mrdoob/three.js/blob/r180/examples/textures/planets/earth_atmos_2048.jpg"
            target="_blank"
            rel="noreferrer"
          >
            three.js contributors
          </a>{' '}
          (MIT). Rendering: CesiumJS (Apache 2.0). Imagery and rendering assets are bundled locally.
        </p>
        <div className="modal-footer">
          <span>
            <Command size={12} /> Drag to rotate · Scroll to zoom
          </span>
          <button
            onClick={() => {
              onReset();
              onClose();
            }}
          >
            <RotateCcw size={13} /> Reset Earth view
          </button>
        </div>
      </section>
    </div>
  );
}
