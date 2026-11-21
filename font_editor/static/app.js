(function () {
  'use strict';

  var FIXTURE = {
    name: 'Fixture A',
    advance: 500,
    points: [[30, 0], [215, 700], [285, 700], [470, 0], [390, 0], [345, 160], [155, 160], [110, 0]]
  };
  var CTRL = /[\u0000-\u001f\u007f-\u009f]/;
  var MAX_GLYPHS = 128;

  function $(id) { return document.getElementById(id); }

  var el = {
    newFont: $('new-font'), save: $('save'), dirty: $('dirty'), status: $('status'),
    error: $('error'), conflict: $('conflict'), lock: $('editor-lock'),
    fontName: $('font-name'), capHeight: $('cap-height'),
    addForm: $('add-glyph-form'), glyphName: $('glyph-name'), advanceWidth: $('advance-width'),
    addFixture: $('add-fixture'), glyphList: $('glyph-list'), glyphEmpty: $('glyph-empty'),
    panel: $('glyph-panel'), panelHint: $('panel-hint'), selWidth: $('selected-width'),
    pointSelect: $('point-select'), pointX: $('point-x'), pointY: $('point-y'), step: $('step'),
    left: $('move-left'), right: $('move-right'), up: $('move-up'), down: $('move-down'),
    canvas: $('glyph-canvas'), readout: $('preview-readout'),
    fontList: $('font-list'), fontEmpty: $('font-empty'), fontRetry: $('font-retry')
  };

  var state = blank();
  var fonts = [];
  var view = null;

  function blank() {
    return {
      id: null, version: null, title: '', capHeight: 700, glyphs: [],
      selGlyph: -1, selPoint: 0, dirty: false, saving: false, conflict: null, liveErr: false
    };
  }

  /* ---------- helpers ---------- */

  function parseInteger(s) {
    var t = String(s).trim();
    return /^-?\d+$/.test(t) ? Number(t) : null;
  }
  function inRange(n, lo, hi) { return n !== null && n >= lo && n <= hi; }
  function clamp(n, lo, hi) { return Math.max(lo, Math.min(hi, n)); }
  function curGlyph() { return state.glyphs[state.selGlyph] || null; }
  function nameTaken(name, exceptIndex) {
    var low = name.trim().toLowerCase();
    return state.glyphs.some(function (g, i) { return i !== exceptIndex && g.name.trim().toLowerCase() === low; });
  }

  /* ---------- messages ---------- */

  function clearError() {
    el.error.textContent = '';
    state.liveErr = false;
  }
  function renderConflict() {
    el.conflict.textContent = '';
    var c = state.conflict;
    if (!c) { return; }
    var a = document.createElement('button');
    a.type = 'button';
    a.className = 'btn primary';
    a.textContent = 'Save my edits over version ' + c.version;
    a.addEventListener('click', overwriteSave);
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'btn secondary';
    b.textContent = 'Load latest';
    b.addEventListener('click', loadLatest);
    el.conflict.appendChild(a);
    el.conflict.appendChild(b);
  }
  function clearMessages() {
    el.status.textContent = '';
    clearError();
    state.conflict = null;
    renderConflict();
  }
  function showStatus(text) {
    clearError();
    el.status.textContent = text;
  }
  function showErrors(summary, items) {
    el.status.textContent = '';
    el.error.textContent = '';
    var p = document.createElement('p');
    p.textContent = summary;
    el.error.appendChild(p);
    if (items && items.length) {
      var ul = document.createElement('ul');
      items.forEach(function (t) {
        var li = document.createElement('li');
        li.textContent = t;
        ul.appendChild(li);
      });
      el.error.appendChild(ul);
    }
  }
  function liveError(text) {
    showErrors(text);
    state.liveErr = true;
  }
  function liveOk() {
    if (state.liveErr) { clearError(); }
  }

  /* ---------- validation (mirrors the server rules) ---------- */

  function contourProblems(points) {
    var out = [];
    var n = points.length;
    var i, a, b, area = 0, minY = Infinity, maxY = -Infinity;
    for (i = 0; i < n; i++) {
      a = points[i];
      b = points[(i + 1) % n];
      if (a.x === b.x && a.y === b.y) {
        out.push('P' + (i + 1) + ' and P' + (((i + 1) % n) + 1) + ' are the same point.');
      }
      area += a.x * b.y - b.x * a.y;
      minY = Math.min(minY, a.y);
      maxY = Math.max(maxY, a.y);
    }
    if (area === 0) { out.push('The outline has no area.'); }
    if (!(maxY - minY > 0)) { out.push('The outline has no height.'); }
    return out;
  }

  function glyphProblems(g, label) {
    var out = [];
    var pre = label + ': ';
    var name = g.name.trim();
    if (name.length < 1 || name.length > 24) { out.push(pre + 'name must be 1 to 24 characters.'); }
    if (CTRL.test(name)) { out.push(pre + 'name has control characters.'); }
    if (!Number.isInteger(g.advance) || g.advance < 100 || g.advance > 1500) {
      out.push(pre + 'width must be a whole number from 100 to 1500.');
    }
    if (g.points.length < 3 || g.points.length > 64) {
      out.push(pre + 'needs 3 to 64 points.');
      return out;
    }
    var bad = false;
    g.points.forEach(function (p, i) {
      ['x', 'y'].forEach(function (k) {
        if (!Number.isInteger(p[k]) || p[k] < -1000 || p[k] > 2000) {
          out.push(pre + 'P' + (i + 1) + ' ' + k.toUpperCase() + ' must be a whole number from -1000 to 2000.');
          bad = true;
        }
      });
    });
    if (!bad) {
      contourProblems(g.points).forEach(function (m) { out.push(pre + m); });
    }
    return out;
  }

  function validateDraft() {
    var out = [];
    var title = state.title.trim();
    if (title.length < 1 || title.length > 60) { out.push('Font name must be 1 to 60 characters.'); }
    if (CTRL.test(title)) { out.push('Font name has control characters.'); }
    if (!Number.isInteger(state.capHeight) || state.capHeight < 300 || state.capHeight > 1000) {
      out.push('Cap height must be a whole number from 300 to 1000.');
    }
    if (state.glyphs.length > MAX_GLYPHS) { out.push('A font can have at most ' + MAX_GLYPHS + ' glyphs.'); }
    var seen = {};
    state.glyphs.forEach(function (g, i) {
      var key = g.name.trim().toLowerCase();
      if (seen[key]) { out.push('Glyph name "' + g.name + '" is used more than once.'); }
      seen[key] = true;
      glyphProblems(g, 'Glyph "' + g.name + '"').forEach(function (m) { out.push(m); });
    });
    return out;
  }

  /* ---------- network ---------- */

  function api(method, path, body) {
    var opts = { method: method, headers: {} };
    if (body !== undefined) {
      opts.headers['Content-Type'] = 'application/json';
      opts.body = JSON.stringify(body);
    }
    return fetch(path, opts).then(function (r) {
      return r.text().then(function (t) {
        var data = null;
        try { data = t ? JSON.parse(t) : null; } catch (e) { data = null; }
        return { ok: r.ok, status: r.status, data: data };
      });
    });
  }

  function serverMessage(res, fallback) {
    var err = res && res.data && res.data.error;
    var items = [];
    if (err && Array.isArray(err.details)) {
      err.details.forEach(function (d) {
        items.push((d.field ? d.field + ': ' : '') + d.message);
      });
    }
    return { summary: (err && err.message) || fallback + ' (HTTP ' + res.status + ').', items: items };
  }

  /* ---------- model adoption ---------- */

  function normalizePoint(p) {
    return Array.isArray(p) ? { x: p[0], y: p[1] } : { x: p.x, y: p.y };
  }

  function adopt(font, keepSelection) {
    var prevSel = state.selGlyph;
    var prevPoint = state.selPoint;
    state.id = font.id;
    state.version = font.version;
    state.title = font.title;
    state.capHeight = font.cap_height;
    state.glyphs = font.glyphs.map(function (g) {
      return { id: g.id, name: g.name, advance: g.advance, points: g.points.map(normalizePoint) };
    });
    state.dirty = false;
    if (keepSelection && state.glyphs.length) {
      state.selGlyph = clamp(prevSel, 0, state.glyphs.length - 1);
      state.selPoint = clamp(prevPoint, 0, state.glyphs[state.selGlyph].points.length - 1);
    } else {
      state.selGlyph = state.glyphs.length ? 0 : -1;
      state.selPoint = 0;
    }
  }

  /* ---------- rendering ---------- */

  function renderDirty() {
    el.dirty.textContent = state.dirty ? 'Unsaved changes' : '';
  }

  function renderHeaderFields() {
    el.fontName.value = state.title;
    el.capHeight.value = String(state.capHeight);
  }

  function renderGlyphList(focusIndex) {
    el.glyphList.textContent = '';
    state.glyphs.forEach(function (g, i) {
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.type = 'button';
      b.dataset.index = String(i);
      b.textContent = g.name + ' — ' + g.advance;
      if (i === state.selGlyph) { b.setAttribute('aria-current', 'true'); }
      li.appendChild(b);
      el.glyphList.appendChild(li);
      if (i === focusIndex) { b.focus(); }
    });
    el.glyphEmpty.hidden = state.glyphs.length > 0;
  }

  function syncPanel(skip) {
    var g = curGlyph();
    el.panel.disabled = !g;
    el.panelHint.hidden = !!g;
    if (!g) {
      el.selWidth.value = '';
      el.pointX.value = '';
      el.pointY.value = '';
      el.pointSelect.textContent = '';
      return;
    }
    if (skip !== el.selWidth) { el.selWidth.value = String(g.advance); }
    if (el.pointSelect.options.length !== g.points.length) {
      el.pointSelect.textContent = '';
      g.points.forEach(function (p, i) {
        var o = document.createElement('option');
        o.value = String(i);
        o.textContent = 'P' + (i + 1);
        el.pointSelect.appendChild(o);
      });
    }
    el.pointSelect.value = String(state.selPoint);
    var p = g.points[state.selPoint];
    if (skip !== el.pointX) { el.pointX.value = String(p.x); }
    if (skip !== el.pointY) { el.pointY.value = String(p.y); }
  }

  function getView(w, h, g) {
    var cap = state.capHeight;
    var adv = g ? g.advance : 500;
    var maxY = cap;
    if (g) { g.points.forEach(function (p) { maxY = Math.max(maxY, p.y); }); }
    var xmin = -100, xmax = adv + 100, ymin = -200, ymax = maxY + 200;
    var s = Math.min(w / (xmax - xmin), h / (ymax - ymin));
    return {
      s: s, xmin: xmin, ymin: ymin, h: h, w: w,
      ox: (w - (xmax - xmin) * s) / 2,
      oy: (h - (ymax - ymin) * s) / 2
    };
  }
  function sx(v, x) { return v.ox + (x - v.xmin) * v.s; }
  function sy(v, y) { return v.h - (v.oy + (y - v.ymin) * v.s); }

  function drawLabel(ctx, text, x, y) {
    ctx.fillStyle = '#3a4550';
    ctx.font = '12px system-ui, sans-serif';
    ctx.fillText(text, x, y);
  }

  function renderPreview() {
    var c = el.canvas;
    var g = curGlyph();
    var cap = state.capHeight;
    var sel = g ? 'P' + (state.selPoint + 1) : '';

    if (g) {
      c.setAttribute('aria-label', 'Glyph ' + g.name + ', advance ' + g.advance + ', ' + g.points.length + ' points');
      c.dataset.glyphId = g.id === undefined ? '' : String(g.id);
      c.dataset.advance = String(g.advance);
      c.dataset.pointCount = String(g.points.length);
      c.dataset.selectedPoint = sel;
      var p = g.points[state.selPoint];
      el.readout.textContent = 'Advance ' + g.advance + ' · Cap height ' + cap +
        ' · Point ' + sel + ' (' + p.x + ', ' + p.y + ')';
    } else {
      c.setAttribute('aria-label', 'No glyph selected');
      c.dataset.glyphId = '';
      c.dataset.advance = '';
      c.dataset.pointCount = '0';
      c.dataset.selectedPoint = '';
      el.readout.textContent = 'No glyph selected · Cap height ' + cap;
    }

    var dpr = window.devicePixelRatio || 1;
    var w = c.clientWidth, h = c.clientHeight;
    if (!w || !h) { return; }
    var bw = Math.round(w * dpr), bh = Math.round(h * dpr);
    if (c.width !== bw) { c.width = bw; }
    if (c.height !== bh) { c.height = bh; }
    var ctx = c.getContext('2d');
    if (!ctx) { return; }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    view = getView(w, h, g);
    var v = view;
    var adv = g ? g.advance : 500;
    var left = sx(v, v.xmin), right = sx(v, adv + 100);

    ctx.lineWidth = 1;
    // cap-height guide
    ctx.strokeStyle = '#1d4ed8';
    ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(left, sy(v, cap)); ctx.lineTo(right, sy(v, cap)); ctx.stroke();
    drawLabel(ctx, 'cap height', left + 4, sy(v, cap) - 4);
    // origin x=0
    ctx.strokeStyle = '#6b7280';
    ctx.setLineDash([]);
    ctx.beginPath(); ctx.moveTo(sx(v, 0), 0); ctx.lineTo(sx(v, 0), h); ctx.stroke();
    // advance mark
    ctx.strokeStyle = '#9a3412';
    ctx.setLineDash([6, 4]);
    ctx.beginPath(); ctx.moveTo(sx(v, adv), 0); ctx.lineTo(sx(v, adv), h); ctx.stroke();
    drawLabel(ctx, 'advance', Math.max(2, sx(v, adv) - 48), 14);
    // baseline
    ctx.strokeStyle = '#1b1f23';
    ctx.setLineDash([]);
    ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(left, sy(v, 0)); ctx.lineTo(right, sy(v, 0)); ctx.stroke();
    drawLabel(ctx, 'baseline', left + 4, sy(v, 0) + 14);
    ctx.lineWidth = 1;

    if (!g) {
      drawLabel(ctx, 'No glyph selected', left + 4, 30);
      return;
    }

    ctx.beginPath();
    g.points.forEach(function (pt, i) {
      var X = sx(v, pt.x), Y = sy(v, pt.y);
      if (i === 0) { ctx.moveTo(X, Y); } else { ctx.lineTo(X, Y); }
    });
    ctx.closePath();
    ctx.fillStyle = 'rgba(15, 76, 92, 0.16)';
    ctx.fill();
    ctx.strokeStyle = '#0f4c5c';
    ctx.lineWidth = 2;
    ctx.stroke();

    g.points.forEach(function (pt, i) {
      var X = sx(v, pt.x), Y = sy(v, pt.y);
      var on = i === state.selPoint;
      ctx.beginPath();
      ctx.arc(X, Y, on ? 8 : 5, 0, Math.PI * 2);
      ctx.fillStyle = on ? '#b42318' : '#ffffff';
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = on ? '#ffffff' : '#0f4c5c';
      ctx.stroke();
      if (on) {
        ctx.beginPath();
        ctx.arc(X, Y, 8, 0, Math.PI * 2);
        ctx.strokeStyle = '#7a0b0b';
        ctx.lineWidth = 1;
        ctx.stroke();
        drawLabel(ctx, sel, X + 11, Y - 9);
      }
    });
  }

  function renderSaving() {
    el.lock.disabled = state.saving;
    el.save.disabled = state.saving;
  }

  function renderFontList() {
    el.fontList.textContent = '';
    fonts.forEach(function (f) {
      var li = document.createElement('li');
      var b = document.createElement('button');
      b.type = 'button';
      b.dataset.id = String(f.id);
      b.textContent = f.title;
      if (f.id === state.id) { b.setAttribute('aria-current', 'true'); }
      li.appendChild(b);
      el.fontList.appendChild(li);
    });
    el.fontEmpty.hidden = fonts.length > 0;
  }

  function renderAll() {
    renderHeaderFields();
    renderGlyphList();
    syncPanel();
    renderPreview();
    renderDirty();
    renderSaving();
    renderFontList();
  }

  function markDirty() {
    state.dirty = true;
    renderDirty();
  }

  /* ---------- actions ---------- */

  function confirmDiscard() {
    return !state.dirty || window.confirm('Discard unsaved changes?');
  }

  function newFont() {
    if (state.saving || !confirmDiscard()) { return; }
    state = blank();
    clearMessages();
    renderAll();
    el.fontName.focus();
  }

  function selectGlyph(i, focusList) {
    state.selGlyph = i;
    state.selPoint = 0;
    renderGlyphList(focusList ? i : undefined);
    syncPanel();
    renderPreview();
    renderFontList();
  }

  function addGlyph(g) {
    state.glyphs.push(g);
    markDirty();
    selectGlyph(state.glyphs.length - 1, false);
    showStatus('Added glyph ' + g.name);
  }

  function onAddGlyph(e) {
    e.preventDefault();
    if (state.saving) { return; }
    var problems = [];
    var name = el.glyphName.value.trim();
    var adv = parseInteger(el.advanceWidth.value);
    var cap = state.capHeight;
    if (!name) { problems.push('Glyph name is required.'); }
    else if (name.length > 24) { problems.push('Glyph name must be 24 characters or fewer.'); }
    else if (CTRL.test(name)) { problems.push('Glyph name has control characters.'); }
    else if (nameTaken(name, -1)) { problems.push('A glyph named "' + name + '" already exists.'); }
    if (!inRange(adv, 100, 1500)) { problems.push('Advance width must be a whole number from 100 to 1500.'); }
    if (!inRange(cap, 300, 1000)) { problems.push('Cap height must be a whole number from 300 to 1000.'); }
    if (state.glyphs.length >= MAX_GLYPHS) { problems.push('A font can have at most ' + MAX_GLYPHS + ' glyphs.'); }
    if (!problems.length) {
      var inset = Math.min(50, Math.floor((adv - 1) / 2));
      var g = {
        name: name, advance: adv,
        points: [{ x: inset, y: 0 }, { x: adv - inset, y: 0 }, { x: adv - inset, y: cap }, { x: inset, y: cap }]
      };
      problems = glyphProblems(g, 'New glyph');
      if (!problems.length) {
        el.glyphName.value = '';
        addGlyph(g);
        return;
      }
    }
    showErrors('Cannot add glyph.', problems);
  }

  function onAddFixture() {
    if (state.saving) { return; }
    if (nameTaken(FIXTURE.name, -1)) {
      showErrors('Cannot add fixture glyph.', ['A glyph named "' + FIXTURE.name + '" already exists.']);
      return;
    }
    if (state.glyphs.length >= MAX_GLYPHS) {
      showErrors('Cannot add fixture glyph.', ['A font can have at most ' + MAX_GLYPHS + ' glyphs.']);
      return;
    }
    addGlyph({
      name: FIXTURE.name,
      advance: FIXTURE.advance,
      points: FIXTURE.points.map(function (p) { return { x: p[0], y: p[1] }; })
    });
  }

  function onTitleInput() {
    state.title = el.fontName.value;
    markDirty();
  }

  function onCapInput() {
    var v = parseInteger(el.capHeight.value);
    if (!inRange(v, 300, 1000)) {
      liveError('Cap height must be a whole number from 300 to 1000.');
      return;
    }
    liveOk();
    state.capHeight = v;
    markDirty();
    renderPreview();
  }

  function onWidthInput() {
    var g = curGlyph();
    if (!g) { return; }
    var v = parseInteger(el.selWidth.value);
    if (!inRange(v, 100, 1500)) {
      liveError('Selected glyph width must be a whole number from 100 to 1500.');
      return;
    }
    liveOk();
    g.advance = v;
    markDirty();
    renderGlyphList();
    renderPreview();
  }

  function onPointCoord(axis, input) {
    var g = curGlyph();
    if (!g) { return; }
    var v = parseInteger(input.value);
    if (!inRange(v, -1000, 2000)) {
      liveError('Point ' + axis.toUpperCase() + ' must be a whole number from -1000 to 2000.');
      return;
    }
    liveOk();
    g.points[state.selPoint][axis] = v;
    markDirty();
    renderPreview();
  }

  function getStep() {
    var v = parseInteger(el.step.value);
    if (!inRange(v, 1, 100)) {
      liveError('Step must be a whole number from 1 to 100.');
      return null;
    }
    liveOk();
    return v;
  }

  function movePoint(dx, dy, fine) {
    var g = curGlyph();
    if (!g || state.saving) { return; }
    var step = fine ? 1 : getStep();
    if (step === null) { return; }
    var p = g.points[state.selPoint];
    p.x = clamp(p.x + dx * step, -1000, 2000);
    p.y = clamp(p.y + dy * step, -1000, 2000);
    markDirty();
    syncPanel();
    renderPreview();
  }

  function onCanvasClick(e) {
    var g = curGlyph();
    if (!g || !view || state.saving) { return; }
    var r = el.canvas.getBoundingClientRect();
    var mx = e.clientX - r.left, my = e.clientY - r.top;
    var best = -1, bestD = 14 * 14 + 1;
    g.points.forEach(function (p, i) {
      var dx = sx(view, p.x) - mx, dy = sy(view, p.y) - my;
      var d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; best = i; }
    });
    if (best >= 0) {
      state.selPoint = best;
      syncPanel();
      renderPreview();
    }
  }

  function onCanvasKey(e) {
    var map = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, 1], ArrowDown: [0, -1] };
    var m = map[e.key];
    if (!m || e.ctrlKey || e.altKey || e.metaKey) { return; }
    e.preventDefault();
    movePoint(m[0], m[1], e.shiftKey);
  }

  /* ---------- save / load ---------- */

  function buildPayload(withVersion) {
    var body = {
      title: state.title.trim(),
      cap_height: state.capHeight,
      glyphs: state.glyphs.map(function (g) {
        var o = {};
        if (g.id !== undefined && g.id !== null) { o.id = g.id; }
        o.name = g.name.trim();
        o.advance = g.advance;
        o.points = g.points.map(function (p) { return { x: p.x, y: p.y }; });
        return o;
      })
    };
    if (withVersion) { body.version = state.version; }
    return body;
  }

  function setSaving(on) {
    state.saving = on;
    renderSaving();
    if (!on && (document.activeElement === document.body || !document.activeElement)) {
      el.save.focus();
    }
  }

  function save() {
    if (state.saving) { return Promise.resolve(); }
    clearMessages();
    var problems = validateDraft();
    if (problems.length) {
      showErrors('Fix these problems before saving.', problems);
      return Promise.resolve();
    }
    var isNew = state.id === null;
    var path = isNew ? '/api/v1/fonts' : '/api/v1/fonts/' + state.id;
    var body = buildPayload(!isNew);
    setSaving(true);
    return api(isNew ? 'POST' : 'PUT', path, body).then(function (res) {
      setSaving(false);
      if (res.ok && res.data) {
        adopt(res.data, true);
        renderAll();
        showStatus('Saved ' + state.title + ' (version ' + state.version + ')');
        return loadFontList();
      }
      handleSaveError(res);
    }, function () {
      setSaving(false);
      showErrors('Could not reach the server. Your edits are kept. Press Save to retry.');
    });
  }

  function handleSaveError(res) {
    var err = res.data && res.data.error;
    if (res.status === 409 && err && err.code === 'stale_version' && err.current) {
      state.conflict = err.current;
      showErrors('Another save changed this font (now version ' + err.current.version + ').');
      renderConflict();
      return;
    }
    if (res.status === 409 && err && err.code === 'duplicate_title') {
      showErrors(err.message || 'Another font already uses this name. Your edits are kept.');
      return;
    }
    if (res.status === 404) {
      showErrors('This font no longer exists on the server. Your edits are kept.');
      return;
    }
    var m = serverMessage(res, 'Save failed');
    showErrors(m.summary, m.items);
  }

  function overwriteSave() {
    var cur = state.conflict;
    if (!cur || state.saving) { return; }
    var ids = {};
    cur.glyphs.forEach(function (g) { ids[g.id] = true; });
    state.glyphs.forEach(function (g) {
      if (g.id !== undefined && !ids[g.id]) { delete g.id; }
    });
    state.version = cur.version;
    state.conflict = null;
    renderConflict();
    save();
  }

  function loadLatest() {
    var cur = state.conflict;
    if (!cur || state.saving) { return; }
    clearMessages();
    adopt(cur, false);
    renderAll();
    showStatus('Loaded ' + state.title + ' (version ' + state.version + ')');
  }

  function loadFont(id) {
    if (state.saving || !confirmDiscard()) { return Promise.resolve(); }
    return api('GET', '/api/v1/fonts/' + id).then(function (res) {
      if (res.ok && res.data) {
        clearMessages();
        adopt(res.data, false);
        renderAll();
        showStatus('Loaded ' + state.title + ' (version ' + state.version + ')');
      } else {
        var m = serverMessage(res, 'Could not load font');
        showErrors(m.summary, m.items);
      }
    }, function () {
      showErrors('Could not reach the server. Try again.');
    });
  }

  function loadFontList() {
    return api('GET', '/api/v1/fonts').then(function (res) {
      if (!res.ok || !res.data || !Array.isArray(res.data.fonts)) { throw new Error('bad'); }
      fonts = res.data.fonts;
      el.fontRetry.hidden = true;
      renderFontList();
    }).catch(function () {
      el.fontRetry.hidden = false;
      if (!el.status.textContent) { showErrors('Could not load the saved fonts list.'); }
    });
  }

  /* ---------- wiring ---------- */

  el.newFont.addEventListener('click', newFont);
  el.save.addEventListener('click', save);
  el.fontName.addEventListener('input', onTitleInput);
  el.capHeight.addEventListener('input', onCapInput);
  el.capHeight.addEventListener('change', function () { el.capHeight.value = String(state.capHeight); });
  el.addForm.addEventListener('submit', onAddGlyph);
  el.addFixture.addEventListener('click', onAddFixture);
  el.selWidth.addEventListener('input', onWidthInput);
  el.selWidth.addEventListener('change', function () { syncPanel(); });
  el.pointX.addEventListener('input', function () { onPointCoord('x', el.pointX); });
  el.pointY.addEventListener('input', function () { onPointCoord('y', el.pointY); });
  el.pointX.addEventListener('change', function () { syncPanel(); });
  el.pointY.addEventListener('change', function () { syncPanel(); });
  el.step.addEventListener('change', function () { if (getStep() === null) { el.step.value = '10'; } });
  el.pointSelect.addEventListener('change', function () {
    state.selPoint = Number(el.pointSelect.value);
    syncPanel();
    renderPreview();
  });
  el.left.addEventListener('click', function (e) { movePoint(-1, 0, e.shiftKey); });
  el.right.addEventListener('click', function (e) { movePoint(1, 0, e.shiftKey); });
  el.up.addEventListener('click', function (e) { movePoint(0, 1, e.shiftKey); });
  el.down.addEventListener('click', function (e) { movePoint(0, -1, e.shiftKey); });
  el.canvas.addEventListener('click', onCanvasClick);
  el.canvas.addEventListener('keydown', onCanvasKey);
  el.glyphList.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('button') : null;
    if (!b || state.saving) { return; }
    selectGlyph(Number(b.dataset.index), true);
  });
  el.fontList.addEventListener('click', function (e) {
    var b = e.target.closest ? e.target.closest('button') : null;
    if (b) { loadFont(Number(b.dataset.id)); }
  });
  el.fontRetry.addEventListener('click', function () { clearMessages(); loadFontList(); });

  if (typeof ResizeObserver === 'function') {
    new ResizeObserver(function () { renderPreview(); }).observe(el.canvas);
  } else {
    window.addEventListener('resize', renderPreview);
  }
  window.addEventListener('beforeunload', function (e) {
    if (state.dirty) { e.preventDefault(); e.returnValue = ''; }
  });

  renderAll();
  loadFontList();
})();
