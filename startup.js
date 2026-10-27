/* Gesture-owned startup UI. Loaded before the CDN scripts so loading failures
 * remain recoverable even when p5 never calls setup(). No audio is created here. */
(function () {
  "use strict";
  const overlay = document.getElementById("startOverlay");
  const button = document.getElementById("startButton");
  const reload = document.getElementById("startReload");
  const title = overlay.querySelector(".start-title");
  const sub = overlay.querySelector(".start-sub");
  const note = overlay.querySelector(".start-sync-note");
  let start = null, cancel = null, active = null;

  // An older worker can serve its cached sketch for the new versioned URL.
  // Once the replacement takes control, reload the idle shell exactly once.
  const serviceWorker = window.navigator?.serviceWorker;
  if (serviceWorker?.controller) {
    serviceWorker.addEventListener("controllerchange", () => {
      if (!active && !window.AudioEngine?.started && !window.AudioEngine?.starting) {
        window.location.reload();
      }
    }, { once:true });
  }

  function loadingFailed() {
    if (start) return;
    title.textContent = "読み込みを確認してください";
    sub.textContent = "音と画面の準備ができませんでした";
    note.textContent = "通信を確認して、下の「読み込み直す」を押してください。";
    reload.hidden = false;
  }
  const bootTimer = window.setTimeout(loadingFailed, 20000);
  window.addEventListener("load", loadingFailed, { once:true });

  function reset(message = "音を再開するには、もう一度タップしてください。") {
    if (active) {
      window.clearTimeout(active.timer);
      active.finish(false);
      active = null;
    }
    overlay.removeAttribute("aria-busy");
    overlay.style.display = "flex";
    button.disabled = !start;
    title.textContent = start ? "Tap to start" : "読み込み中…";
    sub.textContent = start ? "タップして音を再開します" : "音と画面を準備しています";
    note.textContent = message;
  }

  // A native click covers a completed touch, mouse click and Enter/Space.
  // Do not start on touch pointerdown: the browser may not grant audio yet.
  overlay.addEventListener("click", async (event) => {
    if (event.target.closest?.("#startReload") || !start || active) return;
    event.preventDefault();
    event.stopPropagation();
    const attempt = {};
    const cancelled = new Promise(resolve => { attempt.finish = resolve; });
    const timeout = new Promise((_, reject) => {
      attempt.timer = window.setTimeout(() => reject(new Error("Audio start timed out")), 10000);
    });
    active = attempt;
    overlay.setAttribute("aria-busy", "true");
    button.disabled = true;
    sub.textContent = "音を準備しています…";
    note.textContent = "そのまま少しお待ちください。";
    try {
      // Call synchronously in this gesture, before the first await.
      const ready = await Promise.race([start(), timeout, cancelled]);
      if (active !== attempt) return;
      if (!ready) throw new Error("Audio start cancelled");
      overlay.style.display = "none";
    } catch (error) {
      if (active !== attempt) return;
      cancel?.("start failed");
      console.warn("[namima] audio start failed", error);
      reset("音を開始できませんでした。もう一度タップして試せます。");
    } finally {
      window.clearTimeout(attempt.timer);
      if (active === attempt) {
        active = null;
        overlay.removeAttribute("aria-busy");
        button.disabled = false;
      }
    }
  });

  window.NamimaStartup = Object.freeze({
    ready(startAudio, cancelAudio) {
      start = startAudio;
      cancel = cancelAudio;
      window.clearTimeout(bootTimer);
      reset("Music SYNC後も、ここを押すまで音は始まりません。");
      sub.textContent = "タップして音を有効にします";
      reload.hidden = true;
    },
    reset
  });
})();
