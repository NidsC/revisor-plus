/* Independent subject/topic disclosure, capped session sizes, and smooth card layout. */
(() => {
  const bank = document.querySelector('[data-qbank]');
  if (!bank) return;

  const sizes = [5, 10, 15, 20, 25, 30];
  const subjects = [...bank.querySelectorAll('[data-subject]')];
  const desktop = window.matchMedia('(min-width: 761px)');

  function sync(controls) {
    const range = controls.querySelector('[data-size]');
    const cap = controls.hasAttribute('data-free-left') ? Number(controls.dataset.freeLeft) : null;
    const count = cap === null ? sizes[Number(range.value)] : Math.min(sizes[Number(range.value)], cap);
    const label = count + ' question' + (count === 1 ? '' : 's');
    controls.querySelector('[data-sizelab]').textContent = label;
    range.setAttribute('aria-valuetext', label);
    controls.querySelector('[data-go="untimed"]').href = controls.dataset.start + '?count=' + count;
    controls.querySelector('[data-go="timed"]').href = controls.dataset.start + '?count=' + count + '&mode=test';
  }

  bank.querySelectorAll('[data-controls]').forEach((controls) => {
    const range = controls.querySelector('[data-size]');
    if (controls.hasAttribute('data-free-left')) {
      const cap = Number(controls.dataset.freeLeft);
      const allowed = sizes.filter(n => n <= cap);
      range.max = Math.max(0, allowed.length - 1);
      range.value = Math.min(Number(range.value), Number(range.max));
    }
    sync(controls);
  });

  bank.addEventListener('input', (event) => {
    const range = event.target.closest('[data-size]');
    if (range) sync(range.closest('[data-controls]'));
  });

  /* Keep the two desktop columns independent so an open card grows in place. */
  function sizeSubject(subject) {
    if (!desktop.matches) {
      subject.style.removeProperty('grid-row-end');
      return;
    }

    const gridStyle = getComputedStyle(bank);
    const rowHeight = parseFloat(gridStyle.gridAutoRows) || 4;
    const subjectStyle = getComputedStyle(subject);
    const bottomGap = parseFloat(subjectStyle.marginBottom) || 0;
    const height = subject.getBoundingClientRect().height;
    subject.style.gridRowEnd = `span ${Math.max(1, Math.ceil((height + bottomGap) / rowHeight))}`;
  }

  function sizeAllSubjects() {
    subjects.forEach(sizeSubject);
  }

  let layoutFrame = 0;
  function queueLayout() {
    cancelAnimationFrame(layoutFrame);
    layoutFrame = requestAnimationFrame(sizeAllSubjects);
  }

  if ('ResizeObserver' in window) {
    const observer = new ResizeObserver((entries) => {
      if (!desktop.matches) return;
      entries.forEach((entry) => sizeSubject(entry.target));
    });
    subjects.forEach((subject) => observer.observe(subject));
  }

  if (desktop.addEventListener) desktop.addEventListener('change', queueLayout);
  else desktop.addListener(queueLayout);
  window.addEventListener('resize', queueLayout, { passive: true });
  requestAnimationFrame(sizeAllSubjects);

  function setSubject(subject, open) {
    subject.classList.toggle('is-open', open);
    const button = subject.querySelector('[data-caret]');
    button.setAttribute('aria-expanded', String(open));
    button.querySelector('[data-caret-label]').textContent = open ? 'Hide topics' : 'Choose topics';
  }

  bank.addEventListener('click', (event) => {
    if (event.target.closest('[aria-disabled="true"]')) {
      event.preventDefault();
      return;
    }

    const areaButton = event.target.closest('[data-area-toggle]');
    if (areaButton) {
      const area = areaButton.closest('[data-area]');
      const open = area.classList.toggle('is-open');
      areaButton.setAttribute('aria-expanded', String(open));
      queueLayout();
      return;
    }

    const subjectButton = event.target.closest('[data-caret]');
    if (!subjectButton) return;

    const subject = subjectButton.closest('[data-subject]');
    const open = !subject.classList.contains('is-open');
    subjects.forEach((other) => setSubject(other, other === subject && open));
    queueLayout();
  });
})();
