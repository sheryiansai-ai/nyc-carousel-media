# Install test, 12 Nov 2026 (collection format) — item layout fixed in the evening calendar run
- `big-tech-student-programs-slide-01..08.png`: the full 13 Nov deck rendered by `render-collection.js` (1080x1350).
  - Cover rendered as style **G** (notice board, Figma gpt-image-2.5-flare scene, flyer areas found by `scripts/blanks.py`), because the student cut-out for style C is not in the cloud yet. The real 13 Nov post plans style C with student-3.
  - Item slides now follow the owner-approved layout: page counter as plain small mono text top-right (no pill); company logo 40px on its own line above the name; name 42px Helvetica 500, left, one line (36px if long); screenshot card full width (428 of 480 css px) down to the fact; fact bottom-left, 20px Helvetica 500, after a 30px lime (#d0df83) circle with a dark check. Everything left-aligned.
  - The cards show a dashed "Screenshot not captured" placeholder: the Mac had not yet made `shot-N.jpg` for 13 Nov on codex-images (plans got screenshot entries at 18:10 IST). Rendered with `--allow-missing-shots`; the daily run never uses that flag and never posts a placeholder.
- `sheet.png` (contact sheet) and `sheet-375.png` (phone check, every slide at 375px wide).
- `layout-check-item-tall-screenshot-cropped.png`: layout check with a grey dummy 1440x7200 image (not a real page) and `shotCropTop` 60, showing how a tall Mac screenshot is cropped into the card.
- `layout-check-item-logo-fallback.png`: what an item slide looks like when its screenshot is missing (company logo large in the card; max 2 per deck).
- `layout-check-cover-C-no-student.png`: cover C layout (16 Nov field and logos) without the cut-out, layout check only.
- `layout-check-last-slide-dm-true.png`: last slide with dm_automation = true.
No student photos are in this folder.
