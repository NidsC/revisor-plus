
(() => {
  if (window.__revisorCleanStudyModesV2) return;
  window.__revisorCleanStudyModesV2 = true;

  const norm = (value) => (value || '').replace(/\s+/g, ' ').trim().toLowerCase();
  const all = (selector, root = document) => Array.from(root.querySelectorAll(selector));

  function findPageHeading() {
    return all('h1,h2').find((el) => {
      const t = norm(el.textContent);
      return t === 'question bank' || t === 'choose what to practise' || t === 'mock papers';
    }) || null;
  }

  function modeFromPage() {
    const heading = findPageHeading();
    if (!heading) return null;
    const t = norm(heading.textContent);
    return (t === 'question bank' || t === 'choose what to practise') ? 'practice' : 'mocks';
  }

  function likelyHeaderScope() {
    const brand = findBrand();
    return (
      brand?.closest('header') ||
      brand?.closest('nav') ||
      document.querySelector('header') ||
      document.querySelector('nav') ||
      document.body
    );
  }

  function findBrand() {
    return all('a').find((a) => {
      const clone = a.cloneNode(true);
      clone.querySelectorAll('.rp-brand-mode').forEach((el) => el.remove());
      const t = norm(clone.textContent).replace(/\s/g, '');
      return t === 'revisorplus';
    }) || null;
  }

  function setBrandMode(mode) {
    const brand = findBrand();
    if (!brand) return;

    const old = brand.querySelector('.rp-brand-mode');
    if (old) old.remove();

    const modeName =
      mode === 'practice' ? 'Practice' :
      mode === 'mocks' ? 'Mocks' :
      mode === 'study' ? 'Study' : '';

    if (!modeName) return;

    const span = document.createElement('span');
    span.className = 'rp-brand-mode';
    span.textContent = modeName;
    brand.appendChild(span);
  }

  function getNavUrls() {
    const scope = likelyHeaderScope();
    const links = all('a', scope);

    const practice = links.find((a) => norm(a.textContent) === 'practice');
    const mocks = links.find((a) => ['mock papers', 'mocks', 'mock'].includes(norm(a.textContent)));

    return {
      practice: practice?.href || '/practice/',
      mocks: mocks?.href || '/mocks/',
    };
  }

  function rewriteNavigation(urls) {
    const scopes = [
      likelyHeaderScope(),
      document.querySelector('header'),
      document.querySelector('nav'),
      document.body
    ].filter(Boolean);

    const seen = new Set();
    const links = [];
    scopes.forEach((scope) => {
      all('a', scope).forEach((a) => {
        if (!seen.has(a)) {
          seen.add(a);
          links.push(a);
        }
      });
    });

    const practice = links.find((a) => norm(a.textContent) === 'practice');
    const study = links.find((a) => norm(a.textContent) === 'study');
    const mockLinks = links.filter((a) =>
      ['mock papers', 'mocks', 'mock'].includes(norm(a.textContent))
    );

    const studyLink = study || practice;
    if (studyLink) {
      studyLink.textContent = 'Study';
      studyLink.href = urls.practice + (urls.practice.includes('?') ? '&' : '?') + 'study=1';
    }

    mockLinks.forEach((mocks) => {
      if (mocks === studyLink) return;
      mocks.style.display = 'none';
      mocks.setAttribute('aria-hidden', 'true');
      mocks.tabIndex = -1;
    });
  }

  function mainContent() {
    const heading = findPageHeading();
    return (
      heading?.closest('main') ||
      document.querySelector('main') ||
      heading?.closest('.container') ||
      document.querySelector('.container') ||
      document.querySelector('.container-fluid') ||
      document.body
    );
  }

  function makeStudyHub(urls) {
    document.body.classList.add('rp-mode-page', 'rp-mode-study');
    setBrandMode('study');

    const main = mainContent();
    Array.from(main.children).forEach((el) => {
      if (el.matches('script,style')) return;
      el.dataset.rpStudyOriginal = '1';
      el.style.display = 'none';
    });

    const hub = document.createElement('section');
    hub.className = 'rp-study-hub';
    hub.innerHTML = `
      <div class="rp-study-hub__intro">
        <div class="rp-study-hub__eyebrow">Study</div>
        <h1>How do you want to study today?</h1>
        <p>Practise a skill when you want to improve. Choose a mock when you want to test yourself.</p>
      </div>

      <div class="rp-study-hub__cards">
        <a href="${urls.practice}" class="rp-study-card rp-study-card--practice">
          <div class="rp-study-card__brand">RevisorPlus <span>Practice</span></div>
          <div class="rp-study-card__icon" aria-hidden="true">✦</div>
          <h2>Learn &amp; improve</h2>
          <p>Choose a topic and work at your own pace. No exam pressure — just build the skills you need.</p>
          <span class="rp-study-card__cta">Start practising <span aria-hidden="true">→</span></span>
        </a>

        <a href="${urls.mocks}" class="rp-study-card rp-study-card--mocks">
          <div class="rp-study-card__brand">RevisorPlus <span>Mocks</span></div>
          <div class="rp-study-card__icon" aria-hidden="true">◷</div>
          <h2>Test yourself</h2>
          <p>Try a timed paper and see how you perform under exam conditions.</p>
          <span class="rp-study-card__cta">View mocks <span aria-hidden="true">→</span></span>
        </a>
      </div>

      <div class="rp-study-hub__hint">Not sure? Start with Practice.</div>
    `;

    main.prepend(hub);
  }

  function hideOldIntro(heading) {
    heading.classList.add('rp-original-page-title');

    let next = heading.nextElementSibling;
    if (next) {
      const t = norm(next.textContent);
      if (
        t.includes('pick a subtopic') ||
        t.includes('full paper under the clock')
      ) {
        next.classList.add('rp-original-page-copy');
      }
    }
  }

  function insertModeHero(mode, heading, urls) {
    const wrap = document.createElement('div');
    wrap.className = 'rp-mode-wrap';

    const back = document.createElement('a');
    back.className = 'rp-back-study';
    back.href = urls.practice + (urls.practice.includes('?') ? '&' : '?') + 'study=1';
    back.textContent = '← Back to Study';

    const hero = document.createElement('section');
    hero.className = 'rp-mode-hero';

    if (mode === 'practice') {
      hero.innerHTML = `
        <span class="rp-mode-kicker">Practice</span>
        <h1 class="rp-mode-title">What do you want to practise?</h1>
        <p class="rp-mode-copy">Choose a topic and work on one skill at a time.</p>
      `;
    } else {
      hero.innerHTML = `
        <span class="rp-mode-kicker">Mocks</span>
        <h1 class="rp-mode-title">Choose a mock exam</h1>
        <p class="rp-mode-copy">Start with your recommended mock, or choose a full timed paper.</p>
      `;
    }

    wrap.append(back, hero);
    heading.parentElement.insertBefore(wrap, heading);
  }

  function nearestCard(el) {
    if (!el) return null;
    return el.closest('.card, article, section, li, .border, [class*="card"]') || el.parentElement;
  }

  function enhancePractice(root) {
    document.body.classList.add('rp-mode-page', 'rp-mode-practice');
    setBrandMode('practice');

    all('a,button', root).forEach((el) => {
      const t = norm(el.textContent);

      if (t === 'practise' || t === 'practice') {
        el.classList.add('rp-practice-action');
        const card = nearestCard(el);
        if (card) card.classList.add('rp-topic-card');
      }

      if (t === 'timed') {
        el.classList.add('rp-timed-action');
        const card = nearestCard(el);
        if (card) card.classList.add('rp-topic-card');
      }
    });

    all('h2,h3,h4,p,div', root).forEach((el) => {
      if (el.children.length > 0) return;
      const text = (el.textContent || '').trim();
      if (/^(ENG|MAT|VR|NVR)\s*[—-]/i.test(text)) {
        el.classList.add('rp-subject-heading');
      }
    });
  }

  function smallestMatchingElements(root, predicate) {
    return all('*', root).filter((el) => {
      if (!predicate(el)) return false;
      return !Array.from(el.children).some((child) => predicate(child));
    });
  }

  function extractTopicName(text) {
    let value = (text || '').replace(/\s+/g, ' ').trim();
    value = value.replace(/^(ENG|MAT|VR|NVR)\s+/i, '');
    const cut = value.search(/you'?re at\s+\d+%/i);
    if (cut > 0) value = value.slice(0, cut).trim();
    return value;
  }

  function simplifyTargetedMock(root) {
    const targetedTitle = all('h2,h3,h4', root).find(
      (el) => norm(el.textContent) === 'targeted paper'
    );
    if (!targetedTitle) return;

    const card = nearestCard(targetedTitle);
    if (!card) return;

    card.classList.add('rp-targeted-paper', 'rp-targeted-simplified');

    const description = Array.from(card.children).find((el) => {
      const t = norm(el.textContent);
      return t.includes('chosen from your last') || t.includes('most come from where');
    }) || all('p', card).find((el) => {
      const t = norm(el.textContent);
      return t.includes('chosen from your last') || t.includes('most come from where');
    });

    if (description) {
      description.textContent = 'A personalised paper built around the areas where you can gain the most marks.';
    }

    const why = all('h2,h3,h4,p,div', card).find(
      (el) => norm(el.textContent) === 'why these questions'
    );

    const rowPredicate = (el) => {
      const t = norm(el.textContent);
      return t.includes("you're at") && t.includes('question') && /\d+%/.test(t);
    };

    const rows = smallestMatchingElements(card, rowPredicate);
    const topicNames = [];

    rows.forEach((row) => {
      const name = extractTopicName(row.textContent);
      if (name && !topicNames.includes(name)) topicNames.push(name);
      row.classList.add('rp-mock-breakdown-hidden');
      row.dataset.rpMockBreakdownRow = '1';
    });

    if (why) {
      why.classList.add('rp-mock-breakdown-hidden');
      why.dataset.rpMockBreakdownHeading = '1';
    }

    const summary = document.createElement('div');
    summary.className = 'rp-target-summary';

    const focus = topicNames.slice(0, 3);
    summary.innerHTML = `
      <div class="rp-target-summary__label">This mock focuses on</div>
      <div class="rp-target-summary__chips">
        ${
          focus.length
            ? focus.map((name) => `<span class="rp-target-summary__chip">${name}</span>`).join('')
            : '<span class="rp-target-summary__chip">Your priority topics</span>'
        }
      </div>
    `;

    if (why) {
      why.insertAdjacentElement('beforebegin', summary);
    } else {
      targetedTitle.insertAdjacentElement('afterend', summary);
    }

    if (rows.length) {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'rp-target-breakdown-toggle';
      toggle.textContent = 'See what’s included';
      toggle.setAttribute('aria-expanded', 'false');

      summary.insertAdjacentElement('afterend', toggle);

      toggle.addEventListener('click', () => {
        const open = toggle.getAttribute('aria-expanded') === 'true';
        toggle.setAttribute('aria-expanded', open ? 'false' : 'true');
        toggle.textContent = open ? 'See what’s included' : 'Hide breakdown';

        if (why) why.classList.toggle('rp-mock-breakdown-hidden', open);
        rows.forEach((row) => row.classList.toggle('rp-mock-breakdown-hidden', open));
      });
    }

    all('a,button', card).forEach((el) => {
      if (norm(el.textContent).includes('start my targeted paper')) {
        el.classList.add('rp-mock-action');
      }
    });
  }

  function enhanceMocks(root) {
    document.body.classList.add('rp-mode-page', 'rp-mode-mocks');
    setBrandMode('mocks');

    simplifyTargetedMock(root);

    const fullHeading = all('h2,h3,h4', root).find(
      (el) => norm(el.textContent) === 'or sit a full paper'
    );
    if (fullHeading) fullHeading.textContent = 'Full papers';

    all('a,button', root).forEach((el) => {
      const t = norm(el.textContent);

      if (/^start .* paper$/.test(t)) {
        el.classList.add('rp-mock-action');
        const card = nearestCard(el);
        if (card) card.classList.add('rp-paper-card');
      }

      if (t === 'practice instead') {
        el.style.display = 'none';
      }
    });
  }


  function isTargetPage() {
    return !!all('h1,h2').find((el) => norm(el.textContent) === 'my target');
  }

  function safeText(value, fallback = '') {
    const v = (value || '').replace(/\s+/g, ' ').trim();
    return v || fallback;
  }

  function esc(value) {
    return safeText(value)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function numberValue(value, fallback = 0) {
    const n = parseFloat(String(value || '').replace(/[^0-9.\-]/g, ''));
    return Number.isFinite(n) ? n : fallback;
  }

  function clampPct(value) {
    return Math.max(0, Math.min(100, numberValue(value, 0)));
  }

  function linesFromPage() {
    return (document.body.innerText || '')
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean);
  }

  function nextLineAfter(lines, label) {
    const idx = lines.findIndex((line) => norm(line) === norm(label));
    return idx >= 0 && idx + 1 < lines.length ? lines[idx + 1] : '';
  }

  function textMatch(pattern, fallback = '') {
    const body = document.body.innerText || '';
    const m = body.match(pattern);
    return m ? safeText(m[1], fallback) : fallback;
  }

  function targetData() {
    const lines = linesFromPage();
    const body = document.body.innerText || '';

    let school = '';
    const targetIdx = lines.findIndex((line) => norm(line) === 'target');
    if (targetIdx >= 0 && lines[targetIdx + 1]) school = lines[targetIdx + 1];

    if (!school) {
      const myTargetIdx = lines.findIndex((line) => norm(line) === 'my target');
      for (let i = myTargetIdx + 1; i < Math.min(lines.length, myTargetIdx + 12); i++) {
        const candidate = lines[i];
        if (
          candidate &&
          !['change target','practise','practice','target'].includes(norm(candidate)) &&
          !/\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}/.test(candidate)
        ) {
          school = candidate;
          break;
        }
      }
    }

    const date = textMatch(/(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\s*[·•-]\s*\d+\s+days?\s+to\s+go/i, '');
    const days = textMatch(/\b(\d+)\s+days?\s+to\s+go\b/i, '');
    const hoursNeeded = textMatch(/Hours needed\s*([\d.]+)\s*\/?wk/i, '');
    const doingNow = textMatch(/Doing now\s*([\d.]+)\s*\/?wk/i, '');
    const hoursLogged = textMatch(/Hours logged\s*([\d.]+)\s*\/\s*([\d.]+)/i, '');
    const hoursTotalMatch = body.match(/Hours logged\s*([\d.]+)\s*\/\s*([\d.]+)/i);
    const hoursTotal = hoursTotalMatch ? hoursTotalMatch[2] : '';
    const attainment = textMatch(/Attainment vs target\s*(\d+)%/i, '');

    const englishMatch = body.match(/English\s*(\d+)%\s*\/\s*(\d+)%\s*target/i);
    const mathsMatch = body.match(/Maths\s*(\d+)%\s*\/\s*(\d+)%\s*target/i);

    return {
      school: safeText(school, 'Your target school'),
      date,
      days,
      hoursNeeded,
      doingNow,
      hoursLogged,
      hoursTotal,
      attainment,
      english: englishMatch ? englishMatch[1] : '',
      englishTarget: englishMatch ? englishMatch[2] : '',
      maths: mathsMatch ? mathsMatch[1] : '',
      mathsTarget: mathsMatch ? mathsMatch[2] : '',
      area: nextLineAfter(lines, 'Area'),
      assessment: nextLineAfter(lines, 'Assessment'),
      testWindow: nextLineAfter(lines, 'Test window'),
      papers: nextLineAfter(lines, 'Papers'),
      selection: nextLineAfter(lines, 'Selection'),
    };
  }

  function findActionHref(labelOptions, fallback) {
    const labels = labelOptions.map(norm);
    const el = all('a,button').find((node) => labels.includes(norm(node.textContent)));
    if (!el) return fallback;
    if (el.tagName === 'A') return el.href;
    const form = el.closest('form');
    return form?.action || fallback;
  }

  function findCalculationNotes() {
    const heading = all('h2,h3,h4,div,p').find(
      (el) => norm(el.textContent) === 'where these numbers come from'
    );
    if (!heading) return '';

    let node = heading.nextElementSibling;
    while (node && !['UL','OL'].includes(node.tagName)) node = node.nextElementSibling;
    if (!node) {
      const parent = heading.parentElement;
      node = parent?.querySelector('ul,ol');
    }
    return node ? node.innerHTML : '';
  }

  function enhanceTargetPage(urls) {
    document.body.classList.add('rp-target-page');

    const data = targetData();
    const heading = all('h1,h2').find((el) => norm(el.textContent) === 'my target');
    const main =
      heading?.closest('main') ||
      document.querySelector('main') ||
      heading?.closest('.container') ||
      document.querySelector('.container') ||
      document.querySelector('.container-fluid');

    if (!main) return;

    const changeHref = findActionHref(['change target'], '#');
    const practiseHref = findActionHref(['practise','practice'], urls.practice || '#');
    const calculationNotes = findCalculationNotes();

    const mapQuery = [data.school, data.area, 'UK'].filter(Boolean).join(', ');
    const mapEmbed = 'https://www.google.com/maps?q=' + encodeURIComponent(mapQuery) + '&output=embed';
    const mapOpen = 'https://www.google.com/maps/search/?api=1&query=' + encodeURIComponent(mapQuery);

    const attainment = clampPct(data.attainment || 0);
    const english = clampPct(data.english || 0);
    const maths = clampPct(data.maths || 0);
    const weekPct = data.hoursNeeded
      ? Math.max(0, Math.min(100, (numberValue(data.doingNow) / Math.max(numberValue(data.hoursNeeded), .1)) * 100))
      : 0;

    Array.from(main.children).forEach((el) => {
      if (el.matches('script,style')) return;
      el.classList.add('rp-target-original');
    });

    const hub = document.createElement('section');
    hub.className = 'rp-target-hub';

    hub.innerHTML = `
      <div class="rp-target-hub__header">
        <div>
          <h1>My target</h1>
          <p>Your school, exam date and what to focus on.</p>
        </div>
        <div class="rp-target-hub__actions">
          <a class="rp-target-hub__btn" href="${esc(changeHref)}">Change school</a>
          <a class="rp-target-hub__btn rp-target-hub__btn--primary" href="${esc(practiseHref)}">Start practising</a>
        </div>
      </div>

      <div class="rp-target-hub__hero">
        <section class="rp-target-school">
          <div class="rp-target-school__eyebrow">Your chosen school</div>
          <h2>${esc(data.school)}</h2>
          <div class="rp-target-school__meta">
            ${data.area ? `<span>${esc(data.area)}</span>` : ''}
            ${data.date ? `<span>${esc(data.date)}</span>` : ''}
            ${data.days ? `<span><strong>${esc(data.days)} days</strong> to go</span>` : ''}
          </div>

          <div class="rp-target-school__progress">
            <div class="rp-target-school__progress-head">
              <span>Progress towards your target</span>
              <strong>${esc(data.attainment || '—')}${data.attainment ? '%' : ''}</strong>
            </div>
            <div class="rp-target-bar"><span style="width:${attainment}%"></span></div>
          </div>

          <div class="rp-target-school__encourage">
            Keep working through the recommended topics. Small, regular sessions are enough — you do not need to fix everything at once.
          </div>
        </section>

        <section class="rp-target-map">
          <div class="rp-target-map__head">
            <strong>School location</strong>
            <a href="${esc(mapOpen)}" target="_blank" rel="noopener noreferrer">Open map ↗</a>
          </div>
          <iframe
            title="Map showing ${esc(data.school)}"
            loading="lazy"
            referrerpolicy="no-referrer-when-downgrade"
            src="${esc(mapEmbed)}">
          </iframe>
        </section>
      </div>

      <div class="rp-target-stats">
        <div class="rp-target-stat">
          <span>This week</span>
          <strong>${esc(data.doingNow || '—')}${data.doingNow ? ' hrs' : ''}</strong>
        </div>
        <div class="rp-target-stat">
          <span>Weekly target</span>
          <strong>${esc(data.hoursNeeded || '—')}${data.hoursNeeded ? ' hrs' : ''}</strong>
        </div>
        <div class="rp-target-stat">
          <span>Total practice</span>
          <strong>${esc(data.hoursLogged || '—')}${data.hoursLogged ? ' hrs' : ''}</strong>
        </div>
      </div>

      <div class="rp-target-main">
        <section class="rp-target-panel">
          <span class="rp-target-panel__kicker">Subjects</span>
          <h3>How you’re doing</h3>
          <p class="rp-target-panel__copy">A quick view of the papers linked to this school target.</p>

          <div class="rp-target-subjects">
            <div class="rp-target-subject">
              <div class="rp-target-subject__head">
                <strong>English</strong>
                <span>${esc(data.english || '—')}${data.english ? '%' : ''}${data.englishTarget ? ` · target ${esc(data.englishTarget)}%` : ''}</span>
              </div>
              <div class="rp-target-bar"><span style="width:${english}%"></span></div>
              ${data.english && data.englishTarget ? `<div class="rp-target-subject__note">${Math.max(0, numberValue(data.englishTarget) - numberValue(data.english))} points to your current target.</div>` : ''}
            </div>

            <div class="rp-target-subject">
              <div class="rp-target-subject__head">
                <strong>Maths</strong>
                <span>${esc(data.maths || '—')}${data.maths ? '%' : ''}${data.mathsTarget ? ` · target ${esc(data.mathsTarget)}%` : ''}</span>
              </div>
              <div class="rp-target-bar"><span style="width:${maths}%"></span></div>
              ${data.maths && data.mathsTarget ? `<div class="rp-target-subject__note">${Math.max(0, numberValue(data.mathsTarget) - numberValue(data.maths))} points to your current target.</div>` : ''}
            </div>
          </div>

          ${data.hoursNeeded ? `
          <div class="rp-target-more">
            <details>
              <summary>Weekly practice plan</summary>
              <div class="rp-target-more__content">
                You have completed ${esc(data.doingNow || '0')} of roughly ${esc(data.hoursNeeded)} planned hours this week.
                <div class="rp-target-bar" style="margin-top:.65rem;"><span style="width:${weekPct}%"></span></div>
              </div>
            </details>
          </div>` : ''}
        </section>

        <section class="rp-target-panel">
          <span class="rp-target-panel__kicker">Chosen school</span>
          <h3>${esc(data.school)}</h3>
          <p class="rp-target-panel__copy">The key details only.</p>

          <div class="rp-target-details">
            ${data.area ? `<div class="rp-target-detail"><span>Area</span><strong>${esc(data.area)}</strong></div>` : ''}
            ${data.assessment ? `<div class="rp-target-detail"><span>Assessment</span><strong>${esc(data.assessment)}</strong></div>` : ''}
            ${data.testWindow ? `<div class="rp-target-detail"><span>Test window</span><strong>${esc(data.testWindow)}</strong></div>` : ''}
            ${data.papers ? `<div class="rp-target-detail"><span>Papers</span><strong>${esc(data.papers)}</strong></div>` : ''}
          </div>

          ${data.selection ? `
          <div class="rp-target-more">
            <details>
              <summary>Admissions notes</summary>
              <div class="rp-target-more__content">${esc(data.selection)}</div>
            </details>
          </div>` : ''}

          <div class="rp-target-verified">
            School admissions information can change. Confirm final requirements with the school before applying.
          </div>
        </section>
      </div>

      ${calculationNotes ? `
      <div class="rp-target-more">
        <details>
          <summary>How is my target worked out?</summary>
          <div class="rp-target-more__content"><ul>${calculationNotes}</ul></div>
        </details>
      </div>` : ''}
    `;

    main.prepend(hub);
  }


  function init() {
    const urls = getNavUrls();
    rewriteNavigation(urls);

    if (isTargetPage()) {
      enhanceTargetPage(urls);
      return;
    }

    const mode = modeFromPage();
    if (!mode) return;

    const params = new URLSearchParams(location.search);
    const wantsStudyHub = params.get('study') === '1';

    if (wantsStudyHub && mode === 'practice') {
      makeStudyHub(urls);
      return;
    }

    const heading = findPageHeading();
    const root = mainContent();

    hideOldIntro(heading);
    insertModeHero(mode, heading, urls);

    if (mode === 'practice') enhancePractice(root);
    if (mode === 'mocks') enhanceMocks(root);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, { once: true });
  } else {
    init();
  }
})();
