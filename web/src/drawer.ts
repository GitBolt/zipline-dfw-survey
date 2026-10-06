import { el } from "./format";

export interface Drawer {
  /** Show `body` in the drawer. `tabs` adds a row of buttons above it. */
  open(options: { body: HTMLElement; wide: boolean; label: string; tabs?: HTMLElement; onClose?: () => void }): void;
  close(): void;
  isOpen(): boolean;
}

/** A panel over the right edge of the map. It scrolls inside itself so the page never has to. */
export function createDrawer(host: HTMLElement): Drawer {
  const close = el("button", { type: "button", class: "drawer-close", "aria-label": "Close panel" }, ["Close"]);
  const head = el("div", { class: "drawer-head" });
  const content = el("div", { class: "drawer-body" });
  const node = el("aside", { class: "drawer", tabindex: "-1" }, [head, content]);
  node.hidden = true;
  host.append(node);
  let onClose: (() => void) | undefined;

  function shut(): void {
    if (node.hidden) return;
    node.hidden = true;
    const done = onClose;
    onClose = undefined;
    done?.();
  }
  close.addEventListener("click", shut);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") shut();
  });

  return {
    open(options) {
      const previous = onClose;
      onClose = undefined;
      previous?.();
      onClose = options.onClose;
      node.classList.toggle("wide", options.wide);
      node.setAttribute("aria-label", options.label);
      head.replaceChildren(options.tabs ?? el("span", { class: "drawer-title" }, [options.label]), close);
      content.replaceChildren(options.body);
      node.hidden = false;
      content.scrollTop = 0;
      node.focus({ preventScroll: true });
    },
    close: shut,
    isOpen: () => !node.hidden,
  };
}
