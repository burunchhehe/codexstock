(function bootCodexStockUiV2() {
  "use strict";
  if (new URLSearchParams(window.location.search).get("ui") !== "v2") return;
  document.body.dataset.uiV2 = "true";
  const start = () => {
    const ui = window.CodexStockUiV2;
    if (!ui) return;
    ui.mount();
    ui.start();
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
