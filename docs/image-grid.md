# Patient image grid

In `/patient/<id>/exams`, select original images from one or several visits. **Tools** appears at the bottom right. **So sánh** opens the existing comparison workspace (up to eight originals). **Tạo lưới ảnh** opens a separate grid editor (up to 36 originals).

1. Set rows and columns (1–6 each), cell aspect ratio, spacing, and background. A layout must have enough cells for every selected image. Empty cells can be used for space or text. Shrinking compacts images only when needed to preserve them.
2. Click an image or use **Chọn ô**. Select whole-image fit or fill, adjust **Phóng ảnh**, and drag the image within its clipped cell. **Đặt lại ảnh** resets zoom and centering. **Phóng bản xem** changes only the preview size.
3. Select another cell and click **Đổi chỗ**. Images retain their individual framing, including when swapped with an empty cell.
4. Enter text and click **Thêm chữ**, then drag it into position. Click text or select it under **Chú thích** to edit its content, size, and color, or delete it. Select **Chữ mới** to prepare another label. Up to 20 labels of 500 characters are supported.
5. Click **Tải PNG**. Square cells export at 400 × 400 pixels; landscape cells at 400 × 300; portrait at 300 × 400. Preview scaling and the blue cell selection border are excluded from export. Download the composition before closing; an edited draft is discarded after confirmation.

The editor reuses the authenticated patient comparison catalog and same-origin upload URLs. It composes the grid entirely in the browser using a pinned local Konva 10.7.0 bundle, with no CDN or external processing. Sources are decoded sequentially and retained at at most 1600 pixels on the longest side to bound memory. No database migration, image overwrite, automatic attachment, draft persistence, or server upload is involved. Text is rendered on the canvas as text, never HTML.

Geometry regressions: `node tests/image_grid_core.test.cjs`. Controller regressions: `node tests/image_grid_ui.test.cjs` (DOM/canvas adapters; not rendered browser QA). Existing comparison regressions: `node tests/comparison_core.test.cjs`, `node tests/comparison_ui.test.cjs`, and `python -m pytest tests/test_comparisons.py` (isolated in-memory data and temporary uploads).

Browser acceptance: check Tools visibility after selecting/clearing; open both submenus; create a grid from different visits; test fit/fill, zoom/pan, empty-cell swapping, rejected undersized layouts, Vietnamese multiline text, preview resize, PNG dimensions/absence of selection border, close cancellation, missing sources, and narrow screens. Use synthetic images for validation.

Validation on 2026-10-02: geometry/controller regressions, existing comparison JavaScript regressions, and all 20 isolated Python comparison tests passed. Rendered browser QA remains pending because the browser connection failed during startup.
