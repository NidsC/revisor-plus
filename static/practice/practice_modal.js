// Practice-setup modal: question count validation + timed/untimed toggle.
// Populated per-open from the triggering "Practice" button's data attributes
// (Bootstrap's show.bs.modal event carries it as event.relatedTarget), so one
// modal instance serves every subtopic card on the page.
(() => {
  const modalEl = document.getElementById("practiceModal");
  if (!modalEl) return;

  const titleEl = document.getElementById("practiceModalLabel");
  const countInput = document.getElementById("practiceCount");
  const countError = document.getElementById("practiceCountError");
  const startBtn = document.getElementById("practiceStartBtn");
  const toggleBtns = Array.from(modalEl.querySelectorAll(".kid-modal-toggle-btn"));

  let startUrl = null;
  let mode = "practice";

  function readStored(key) {
    try {
      return localStorage.getItem(key);
    } catch {
      return null;
    }
  }

  function writeStored(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch {
      // Ignore storage failures (private browsing, disabled storage, etc.).
    }
  }

  function validCount() {
    const raw = countInput.value.trim();
    if (raw === "") return null;
    const n = Number(raw);
    return Number.isInteger(n) && n > 0 && n <= 40 ? n : null;
  }

  function refresh() {
    const n = validCount();
    const valid = n !== null && startUrl !== null;
    countError.hidden = n !== null;
    countInput.classList.toggle("is-invalid", n === null);
    countInput.setAttribute("aria-invalid", n === null ? "true" : "false");
    startBtn.classList.toggle("disabled", !valid);
    startBtn.setAttribute("aria-disabled", valid ? "false" : "true");
    startBtn.tabIndex = valid ? 0 : -1;
    startBtn.href = valid ? `${startUrl}?count=${n}&mode=${mode}` : "#";
  }

  countInput.addEventListener("input", () => {
    refresh();
    const n = validCount();
    if (n !== null) writeStored("practiceLastCount", String(n));
  });

  toggleBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      toggleBtns.forEach((b) => {
        b.classList.remove("is-active");
        b.setAttribute("aria-checked", "false");
      });
      btn.classList.add("is-active");
      btn.setAttribute("aria-checked", "true");
      mode = btn.dataset.mode;
      writeStored("practiceLastMode", mode);
      refresh();
    });
  });

  startBtn.addEventListener("click", (event) => {
    if (startBtn.classList.contains("disabled")) event.preventDefault();
  });

  modalEl.addEventListener("show.bs.modal", (event) => {
    const trigger = event.relatedTarget;
    if (!trigger) return;
    startUrl = trigger.dataset.startUrl;
    titleEl.textContent = `Practice: ${trigger.dataset.subtopicName}`;

    const storedCount = Number(readStored("practiceLastCount"));
    countInput.value =
      Number.isInteger(storedCount) && storedCount > 0 && storedCount <= 40 ? storedCount : 10;

    const storedMode = readStored("practiceLastMode");
    const validModes = toggleBtns.map((b) => b.dataset.mode);
    mode = validModes.includes(storedMode) ? storedMode : "practice";
    toggleBtns.forEach((b) => {
      const active = b.dataset.mode === mode;
      b.classList.toggle("is-active", active);
      b.setAttribute("aria-checked", active ? "true" : "false");
    });
    refresh();
  });
})();
