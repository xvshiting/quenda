// ═══════════════════════════════════════════════════════════
// Anthropic-style web slide player
// ═══════════════════════════════════════════════════════════

let currentSlide = 0;
let isPlaying = false;
let animationQueue = [];
let slideStartTime = 0;
const prefersReducedMotion = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true;

// ─── DOM 引用 ───
const slideEl = document.getElementById('slide');
const counterEl = document.getElementById('counter');
const btnPrev = document.getElementById('btn-prev');
const btnNext = document.getElementById('btn-next');
const btnReplay = document.getElementById('btn-replay');
const btnAutoplay = document.getElementById('btn-autoplay');
const btnRecord = document.getElementById('btn-record');
const btnTheme = document.getElementById('btn-theme');
const btnNotes = document.getElementById('btn-notes');
const btnPresenter = document.getElementById('btn-presenter');
const notesPanel = document.getElementById('notes-panel');
const notesContent = document.getElementById('notes-content');
const btnNotesClose = document.getElementById('btn-notes-close');
let presenterWindow = null;
let presenterStartedAt = Date.now();

// data.js 使用最终画布百分比坐标。禁止按页码二次缩放，否则换页数后布局会漂移。
const CONTENT_Y_SCALE = 1;

// ─── 初始化 ───
function init() {
  document.title = DECK_META.title || 'Presentation';
  document.body.dataset.theme = DECK_META.theme || 'anthropic-warm';
  const requestedSlide = Number(new URLSearchParams(window.location.search).get('slide'));
  if (Number.isInteger(requestedSlide) && requestedSlide >= 1 && requestedSlide <= SLIDES.length) currentSlide = requestedSlide - 1;
  renderSlide(currentSlide);
  bindEvents();
}

// ─── 事件绑定 ───
function bindEvents() {
  btnPrev.addEventListener('click', () => {
    if (currentSlide > 0) {
      currentSlide--;
      renderSlide(currentSlide);
      playAnimations();
    }
  });

  btnNext.addEventListener('click', () => {
    if (currentSlide < SLIDES.length - 1) {
      currentSlide++;
      renderSlide(currentSlide);
      playAnimations();
    }
  });

  btnReplay.addEventListener('click', () => {
    renderSlide(currentSlide);
    playAnimations();
  });

  btnAutoplay.addEventListener('click', () => {
    if (!isPlaying) {
      startAutoplay();
    } else {
      stopAutoplay();
    }
  });

  btnRecord.addEventListener('click', () => {
    toggleRecording();
  });

  btnTheme.addEventListener('click', cycleTheme);
  btnNotes.addEventListener('click', toggleNotes);
  btnPresenter.addEventListener('click', openPresenterView);
  btnNotesClose.addEventListener('click', closeNotes);

  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === ' ') {
      e.preventDefault();
      if (currentSlide < SLIDES.length - 1) {
        currentSlide++;
        renderSlide(currentSlide);
        playAnimations();
      }
    } else if (e.key === 'ArrowLeft') {
      if (currentSlide > 0) {
        currentSlide--;
        renderSlide(currentSlide);
        playAnimations();
      }
    } else if (e.key === 'r' || e.key === 'R') {
      renderSlide(currentSlide);
      playAnimations();
    } else if (e.key === 't' || e.key === 'T') {
      cycleTheme();
    } else if (e.key === 'n' || e.key === 'N') {
      toggleNotes();
    } else if (e.key === 's' || e.key === 'S') {
      openPresenterView();
    }
  });
}

// ─── 渲染幻灯片 ───
function renderSlide(index) {
  const slide = SLIDES[index];
  if (!slide) return;

  // 清空画布
  slideEl.innerHTML = '';
  slideEl.dataset.slide = String(index + 1);
  animationQueue = [];

  // 添加页脚
  addFooter(index);

  // 渲染所有元素
  slide.elements.forEach((el, i) => {
    const domEl = createElement(el, i);
    if (domEl) {
      slideEl.appendChild(domEl);
      
      // 加入动画队列
      if (el.anim) {
        animationQueue.push({
          element: domEl,
          config: el.anim,
          elementData: el
        });
      }
    }
  });

  // 更新计数器
  counterEl.textContent = `${index + 1} / ${SLIDES.length}`;
  btnPrev.disabled = index === 0;
  btnNext.disabled = index === SLIDES.length - 1;
  slideEl.setAttribute('aria-label', `第 ${index + 1} 张，共 ${SLIDES.length} 张`);
  notesContent.innerHTML = slide.notes || '<p>本页暂无讲者备注。</p>';
  syncPresenterView();
}

function cycleTheme() {
  const themes = Array.isArray(DECK_META.themes) && DECK_META.themes.length ? DECK_META.themes : [DECK_META.theme || 'anthropic-warm'];
  const current = document.body.dataset.theme || themes[0];
  const next = themes[(Math.max(0, themes.indexOf(current)) + 1) % themes.length];
  document.body.dataset.theme = next;
  btnTheme.title = `当前主题：${next}`;
  syncPresenterView();
}

function toggleNotes() {
  const open = !notesPanel.classList.contains('open');
  notesPanel.classList.toggle('open', open);
  notesPanel.setAttribute('aria-hidden', String(!open));
  btnNotes.classList.toggle('active', open);
}

function closeNotes() {
  notesPanel.classList.remove('open');
  notesPanel.setAttribute('aria-hidden', 'true');
  btnNotes.classList.remove('active');
}

function openPresenterView() {
  if (presenterWindow && !presenterWindow.closed) {
    presenterWindow.focus();
    syncPresenterView();
    return;
  }
  presenterStartedAt = Date.now();
  presenterWindow = window.open('', 'anthropic-presenter', 'width=1280,height=820');
  if (!presenterWindow) {
    alert('浏览器阻止了演讲者窗口，请允许弹出窗口。');
    return;
  }
  presenterWindow.document.write(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>Presenter · ${DECK_META.title || ''}</title><style>
    *{box-sizing:border-box}body{margin:0;background:#111;color:#eee;font-family:-apple-system,BlinkMacSystemFont,"Noto Sans SC",sans-serif;padding:24px}
    .grid{display:grid;grid-template-columns:1.25fr .75fr;gap:18px;height:calc(100vh - 48px)}.card{background:#1d1d1c;border:1px solid #363634;border-radius:14px;padding:20px;overflow:auto}
    .label{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:#aaa}.title{font-size:34px;line-height:1.25;margin-top:14px}.next{font-size:22px;line-height:1.35;margin-top:14px;color:#ccc}
    .notes{font-size:20px;line-height:1.7}.notes strong{color:#efa077}.meta{display:flex;justify-content:space-between;font-variant-numeric:tabular-nums}.controls{display:flex;gap:10px;margin-top:18px}button{background:#333;color:#fff;border:1px solid #555;border-radius:8px;padding:10px 16px;cursor:pointer}
  </style></head><body><div class="grid"><section class="card"><div class="label">Current</div><div id="p-current" class="title"></div><div class="label" style="margin-top:32px">Speaker script</div><div id="p-notes" class="notes"></div></section><aside><section class="card"><div class="label">Next</div><div id="p-next" class="next"></div></section><section class="card" style="margin-top:18px"><div class="meta"><span id="p-count"></span><span id="p-time"></span></div><div class="controls"><button id="p-prev">← 上一页</button><button id="p-next-btn">下一页 →</button></div></section></aside></div></body></html>`);
  presenterWindow.document.close();
  presenterWindow.document.getElementById('p-prev').onclick = () => { if (currentSlide > 0) { currentSlide--; renderSlide(currentSlide); playAnimations(); } };
  presenterWindow.document.getElementById('p-next-btn').onclick = () => { if (currentSlide < SLIDES.length - 1) { currentSlide++; renderSlide(currentSlide); playAnimations(); } };
  presenterWindow.setInterval(syncPresenterView, 1000);
  syncPresenterView();
}

function slideLabel(slide) {
  if (!slide) return '—';
  const title = (slide.elements || []).find((item) => item.type === 'text' && /title-/.test(item.class || ''));
  return title ? String(title.text).replace(/<[^>]+>/g, '') : slide.id;
}

function syncPresenterView() {
  if (!presenterWindow || presenterWindow.closed) return;
  const doc = presenterWindow.document;
  const set = (id, value, html = false) => { const el = doc.getElementById(id); if (el) html ? el.innerHTML = value : el.textContent = value; };
  set('p-current', slideLabel(SLIDES[currentSlide]));
  set('p-next', slideLabel(SLIDES[currentSlide + 1]));
  set('p-notes', SLIDES[currentSlide].notes || '<p>本页暂无讲者备注。</p>', true);
  set('p-count', `${currentSlide + 1} / ${SLIDES.length}`);
  const elapsed = Math.floor((Date.now() - presenterStartedAt) / 1000);
  set('p-time', `${String(Math.floor(elapsed / 60)).padStart(2, '0')}:${String(elapsed % 60).padStart(2, '0')}`);
}

// ─── 创建元素 ───
function createElement(data, index) {
  let el;

  switch (data.type) {
    case 'text':
      el = document.createElement('div');
      el.className = `layer ${data.class || ''}`;
      if (data.style) el.style.cssText = data.style;
      el.innerHTML = data.text;
      applyPosition(el, data);
      addAnimationClass(el, data.anim);
      break;

    case 'rect':
      el = document.createElement('div');
      el.className = `layer ${data.class || ''}`;
      if (data.style) el.style.cssText = data.style;
      applyPosition(el, data);
      addAnimationClass(el, data.anim);
      break;

    case 'line':
      el = document.createElement('div');
      el.className = `layer ${data.class || ''}`;
      if (data.style) el.style.cssText = data.style;
      applyPosition(el, data);
      addAnimationClass(el, data.anim);
      break;

    case 'image':
      el = document.createElement('img');
      el.className = `layer image-layer ${data.class || ''}`;
      el.src = data.src || '';
      el.alt = data.alt || '';
      el.style.objectFit = data.objectFit || 'cover';
      if (data.style) el.style.cssText += data.style;
      applyPosition(el, data);
      addAnimationClass(el, data.anim);
      break;

    case 'icon-badge':
      el = document.createElement('div');
      el.className = `layer icon-badge ${data.accent ? 'accent' : ''}`;
      el.innerHTML = ICON_MAP[data.icon] || '';
      applyPosition(el, data, true);
      addAnimationClass(el, data.anim);
      break;

    case 'num-badge':
      el = document.createElement('div');
      el.className = 'layer num-badge';
      el.textContent = data.text;
      applyPosition(el, data, true);
      addAnimationClass(el, data.anim);
      break;

    case 'num-circle':
      el = document.createElement('div');
      el.className = 'layer num-circle';
      el.textContent = data.text;
      applyPosition(el, data, true);
      addAnimationClass(el, data.anim);
      break;

    case 'card-with-icon':
      el = document.createElement('div');
      el.className = `layer ${data.variant === 'compact' ? 'feature-compact' : data.variant === 'minimal' ? 'feature-item' : 'card feature-card'}`;
      applyPosition(el, data);
      el.style.padding = '0';
      el.style.display = 'flex';
      el.style.alignItems = data.variant === 'minimal' ? 'flex-start' : 'center';
      if (data.variant === 'minimal') el.style.flexDirection = 'column';
      
      // 内部图标 - 用 cqw 单位，相对于 slide 宽度
      const iconDiv = document.createElement('div');
      iconDiv.className = `icon-badge feature-icon ${data.accent !== false ? 'accent' : ''}`;
      iconDiv.innerHTML = ICON_MAP[data.icon] || '';
      iconDiv.style.cssText = data.variant === 'compact'
        ? 'flex-shrink:0;width:2.7cqw;height:2.7cqw;margin:0 1.15cqw 0 0;border-radius:10px;display:flex;align-items:center;justify-content:center;'
        : data.variant === 'minimal'
        ? 'flex-shrink:0;width:3.3cqw;height:3.3cqw;margin:0 0 1.15cqw 0;border-radius:12px;display:flex;align-items:center;justify-content:center;'
        : 'flex-shrink:0;width:5.2cqw;height:5.2cqw;margin-left:4.5%;border-radius:18px;display:flex;align-items:center;justify-content:center;';
      el.appendChild(iconDiv);
      
      // 文字容器
      const textWrap = document.createElement('div');
      textWrap.className = 'feature-copy';
      textWrap.style.cssText = data.variant === 'compact'
        ? 'min-width:0;flex:1;padding:0;display:flex;flex-direction:column;justify-content:center;gap:.3em;'
        : data.variant === 'minimal'
        ? 'padding:0;display:flex;flex-direction:column;gap:.5em;'
        : 'flex:1;padding:0 5%;display:flex;flex-direction:column;justify-content:center;gap:.45em;';
      
      const titleDiv = document.createElement('div');
      titleDiv.className = 'feature-title';
      titleDiv.style.cssText = 'font-weight: 700; font-family: "PingFang SC","Hiragino Sans GB",sans-serif; font-size: clamp(12px, 1.12cqw, 18px); color: var(--text);';
      titleDiv.textContent = data.title;
      textWrap.appendChild(titleDiv);
      
      const descDiv = document.createElement('div');
      descDiv.className = 'feature-desc';
      descDiv.style.cssText = 'white-space: pre-line; font-family: "PingFang SC","Hiragino Sans GB",sans-serif; font-size: clamp(10px, .86cqw, 14px); color: var(--sub); line-height: 1.5;';
      descDiv.textContent = data.desc;
      textWrap.appendChild(descDiv);
      
      el.appendChild(textWrap);
      
      addAnimationClass(el, data.anim);
      break;

    case 'metric-card':
      el = document.createElement('div');
      el.className = `layer metric-card-component ${data.accent ? 'accent' : ''} ${['series-2','series-3'].includes(data.tone) ? data.tone : ''}`;
      applyPosition(el, data);

      const metricValueRow = document.createElement('div');
      metricValueRow.className = 'metric-value-row';
      const metricValue = document.createElement('span');
      metricValue.className = 'metric-value';
      metricValue.textContent = data.value || '';
      const metricUnit = document.createElement('span');
      metricUnit.className = 'metric-unit';
      metricUnit.textContent = data.unit || '';
      metricValueRow.append(metricValue, metricUnit);

      const metricLabel = document.createElement('div');
      metricLabel.className = 'metric-label';
      metricLabel.textContent = data.label || '';
      el.append(metricValueRow, metricLabel);

      if (data.desc) {
        const metricDesc = document.createElement('div');
        metricDesc.className = 'metric-desc';
        metricDesc.textContent = data.desc;
        el.appendChild(metricDesc);
      }

      addAnimationClass(el, data.anim);
      break;

    case 'hook-sequence':
      el = document.createElement('div');
      el.className = 'layer hook-sequence';
      applyPosition(el, data);
      const hookQuestion = document.createElement('div');
      hookQuestion.className = 'hook-question';
      hookQuestion.textContent = data.question || '';
      const hookMisdirect = document.createElement('div');
      hookMisdirect.className = 'hook-misdirect';
      hookMisdirect.textContent = data.misdirect || '';
      const hookReveal = document.createElement('div');
      hookReveal.className = 'hook-reveal';
      hookReveal.textContent = data.reveal || '';
      el.append(hookQuestion, hookMisdirect, hookReveal);
      addAnimationClass(el, data.anim);
      break;

    case 'halving-sequence':
      el = document.createElement('div');
      el.className = 'layer halving-sequence';
      applyPosition(el, data);
      (data.steps || []).forEach((step, stepIndex, steps) => {
        const item = document.createElement('div');
        item.className = `halving-step ${stepIndex === steps.length - 1 ? 'is-final' : ''}`;
        const value = document.createElement('div');
        value.className = 'halving-value';
        value.textContent = step.value || '';
        const label = document.createElement('div');
        label.className = 'halving-label';
        label.textContent = step.label || '';
        item.append(value, label);
        el.appendChild(item);
        if (stepIndex < steps.length - 1) {
          const arrow = document.createElement('div');
          arrow.className = 'halving-arrow';
          arrow.textContent = '→';
          el.appendChild(arrow);
        }
      });
      addAnimationClass(el, data.anim);
      break;

    case 'concept-pair':
      el = document.createElement('div');
      el.className = 'layer concept-pair';
      applyPosition(el, data);
      (data.items || []).slice(0, 2).forEach((item, itemIndex) => {
        const concept = document.createElement('div');
        concept.className = 'concept-pair-item';
        const marker = document.createElement('div');
        marker.className = 'concept-pair-marker';
        marker.textContent = String(itemIndex + 1).padStart(2, '0');
        const title = document.createElement('div');
        title.className = 'concept-pair-title';
        title.textContent = item.title || '';
        const desc = document.createElement('div');
        desc.className = 'concept-pair-desc';
        desc.textContent = item.desc || '';
        concept.append(marker, title, desc);
        el.appendChild(concept);
      });
      addAnimationClass(el, data.anim);
      break;

    case 'equation-explainer':
      el = document.createElement('div');
      el.className = 'layer equation-explainer';
      applyPosition(el, data);
      const equationLabel = document.createElement('div');
      equationLabel.className = 'equation-label';
      equationLabel.textContent = data.label || '';
      const equationValue = document.createElement('div');
      equationValue.className = 'equation-value';
      equationValue.textContent = data.equation || '';
      const equationNote = document.createElement('div');
      equationNote.className = 'equation-note';
      equationNote.textContent = data.note || '';
      el.append(equationLabel, equationValue, equationNote);
      addAnimationClass(el, data.anim);
      break;

    case 'timeline-bar':
      el = document.createElement('div');
      el.className = `layer timeline-bar ${data.accent ? 'accent' : ''}`;
      applyPosition(el, data);
      addAnimationClass(el, data.anim);
      break;

    case 'timeline-dot':
      el = document.createElement('div');
      el.className = `layer timeline-dot ${data.accent ? 'accent' : ''}`;
      applyPosition(el, data, true);
      addAnimationClass(el, data.anim);
      break;

    default:
      console.warn('未知元素类型:', data.type);
      return null;
  }

  return el;
}

/* ─── 应用位置（百分比）─── */
function applyPosition(el, data, isCircle = false) {
  const x = data.x || 0;
  const yScale = CONTENT_Y_SCALE;
  const y = (data.y || 0) * yScale;
  
  if (isCircle && data.size) {
    // 圆形元素：用 slide 宽度的百分比计算尺寸，保证 16:9 画布等比缩放
    // data.size 是百分比(0-100)，相对于 slide 宽度
    const sizePct = data.size;
    el.style.left = `calc(${x}% - ${sizePct / 2}cqw)`;
    el.style.top = `calc(${y}% - ${sizePct / 2}cqw)`;
    el.style.width = `${sizePct}cqw`;
    el.style.height = `${sizePct}cqw`;
  } else if (data.w && data.h) {
    // 矩形元素
    el.style.left = `${x}%`;
    el.style.top = `${y}%`;
    el.style.width = `${data.w}%`;
    el.style.height = `${data.h * yScale}%`;
  }
}

// ─── 添加动画类 ───
function addAnimationClass(el, anim) {
  if (!anim) return;
  
  const type = anim.type || 'fade';
  const animClass = `anim-${type}`;
  el.classList.add(animClass);
}

// ─── 播放动画 ───
function playAnimations() {
  slideStartTime = performance.now();

  if (prefersReducedMotion) {
    animationQueue.forEach(({ element, config, elementData }) => executeAnimation(element, config.type || 'fade', 0, { ...config, duration: 0 }, elementData));
    return;
  }
  
  animationQueue.forEach((item) => {
    const { element, config, elementData } = item;
    const delay = config.delay || 0;
    const duration = config.duration || 0.5;
    const type = config.type || 'fade';

    setTimeout(() => {
      executeAnimation(element, type, duration, config, elementData);
    }, delay * 1000);
  });
}

// ─── 执行单个动画 ───
function executeAnimation(el, type, duration, config, elementData) {
  switch (type) {
    case 'fade':
      el.style.transition = `opacity ${duration}s ease`;
      el.classList.add('show');
      break;

    case 'slide-up':
      el.style.transition = `opacity ${duration}s ease, transform ${duration}s ease`;
      el.classList.add('show');
      break;

    case 'slide-down':
      el.style.transition = `opacity ${duration}s ease, transform ${duration}s ease`;
      el.classList.add('show');
      break;

    case 'slide-left':
      el.style.transition = `opacity ${duration}s ease, transform ${duration}s ease`;
      el.classList.add('show');
      break;

    case 'slide-right':
      el.style.transition = `opacity ${duration}s ease, transform ${duration}s ease`;
      el.classList.add('show');
      break;

    case 'pop':
      el.style.transition = `opacity ${duration}s cubic-bezier(0.34, 1.56, 0.64, 1), transform ${duration}s cubic-bezier(0.34, 1.56, 0.64, 1)`;
      el.classList.add('show');
      break;

    case 'focus-in':
      el.style.transition = `opacity ${duration}s cubic-bezier(.2,.7,.25,1), transform ${duration}s cubic-bezier(.2,.7,.25,1), filter ${duration}s ease`;
      el.classList.add('show');
      break;

    case 'blur-in':
      el.style.transition = `opacity ${duration}s ease, filter ${duration}s ease`;
      el.classList.add('show');
      break;

    case 'wipe-right':
      el.style.transition = `clip-path ${duration}s cubic-bezier(.2,.7,.25,1)`;
      el.classList.add('show');
      break;

    case 'draw-line':
      el.style.transition = `transform ${duration}s ease`;
      el.style.opacity = 1;
      el.style.transform = 'scaleX(1)';
      break;

    case 'draw-line-r':
      el.style.transition = `transform ${duration}s ease`;
      el.style.opacity = 1;
      el.style.transform = 'scaleX(1)';
      break;

    case 'draw-line-y':
      el.style.transition = `transform ${duration}s ease`;
      el.style.opacity = 1;
      el.style.transform = 'scaleY(1)';
      break;

    case 'count-up':
      animateCountUp(el, config, duration);
      break;

    default:
      el.style.transition = `opacity ${duration}s ease`;
      el.classList.add('show');
  }
}

// ─── 数字滚动动画 ───
function animateCountUp(el, config, duration) {
  const endValue = Number(config.endValue);
  const precision = Number.isInteger(config.precision) ? Math.max(0,Math.min(6,config.precision)) : 0;
  const prefix = String(config.prefix || '');
  const suffix = String(config.suffix || '');
  if (!Number.isFinite(endValue)) {
    el.classList.add('show');
    el.style.opacity = 1;
    return;
  }
  if (prefersReducedMotion || duration <= 0) {
    el.classList.add('show');
    el.style.opacity = 1;
    el.textContent = prefix + endValue.toFixed(precision) + suffix;
    return;
  }
  const startTime = performance.now();
  const startValue = 0;
  
  el.classList.add('show');
  el.style.opacity = 1;
  
  function update() {
    const elapsed = (performance.now() - startTime) / 1000;
    const progress = Math.min(elapsed / duration, 1);
    
    // easeOutQuart
    const eased = 1 - Math.pow(1 - progress, 4);
    const currentValue = startValue + (endValue - startValue) * eased;
    
    el.textContent = prefix + currentValue.toFixed(precision) + suffix;
    
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }
  
  requestAnimationFrame(update);
}

// ─── 添加页脚 ───
function addFooter(index) {
  // 页脚线
  const line = document.createElement('div');
  line.className = 'footer-line';
  slideEl.appendChild(line);
  
  // 页脚文字
  const text = document.createElement('div');
  text.className = 'footer-text';
  text.textContent = typeof DECK_META !== 'undefined' ? (DECK_META.footer || '') : '';
  slideEl.appendChild(text);
  
  // 页码
  const page = document.createElement('div');
  page.className = 'footer-page';
  page.textContent = String(index + 1).padStart(2, '0') + ' / ' + String(SLIDES.length).padStart(2, '0');
  slideEl.appendChild(page);
}

// ─── 自动播放 ───
let autoplayInterval = null;

function startAutoplay() {
  isPlaying = true;
  btnAutoplay.innerHTML = '<i class="fa-solid fa-stop"></i><span>停止播放</span>';
  btnAutoplay.classList.add('active');
  
  // 从当前页开始播放
  playAnimations();
  
  // 计算当前页总时长：取所有动画的最大结束时间；静态页也保留阅读时间。
  const maxAnimationEnd = animationQueue.reduce((max,item) => {
    const delay = Number(item.config?.delay) || 0;
    const duration = prefersReducedMotion ? 0 : (Number(item.config?.duration) || .5);
    return Math.max(max,delay + duration);
  },0);
  const slideDuration = Math.max(2500,(maxAnimationEnd + 1) * 1000);
  
  autoplayInterval = setTimeout(() => {
    if (currentSlide < SLIDES.length - 1) {
      currentSlide++;
      renderSlide(currentSlide);
      playAnimations();
      
      // 递归调用
      setTimeout(() => {
        if (isPlaying) {
          startAutoplay();
        }
      }, 0);
    } else {
      stopAutoplay();
    }
  }, slideDuration);
}

function stopAutoplay() {
  isPlaying = false;
  btnAutoplay.innerHTML = '<i class="fa-solid fa-play"></i><span>自动播放</span>';
  btnAutoplay.classList.remove('active');
  
  if (autoplayInterval) {
    clearTimeout(autoplayInterval);
    autoplayInterval = null;
  }
}

// ─── 录制功能 ───
let mediaRecorder = null;
let recordedChunks = [];
let isRecording = false;

function toggleRecording() {
  if (!isRecording) {
    startRecording();
  } else {
    stopRecording();
  }
}

async function startRecording() {
  try {
    const stream = await navigator.mediaDevices.getDisplayMedia({
      video: { mediaSource: 'screen' }
    });
    
    recordedChunks = [];
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'video/webm;codecs=vp9'
    });
    
    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) {
        recordedChunks.push(e.data);
      }
    };
    
    mediaRecorder.onstop = () => {
      const blob = new Blob(recordedChunks, { type: 'video/webm' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${String(DECK_META.title || 'presentation').replace(/[^a-z0-9-_]+/gi, '-')}-${Date.now()}.webm`;
      a.click();
      URL.revokeObjectURL(url);
    };
    
    mediaRecorder.start();
    isRecording = true;
    btnRecord.innerHTML = '<i class="fa-solid fa-stop"></i><span>停止录制</span>';
    btnRecord.classList.add('active');
    
    // 自动开始播放
    if (!isPlaying) {
      currentSlide = 0;
      renderSlide(currentSlide);
      playAnimations();
      startAutoplay();
    }
    
  } catch (err) {
    console.error('录制失败:', err);
    alert('无法启动录制，请确保允许屏幕共享。');
  }
}

function stopRecording() {
  if (mediaRecorder && isRecording) {
    mediaRecorder.stop();
    isRecording = false;
    btnRecord.innerHTML = '<i class="fa-solid fa-circle"></i><span>录制</span>';
    btnRecord.classList.remove('active');
    stopAutoplay();
  }
}

// ─── 启动 ───
document.addEventListener('DOMContentLoaded', () => {
  init();
  playAnimations(); // 自动播放第一张
});
