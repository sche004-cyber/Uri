const { HEADER, PRELUDE, SHADERS, STATE_TABLES, STATE_NAMES } =
  await import(`./registry.js?v=${Date.now()}`);

const VERT = `#version 300 es
precision highp float;
void main() {
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

const UNIFORMS = [
  'uSize', 'uTime', 'uEnergy', 'uTurb', 'uFlare',
  'uEmber', 'uFocus', 'uRadius', 'uExposure', 'uTex',
];

// A shader that declares `uTex` gets the baked map named by its registry entry
// uploaded on unit 0. Only the lunar texture variant uses this.
const TEX_HEADER = 'uniform sampler2D uTex;' + String.fromCharCode(10);

function loadTexture(gl, url) {
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  // 1x1 placeholder so the first frames before the image arrives are valid.
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, 1, 1, 0, gl.RED, gl.UNSIGNED_BYTE,
                new Uint8Array([200]));
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.REPEAT);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR_MIPMAP_LINEAR);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
  const img = new Image();
  img.onload = () => {
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.R8, img.width, img.height, 0,
                  gl.RED, gl.UNSIGNED_BYTE, img);
    gl.generateMipmap(gl.TEXTURE_2D);
  };
  img.src = url;
  return tex;
}

function compile(gl, type, src, label) {
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(sh);
    // Report the offending line, not just the driver message: these shaders
    // are assembled from several files and the raw line number is useless.
    const m = /0:(\d+)/.exec(log || '');
    let ctx = '';
    if (m) {
      const lines = src.split('\n');
      const n = parseInt(m[1], 10);
      ctx = lines.slice(Math.max(0, n - 3), n + 2)
        .map((l, i) => `${n - 2 + i}| ${l}`).join('\n');
    }
    throw new Error(`${label}: ${log}\n${ctx}`);
  }
  return sh;
}

class View {
  constructor(canvas, key) {
    this.canvas = canvas;
    this.key = key;
    this.def = SHADERS[key];
    this.radius = this.def.radius;
    this.ok = false;
    this.frames = 0;
    this._fpsT = 0;

    const gl = canvas.getContext('webgl2', {
      antialias: false,
      preserveDrawingBuffer: true,
      powerPreference: 'high-performance',
    });
    if (!gl) { this.error = 'WebGL2 unavailable'; return; }
    this.gl = gl;
    const frag = this.def.tex
      ? HEADER + TEX_HEADER + PRELUDE + this.def.src
      : HEADER + PRELUDE + this.def.src;
    this.fragSource = frag;
    try {
      const vs = compile(gl, gl.VERTEX_SHADER, VERT, `${key}:vert`);
      const fs = compile(gl, gl.FRAGMENT_SHADER, frag, `${key}:frag`);
      const prog = gl.createProgram();
      gl.attachShader(prog, vs);
      gl.attachShader(prog, fs);
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
        throw new Error(gl.getProgramInfoLog(prog));
      }
      this.prog = prog;
      this.loc = {};
      for (const u of UNIFORMS) this.loc[u] = gl.getUniformLocation(prog, u);
      this.vao = gl.createVertexArray();
      if (this.def.tex) this.tex = loadTexture(gl, this.def.tex);
      this.ok = true;
    } catch (e) {
      this.error = String(e.message || e);
    }
  }

  resize(dpr) {
    const c = this.canvas;
    const w = Math.max(1, Math.round(c.clientWidth * dpr));
    const h = Math.max(1, Math.round(c.clientHeight * dpr));
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; }
  }

  draw(time, s) {
    if (!this.ok) return;
    const gl = this.gl;
    gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    gl.useProgram(this.prog);
    gl.bindVertexArray(this.vao);
    gl.uniform2f(this.loc.uSize, this.canvas.width, this.canvas.height);
    gl.uniform1f(this.loc.uTime, time);
    gl.uniform1f(this.loc.uEnergy, s.energy);
    gl.uniform1f(this.loc.uTurb, s.turb);
    gl.uniform1f(this.loc.uFlare, s.flare);
    gl.uniform1f(this.loc.uEmber, s.ember);
    gl.uniform1f(this.loc.uFocus, s.focus);
    gl.uniform1f(this.loc.uRadius, this.radius);
    gl.uniform1f(this.loc.uExposure, s.exposure);
    if (this.tex) {
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.tex);
      gl.uniform1i(this.loc.uTex, 0);
    }
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.frames++;
  }
}

// --- per-family state interpolation ----------------------------------------
const KEYS = ['energy', 'turb', 'flare', 'ember', 'focus', 'exposure'];
let stateName = 'idle';
const cur = {};
for (const fam of Object.keys(STATE_TABLES)) cur[fam] = { ...STATE_TABLES[fam].idle };

function stepState(dt) {
  const k = 1 - Math.exp(-dt * 2.4);
  for (const fam of Object.keys(STATE_TABLES)) {
    const tgt = STATE_TABLES[fam][stateName];
    for (const key of KEYS) cur[fam][key] += (tgt[key] - cur[fam][key]) * k;
  }
}

// --- bootstrap -------------------------------------------------------------
const views = [];
const diag = document.getElementById('diag');
const diagLines = [];
const log = (l) => { diagLines.push(l); if (diag) diag.textContent = diagLines.join('\n'); };

let paused = false, timeScale = 1, simTime = 0;

function init() {
  const grid = document.getElementById('grid');
  for (const [key, def] of Object.entries(SHADERS)) {
    const cell = document.createElement('div');
    cell.className = 'cell';
    cell.dataset.key = key;
    cell.innerHTML =
      `<div class="head"><span class="t">${def.title}</span>` +
      `<span class="badge" data-badge="${key}">ok</span></div>` +
      `<canvas data-key="${key}"></canvas>`;
    grid.appendChild(cell);
  }
  for (const el of document.querySelectorAll('canvas[data-key]')) {
    const v = new View(el, el.dataset.key);
    views.push(v);
    const badge = document.querySelector(`[data-badge="${v.key}"]`);
    if (!v.ok) {
      if (badge) { badge.textContent = 'SHADER ERROR'; badge.className = 'badge bad'; }
      log(`[${v.key}] ${v.error}`);
    } else {
      log(`[${v.key}] compiled ok`);
    }
  }
  window.__views = views;
  window.__ready = views.length > 0 && views.every(v => v.ok);
  log(`ready=${window.__ready} views=${views.length}`);
}

let last = performance.now();
function frame(now) {
  const dt = Math.min((now - last) / 1000, 0.05);
  last = now;
  if (!paused) simTime += dt * timeScale;
  stepState(dt);
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  for (const v of views) { v.resize(dpr); v.draw(simTime, cur[v.def.family]); }
  const v0 = views[0];
  if (v0) {
    v0._fpsT += dt;
    if (v0._fpsT > 0.5) {
      const f = document.getElementById('fps');
      if (f) f.textContent = `${Math.round(v0.frames / v0._fpsT)} fps`;
      v0.frames = 0; v0._fpsT = 0;
    }
  }
  requestAnimationFrame(frame);
}

function wire() {
  const bar = document.getElementById('states');
  for (const n of STATE_NAMES) {
    const b = document.createElement('button');
    b.textContent = n;
    b.dataset.state = n;
    if (n === 'idle') b.classList.add('on');
    b.addEventListener('click', () => {
      document.querySelectorAll('[data-state]').forEach(x => x.classList.remove('on'));
      b.classList.add('on');
      stateName = n;
    });
    bar.appendChild(b);
  }
  const p = document.getElementById('pause');
  p.addEventListener('click', () => {
    paused = !paused;
    p.textContent = paused ? 'play' : 'pause';
    p.classList.toggle('on', paused);
  });
  const ts = document.getElementById('speed');
  ts.addEventListener('input', () => {
    timeScale = parseFloat(ts.value);
    document.getElementById('speedVal').textContent = timeScale.toFixed(2) + 'x';
  });
}

// Deterministic capture, independent of layout and of the pane being visible:
// requestAnimationFrame is suspended while the Browser pane is hidden, so the
// normal draw loop cannot produce evidence frames.
window.__capture = (key, state, t, w, h) => {
  const v = views.find(x => x.key === key);
  if (!v || !v.ok) return null;
  const s = STATE_TABLES[v.def.family][state];
  if (!s) return null;
  v.canvas.width = w; v.canvas.height = h;
  v.draw(t, s);
  return v.canvas.toDataURL('image/png');
};
window.__solo = (key) => { document.body.dataset.solo = key || ''; };
window.__errors = () => views.filter(v => !v.ok).map(v => ({ key: v.key, error: v.error }));

init();
wire();
requestAnimationFrame(frame);
