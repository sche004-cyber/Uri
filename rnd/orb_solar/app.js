const { HEADER, LIB, PROTOS, STATES } =
  await import(`./shaders.js?v=${Date.now()}`);

const VERT = `#version 300 es
precision highp float;
void main() {
  // Fullscreen triangle, no vertex buffer needed.
  vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
  gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}`;

const UNIFORMS = [
  'uSize', 'uTime', 'uEnergy', 'uTurb', 'uFlare',
  'uEmber', 'uFocus', 'uRadius', 'uExposure',
];

function compile(gl, type, src, label) {
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(sh);
    console.error(`[${label}] compile failed\n${log}`);
    throw new Error(`${label}: ${log}`);
  }
  return sh;
}

class OrbView {
  constructor(canvas, protoKey, opts = {}) {
    this.canvas = canvas;
    this.key = protoKey;
    this.radius = opts.radius ?? 0.40;
    this.ok = false;
    this.frames = 0;
    this.fps = 0;
    this._fpsT = 0;

    const gl = canvas.getContext('webgl2', {
      antialias: false,
      preserveDrawingBuffer: true, // so screenshots capture the live frame
      powerPreference: 'high-performance',
    });
    if (!gl) { this.error = 'WebGL2 unavailable'; return; }
    this.gl = gl;

    const frag = HEADER + LIB + PROTOS[protoKey].src;
    this.fragSource = frag;
    try {
      const vs = compile(gl, gl.VERTEX_SHADER, VERT, `${protoKey}:vert`);
      const fs = compile(gl, gl.FRAGMENT_SHADER, frag, `${protoKey}:frag`);
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
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    this.frames++;
  }
}

// --- state interpolation ---------------------------------------------------
const cur = { ...STATES.idle };
let target = { ...STATES.idle };
const KEYS = Object.keys(STATES.idle);

function stepState(dt) {
  // Critically-damped-ish approach; states should feel like a living thing
  // changing posture, not a value snapping.
  const k = 1 - Math.exp(-dt * 2.4);
  for (const key of KEYS) cur[key] += (target[key] - cur[key]) * k;
}

// --- bootstrap -------------------------------------------------------------
const views = [];
const diag = document.getElementById('diag');
const diagLines = [];

function log(line) {
  diagLines.push(line);
  if (diag) diag.textContent = diagLines.join('\n');
}

const dprCap = 2;
let paused = false;
let timeScale = 1;
let simTime = 0;

function init() {
  for (const el of document.querySelectorAll('canvas[data-proto]')) {
    const v = new OrbView(el, el.dataset.proto, {
      radius: parseFloat(el.dataset.radius || '0.40'),
    });
    views.push(v);
    const badge = document.querySelector(`[data-badge="${el.dataset.proto}"]`);
    if (!v.ok) {
      if (badge) { badge.textContent = 'SHADER ERROR'; badge.className = 'badge bad'; }
      log(`[${el.dataset.proto}] ${v.error}`);
    } else {
      log(`[${el.dataset.proto}] compiled ok`);
    }
  }
  window.__orbViews = views;
  window.__orbReady = views.length > 0 && views.every(v => v.ok);
  log(`ready=${window.__orbReady} views=${views.length}`);
}

let last = performance.now();
function frame(now) {
  const dtReal = Math.min((now - last) / 1000, 0.05);
  last = now;
  if (!paused) simTime += dtReal * timeScale;
  stepState(dtReal);

  const dpr = Math.min(window.devicePixelRatio || 1, dprCap);
  for (const v of views) { v.resize(dpr); v.draw(simTime, cur); }

  // fps readout, averaged over 500ms
  const v0 = views[0];
  if (v0) {
    v0._fpsT += dtReal;
    if (v0._fpsT > 0.5) {
      const f = document.getElementById('fps');
      if (f) f.textContent = `${Math.round(v0.frames / v0._fpsT)} fps`;
      v0.frames = 0; v0._fpsT = 0;
    }
  }
  requestAnimationFrame(frame);
}

// --- controls --------------------------------------------------------------
function wire() {
  document.querySelectorAll('[data-state]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-state]').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      target = { ...STATES[btn.dataset.state] };
      window.__orbState = btn.dataset.state;
    });
  });
  const p = document.getElementById('pause');
  if (p) p.addEventListener('click', () => {
    paused = !paused;
    p.textContent = paused ? 'play' : 'pause';
    p.classList.toggle('on', paused);
  });
  const ts = document.getElementById('speed');
  if (ts) ts.addEventListener('input', () => {
    timeScale = parseFloat(ts.value);
    document.getElementById('speedVal').textContent = timeScale.toFixed(2) + 'x';
  });
}

// Test hooks so a headless/driven browser can set an exact state + time
// and capture a deterministic frame for evidence.
window.__orbSet = (stateName, t) => {
  if (STATES[stateName]) {
    target = { ...STATES[stateName] };
    Object.assign(cur, STATES[stateName]);
  }
  if (typeof t === 'number') { simTime = t; paused = true; }
  return { state: stateName, time: simTime };
};
window.__orbSolo = (key) => {
  document.body.dataset.solo = key || '';
};

// Deterministic capture that does not depend on layout or on the page being
// visible: requestAnimationFrame is suspended while the pane is hidden, so the
// normal draw loop cannot be used to produce evidence frames.
window.__orbCapture = (key, stateName, t, w, h) => {
  const v = views.find(x => x.key === key);
  if (!v || !v.ok) return null;
  const s = STATES[stateName];
  if (!s) return null;
  v.canvas.width = w;
  v.canvas.height = h;
  v.draw(t, s);
  return v.canvas.toDataURL('image/png');
};

init();
wire();
requestAnimationFrame(frame);
