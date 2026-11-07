# Round-1 deck source

`build.js` builds `TouristGuide_NIT_Jamshedpur.pptx` (intro + 7 scored slides + annexure A1–A4) with pptxgenjs.

    NODE_PATH=<folder with pptxgenjs and jszip> node build.js out.pptx
    VIDEO_URL=https://... node build.js out.pptx   # puts the demo video link on the cover

- `img/e_*.png`: English app screens from the live build (slide 3), shot by `shoot_en.js` / `shoot_en2.js`; `img/f_*.png` are the older Hindi/WhatsApp frames.
- `build_whatsapp_screens.js`: the earlier version of the deck with WhatsApp screens.
- `shoot2.js`, `shoot4.js`, `console.js`, `console2.js`: Playwright scripts that took those screenshots from a local server.
- `arch.html`: the architecture diagram (annexure A1), rendered to `img/arch.png`.
- `img/bg_*.jpg`: backgrounds from the Sync submission template.
- `build.js` calls `applyTheme` from the pptx skill to write the theme colours; drop that call if it isn't available.
