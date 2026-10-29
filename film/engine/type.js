// type.js: cards and quoted counts, set in Old Standard TT (fonts/, SIL OFL 1.1: fonts/OFL.txt). Owner: A.
// A shot draws type with shot.type = (T, tl, F) => { T.text(...); }. The layer goes through the print pass, so
// type is printed like everything else: 'light' lettering is scraped and burnished out of the dark (cards over
// night), 'ink' lettering is printed dark (over daylight or bare paper). Coordinates are frame pixels, 1920x1080.
'use strict';
(function () {
  const T = window.TYPE = {};
  let E, gl, cv, ctx, tex;
  T.FAMILY = 'Old Standard TT';
  T.init = async (engine) => {
    E = engine; gl = E.gl;
    for (const [file, style, weight] of [['OldStandard-Regular.ttf', 'normal', '400'], ['OldStandard-Italic.ttf', 'italic', '400'], ['OldStandard-Bold.ttf', 'normal', '700']]) {
      const f = new FontFace(T.FAMILY, `url(fonts/${file})`, { style, weight });
      document.fonts.add(await f.load());
    }
    cv = document.createElement('canvas'); cv.width = E.W; cv.height = E.H;
    ctx = cv.getContext('2d', { willReadFrequently: false });
    tex = gl.createTexture();
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE); gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    T.ctx = ctx;
  };
  const font = (o) => `${o.italic ? 'italic ' : ''}${o.bold ? '700 ' : '400 '}${o.size || 36}px "${T.FAMILY}"`;
  const colour = (o) => (o.mode === 'ink' ? `rgba(0,255,0,${o.alpha ?? 1})` : `rgba(255,0,0,${o.alpha ?? 1})`);

  // One line. o: { size=36, italic, bold, align='center'|'left'|'right', mode='light'|'ink', alpha=1, tracking=0 (px),
  // caps (small capitals) }. Returns the width in px.
  T.text = (str, x, y, o = {}) => {
    ctx.font = font(o); ctx.textAlign = o.align || 'center'; ctx.textBaseline = 'alphabetic';
    ctx.letterSpacing = (o.tracking || 0) + 'px'; ctx.fontVariantCaps = o.caps ? 'small-caps' : 'normal';
    ctx.fillStyle = colour(o); ctx.fillText(str, x, y);
    return ctx.measureText(str).width;
  };
  // A run of segments on one line, each { text, italic?, bold? }, sharing o (size, mode, alpha, align).
  // For lines set like the printed reports: [{text:'272 killed, viz., '}, {text:'"Larks,"', italic:true}, ...].
  T.run = (segs, x, y, o = {}) => {
    ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic'; ctx.letterSpacing = (o.tracking || 0) + 'px'; ctx.fontVariantCaps = 'normal';
    const widths = segs.map(s => { ctx.font = font(Object.assign({}, o, s)); return ctx.measureText(s.text).width; });
    const total = widths.reduce((a, b) => a + b, 0);
    let cx = o.align === 'left' ? x : o.align === 'right' ? x - total : x - total / 2;
    segs.forEach((s, i) => { ctx.font = font(Object.assign({}, o, s)); ctx.fillStyle = colour(Object.assign({}, o, s)); ctx.fillText(s.text, cx, y); cx += widths[i]; });
    return total;
  };
  // Several lines: lines = [string | {text, size?, italic?, ...} | segments array], o.lead = line spacing (x size).
  T.block = (lines, x, y, o = {}) => {
    let cy = y;
    for (const l of lines) {
      const lo = Object.assign({}, o, typeof l === 'object' && !Array.isArray(l) ? l : {});
      if (Array.isArray(l)) T.run(l, x, cy, lo); else T.text(typeof l === 'string' ? l : l.text, x, cy, lo);
      cy += (lo.size || 36) * (lo.lead || 1.35);
    }
  };
  T.measure = (str, o = {}) => { ctx.font = font(o); ctx.letterSpacing = (o.tracking || 0) + 'px'; return ctx.measureText(str).width; };
  // Tally marks in fives (four strokes and a bar through), n marks from (x, y), mark height h. Drawn as ruled strokes.
  T.tally = (n, x, y, o = {}) => {
    const h = o.h || 28, gap = o.gap || h * 0.22, groupGap = o.groupGap || h * 0.5;
    ctx.strokeStyle = colour(o); ctx.lineWidth = o.width || Math.max(1.5, h * 0.07); ctx.lineCap = 'round';
    let cx = x;
    for (let g = 0; g * 5 < n; g++) {
      const k = Math.min(5, n - g * 5), x0 = cx;
      for (let i = 0; i < Math.min(k, 4); i++) { ctx.beginPath(); ctx.moveTo(cx, y); ctx.lineTo(cx + h * 0.04, y - h); ctx.stroke(); cx += gap; }
      if (k === 5) { ctx.beginPath(); ctx.moveTo(x0 - gap * 0.4, y - h * 0.25); ctx.lineTo(cx - gap * 0.4, y - h * 0.8); ctx.stroke(); }
      cx += groupGap;
    }
  };

  // Called by core each frame: draw the shot's type (if any) and upload; null if the shot has none.
  T.render = (F) => {
    if (!F.shot.type) return null;
    ctx.setTransform(1, 0, 0, 1, 0, 0); ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over'; ctx.fillStyle = '#000'; ctx.fillRect(0, 0, E.W, E.H);
    ctx.globalCompositeOperation = 'lighter';
    F.shot.type(T, F.tl, F);
    ctx.globalCompositeOperation = 'source-over';
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, cv);
    return tex;
  };
})();
