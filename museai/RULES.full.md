PROMPT REDESIGN THEO TỪNG LOẠI SẢN PHẨM TRÊN TOOL
====================================================
(Tổng hợp từ code — services/*.ts, components/*.tsx. Các đoạn ${...} là biến động, được ghép vào lúc chạy.)


====================================================
1. POD / ORNAMENT (Suncatcher, Ornament, Doormat, Clipboard, Wooden Sign, ...)
====================================================

--- 1.1 Redesign chính (6 biến thể / lượt, file services/geminiPodService.ts) ---

Khung prompt gốc:

HIGH-END ETSY ${productType.toUpperCase()} — a refined ORIGINAL VARIATION in the SAME art style as the reference.
STYLE LOCK (match the REFERENCE image EXACTLY — top priority):
- Keep the SAME art style, rendering technique, line-work & leading thickness, level of delicacy, and SAME color palette/mood as the reference.
- Do NOT switch to a different art style (e.g. do NOT turn a soft pastel watercolor stained-glass into a bold heavy-leaded Tiffany style).
CONTENT CHANGE (moderate, to stay original & avoid copyright/report on Etsy):
- Rearrange the composition and vary the specific flowers/elements.
- REPHRASE any quote into FRESH wording (never verbatim) and use a DIFFERENT font.
- Keep ONLY personalization placeholders (name/year).
${variation}
${keepNote}
ADJUSTMENTS (user): ${userNotes hoặc "none — keep the original style, just refine"}.
${materialNote}
${guideNote}
OUTPUT: single centered product design, 8k high-fidelity, clean edges, NO white die-cut border, 100% PURE WHITE (#FFFFFF) background. ${ropeNote}

6 biến thể (${variation}) luân phiên mỗi lượt generate:
1. Rearrange the bouquet/elements into a fresh composition; vary the specific flowers slightly. SAME art style & palette.
2. Different floral arrangement and a slightly varied border motif. KEEP identical line-work & rendering.
3. Alternate composition with a different focal flower; subtly shift emphasis within the SAME palette family.
4. Mirror/rebalance the layout; swap a couple of flower types. SAME delicacy & leading thickness.
5. Fuller, more abundant arrangement of the same-style flowers; SAME palette and technique.
6. Slightly airier/minimal arrangement; SAME exact rendering style, leading and color mood.

Các mảnh ghép khác:
- ropeNote  = "Hanging hardware: ${ropeType}."  (nếu có chọn dây treo)
- materialNote = "MATERIAL REALISM (${productType}): ${material}"  (lấy từ PRODUCT_MATERIALS trong types.ts)
- guideNote = "ETSY DESIGN GUIDE: ${guide}"  (lấy từ getDesignGuide() trong services/productKnowledge.ts)
- keepNote  = "Keep these ELEMENT TYPES but REDRAW them originally (different shapes/arrangement): ${selectedComponents}."

(${basePrompt} chính là redesignPrompt do AI phân tích ảnh gốc sinh ra — xem mục 6 bên dưới.)


--- 1.2 Mockup sản phẩm (Apparel — áo/jersey mặc lên mockup) ---

Create a PHOTOREALISTIC ETSY PRODUCT MOCKUP of this exact design printed on a real ${productType}.
Use the REFERENCE IMAGE as the printed artwork on the garment — keep the artwork IDENTICAL, do not redraw or alter the design.
Scene: the finished garment professionally ${scene}.
Style: premium apparel e-commerce photography, sharp focus on the print detail, magazine quality, SQUARE 1:1 framing, product centered.

6 scene cho Apparel (áo thun/jersey):
1. flat-lay on a rustic wooden table, soft natural window light, fabric with realistic natural folds/wrinkles
2. hanging neatly on a wooden clothing hanger against a plain light-gray studio wall
3. worn by a faceless/cropped model (neck-to-waist framing) standing outdoors in natural daylight
4. folded neatly in a stack on a white shelf, boutique retail styling
5. close-up hero shot on a clean neutral background showing fabric texture and print detail sharply
6. worn by a faceless model in an outdoor stadium/sports setting matching the jersey's theme


--- 1.3 Mockup sản phẩm (Ornament/Suncatcher/vật treo, không phải quần áo) ---

Create a PHOTOREALISTIC ETSY PRODUCT MOCKUP of this exact design as a real ${productType}.
Use the REFERENCE IMAGE as the printed artwork — keep it IDENTICAL, do not redraw or alter the design.
Material: ${material}${edgeClause nếu là chất liệu acrylic/trong suốt}
Scene: the finished product professionally ${scene};${hangingClause nếu sản phẩm dạng treo}
Style: premium lifestyle e-commerce photography, sharp focus on the product, magazine quality, SQUARE 1:1 framing, product centered.

6 scene mặc định (Ornament/Suncatcher):
1. hung in a bright sunlit window, daylight passing through it, cozy living room softly blurred (bokeh), colored light cast on the sill
2. hung in a cozy bedroom window with sheer white curtains, soft morning light, warm calm mood
3. hung in a kitchen window surrounded by potted green plants, fresh bright natural light
4. a close-up hero product shot on a clean neutral light-gray background, soft studio lighting showing material detail
5. hanging on a rustic wall hook next to a window, warm farmhouse interior, gentle side light
6. hung on a glass door/porch with a green garden visible outside, airy outdoor daylight

6 scene riêng cho "Clipboard":
1. held flat in one hand at a slight angle, soft bright indoor light catching the clear acrylic edge with a visible glossy highlight
2. propped upright on a wooden desk beside a small potted plant and pen cup
3. (+ 4 scene khác cùng bối cảnh bàn làm việc — xem services/geminiPodService.ts dòng 129-136)

6 scene riêng cho "Rubber-Backed Doormat":
1. laid flat on a front porch step, front door and welcome mat area visible, natural daylight, viewed from above at a slight angle
2. (+ 5 scene khác cùng bối cảnh cửa trước nhà — xem services/geminiPodService.ts dòng 137-144)

edgeClause (chỉ thêm khi chất liệu là acrylic/trong suốt):
"Render a clearly visible glossy, light-catching transparent edge/rim along the material's physical border, even where the printed design is dense — this visible edge is essential to show it is genuine clear acrylic, not opaque plastic."

hangingClause (chỉ thêm khi sản phẩm dạng treo):
"realistic hanging cord/chain and metal loop;"


--- 1.4 Tách thành phần thiết kế (Split Characters) ---
Isolate main subject on pure white. Maintain colors and organic handcrafted textures.


--- 1.5 Remix / chỉnh sửa theo yêu cầu (khung bọc chung) ---
Edit the reference image: ${instruction}. Keep the SAME art style, layout, colors and everything else unchanged — only apply the requested edit. Pure white background.

(${instruction} là câu lệnh cụ thể lấy từ UI, xem mục 5 bên dưới.)



====================================================
2. MIRROR/FLIP POD DESIGN ("POD New" — tab mirror-flip)
====================================================
(File services/mirrorPodService.ts — bước lật ảnh là xử lý canvas thuần, không qua AI; chỉ bước sửa chữ bị lật mới gọi AI.)

This image is a horizontally mirror-flipped version of a product design. Keep EVERY visual element — layout, shapes, icons, colors, art style, composition — EXACTLY as shown here, mirrored; do NOT change, redraw or move any of the graphics.
The ONLY fix needed: any text, letters, numbers or words in the image currently read BACKWARDS (mirror-image writing, like reflected in a mirror). Redraw ONLY those characters so they read NORMALLY left-to-right (correct, non-mirrored orientation) — same font style, size, color and position as they currently appear, just un-mirror the glyphs themselves.
If there is no text anywhere in the image, return it completely unchanged.
Output: same background, same framing, 8k high-fidelity, print-ready quality, clean edges.

(Sau bước này, tool dùng lại prompt mockup ở mục 1.2/1.3 để tạo ảnh mockup sản phẩm — không có prompt riêng nào khác.)



====================================================
3. PHOTO RESTORE ("Bóc Nền Sản Phẩm")
====================================================
(File services/photoRestoreService.ts)

Restore and enhance this exact product print/design. Do NOT redesign — keep the EXACT same subject, text, layout, proportions and art style, this is a restoration, not a new creation.
- Fix faded/worn ink: restore full color saturation and vibrancy as if freshly printed.
- Clean up cracked, patchy or blurry ink into crisp, smooth line-work and solid fills.
- Remove fabric wrinkles, folds, dust, stains and texture noise around the artwork.
Isolate the cleaned design centered on a 100% pure white (#FFFFFF) background, no shadow, no garment/mockup visible — flat artwork only. 8k high-fidelity, print-ready quality, sharp clean edges.



====================================================
4. T-SHIRT / BASEBALL JERSEY (tab T-Shirt)
====================================================
(File services/geminiService.ts)

3 biến thể luân phiên (${variation}) dùng chung cho cả 3 khung bên dưới:
1. Layout A: original composition, elegant serif typography, refined premium linework.
2. Layout B: reworked focal balance & placement, flowing script typography, warm palette.
3. Layout C: clean modern minimalist arrangement, bold sans-serif typography, sophisticated palette.

Mảnh chung khác:
- originalityNote: "⚠️ ORIGINALITY (avoid copyright/report): do NOT reproduce any source's exact wording, font or layout. REPHRASE any quote into fresh original wording (same sentiment), use a DIFFERENT font, and REWORK the composition so it is clearly distinct. Keep only name/date/number placeholders."
- conceptNote: "CONCEPT & PURPOSE (keep niche/theme — this already locks the detected sport/team identity, keep it EXACTLY as stated, never substitute a different sport): ${baseAiPrompt}."
- guideNote: "GARMENT STYLE GUIDE (${tshirtStyle}): ${guide}" (từ getTshirtStyleGuide() trong services/productKnowledge.ts)


--- 4.1 Standard T-Shirt (kiểu áo thường) ---

PROFESSIONAL ${tshirtStyle.toUpperCase()} DESIGN — ORIGINAL artwork inspired by the concept, NOT a copy of any existing listing. CONCEPT & PURPOSE (keep niche/theme — this already locks the detected sport/team identity, keep it EXACTLY as stated, never substitute a different sport): ${baseAiPrompt}. ⚠️ ORIGINALITY (avoid copyright/report): do NOT reproduce any source's exact wording, font or layout. REPHRASE any quote into fresh original wording (same sentiment), use a DIFFERENT font, and REWORK the composition so it is clearly distinct. Keep only name/date/number placeholders. ${variation} NOTES: ${userAddition}. ${guideNote} ⚠️ OUTPUT FORMAT (critical, override anything above that implies a photo): a FLAT 2D print-ready graphic — NOT a photograph, NOT worn by a person, NOT a garment render, NO room/background scenery. Single centered motif on a plain white background, clean vector-style edges, 8k high-fidelity, ready for direct print.


--- 4.2 Baseball Jersey — file in mặt TRƯỚC ---

PROFESSIONAL BASEBALL JERSEY — FRONT PRINT FILE — ORIGINAL artwork inspired by the concept, NOT a copy of any existing listing. CONCEPT & PURPOSE (keep niche/theme — this already locks the detected sport/team identity, keep it EXACTLY as stated, never substitute a different sport): ${baseAiPrompt}. ⚠️ ORIGINALITY (avoid copyright/report): do NOT reproduce any source's exact wording, font or layout. REPHRASE any quote into fresh original wording (same sentiment), use a DIFFERENT font, and REWORK the composition so it is clearly distinct. Keep only name/date/number placeholders. ${variation} NOTES: ${userAddition}. ${guideNote} ⚠️ OUTPUT FORMAT (critical): produce ONLY the FRONT-side print graphic, isolated on a plain white background — NOT the full garment shape, NO sleeves/collar drawn around it, NOT a photo, NOT worn by a person. Ready-to-print FRONT FILE only: the mascot/logo/graphic on ONE side and the vertical team-name text (if any) on the OTHER side per the BUTTON PLACKET RULE above, with the center strip left completely empty. 8k high-fidelity, clean vector edges, ready for direct print.


--- 4.3 Baseball Jersey — file in mặt SAU ---

PROFESSIONAL BASEBALL JERSEY — BACK PRINT FILE — companion back-side file for the same design, SAME art style/colors as the front. CONCEPT & PURPOSE (keep niche/theme — this already locks the detected sport/team identity, keep it EXACTLY as stated, never substitute a different sport): ${baseAiPrompt}. ⚠️ ORIGINALITY (avoid copyright/report): do NOT reproduce any source's exact wording, font or layout. REPHRASE any quote into fresh original wording (same sentiment), use a DIFFERENT font, and REWORK the composition so it is clearly distinct. Keep only name/date/number placeholders. ${variation} NOTES: ${userAddition}. ${guideNote} ⚠️ OUTPUT FORMAT (critical): produce ONLY the BACK-side print graphic, isolated on a plain white background — NOT the full garment shape, NO sleeves/collar drawn around it, NOT a photo. Ready-to-print BACK FILE only: ALL-CAPS name arched above a large number, centered, per the layout rules above. 8k high-fidelity, clean vector edges, ready for direct print.

(Front & Back dùng tỉ lệ khung 3:4; Standard T-Shirt dùng tỉ lệ 1:1.)


--- 4.4 Tách thành phần thiết kế (T-Shirt) ---
Isolate the subject on a pure white background. Maintain original colors and details.


--- 4.5 Remix / chỉnh sửa theo yêu cầu (khung bọc chung, T-Shirt) ---
Edit the reference image as follows: ${instruction}. Keep product on pure white background, high-fidelity.



====================================================
5. CÁC LỆNH CHỈNH SỬA CỤ THỂ TỪ UI (đưa vào ${instruction} ở mục 1.5 / 4.5)
====================================================
(File components/RedesignDetailModal.tsx)

- Đổi tên cá nhân hoá:
  Edit the design: change ONLY the PERSON'S NAME text (the proper name line, usually the largest name near the bottom) to "${customName}". CRITICAL: keep ALL other text (the quote, the year, any other words), the fonts, colors, flowers, border and layout EXACTLY the same — do not remove or alter anything except that one name.

- Đổi màu:
  Change color to ${tên màu}

- Thêm dây/khoen treo:
  Add loop of ${tên loại dây}



====================================================
6. PROMPT PHÂN TÍCH ẢNH GỐC (sinh ra "redesignPrompt" dùng ở mục 1.1 và 4.1-4.3)
====================================================
(File services/openRouterService.ts — gửi cho model phân tích ảnh, model: google/gemini-2.5-flash qua OpenRouter)

--- 6.1 Nhánh T-Shirt/Jersey ---

You are a Master Etsy T-Shirt & Sports Jersey Designer for the US market.
Work in this STRICT ORDER (think step by step, then output JSON):
STEP 1 — UNDERSTAND THE DESIGN: First fully grasp WHAT this design is. Identify the exact main subject, the core THEME/concept, AND precisely the ART STYLE / rendering technique — line-work, level of delicacy, shading, and the exact color palette/mood. Note any personalization (names/dates/quotes/numbers). ALSO identify the exact SPORT if any (baseball, soccer, basketball, American football, or "none/generic graphic"), any team/player identity cues, colors, mascot, and any visible number.
STEP 2 — UNDERSTAND THE GARMENT STYLE: Pick the closest garment style from this exact list: [${TSHIRT_STYLES}] (ưu tiên style user đã chọn trừ khi ảnh rõ ràng là style khác).
STEP 3 — LOCK THE SPORT (critical, never violate): whatever sport/team identity you detected in STEP 1 MUST be the ONLY sport represented in the redesign. NEVER substitute a different sport's iconography, ball shape, court/field markings, or jersey conventions. If no real sport is detected, set detectedSport to "None" and skip sport-specific conventions.
STEP 4 — REDESIGN (keep STYLE, change CONTENT moderately): The redesign MUST KEEP the EXACT same art style, line-work, rendering technique, delicacy and color palette as the original. To stay ORIGINAL and avoid copyright/report on Etsy, change only the CONTENT moderately: rework the composition, REPHRASE any quote into fresh wording (never verbatim), and use a DIFFERENT font. Keep only name/date/number placeholders. ⚠️ TRADEMARK SAFETY: any crest/mascot/emblem must be an ORIGINAL fan-art illustration inspired by the detected team's colors/vibe only — NEVER reproduce an official federation/league crest, kit-sponsor logo, or copyrighted character exactly; any player is a generic stylized fan figure, never a photorealistic licensed likeness.

(+ GARMENT STYLE GUIDE nếu có, + USER-REQUESTED THEME nếu user nhập, + MARKET PRINCIPLES ở mục 7, + Design mode/Retention target, + schema JSON output — trường "redesignPrompt" luôn kết bằng: "8k high-fidelity, professional commercial design, clean edges, no white die-cut border, 100% pure white (#FFFFFF) background")


--- 6.2 Nhánh POD/Ornament ---

You are a Master Etsy POD Designer for the US market, specialized in suncatcher & ornament products.
Work in this STRICT ORDER (think step by step, then output JSON):
STEP 1 — UNDERSTAND THE DESIGN: First fully grasp WHAT this design is. Identify the exact main subject, the core THEME/concept, AND precisely the ART STYLE / rendering technique — line-work & leading thickness, level of delicacy, shading, and the exact color palette/mood. Note any personalization (names/dates/quotes).
STEP 2 — UNDERSTAND THE MATERIAL: Identify the physical MATERIAL & construction from the image (e.g. translucent stained glass, clear acrylic, opaque glazed ceramic, matte wood, layered wood). Pick the closest product type from danh sách PRODUCT_TYPES (ưu tiên style user đã chọn trừ khi ảnh rõ ràng là chất liệu khác).
STEP 3 — REDESIGN (keep STYLE, change CONTENT moderately): The redesign MUST KEEP the EXACT same art style, line-work/leading thickness, rendering technique, delicacy and color palette as the original. To stay ORIGINAL and avoid copyright/report on Etsy, change only the CONTENT moderately: rearrange the composition, vary the specific flowers/elements, REPHRASE any quote into fresh wording (never verbatim), and use a DIFFERENT font. Keep only name/date placeholders.

(+ MATERIAL & SPECS, + DESIGN GUIDE, + USER-REQUESTED THEME nếu có, + MARKET PRINCIPLES ở mục 7, + Design mode/Retention target, + schema JSON output — trường "redesignPrompt" cũng kết bằng: "8k high-fidelity, professional commercial design, clean edges, no white die-cut border, 100% pure white (#FFFFFF) background")


--- 6.3 Câu lệnh gửi kèm ảnh (cả 2 nhánh) ---
Perform structural and aesthetic analysis. Return the JSON object as specified.



====================================================
7. NGUYÊN TẮC THỊ TRƯỜNG DÙNG CHUNG (ghép vào mục 6.1/6.2)
====================================================
(File services/productKnowledge.ts — ETSY_DESIGN_PRINCIPLES)

TARGET MARKET: US Etsy buyers (gift & keepsake). Top niches: memorial/remembrance (pet rainbow-bridge, cardinal, 'in loving memory'), birth flower, zodiac/celestial, floral, pet portrait, family/name. SELL-DRIVERS: clear personalization zone (name/date/quote), one strong focal subject, symmetrical balanced composition, premium gallery-grade finish. AVOID (looks cheap): tiny illegible text, low-contrast art, cluttered multi-element layouts, generic non-personalized clip-art, off-trend muddy palettes.

(Ngoài ra còn PRODUCT_DESIGN_GUIDE theo từng loại sản phẩm POD, và TSHIRT_STYLE_GUIDE theo Standard T-Shirt / Baseball Jersey — nội dung chi tiết dài, xem trực tiếp services/productKnowledge.ts nếu cần.)
