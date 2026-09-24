(function bootCodexStockUiV2() {
  "use strict";

  const params = new URLSearchParams(window.location.search);
  if (params.get("ui") !== "v2") return;

  document.body.dataset.uiV2 = "true";
  const start = () => {
    const ui = window.CodexStockUiV2;
    if (!ui) return;
    const host = ui.mount();
    let observer;
    const refresh = () => {
      if (!host.isConnected) {
        observer?.disconnect();
        return;
      }
      ui.render(host);
    };
    refresh();
    // Observe only legacy app bindings so this renderer never observes itself.
    const legacyApp = document.querySelector(".app-shell");
    if (legacyApp) {
      observer = new MutationObserver(refresh);
      observer.observe(legacyApp, { childList: true, subtree: true, characterData: true });
    }
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start, { once: true });
  else start();
})();
