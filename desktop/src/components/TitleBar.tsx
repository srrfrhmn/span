import { Minus, Square, Copy, X } from "lucide-react";
import { useEffect, useState } from "react";
import { getCurrentWindow, type Window } from "@tauri-apps/api/window";

/**
 * Resolved on first use rather than at module scope: Tauri installs its
 * internals during page start-up, and touching them too early throws.
 */
let handle: Window | null = null;
function appWindow(): Window {
  handle ??= getCurrentWindow();
  return handle;
}

export function TitleBar() {
  const [maximized, setMaximized] = useState(false);

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    const win = appWindow();
    void win
      .isMaximized()
      .then(setMaximized)
      .catch(() => undefined);
    void win
      .onResized(() => {
        void win
          .isMaximized()
          .then(setMaximized)
          .catch(() => undefined);
      })
      .then((stop) => {
        unlisten = stop;
      })
      .catch(() => undefined);
    return () => unlisten?.();
  }, []);

  const toggle = () => {
    void appWindow()
      .toggleMaximize()
      .catch(() => undefined);
  };

  return (
    <header className="titlebar" data-tauri-drag-region onDoubleClick={toggle}>
      <div className="titlebar__brand" data-tauri-drag-region>
        <span className="mark" aria-hidden>
          s
        </span>
        <span className="titlebar__name">span</span>
      </div>

      <div className="titlebar__controls" onDoubleClick={(event) => event.stopPropagation()}>
        <button
          className="winbtn"
          aria-label="Minimize"
          onClick={() => void appWindow().minimize().catch(() => undefined)}
        >
          <Minus size={15} />
        </button>
        <button
          className="winbtn"
          aria-label={maximized ? "Restore" : "Maximize"}
          onClick={toggle}
        >
          {maximized ? <Copy size={13} /> : <Square size={12} />}
        </button>
        <button
          className="winbtn winbtn--close"
          aria-label="Close"
          onClick={() => void appWindow().close().catch(() => undefined)}
        >
          <X size={15} />
        </button>
      </div>
    </header>
  );
}
