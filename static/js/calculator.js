/*
 * On-screen calculator for QR/DM practice, modelled on the real UCAT tool.
 *
 * Deliberately a desk-calculator state machine rather than an expression
 * parser: "2 + 3 x 4 =" gives 20, not 14, exactly as the exam calculator does.
 * No eval() anywhere.
 *
 * Loaded on every question page but inert unless the panel markup is present
 * (see templates/practice/_calculator.html), so VR/SJT pages cost nothing.
 */
(function () {
  "use strict";

  var panel = document.getElementById("calc-panel");
  if (!panel) return; // not a QR/DM question — do nothing at all

  var toggle = document.getElementById("calc-toggle");
  var head = document.getElementById("calc-head");
  var closeBtn = document.getElementById("calc-close");
  var displayEl = document.getElementById("calc-display");

  var MAX_DIGITS = 12;
  var STORE_KEY = "medrev.calc";

  // --- state ------------------------------------------------------------
  var current = "0";      // what the user is typing
  var accumulator = null; // left-hand side of a pending operation
  var pendingOp = null;   // "+", "-", "*", "/"
  var freshEntry = true;  // next digit starts a new number
  var errored = false;
  var memory = 0;
  var active = false;

  // --- persistence (best effort; never breaks the calculator) -----------
  function loadState() {
    try {
      var raw = sessionStorage.getItem(STORE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function saveState() {
    try {
      sessionStorage.setItem(STORE_KEY, JSON.stringify({
        open: !panel.hidden,
        top: panel.style.top || "",
        left: panel.style.left || "",
        memory: memory
      }));
    } catch (e) { /* private browsing / quota — ignore */ }
  }

  // --- helpers ----------------------------------------------------------
  // Kill binary-float noise: 0.1 + 0.2 must read 0.3, not 0.30000000000000004.
  function tidy(n) {
    if (!isFinite(n)) return null;
    return parseFloat(n.toPrecision(12));
  }

  function showError() {
    errored = true;
    current = "0";
    accumulator = null;
    pendingOp = null;
    freshEntry = true;
    displayEl.textContent = "Error";
    displayEl.classList.add("is-error");
  }

  function render() {
    if (errored) return;
    displayEl.classList.remove("is-error");
    var text = current;
    if (text.length > MAX_DIGITS + 2) text = String(tidy(parseFloat(text)));
    displayEl.textContent = text;
  }

  function setMemoryFlag() {
    panel.classList.toggle("has-memory", memory !== 0);
  }

  function clearAll() {
    current = "0";
    accumulator = null;
    pendingOp = null;
    freshEntry = true;
    errored = false;
    displayEl.classList.remove("is-error");
    render();
  }

  // --- number entry -----------------------------------------------------
  function inputDigit(d) {
    if (errored) clearAll();
    if (freshEntry) {
      current = d;
      freshEntry = false;
    } else {
      var digits = current.replace(/[-.]/g, "").length;
      if (digits >= MAX_DIGITS) return;
      current = current === "0" ? d : current + d;
    }
    render();
  }

  function inputDot() {
    if (errored) clearAll();
    if (freshEntry) {
      current = "0.";
      freshEntry = false;
    } else if (current.indexOf(".") === -1) {
      current += ".";
    }
    render();
  }

  function backspace() {
    if (errored) { clearAll(); return; }
    if (freshEntry) return;
    current = current.length > 1 ? current.slice(0, -1) : "0";
    if (current === "-" || current === "") current = "0";
    render();
  }

  // --- arithmetic -------------------------------------------------------
  function apply(a, b, op) {
    switch (op) {
      case "+": return a + b;
      case "-": return a - b;
      case "*": return a * b;
      case "/": return b === 0 ? null : a / b;
      default: return b;
    }
  }

  function resolvePending() {
    var value = parseFloat(current);
    if (pendingOp === null || accumulator === null) return value;
    var result = apply(accumulator, value, pendingOp);
    if (result === null) return null; // divide by zero
    return tidy(result);
  }

  function chooseOp(op) {
    if (errored) return;
    var result = resolvePending();
    if (result === null) { showError(); return; }
    accumulator = result;
    current = String(result);
    pendingOp = op;
    freshEntry = true;
    render();
  }

  function equals() {
    if (errored) return;
    var result = resolvePending();
    if (result === null) { showError(); return; }
    current = String(result);
    accumulator = null;
    pendingOp = null;
    freshEntry = true;
    render();
  }

  function sqrt() {
    if (errored) return;
    var v = parseFloat(current);
    if (v < 0) { showError(); return; }
    current = String(tidy(Math.sqrt(v)));
    freshEntry = true;
    render();
  }

  // Desk-calculator percent: "50 + 10 %" -> 10% of 50. Bare "40 %" -> 0.4.
  function percent() {
    if (errored) return;
    var v = parseFloat(current);
    var result = (pendingOp && accumulator !== null)
      ? tidy(accumulator * v / 100)
      : tidy(v / 100);
    current = String(result);
    freshEntry = true;
    render();
  }

  function memoryOp(kind) {
    if (errored) return;
    var v = parseFloat(current);
    if (kind === "MC") memory = 0;
    else if (kind === "MR") { current = String(tidy(memory)); freshEntry = true; render(); }
    else if (kind === "M+") memory = tidy(memory + v);
    else if (kind === "M-") memory = tidy(memory - v);
    setMemoryFlag();
    saveState();
  }

  // --- activation: mirrors the real calculator going inactive on click-off
  function setActive(on) {
    active = on;
    panel.classList.toggle("is-active", on);
  }

  document.addEventListener("pointerdown", function (e) {
    if (panel.hidden) return;
    setActive(panel.contains(e.target));
  });

  // --- buttons ----------------------------------------------------------
  panel.addEventListener("click", function (e) {
    var btn = e.target.closest("button");
    if (!btn) return;
    if (btn.dataset.digit !== undefined) return inputDigit(btn.dataset.digit);
    if (btn.dataset.op !== undefined) return chooseOp(btn.dataset.op);
    if (btn.dataset.mem !== undefined) return memoryOp(btn.dataset.mem);
    switch (btn.dataset.act) {
      case "dot": return inputDot();
      case "equals": return equals();
      case "sqrt": return sqrt();
      case "percent": return percent();
      case "clear": return clearAll();
      case "clearEntry": current = "0"; freshEntry = true; errored = false; return render();
    }
  });

  // --- keyboard: only while the panel has focus -------------------------
  document.addEventListener("keydown", function (e) {
    if (!active || panel.hidden) return;      // keys reach the page as normal
    if (e.ctrlKey || e.metaKey || e.altKey) return;
    var k = e.key;

    if (k >= "0" && k <= "9") inputDigit(k);
    else if (k === ".") inputDot();
    else if (k === "+" || k === "-" || k === "*" || k === "/") chooseOp(k);
    else if (k === "Enter" || k === "=") equals();
    else if (k === "Backspace") backspace();
    else if (k === "Escape") clearAll();
    else if (k === "%") percent();
    else return;                              // untouched keys keep default behaviour

    e.preventDefault();
  });

  // --- open / close -----------------------------------------------------
  function open() {
    panel.hidden = false;
    setActive(true);
    saveState();
  }

  function close() {
    panel.hidden = true;
    setActive(false);
    saveState();
  }

  if (toggle) {
    toggle.addEventListener("click", function () {
      if (panel.hidden) open(); else close();
    });
  }
  if (closeBtn) closeBtn.addEventListener("click", close);

  // --- drag -------------------------------------------------------------
  var dragging = false, offsetX = 0, offsetY = 0;

  head.addEventListener("pointerdown", function (e) {
    if (e.target.closest(".calc-close")) return;
    var box = panel.getBoundingClientRect();
    dragging = true;
    offsetX = e.clientX - box.left;
    offsetY = e.clientY - box.top;
    head.setPointerCapture(e.pointerId);
  });

  head.addEventListener("pointermove", function (e) {
    if (!dragging) return;
    var box = panel.getBoundingClientRect();
    // Clamp so the panel can never be dragged out of reach.
    var maxLeft = Math.max(0, window.innerWidth - box.width);
    var maxTop = Math.max(0, window.innerHeight - box.height);
    var left = Math.min(Math.max(0, e.clientX - offsetX), maxLeft);
    var top = Math.min(Math.max(0, e.clientY - offsetY), maxTop);
    panel.style.left = left + "px";
    panel.style.top = top + "px";
    panel.style.right = "auto";
  });

  head.addEventListener("pointerup", function (e) {
    if (!dragging) return;
    dragging = false;
    head.releasePointerCapture(e.pointerId);
    saveState();
  });

  // --- restore across questions ----------------------------------------
  var saved = loadState();
  if (saved) {
    if (typeof saved.memory === "number") { memory = saved.memory; setMemoryFlag(); }
    if (saved.left) { panel.style.left = saved.left; panel.style.right = "auto"; }
    if (saved.top) panel.style.top = saved.top;
    if (saved.open) { panel.hidden = false; setActive(false); }
  }
  render();
})();
