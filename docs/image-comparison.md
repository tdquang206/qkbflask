# Patient image comparison and mMASI

## Workflow

The desktop workspace has three left-hand tabs: **Chỉnh ảnh** (default), **Chấm điểm**, and **Lưu vào lịch sử**. Switching tabs preserves draft values. Grading keeps photographs alongside the form; the scoring baseline is only shown in that tab and does not affect lighting. The tab badge shows incomplete/confirmed grading status. Mobile uses a compact tab row for quick viewing.

Photographs initially fit the entire frame, centered with their aspect ratio preserved. Each photograph keeps its own fit, zoom, brightness, contrast, patch, and crop controls below it. **Vừa khung** restores fitted zoom/pan without clearing the crop or lighting adjustments. Reset clears adjustments and restores fitted zoom.

Reference patches remain visible as overlays after selection, including after zoom, crop, and reopening. A separate checkbox hides those overlays; they are not burned into exported images. **Gợi ý vùng** offers up to three numbered low-texture/moderate-brightness candidate patches, excluding heavily clipped candidates. Selection requires a click or manual drawing. These heuristics do not identify healthy skin or establish correspondence between images: the clinician must choose matching physical reference areas. If a saved patch lies outside the current crop, the caption says so.

The red **Đóng** button opens a choice of **Lưu và đóng**, **Bỏ thay đổi và đóng**, or **Tiếp tục chỉnh**. Saving uses the destination/output options in the save tab. If appending a note still needs preview, the save tab opens for review first. A failed save keeps the draft and popup open. Escape/backdrop dismissal uses the same close flow; closing a browser tab still uses its native unsaved-change warning.

1. In patient exam history, select up to eight original photographs and click **So sánh**. Paper assessments and ordinary attachments remain usable in the existing image viewer.
2. Choose a lighting reference image and a baseline visit independently. Zoom and drag to pan. Select a crop on the full original if the views need to cover the same area.
3. For **Gợi ý cân sáng**, draw a corresponding reference patch on every image, preferably a neutral reference area rather than the lesion. The suggestion matches patch luminance mean and contrast, with conservative limits. It does not infer skin regions or establish true color calibration. Manual brightness/contrast controls and the original toggle remain available.
4. Enable **Chấm điểm** to enter mMASI observations once per visit, using all supporting photographs from that visit. Select whether the assessment uses original or adjusted images. Complete every facial region and explicitly confirm the assessment. Missing observations do not become zero. Changes to image adjustments clear confirmation.
5. Select the destination exam. The comparison settings and grading data are always saved. Optionally save adjusted JPEG copies, a labelled comparison sheet, and append a summary to the exam note. Review the summary before appending. Each save creates a new comparison version.
6. Reopen from **So sánh đã lưu**. **Tải ZIP** downloads the record, source images, and saved derivatives together. Deleting a comparison record retains attachments and any note previously appended.

## Grading

The initial method is mMASI, version 1. The clinician supplies area (0–6) and darkness (0–4) for forehead, patient right malar, patient left malar, and chin. Weights are 0.3, 0.3, 0.3, and 0.1. The total is the weighted sum of area × darkness, ranging from 0 to 24. There is no homogeneity component and no automatic diagnosis or image-based clinical score.

The browser shows provisional arithmetic. The server validates inputs and independently calculates the stored result. Blank inputs produce a null score and incomplete status. Complete inputs without confirmation remain incomplete. Differences from baseline are shown only for completed assessments using the same method/view; negative differences mean lower scores. No clinical severity thresholds or treatment recommendations are inferred.

Method references: [mMASI validation](https://pubmed.ncbi.nlm.nih.gov/20398960/) and [mMASI calculation and interpretation](https://jamanetwork.com/journals/jamadermatology/fullarticle/2519450). Lighting/angle limitations are supported by [this camera distance and angle study](https://pubmed.ncbi.nlm.nih.gov/36772956/).

To add a method, register a versioned definition and server calculator in `utils/grading.py`, plus its browser calculator in `static/comparison_core.js`. The current form renderer consumes the method's region/field definitions. A method with a different form structure can supply a dedicated renderer in `static/comparison.js`. Add scoring and incomplete-input tests; do not change the meaning of an existing version. POSAS is not implemented.

## Persistence and files

- `patients[].exams[].comparisons[]` contains the versioned record, source image IDs, owning exam IDs, reference/baseline/destination choices, normalized crop/reference-patch rectangles, brightness/contrast settings, assessments, optional comment, generated summary, author, timestamp, and derivative image IDs.
- Existing records require no startup migration. Legacy image IDs are deterministic on read and persisted on comparison save or patient asset rename. New uploads receive IDs and unique filenames, preventing same-day uploads from overwriting prior sources.
- Adjusted files are new JPEGs in `uploads/comparisons/<patient UUID>/`, named `<original stem>_edited_01.jpg`, `_edited_02.jpg`, etc. Exclusive file creation prevents collisions. The input always comes from an original attachment; adjusted copies cannot be used as new editing sources.
- Original bytes remain unchanged. Individual edited copies have no burned-in clinical text. Comparison sheets are labelled with dates, adjusted-image status, and grading status/view.
- Derivative image metadata includes source/reference IDs, the source filename at save time, transform version/settings, author, timestamp, and comparison ID. Files keep their saved names when the patient's phone changes; references continue using stable IDs. Copies are grouped next to their original when attached to the same visit, otherwise labelled with the source filename in the destination visit.
- Ordinary exam edits preserve extra comparison fields. Source or derivative attachments referenced by saved comparisons cannot be deleted until those records are removed. An original used by an edited copy remains protected until that copy is removed. A missing file caused by external filesystem changes prevents reopening that source; ZIP manifests report missing files.
- Saves reject stale exam-history revisions and remove newly generated files on a failed write. TinyDB has no general multi-process transaction mechanism; use the app's normal single-process desktop deployment.

## Backup and security

Comparison metadata uses the existing encrypted TinyDB database. Image attachments use the existing on-disk upload storage; image files themselves are not AES-encrypted by TinyDB. The current weekly database backup does **not** include uploads. Back up the uploads directory together with the database. A comparison ZIP is a portable export containing images and readable metadata; it is not an automatic database-restore format.

All comparison endpoints require login; writes use CSRF. The server accepts owned image IDs and bounded adjustment/scoring parameters rather than client-provided source URLs or filesystem paths. It resolves source files under uploads and generates copies with Pillow. No external image-processing service is called.

Browser previews use at most 1000 pixels on the longest side. Full-resolution derivatives are generated only on save; at most eight images and 25 megapixels per source are allowed. Contrast is a channel-wise linear transform about 128, followed by brightness offset and clamping; browser and server share the same rounding convention. This cannot recover clipped highlights, remove directional shadows, or compensate for different camera angles. Cropping and downsampling may have slight edge rounding differences between preview and export.

## Verification

Automated tests cover score endpoints and missing observations, CSRF/authentication, patient ownership, untouched originals, revision conflicts, repeat saves, rollback, ZIP contents, note preservation, image transforms, source-ID stability across phone renames, and existing exam edit/deletion interactions. JavaScript helper tests run with `node tests/comparison_core.test.cjs`. `node tests/comparison_ui.test.cjs` exercises the real UI controller with a DOM adapter, including tab preservation, fitted opening, persistent patches/suggestions, close choices, failed saves, and note-preview requirements. This does not replace rendered browser QA.

Manual browser acceptance still needs a connected browser: select photographs from different visits, draw reference patches/crops, adjust and reset, zoom/pan, complete mMASI, switch original/adjusted view, inspect the note preview, save all output options, reopen, and check narrow-screen layout. Use copies of clinical data for this check.
