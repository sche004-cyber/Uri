import { HEADER, LIB } from '../orb_solar/shaders.js';
import { EXTRA } from './extra.js';
import { SOLAR_E } from './solar.js';
import { SAKURA_A, SAKURA_B, SAKURA_C } from './sakura.js';
import { LUNAR_A, LUNAR_B, LUNAR_C, LUNAR_T, LUNAR_SAKURA } from './lunar.js';

export { HEADER };
export const PRELUDE = LIB + EXTRA;

export const SHADERS = {
  solarE:   { family: 'solar',  title: 'Solar E - Refined',       src: SOLAR_E,     radius: 0.38 },
  sakuraA:  { family: 'sakura', title: 'Sakura A - Blossom Vortex', src: SAKURA_A,  radius: 0.30 },
  sakuraB:  { family: 'sakura', title: 'Sakura B - Wind Current',   src: SAKURA_B,  radius: 0.30 },
  sakuraC:  { family: 'sakura', title: 'Sakura C - Blossom Heart',  src: SAKURA_C,  radius: 0.26 },
  lunarA:   { family: 'lunar',  title: 'Lunar A - Cloud Veil',      src: LUNAR_A,   radius: 0.34 },
  lunarB:   { family: 'lunar',  title: 'Lunar B - Night Window',    src: LUNAR_B,   radius: 0.32 },
  lunarC:   { family: 'lunar',  title: 'Lunar C - Moon Current',    src: LUNAR_C,   radius: 0.33 },
  lunarT:   { family: 'lunar',  title: 'Lunar T - baked albedo',   src: LUNAR_T,   radius: 0.33, tex: 'moon_albedo.png' },
  hybridH:  { family: 'lunar',  title: 'H - Moonlit Blossom',       src: LUNAR_SAKURA, radius: 0.32 },
};

// The nine states of URI's existing `CompanionState` contract
// (lib/living/companion/companion_state.dart). The companion is an expression
// of an authoritative fact, so the shader has to cover every state the rest of
// the app can already report - not only the five in the visual brief.
export const STATE_NAMES = [
  'unavailable', 'idle', 'listening', 'thinking', 'speaking',
  'working', 'awaitingApproval', 'success', 'error',
];

const S = (energy, turb, flare, ember, focus, exposure) =>
  ({ energy, turb, flare, ember, focus, exposure });

export const STATE_TABLES = {
  // Solar: energy drives flame and brightness, flare drives the prominences,
  // ember the drifting field, focus the coherence of the arcs.
  solar: {
    unavailable:      S(0.06, 0.05, 0.00, 0.05, 0.95, 0.72),
    idle:             S(0.22, 0.16, 0.10, 0.28, 0.85, 1.00),
    listening:        S(0.36, 0.14, 0.14, 0.44, 0.95, 1.08),
    thinking:         S(0.62, 0.48, 0.30, 0.52, 0.70, 1.06),
    speaking:         S(0.74, 0.34, 0.62, 0.60, 0.88, 1.10),
    working:          S(1.00, 0.74, 0.92, 1.00, 0.55, 1.16),
    awaitingApproval: S(0.44, 0.10, 0.20, 0.34, 1.00, 1.04),
    success:          S(0.86, 0.22, 1.00, 0.86, 0.98, 1.22),
    error:            S(0.58, 0.95, 0.44, 0.42, 0.22, 0.92),
  },
  // Sakura: flare is the energy ribbons, ember the petal and pollen count,
  // focus how tightly the petals hold their arms.
  sakura: {
    unavailable:      S(0.06, 0.05, 0.00, 0.06, 0.95, 0.74),
    idle:             S(0.24, 0.18, 0.10, 0.34, 0.80, 1.00),
    listening:        S(0.38, 0.12, 0.16, 0.46, 0.96, 1.06),
    thinking:         S(0.60, 0.42, 0.34, 0.62, 0.72, 1.05),
    speaking:         S(0.72, 0.28, 0.58, 0.58, 0.90, 1.08),
    working:          S(0.95, 0.66, 0.86, 1.00, 0.58, 1.14),
    awaitingApproval: S(0.44, 0.10, 0.22, 0.38, 1.00, 1.03),
    success:          S(0.88, 0.20, 1.00, 0.95, 0.96, 1.20),
    error:            S(0.55, 0.92, 0.40, 0.40, 0.20, 0.90),
  },
  // Lunar: focus is how far the clouds part, flare the shafts and halo,
  // ember the stars and mist. Low focus obscures the moon.
  lunar: {
    unavailable:      S(0.05, 0.10, 0.00, 0.06, 0.30, 0.70),
    idle:             S(0.22, 0.24, 0.12, 0.30, 0.55, 1.00),
    listening:        S(0.32, 0.16, 0.18, 0.34, 0.88, 1.05),
    thinking:         S(0.55, 0.52, 0.26, 0.42, 0.45, 1.02),
    speaking:         S(0.62, 0.26, 0.60, 0.40, 0.70, 1.08),
    working:          S(0.92, 0.70, 0.80, 0.60, 0.40, 1.12),
    awaitingApproval: S(0.40, 0.14, 0.22, 0.32, 0.92, 1.04),
    success:          S(0.72, 0.12, 0.75, 0.45, 1.00, 1.16),
    error:            S(0.50, 0.88, 0.30, 0.30, 0.12, 0.88),
  },
};
