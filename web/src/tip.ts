/** One shared tooltip. Marks opt in with a `data-tip` attribute; values lead, labels follow. */
let node: HTMLDivElement | null = null;

function ensure(): HTMLDivElement {
  if (!node) {
    node = document.createElement("div");
    node.className = "tip";
    node.setAttribute("role", "tooltip");
    node.hidden = true;
    document.body.append(node);
  }
  return node;
}

export function showTip(text: string, x: number, y: number): void {
  const tip = ensure();
  tip.replaceChildren();
  const [head, ...rest] = text.split("\n");
  const strong = document.createElement("strong");
  strong.textContent = head;
  tip.append(strong);
  for (const line of rest) {
    const row = document.createElement("span");
    row.textContent = line;
    tip.append(row);
  }
  tip.hidden = false;
  const box = tip.getBoundingClientRect();
  const left = Math.min(window.innerWidth - box.width - 8, Math.max(8, x + 14));
  const top = y + 18 + box.height > window.innerHeight ? y - box.height - 12 : y + 18;
  tip.style.left = `${left}px`;
  tip.style.top = `${Math.max(8, top)}px`;
}

export function hideTip(): void {
  if (node) node.hidden = true;
}

export function installTips(root: HTMLElement): void {
  const find = (target: EventTarget | null) =>
    target instanceof Element ? target.closest<HTMLElement | SVGElement>("[data-tip]") : null;
  root.addEventListener("pointermove", (event) => {
    const mark = find(event.target);
    if (mark) showTip(mark.getAttribute("data-tip") ?? "", event.clientX, event.clientY);
    else hideTip();
  });
  root.addEventListener("pointerleave", hideTip);
  root.addEventListener("focusin", (event) => {
    const mark = find(event.target);
    if (!mark) return;
    const box = mark.getBoundingClientRect();
    showTip(mark.getAttribute("data-tip") ?? "", box.left + box.width / 2, box.top);
  });
  root.addEventListener("focusout", hideTip);
}
