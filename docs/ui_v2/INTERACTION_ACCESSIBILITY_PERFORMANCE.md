# Interaction, accessibility and performance boundary

Single click uses the existing recognizer delay, gives one local acknowledgement, and reveals contextual controls. Chat opens the approved detached shared conversation; close retains draft/turn state. Double click opens Dashboard and suppresses single-click acknowledgement/opening. No Brain request or microphone opening occurs merely by revealing controls. Explicit Voice uses the existing controller. Wake phrase activation is unsupported by the accepted baseline.

Native compact controls are 80px circular icon-and-label targets with 14px labels; the 828x1280 reference-size layout uses approximately 99px circles with larger proportional icons. Labels remain upright through a 180-second orbit. Shared geometry drives rendering and native hit regions. Full-turn circular-clearance tests cover every degree at 440x680 and 360x560. Voice stays below every orbital path and chat below voice. At large text or over four contextual actions, stationary text controls replace the orbit.

The existing Companion clock drives the UI. Orbit geometry updates at most 10Hz; no independent continuous ticker/renderer is introduced. Reduced motion, hidden windows, pointer approach, pressing/focus, open chat and active voice stop travel. Windows polls only the pointer’s position relative to its own window; no global hooks, screenshot or listening permission is added. Pointer departure holds travel for 1.5 seconds. Unsupported pointer reads fail static.

Keyboard controls, visible labels, tooltips, focus and 200% text are tested. The detached transcript scrolls in its remaining space. No floating control approves a task. Pending decisions remain in explicit Review, drafts in the existing document desk, and runtime state is never inferred from text or decorative animation.

Voice bars use the actual RMS level and shared paced waveform driver; silent listening stays quiet. The bar display is not an audio-frequency spectrum. Capture audio levels are fixtures, not microphone recordings. Hidden gallery previews stop and dispose resources; only one model renders at a time.

Native RGBA rendering/96-DPI region inspection are available; desktop compositor behavior, cross-app clicks, hardware DPI/monitors, GPU/VRAM/frame/memory profiling and live backend/voice/auth journeys are NOT VERIFIED. No performance percentage or VRAM claim is made. Future qualification must compare measured behavior against the exact accepted baseline.

Escape closes the detached conversation first, then collapses floating controls. It preserves the shared draft and never cancels a runtime task or speech session. From other modes it retains the existing Companion navigation shortcut.
