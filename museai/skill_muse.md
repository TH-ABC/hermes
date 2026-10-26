# Skill: Làm TVC 30s trên Muse AI (muse.ai) — rút ra từ các lần thành công và thất bại

> Cập nhật 29/09/2026 sau 4 dự án TVC CaThiFood (1 Biệt đội nguyên liệu, 2 Review thật, 3 ASMR 5 phút, 4 Ca đêm).
> Tài liệu liên quan: `CaThiFood_TVC_Playbook_MuseAI.md` (brief thương hiệu và concept), `prompts_ACDE.md` (các khối KHÓA), `TVC10_kichban.md` (kịch bản 10 TVC và bảng kết quả).

---

## 1. Quy trình chuẩn (đã chạy đạt ở dự án 2, 3, 4)

1. **Mỗi dự án một đoạn chat phụ mới.** Bấm "+" cạnh "Đoạn chat phụ". Chờ URL đổi sang `/thread/new` rồi mới gửi tin; gửi sớm thì tin bị gộp vào thread cũ.
2. **Tin nhắn đầu tiên** gồm:
   - ảnh ref đính kèm, đánh số "ảnh 1/2/3" (gửi được nhiều file cùng lúc);
   - kịch bản;
   - toàn bộ khối KHÓA (MỲ QUẢNG, BAO BÌ, DIỄN XUẤT, QUY TẮC CHUNG);
   - câu **"BƯỚC 1: CHỈ tạo N keyframe 720×1280, CHƯA render video, mình duyệt từng khung"**.
3. **Duyệt keyframe.** Mỗi khung ghi rõ ĐẠT hoặc LỖI. Khung ĐẠT phải ghi "giữ nguyên" để Muse không vẽ lại. Khung LỖI chỉ ra lỗi cụ thể và cách sửa. Thường mất 2–4 vòng.
4. **Chốt keyframe.** Liệt kê chính xác phiên bản (ví dụ "K1 v3, K2 v1, K3–K7 v2, K8 v4, K9 = ảnh 3").
5. **Render.** Timeline chi tiết 3 đoạn × 10s: mỗi shot ghi mốc giây, chuyển động máy quay và hành động.
6. **Âm thanh.** Xem mục 4. Thử giọng bằng file TEST riêng, tự chấm rồi mới ghép.
7. **Tự QC bản 30s ở máy** (mục 5). Chỉ yêu cầu làm lại đúng shot lỗi, "giữ nguyên các shot khác và toàn bộ audio".
8. **Đạt mới tải** vào `output/NN_Ten_30s.mp4`, rồi cập nhật bảng trong `TVC10_kichban.md`.

Thời gian thực tế:
- mỗi vòng keyframe 3–6 phút;
- render + ghép 30s khoảng 10–15 phút;
- sửa 2–3 shot khoảng 8 phút.

---

## 2. Thao tác UI Muse (Claude in Chrome)
- **Chrome chặn tải mp4** (thẻ `<a download>` và nút "Tải video xuống" đều không ra file): chạy relay lưu file ở máy (`tools/save_server.py`, cổng 8798). Chèn một nút vào trang Muse, bấm thật để `window.open` relay, rồi `postMessage` ArrayBuffer của video, relay sẽ POST về máy. Không đổi cài đặt tải xuống của Chrome.

- **Ô chat:** tìm bằng `find "chat message input textbox (Nhắn tin)"`, rồi click theo ref. Click theo tọa độ đôi khi trúng lớp phủ video nên chữ không vào ô. Luôn zoom kiểm tra chữ đã nằm trong ô trước khi nhấn Return, và zoom lần nữa sau khi gửi.
- **Trạng thái Muse:** nút gửi là ô vuông = đang xử lý; nút là mũi tên = rảnh. Dưới avatar có dòng trạng thái ("đang xử lý", "Ghép âm thanh", "Kiểm tra VO"…).
- **Lượt bị chết im:** trạng thái hết "đang xử lý" nhưng không có trả lời. Nguyên nhân hay gặp là Muse xin quyền mạng ngoài, bị từ chối và dừng luôn. Cách xử lý: tải lại trang để xác nhận, rồi gửi lại, thêm câu "KHÔNG cần tải model/tool bên ngoài (không huggingface, không Whisper), mình tự kiểm âm thanh ở máy".
- **Bảo mật:** Muse hay xin quyền tải từ huggingface.co. **Luôn TỪ CHỐI** (toast "Đã từ chối yêu cầu"). Không bao giờ cấp quyền mạng bên thứ ba.
- **Chờ:** dùng `sleep` chạy nền (4–8 phút). Không bấm liên tục.
- **Ảnh keyframe:** ảnh blob lazy-load, khoảng 1152×2048. Cuộn lên 5–6 nấc mỗi lần, chờ 2s cho ảnh tải. Lọc ảnh sau một tin nhắn bằng `compareDocumentPosition`, vẽ 2 ảnh lên canvas overlay để zoom soi. Nhớ xóa overlay trước khi gõ.
- **Xem keyframe dạng lưới "+N":** click ô đầu tiên để mở viewer. Dùng ArrowLeft/ArrowRight và `zoom` vùng giữa (556,36)→(956,748) để soi từng khung. Chrome **chặn tải nhiều file liên tiếp** (chỉ file đầu được lưu). Script JS lặp qua viewer dễ bị timeout 45s, nên soi bằng zoom là nhanh nhất.
- **Video:** click thumbnail rồi Escape để blob tải. Lấy video 30s bằng `[...document.querySelectorAll('video')].filter(v=>v.duration==30).pop().currentSrc`. Tải bằng thẻ `<a download>` rồi click; file vào `~/Downloads`.
- **Cuộn thread bị kẹt** (lăn chuột không cuộn, dự án 6): cuộn bằng JS. Tìm container: `window.__sc=[...document.querySelectorAll('*')].filter(e=>e.scrollHeight>e.clientHeight+200&&getComputedStyle(e).overflowY.match(/auto|scroll/)).sort((a,b)=>b.scrollHeight-a.scrollHeight)[0]`. Container dạng column-reverse: `scrollTop=0` là đáy, giá trị ÂM là cuộn lên (`window.__sc.scrollTop-=800`).
- **Gõ tin dài không vào ô** (dự án 6, 2 lần): click ô chat, gõ thử "X", zoom kiểm tra, Backspace, rồi mới gõ tin thật. Tin nhiều đoạn thì thay xuống dòng bằng " ¶ ".
- **Muse báo 503 khi tạo ảnh** (dự án 6 K4): gửi lại đúng khung đó là được, không cần viết lại prompt.
- **Audio test:** không có thẻ `<audio>` trong DOM. Dùng menu "…" cạnh player, chọn "Tải xuống", file mp3 vào `~/Downloads` với tên "VO test <Tên>.mp3".

---

## 3. Hình ảnh: thất bại đã gặp và cách chữa

| Lỗi | Gặp ở | Cách chữa đã hiệu quả |
|---|---|---|
| Mỳ Quảng thành **mì gói/ramen** (sợi xoăn, tròn, vàng đậm) | mọi dự án, nhất là cảnh ăn, gắp và cảnh trong tô ở góc xa | Luôn dán [KHÓA MỲ QUẢNG]. Cảnh macro thường đúng, còn **tô ở hậu cảnh hoặc cảnh nhai hay bị lại sợi xoăn/nui** (dự án 4 v1, 10–20s). Yêu cầu "trong tô giống hệt K5", render từ keyframe làm frame đầu |
| Bao bì thành **ly giấy cao**, nhãn tự chế ("instant", chữ Anh, nhãn trắng) | dự án 4 keyframe v1, D v2 | Mô tả tỉ lệ thật ("tô THẤP bề ngang, rộng ~1,7× chiều cao, nắp đen phẳng"), kèm "nhãn giống ảnh 1, RENDER LẠI trong cảnh (cong theo thân tô, cùng ánh sáng, có bóng)". **ĐỪNG viết "ghép/edit từ ảnh 1"**: Muse hiểu thành cắt dán, ra sticker phẳng (xem mục Bao bì bị dán) |
| Sản phẩm thương hiệu khác xuất hiện (ly "PHỞ HỘI TRUNG") | concept B v2 | Thêm quy tắc "chỉ xuất hiện sản phẩm CaThiFood" |
| **Đồng hồ kim** sai giờ (muốn 2:07, ra 1:35 rồi phút 35) | dự án 4 K1 v1, v2 | Model không vẽ đúng kim. **Đổi sang đồng hồ LED số đỏ "02:07"** là đạt ngay |
| Trứng cút quá to, như **quả bóng đá**, hoặc **màu xanh ôliu** | dự án 1, 4 (K5, K8) | Nói rõ kích thước ("cỡ đầu ngón cái, bằng 1/3 con tôm, nhỏ hơn miếng ba chỉ") và màu ("VÀNG CAM HỔ PHÁCH như nghệ kho, TUYỆT ĐỐI không xanh lá/ôliu/chanh"). Nếu vẫn sai thì **inpaint từ bản cũ đã đạt**, chỉ sửa vùng trứng |
| Số lượng đối tượng sai (xin 3 trứng, ra 4) | dự án 4 K8 | Chấp nhận nếu không ảnh hưởng. Ép số lượng tốn thêm vòng |
| **Vật thể biến mất giữa shot** (tay đặt tô rồi kéo tô đi) | dự án 4 v1, 6–10s | Mô tả hành động có trạng thái kết thúc: "đặt tô, rút TAY ra, TÔ Ở YÊN trên bàn đến hết shot" |
| **End card** vẽ bằng AI hỏng (chữ rác, logo cụt, sai tô) | dự án 1, 3 | **Tự ghép end card ở máy bằng PIL từ ảnh thật** (`refs/MQ_4Vi.jpg`), upload, bảo Muse "dùng Y NGUYÊN ảnh này, không crop/vẽ lại, crossfade 0.3s + zoom 100→103%". Muse chèn chính xác từng pixel (file mẫu `refs/K10b_endcard.png`) |
| Shot ăn/tô cận bị model video vẽ lại thành sợi xoăn + trứng còn vỏ **dù render từ keyframe đúng** (3/3 lần) | dự án 4, 10–14s | **Bỏ model video cho shot đó**: dùng push-in chậm (Ken Burns) trên chính keyframe tĩnh, thêm hơi nóng overlay. Nội dung tô vì thế được khóa tuyệt đối |
| Lỗi nằm sẵn trong keyframe mà mình **duyệt sót** (trứng cút vỏ lốm đốm, nhìn thumbnail không thấy) | dự án 4, K4 v2 | Trước khi duyệt, **zoom crop 2× vùng trong miệng tô** của mọi keyframe có tô. Sửa bằng inpaint CHỈ vùng trong tô, lấy nội dung từ keyframe đúng (K5) |
| Muse tự báo "đã kiểm tra" nhưng vẫn sai | nhiều lần | **Không tin báo cáo của Muse.** Luôn tự rút khung và tự nghe |
| **Thumbnail/viewer hiển thị ảnh CŨ** sau khi Muse sửa (Muse ghi đè cùng đường dẫn file, UI cache blob → K6 v3/K7 v3 nhìn y hệt v2, `img.src` blob trùng) | dự án 5 | Sau mỗi vòng sửa, **reload trang thread** (navigate lại URL, chờ ~15s) rồi mới mở viewer duyệt. Kiểm bằng JS: blob URL của ảnh mới phải khác ảnh cũ |
| **Cảnh trộn đất sét + sản phẩm thật: Muse DÁN bao bì như hình chữ nhật 2D** (lơ lửng, không bóng đổ, còn dải nền thừa, tô thành ly cao, nhãn phẳng đè lên miệng tô) | dự án 6 K6, K7, K8 | Yêu cầu "dùng ảnh 1 làm reference cho model edit/compose để render sản phẩm VÀO cảnh với phối cảnh + ánh sáng + bóng thật, KHÔNG paste 2D"; nêu vị trí (ĐẶT TRÊN mặt bàn, có bóng tiếp xúc), tỉ lệ so với nhân vật (~3×), "nhãn uốn cong theo thân tô, nằm DƯỚI vành miệng" |
| Tay nhân vật đất sét **màu vàng giống bột**, nhăn nheo, tay áo khác màu áo | dự án 6 K3 | Nêu màu da theo khung mặt đã duyệt ("hồng đào như mặt ở K2"), "tay tròn mềm kiểu Aardman, 5 ngón", màu tay áo theo trang phục đã khóa |
| Phụ kiện nhân vật đổi giữa các khung (khăn caro đen-trắng thành khăn màu khác) | dự án 6 K8 | Liệt kê phụ kiện trong khối NHÂN VẬT và nhắc "giống K2/K4/K6" khi sửa |
| Muse "inpaint" bằng cách **tự ghép tay** (dán mảnh ảnh phẳng, tint màu, flip trứng): mảng thức ăn kéo giãn, lơ lửng trên vành tô, tràn ra ngoài mép, mờ nhòe. Muse còn tự báo "đã pixel-diff" | dự án 6 K8 vòng 3 | Ghi rõ "dùng MODEL ẢNH inpaint sinh mới, mask = elip miệng tô, reference = tô ở khung đã đạt; thức ăn THẤP HƠN vành, không vượt đường vành; KHÔNG ghép/tint/flip tay". Soi bằng overlay JS toàn màn hình, vì viewer hay bật/tắt nhầm |
| Hậu cảnh sai bối cảnh (hồ bơi thay vì nhà máy) | dự án 1 | Nêu rõ bối cảnh trong từng shot, kiểm tra ở keyframe |

**Diễn xuất (khối DIỄN XUẤT):**
- Cười bằng mắt, môi mỉm nhẹ, không há miệng hay nhe răng.
- Ăn thì ngậm miệng nhai 2–3s, nuốt xong mới nói.
- Có một nhịp trộn xốt.
- Không ai nói trước camera nếu dùng VO, để tránh lệch khẩu hình.

**Mẹo "wow" đã đạt:**
- hơi nóng làm mờ kính (dự án 4);
- slow-motion đũa nhấc sợi dẹt óng xốt;
- rack focus từ tô ra cầu Rồng;
- hook 2s đầu bằng cận cảnh mạnh (LED 02:07, xé nắp ASMR).

---

## 4. Âm thanh và giọng đọc

### Sự thật về giọng trong Muse
- Muse có khoảng **228 giọng**, toàn giọng multilingual phương Tây. **Không có giọng tiếng Việt gốc.** Mọi giọng đọc tiếng Việt đều có âm sắc "Tây" ở mức nào đó, nên phải thử và chấm.
- Model video tự sinh audio gốc, thường là **tiếng nói tiếng Anh hoặc lảm nhảm**. Luôn ghi: **"TẮT toàn bộ audio gốc của model video"**.
- Muse đôi khi báo "đã có VO theo timeline" nhưng file thực tế **không có giọng** (chỉ nhạc). Luôn kiểm bằng ASR.
- Muse có lúc bỏ nhạc nền vì "không có nhạc bản quyền phù hợp". Nên yêu cầu nhạc cụ thể (piano, sáo trúc, ukulele…) và kiểm tra lại.

### Bảng giọng đã thử

| Giọng (tên trong Muse) | Giới | Dùng ở | Kết quả chấm bằng Whisper large-v3-turbo |
|---|---|---|---|
| **Helio** (`avocado_v2:MAI_03`) | Nam ấm | Dự án 1 (narrator), 2 (reviewer) | **Tốt nhất bên nam.** Nghe đủ câu gần như đúng từng chữ, ngân giọng tự nhiên |
| chip | Nam | Dự án 2 (test V1) | Sai thanh điệu, loại |
| briggs | Nam | Dự án 2 (test V3) | Sai thanh điệu, loại |
| magnus | Nam | Dự án 2 (test V4) | Sai thanh điệu, loại |
| **Aria** (Meta AI Warm, nữ Mỹ) | Nữ ấm | Dự án 4 | **Tốt nhất bên nữ.** Đúng từng chữ, nhịp chậm ấm (2 câu khoảng 5,0s) |
| Isabella (Soothing Ribbon, nữ Anh) | Nữ | Dự án 4 (test) | Đọc "đêm" thành "đen", loại |
| Lily (Mellow Saxophone, nữ Mỹ) | Nữ | Dự án 4 (test) | Đúng chữ nhưng quá nhanh (3,9s), không hợp tone cảm xúc |

Dự án 3 (ASMR) chỉ có 1 câu VO cuối "5 phút. Đúng vị Quảng." ở khoảng 26,5–28,5s.

**Cách chọn giọng:**
1. Yêu cầu: "xuất 3 file audio TEST riêng (mỗi file đọc đủ các câu VO) bằng 3 giọng [nam/nữ] multilingual khác nhau phát âm tiếng Việt tốt nhất, ghi tên giọng".
2. Tải về, rồi chạy ASR local (mục 5).
3. Chọn giọng đúng chữ nhất **và** có tốc độ hợp mood.
4. Báo lại Muse: tên giọng, mốc giây bắt đầu từng câu, "tốc độ giữ nguyên như file test" (không để Muse tự tăng tốc cho vừa khung).

### Spec âm thanh mẫu (dự án 4, đạt)
```
ÂM THANH: TẮT toàn bộ audio gốc của model video (không được có tiếng nói tiếng Anh/lảm nhảm).
Nhạc piano ấm chậm + tiếng mưa nền suốt 30s; SFX: ù ù đèn huỳnh quang, "cạch" đặt tô, xé nắp,
hơi nóng, đũa chạm tô, tiếng thành phố xa. VO NỮ trầm ấm, chậm: 21–26s "<câu 1>" và 26.5–28.5s
"<câu 2>". Nhạc duck -15dB dưới VO.
```
- **Hài/hoạt hình:** sáo trúc + ukulele ở khoảng -20dB, SFX tiếng kêu cute, nước bắn, nắp "cạch" (dự án 1).
- **ASMR:** không nhạc hoặc nhạc rất nhỏ. SFX xé màng, rót nước, bẻ bánh tráng "rụp", đũa trộn.
- **Mức đạt đo được:**
  - nền liên tục khoảng -20…-31 dB RMS, không có lỗ im lặng quá 1,5s;
  - VO nổi hơn nhạc khoảng 15–18 dB;
  - peak dưới 1.0 (không clip).

---

**Dự án 5, bài học VO:** Muse báo "VO2 có mặt, RMS 0.078" nhưng ASR chỉ nghe "Xa nhà mấy cũng có vị nhẹ", còn **mất hẳn câu tagline "Mỳ Quảng CaThiFood"** (VO dài bị cắt ở mốc kết thúc). Cách chữa: tách mỗi câu thành 1 clip VO riêng có mốc giờ riêng. Tránh để chữ "nhà" đứng cuối câu (Aria đọc nuốt thành "nhẹ/nhạc"), đổi thành "vị quê nhà". Nếu một câu VO rơi vào end card thì đặt nó ≥27s và kết thúc ≤29.5s.

## 5. QC tại máy (bắt buộc trước khi tải về output/)

```bash
F=QC.mp4
# 1. Kỹ thuật: phải là 720x1280, 30.000s, có stream audio
ffprobe -v error -show_entries stream=codec_type,width,height,duration -of compact $F
# 2. Âm lượng liên tục (RMS, reset mỗi 0,5s)
ffmpeg -i $F -af "aresample=48000,astats=metadata=1:reset=24000,ametadata=print:key=lavfi.astats.Overall.RMS_level:file=-" -f null - 2>/dev/null | grep RMS
# 3. Lưới khung 1 hình/giây (6x5 = 30 khung) để soát nhanh
ffmpeg -i $F -vf "fps=1,scale=180:-1,tile=6x5" -frames:v 1 grid.jpg
# 4. Cắt khung cận ở các giây nghi ngờ (tay, tô, miệng) ở độ phân giải cao hơn
ffmpeg -ss 9 -i $F -frames:v 1 -vf scale=400:-1 z9.png
# 5. ASR tiếng Việt: server faster-whisper large-v3-turbo local ở 127.0.0.1:8799 (POST WAV)
ffmpeg -i $F -ac 1 -ar 16000 a.wav && curl -s --data-binary @a.wav http://127.0.0.1:8799/
```
- **Đọc kết quả ASR:**
  - Có tiếng Anh thì audio gốc chưa tắt.
  - Nếu chỉ ra câu giống initial_prompt ("nguyên liệu thật, xốt thịt thật…") hoặc "Hãy subscribe…/Thank you for watching", đoạn đó **không có giọng**.
  - Lưu ý: initial_prompt có "Mỳ Quảng CaThiFood" nên ASR dễ nghe đúng tên hãng. Câu còn lại mới là thước đo phát âm.
- **Soát hình theo checklist:**
  - 2 tay 5 ngón;
  - mặt và trang phục đồng nhất giữa 3 đoạn;
  - sợi dẹt ở **mọi** cảnh có tô, kể cả tô hậu cảnh;
  - nhãn đúng ảnh 1;
  - không ai mở miệng nói;
  - vật thể không biến mất;
  - end card đúng ảnh gốc.
- **Nếu không chạy được ffmpeg local:** có thể relay qua popup (xem memory `muse-video-qc-asr`). Trang muse.ai không fetch thẳng localhost được.

---

## 6. Mẫu prompt sửa lỗi hiệu quả

```
QC bản 30s v1: <liệt kê phần ĐẠT>. CÒN N LỖI PHẢI SỬA:
(1) <mốc giây>: <mô tả lỗi thấy được>. Phải: <trạng thái đúng, kể cả trạng thái kết thúc shot>.
(2) ...
Render lại ĐÚNG các shot này từ keyframe <Kx vy> (dùng keyframe làm frame đầu, khóa nội dung tô),
giữ nguyên các shot khác và GIỮ NGUYÊN toàn bộ audio hiện tại, ghép lại bản 30s v2.
```
Nguyên tắc:
- Khen phần đạt để khóa lại.
- Lỗi phải có mốc giây và mô tả thấy được.
- Luôn nói "giữ nguyên phần còn lại".
- Tham chiếu keyframe hoặc shot đã đạt làm chuẩn ("giống hệt K5").

## Công thức đã thành công: claymation (P6 "Hội An đất sét", đạt ở lần render đầu)
- **Duyệt keyframe trước:** duyệt đủ 8 keyframe rồi mới render.
- **Chuyển động theo đoạn:**
  - Nửa đầu (0–15s) làm stop-motion 12fps, lấy từ keyframe đất sét.
  - Nửa sau dùng push-in 100→108% trên ảnh tĩnh, không dùng video model. Cách này khóa được nhãn và sợi mỳ.
- **Chuyển cảnh POP ở giây 15:** scale jump + flash trắng 2 frame, chuyển từ đất sét sang tô thật. Đây là khoảnh khắc "wow".
- **Pha trộn đất sét và đồ thật:** nhân vật đất sét đứng cạnh tô thật trông đẹp, miễn tô đặt TRÊN bàn và có bóng tiếp xúc.
- **Âm thanh:**
  - Nhạc đàn tranh + guitar + trống gỗ.
  - SFX bóp đất sét và dao cạch cạch.
  - VO Helio làm thành 2 clip riêng; duck −18dB.
- **Thời gian render:** Muse mất khoảng 25–30 phút mới xong. Trong lúc đó trạng thái hiện "Đang ghi log" mà chưa có video, cứ tiếp tục chờ.

## Bài học từ P7 "Trước giờ bóng lăn" (4 người, 4 vị)
- **Tô bị vẽ thành ly giấy cao.** Nói rõ "TÔ THẤP RỘNG, rộng ~1,6 lần chiều cao, nắp đen" và lấy khung đã có dáng tô đúng làm chuẩn.
- **Trứng gà cắt đôi thay cho trứng cút.** Model hay tự thêm, nên phải ghi "trứng cút NGUYÊN QUẢ đã bóc, KHÔNG trứng gà cắt đôi".
- **Nhãn tự vẽ ở góc top-down nhiều tô.** Đổi sang top-down thẳng đứng, camera sát, chỉ thấy miệng tô, để không lộ nhãn.
- **Cảnh ăn mừng.** Model vẫn cười lộ răng; chấp nhận được nếu miệng không há to.
- **Duyệt ảnh khi thread dài.**
  - Muse ảo hóa danh sách: chỉ ảnh đang hiển thị mới có trong DOM, và set scrollTop bằng JS không làm ảnh tải.
  - Cách làm: cuộn bằng chuột (computer scroll 5 tick), sau mỗi lần gom `img` vào Map theo vị trí (top + scrollTop), rồi sắp xếp và xem từng cặp bằng overlay.
  - Vòng lặp JS trên 45s sẽ timeout CDP.

## Bài học từ P7, lần render 1 ("Trước giờ bóng lăn")
- **Duyệt keyframe ở cỡ thumbnail là chưa đủ.**
  - K8 (cụng tô) đã được duyệt nhưng khi xem video full-res thì lòng tô là sợi mảnh xoăn như mì gói, đựng trong cốc cao.
  - Với mọi khung có tô, phải phóng to riêng phần lòng tô trước khi duyệt.
  - Khi sửa, yêu cầu "lòng tô lấy đúng nội dung từ khung top-down đã đạt (K4 v3)".
- **Nhạc sôi động to và đều (RMS khoảng -12…-15dB suốt 30s)** làm Whisper chạy trên đoạn 0–18s hoặc 18–30s chỉ trả câu ảo "Hãy subscribe…".
  - Cách xử lý: cắt đúng cửa sổ VO (ví dụ 23,5–30s) để ASR riêng, hoặc thêm `highpass=f=250,lowpass=f=3800`. Khi đó ASR nghe được "5 phút, kịp giờ bóng lăn" (Whisper hay nghe nhầm "lăn" thành "lặng"/"lạnh", vẫn coi là đạt) và "Mỳ Quảng CaThiFood".
- **Sửa một khung sau khi đã render:** yêu cầu Muse gửi keyframe mới để duyệt trước, rồi chỉ thay đoạn thời gian của khung đó, giữ nguyên phần hình còn lại, audio và VO.
- **Muse không ghép được nhãn thật lên tô cầm tay mới:** nhãn ra hình chữ nhật phẳng, lòi khỏi viền tô. Sau 2 lần sửa hỏng, cách an toàn là dùng lại một khung đã đạt với chuyển động khác (ví dụ pull-out + xoay ngược) và giữ audio copy nguyên. Kiểm bằng `cmp` PCM audio giữa hai bản: trùng thì chỉ cần QC lại hình.
- **Muse nói "giữ nguyên 100%" nhưng thực tế render lại cả video** (PSNR 0–24s chỉ khoảng 27dB). Luôn soát lại frame grid toàn bộ, không tin lời Muse.
- **Sau khi Chrome mất kết nối hoặc reload, ảnh trong thread có thể kẹt skeleton.** Click vào bubble để mở lightbox; ảnh full-res vẫn hiện.

## Bài học từ P8 "5 tiếng vs 5 phút" (split-screen Bà / cháu)
- **Nhãn phẳng tự vẽ lòi khỏi tô, lặp lại ở mọi khung có tô cầm tay.** Có hai cách chữa, phải ghi rõ trong prompt:
  - **Cách A:** cắt nguyên tô ĐÃ ĐẬY NẮP từ ảnh bao bì 1 (cutout + đổ bóng) rồi đặt vào cảnh.
  - **Cách B:** chỉ vẽ tô giấy trắng thấp rộng trơn, góc máy thấy miệng tô, KHÔNG thấy nhãn.
  - Khung packshot cạnh tô sứ: dùng tô mở không nhãn, đặt packshot đậy nắp (cách A) phía sau.
- **Muse báo "đã sửa" nhưng gắn lại đúng file cũ.** Luôn lưu ảnh về máy qua relay rồi `md5 -r`. Nếu trùng md5, chỉ ra cho Muse. Ở v3 thì md5 cũng xác nhận các khung "giữ nguyên" là đúng file cũ (tốt).
- **Relay chỉ phát 'ready' MỘT lần mỗi lần load cửa sổ.** Gửi nhiều ảnh thì mỗi ảnh mở `window.open('http://127.0.0.1:8798/?c'+k,'qcsave')` với query khác nhau. Lọc gallery mới nhất bằng `getBoundingClientRect().top>250`.
- **Kích thước cửa sổ Chrome thay đổi giữa các lượt.** Luôn chụp screenshot trước khi click composer. Click trúng sidebar (x<283) sẽ mở thread khác của user, nên phải quay lại thread dự án và đợi load xong mới gõ.
- **Muse hay tự thêm bàn tay người ở mép khung "không người" (packshot).** Tay thừa khi animate dễ thành 3 tay, nên xóa từ keyframe.
- **Cốc cao lặp lại ngay cả khi đã ghi "thấp rộng".** Khi sửa, ghi tỉ lệ số "rộng ~1,6× cao" và chỉ định tư thế cầm (hai tay nâng ngang ngực).

## Bài học từ P9 "Hành trình hạt mè đen" (ĐẠT sau 1 render, không cần sửa)
- Brief 3D nghệ thuật/fluid art không người → Muse ra 8 keyframe đạt ngay vòng 1 (không người = không lỗi tay/mặt). Rất hợp phong cách "wow" sản phẩm.
- K7 ghép hộp thật từ ảnh 1 lên nền phố Hội: nhãn giữ chuẩn khi yêu cầu "ghép/edit từ chính ảnh 1, không tự vẽ nhãn".
- Muse có thể xin quyền mạng microsoft telemetry / github giữa chừng → Từ chối, vẫn hoàn thành.
- SỰ CỐ: sau khi Muse báo "File TVC 30s đã sẵn sàng", avatar Muse kẹt "Đang kết nối..." → thumbnail video quay vòng mãi, không có thẻ <video> 30s, nút "Tải video xuống" không làm gì, reload trang thì thread không tải. Media Muse đi qua kết nối sandbox (/api/falco pending), nên chỉ còn cách chờ Muse kết nối lại. Không gửi tin nhắn mới lúc đang mất kết nối.
- Sự cố "Đang kết nối..." tự hết sau vài giờ. Chỉ cần quay lại thread là thấy video 30s. Không cần render lại.
- Kết quả: 6 clip dùng video model thật (mưa hạt, chảo, cối tự quay, lụa đen, rót chè, rắc mè), K7–K8 push-in trên ảnh tĩnh, end card nguyên ảnh 2. 30 khung đều đạt, không lỗi nào. **Công thức 3D không người + ghép hộp thật là công thức an toàn nhất trong 9 dự án.**
- Giọng nữ Aria đọc đúng cả 2 câu. Whisper nghe thành "mịn như lũa" và "Trẻ Xí Mà", là lỗi nhận dạng gần đúng chứ không phải lỗi phát âm.
- QC ASR: đoạn chỉ có nhạc khiến Whisper bịa "Hãy subscribe cho kênh La La School…", nhận ra được vì mốc thời gian 0–30s dài hơn cả clip. Khi đó chạy lại bằng `vad_filter=True`: kết quả NONE nghĩa là không có lời lạ. Luôn cắt riêng từng cửa sổ VO để kiểm tra lời.
- Lưu mp4 qua relay: `window.open` gọi từ JS không có thao tác người dùng thì bị chặn popup (trả về null). Cách làm: fetch blob trước, gắn listener `click` chạy một lần để mở relay, rồi dùng computer tool click thật vào vùng trống của trang.


## Bài học từ P10 "Chuyến cắm trại biển An Bàng" (lifestyle gia đình, hoàng hôn → đêm)
- **Ảnh poster khuyến mãi làm ref bao bì là nguồn gây lỗi.** Muse cắt nguyên hình chữ nhật từ poster rồi dán lên cảnh, nên dính lá rau, tô mẫu và nền cũ, có viền trắng, trông phẳng như sticker. Có lúc còn bán trong suốt (thấy ngón tay xuyên qua hộp) và không có bóng.
- **Cách chữa:** tự cắt ảnh tách nền (PNG RGBA) tại máy bằng PIL: vẽ polygon mask, blur 1.2px, crop theo bbox. Upload thành ảnh 4/5 và nói rõ "mép khuyết là do tách nền, dựng lại thân trụ".
  - Nên lấy ảnh studio sạch, không bị che (ví dụ Che_XiMa_Tet.jpg cho hộp Xí Mà).
  - Kết quả: hộp đứng trên bàn **đạt** khi yêu cầu "tay mẹ đang mở nắp hộp, ngón tay nằm TRƯỚC hộp, có bóng tiếp xúc".
  - Ly cầm tay / ly bay trước ấm và packshot 3 món cạnh lửa trại vẫn **trượt** sau 3 vòng: vẫn dán phẳng, không bóng, chén nghiêng.
- **Quy tắc rút ra:** tối đa 2 vòng cố ghép bao bì. Nếu vẫn trượt, chuyển sang khung KHÔNG bao bì: tô giấy trắng trơn thấy miệng tô, hero món ăn. Để END CARD (ảnh ghép sẵn từ ảnh thật) gánh phần nhận diện bao bì.
  - Hộp giấy đặt trên bàn thì Muse ghép được. Ly cầm tay hoặc nhiều món xếp cạnh nhau thì không.
- **Blob ảnh cũ sau khi Muse sửa (xác nhận lại):** grab ngay sau khi Muse trả lời cho ra ảnh giống hệt v2 (PSNR = inf). Phải `navigate` reload thread, chờ khoảng 10s cho thread load (lần grab đầu có thể rỗng), cuộn rồi mới grab. Luôn chạy PSNR so với bản trước; PSNR = inf là ảnh cũ.
- **Danh sách ảnh trong thread bị ảo hóa (virtualized):** chỉ ảnh gần viewport mới có naturalWidth. Grab bằng cách lấy text node gần nhất phía trước ảnh khớp `/^K\d/`, lọc nhãn mới (ví dụ "(mới)"), và cho bản sau ghi đè bản trước (thứ tự DOM, bản cuối là mới nhất).
- **Relay bản mới:** một cửa sổ nhận được nhiều postMessage. Gửi bufs[0] khi nhận 'ready', gửi tiếp khi nhận mỗi {saved}, rồi đóng. Kích hoạt bằng click thật vào (1450,500).
- **Server relay/ASR có thể chết sau khi reset context.** Trước khi lưu, kiểm tra bằng `curl 127.0.0.1:8798 / 8799`. Nếu chết thì `nohup` chạy lại.
- **Giới hạn công cụ:** mỗi lệnh JS phải xong trong 45s; browser_batch tổng khoảng 40s trở xuống; `sleep` dài thì chạy nền.

### P10 – bài học render cuối
- **VO bị nuốt âm tiết đầu**: Muse tự dùng `silenceremove` để cắt khoảng lặng clip TTS → mất phụ âm đầu ("Đi đâu" → "…âu", "Mỳ Quảng" → "Quảng"). Whisper KHÔNG nghe ra chữ đầu kể cả khi initial_prompt chứa đúng câu → dấu hiệu chắc chắn là mất thật. Cách phòng: ngay trong yêu cầu render ghi "mỗi clip VO có 0,4s im lặng TRƯỚC chữ đầu, 0,3s sau chữ cuối, KHÔNG silenceremove/cắt đầu, không fade-in". Sau khi sửa: nghe đủ chữ, hình giữ nguyên (PSNR inf).
- **ASR QC chuẩn**: dùng word_timestamps=True + vad_filter=True, chạy 2 lần (có/không initial_prompt). Cả đoạn chỉ có nhạc → Whisper bịa "Hãy subscribe cho kênh La La School…" (segment trải 0–30s) = không có lời; xác nhận bằng vad_filter → SEGS [].
- **Muse xin quyền huggingface.co** để tự transcribe VO → luôn Từ chối; Muse vẫn giao file.
- **"File đã thay thế" → khung video trống**: khi Muse ghi đè cùng tên file, thẻ video trong chat không render (kể cả sau reload). Yêu cầu "gửi lại dưới TÊN MỚI …_v2.mp4, không render lại" → có ngay.
- Blob video cũ sau khi sửa: kiểm byteLength/đuôi src trùng bản trước = stale, phải reload.

## ⚠️ QUY TẮC CỨNG (user phản hồi sau 10 TVC): KHÔNG ĐƯỢC CÓ SHOT ẢNH TĨNH
- "Tĩnh là bị lỗi." Push-in / Ken Burns trên ảnh tĩnh = LỖI, không phải phương án an toàn. Bỏ quy tắc cũ "push-in cho shot khó".
- Mọi shot (trừ end card bao bì) phải dùng model video image-to-video với chuyển động thật nhưng nhẹ & kiểm soát: hơi nước bay, tay gắp/khuấy, người chớp mắt cười, lửa lay, sóng, tóc bay, camera dolly/parallax thật.
- Nếu model video làm hỏng (tô nhảy, sợi biến dạng, nhãn méo): sửa prompt chuyển động (giảm biên độ, khóa vật thể, "object stays fixed"), thử model khác, hoặc tách shot ngắn hơn — KHÔNG lùi về ảnh tĩnh.
- QC chuyển động: so khung đầu/giữa/cuối mỗi shot ở vùng giữa (crop) — nếu chỉ khác nhau bởi tỉ lệ zoom → FAIL.

### P10 v4 – overlay hộp thật: soát "hộp ma" phía sau
- Khi Muse dán cutout bao bì thật lên video, model video vẫn có thể vẽ **một hộp AI thứ hai** (nhãn méo) ló ra sau/cạnh overlay trong vài khung đầu shot. Soát bằng tile vùng quanh hộp: `ffmpeg -ss T -t 4 -vf "fps=2.5,crop=...,tile=11x1"`.
- Nhai/ngậm thìa (miệng ôm thìa khi được đút) là hành động ăn, chấp nhận được. Chỉ cấm há miệng như đang nói hoặc húp há to.
- Sửa có mục tiêu: nêu đúng khoảng thời gian + vị trí, yêu cầu "chỉ còn DUY NHẤT hộp overlay", giữ nguyên mọi thứ khác, xuất tên file mới.

### Đợt sửa CHUYỂN ĐỘNG cho 10 TVC: quy trình và bài học
- **Đo, đừng đoán:** `motion_qc.py FILE 0.2 -v` fit phép zoom/pan affine giữa các khung cách nhau 0.25s. Phần dư <0.2px nghĩa là ảnh tĩnh hoặc Ken Burns (S). Hơi nước/khói mờ KHÔNG đủ kéo phần dư lên, nên shot "ảnh tĩnh + khói" vẫn ra S: vẫn là lỗi (P04 10–13.5s).
- **S ngắn ~1s có thể là video thật ít động** (P08 21.5–22.5s: tay đặt yên nhưng mặt quay đầu). Luôn crop mặt/tay tile 5fps để xác nhận trước khi bắt sửa.
- **Chạy song song:** mỗi TVC một tab/thread riêng, gửi hết yêu cầu rồi chờ. Tab nền mới mở phải đợi ~10s và **chụp screenshot trước** thì click/gõ mới ăn (zoom tab nền trả ảnh đen, chữ gõ bị mất). Luôn gõ thử "X" rồi zoom kiểm tra.
- **Khi lấy file:** Muse hiện cả clip preview 5s 480×480 (~358KB) trong thread. Kiểm tra `window.__kf.n` và ffprobe: bản TVC phải 30.000s 720×1280, nếu không thì grab suffix khác.
- **Liên tục nhân vật:** khi render lại một đoạn giữa, model có thể chèn tay/người khác (P05 motion_v1: tay nữ lạ 6–9s). Tile toàn bộ đoạn đã render lại, không chỉ khung giữa.
- **Mẫu prompt sửa:** "Khách hàng báo LỖI: [khoảng giây] là ẢNH TĨNH… render lại bằng IMAGE-TO-VIDEO thật từ đúng keyframe đã duyệt: [mô tả chuyển động cụ thể]… Giữ khoá… Nếu vẫn tĩnh thì render lại, KHÔNG quay về ảnh tĩnh. KHÔNG đổi: [các đoạn khác, end card, toàn bộ audio]… Xuất file MỚI tên X_motion_v1.mp4". Sau khi tải, audio corr so bản cũ phải bằng 1.000 (nếu thế thì kết quả ASR cũ vẫn dùng được).
- **Nhân tiện soát lại lỗi cũ bị bỏ sót:** P02 22–30s có sợi tròn mảnh kiểu mì trứng, nằm trong đúng shot tĩnh. Shot tĩnh thường cũng là shot chưa được soát kỹ.

- **Cảnh báo khi mô tả nhãn trong prompt sửa:** đừng tả màu nhãn theo trí nhớ ("nâu/cam") – Muse sẽ vẽ đúng lời tả và lệch khỏi tô ở shot kế bên (TVC06 motion_v3: tô cao nhãn nâu đậm ở 14.5–18.5s, cắt sang tô thấp nhãn kem ở 18.5s). Hãy nói "dùng ĐÚNG cái tô của shot X–Ys" và lấy frame đầu shot kế bên làm keyframe cuối. Sau mỗi bản sửa, luôn tile khung ở CẢ hai mép cắt (trước và sau đoạn được render lại).

- **Mép cắt khi render lại một đoạn (bài học TVC06 v4):** Muse hay giải quyết chỗ nối bằng cách để nhân vật ĐỨNG YÊN ~0.5–0.75s rồi DISSOLVE sang shot sau (thấy 2 nhân vật mờ chồng nhau). Cả hai đều là lỗi. Trong prompt luôn ghi: "chuyển động liên tục đến frame cuối, kết thúc đúng tư thế/vị trí ở frame đầu shot sau, HARD CUT, không dissolve/crossfade". QC: tile 10fps quanh mép cắt (`fps=10,tile=14x1`) + motion_qc tại 0.5s trước cắt.
- **Tìm mốc cắt nhanh:** `ffmpeg -i F -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | grep -o "pts_time:[0-9.]*"` → dùng mốc này để ghi chính xác đoạn cần render lại trong prompt.
- **Quy tắc diễn xuất áp cả cho cảnh ăn mừng:** "cười bằng mắt, ngậm miệng" vẫn áp dụng khi reo hò/mừng bàn thắng – yêu cầu mừng bằng CỬ CHỈ (giơ nắm tay, đập tay, ôm vai) thay vì há miệng.
- **Tab Muse mở lại:** sau khi Chrome mất tab group phải tabs_context_mcp(createIfEmpty) + navigate lại thread; trang cần ~15–20s mới render lịch sử; video lazy-load nên chỉ vài `<video>` có src – reload trang để thấy file mới nhất. Viewport có thể đổi (1512×788 → composer ~(970,748)).
- **Xác nhận sửa mép cắt (TVC06 v5):** prompt "continuous motion to the last frame, end on the exact pose of the next shot, HARD CUT, no dissolve" thì Muse cắt cứng được, không còn bóng mờ. motion_qc (residual toàn khung) có thể báo S giả khi nhân vật nhỏ cử động trên nền tĩnh. Khi đó đo thêm độ chênh pixel trong vùng nhân vật mỗi 0.2s: chỉ 1 nhịp ≈0 là khựng tự nhiên, nhiều nhịp liền là đứng hình.
- **Mừng bàn thắng không mở miệng (TVC07 motion_v2):** viết "celebrate with hugs, shoulder pats, raised fists; mouths closed or smiling, nobody shouts or talks" thì có được cười hở răng nhưng không hò hét/khẩu hình nói, đạt luật diễn xuất. Vẫn kiểm crop mặt full-res ở giữa đoạn và đếm tay trong cụm ôm nhau.

## Bao bì bị dán như sticker (rà lại 10 TVC ngày 2026-10-01; người dùng chỉ ra)
- **Lỗi nằm ngay ở bước tạo keyframe ảnh.** Khi đưa ảnh bao bì thật vào và yêu cầu "ghép/edit từ ảnh 1", Muse không vẽ lại bao bì trong cảnh. Nó cắt một mảnh ảnh rồi dán đè lên, sau đó model video chỉ làm khung đó chuyển động. Vì vậy sửa ở bước video là vô ích, phải làm lại keyframe.
- **Các dạng lỗi đã gặp trong bản giao:**
  - 09 (khoảng 19–23s) và 10 (khoảng 17–20s): dán nguyên mảng poster gồm hộp Xí Mà, chén đỏ, nắp và đĩa đỏ, đúng như ảnh quảng cáo. Mảng này lơ lửng giữa cảnh, sai tỉ lệ, không có bóng.
  - 07 (khoảng 3–6s và 24–27s): nhãn là hình chữ nhật phẳng dán trước tô, chữ "REAL", không cong theo thân tô.
  - 01 (khoảng 22–26s) và 08 (khoảng 26s): nhãn do AI tự vẽ, không phải nhãn thật.
- **Sai lầm khi QC:** tôi chỉ kiểm nhãn có đúng chữ và đúng màu không. Nhãn đúng từng pixel lại bị coi là điểm cộng, trong khi đó chính là dấu hiệu của ảnh dán.
- **Checklist bao bì bắt buộc (soát từng khung có sản phẩm, crop full-res):**
  1. Nhãn cong theo thân trụ: chữ ở mép trái và phải co lại, mép trên và dưới là đường elip.
  2. Ánh sáng và màu của nhãn khớp với cảnh (cảnh đêm thì nhãn không được sáng kiểu studio).
  3. Có bóng tiếp xúc với mặt bàn hoặc tay. Tay hay ngón cầm phải nằm TRƯỚC bao bì.
  4. Không còn dính nền, chén hay đĩa của ảnh gốc. Không có viền trắng, không bán trong suốt.
  5. Tỉ lệ đúng với tay và người trong cảnh.
  6. Trong video, bao bì phải chuyển động và đổi phối cảnh cùng cảnh. Nếu nó đứng yên như overlay là lỗi.
- **Cách tạo đúng (cần thử nghiệm và ghi kết quả vào đây):**
  - Prompt kiểu "product as REFERENCE for the image model to render the bowl in-scene; NO cut-and-paste, NO overlay, NO compositing".
  - Mỗi keyframe chỉ đưa một ảnh studio sạch của bao bì. KHÔNG dùng poster khuyến mãi.
  - Nếu sau 2 vòng vẫn bị dán, bỏ bao bì khỏi shot đó: dùng tô giấy trơn và để hero là món ăn. Nhận diện bao bì để end card đảm nhận.
- **Kết quả thử nghiệm (TVC09 packaging_v1, vòng 1):**
  - **Đạt phần chính:**
    - Dùng ảnh studio 3D `refs/Che_XiMa_Tet.jpg` (hộp đứng có phối cảnh), không dùng poster phẳng.
    - Prompt: "TẠO LẠI keyframe bằng MODEL ẢNH sinh mới toàn khung (không dán ảnh)… hộp ĐỨNG 3D góc 3/4, RENDER trong cảnh theo ảnh tham chiếu, chỉ lấy hộp ở giữa, KHÔNG mang bục/nền/túi" + "GỬI keyframe duyệt TRƯỚC, chưa render video".
    - Kết quả: hộp có cạnh bên, ánh đèn lồng hắt lên, bóng tiếp xúc trên bàn gỗ, nhãn đọc được "CHÈ MÈ ĐEN ĂN LIỀN / XÍ MÀ".
  - **Lỗi phụ khi model ảnh sinh mới:**
    - Logo nhỏ CATHI FOOD bị viết sai, chữ micro thành chữ rác.
    - Món ăn đi lệch: chè thành thạch cục, chén đổi sang gốm nâu.
    - Cách xử lý: luôn mô tả lại món ăn và đạo cụ cho khớp các shot kề bên, rồi sửa bằng inpaint cục bộ, giữ nguyên hộp.
  - **Lưu ý UI:** sau khi file_upload, thumbnail vẫn còn trong ô soạn tin nhưng ảnh VẪN được gửi kèm tin nhắn (thấy ở đầu bubble). Đừng gửi lại ảnh lần nữa.
  - **Xem keyframe:** click vào ảnh trong chat để mở lightbox, rồi `zoom` vùng hộp để soi nhãn.
- **Kết quả TVC09 vòng 2 (inpaint cục bộ):**
  - Đạt: chè sệt mịn, chén sứ đỏ son có nắp, logo đọc đúng CATHI FOOD.
  - Lỗi mới: để xử lý chữ micro, Muse "làm mờ bằng code", tạo ra một DẢI BLUR XÁM trên nhãn trông như vết che. Đây cũng là lỗi.
  - Cách xử lý: yêu cầu thay bằng nền trơn cùng màu và vân giấy của nhãn. Từ nay prompt ghi luôn "chữ micro: thay bằng nền trơn của nhãn, KHÔNG blur".
  - Nếu chỉ còn một lỗi nhỏ, gộp lệnh sửa và lệnh render trong cùng một tin nhắn ("sửa X rồi RENDER luôn, không cần hỏi lại") để tiết kiệm một vòng chờ. Sau đó QC video thật kỹ.
- **Kết quả TVC10 packaging_v1 vòng 1:** đạt ngay.
  - Hộp Xí Mà 3D góc 3/4 trên bàn gỗ cắm trại, ăn ánh đèn dây ấm, tay mẹ cầm thìa nằm trước hộp.
  - Ref là `Che_XiMa_Tet.jpg` (studio 3D) cộng với mô tả cảnh cũ.
- **UI: lỗi mất chữ khi gõ.** Sau khi nhấn Escape đóng lightbox, hoặc ngay sau navigate hay file_upload, lần click (1000,724) đầu tiên có thể không focus được ô soạn tin, và `type` mất trắng mà không báo lỗi.
  - Luôn `zoom` vùng composer sau khi gõ để thấy chữ đã vào. Nếu trống, click (950,725) rồi gõ lại.
- **TVC07 (lỗi gốc):** ở 3–6s và 24–27s, nhãn là các khung chữ nhật phẳng dán đè lên tô (có cả chữ "REAL"), và tô 3–6s có sợi mì vàng xoăn.
  - Ref dùng để render lại: `refs/MQ_TomThit.jpg` (tô 3D thấp rộng, nắp đen, trên bục đỏ) và `refs/MQ_4Vi.jpg` (4 vị).
- **SỬA ghi chú UI file_upload (TVC07):** file_upload báo "Uploaded 2 files" nhưng ảnh có thể KHÔNG được đính kèm.
  - Gặp khi upload ngay sau navigate: composer không hiện thumbnail, bubble gửi đi không có ảnh, và Muse tự vẽ nhãn sai ("MY QUANG" không dấu).
  - Quy tắc: sau file_upload, `zoom` vùng composer, PHẢI thấy thumbnail rồi mới gõ và gửi. Sau khi gửi, kiểm tra bubble có ảnh.
  - Không thấy ảnh thì Muse không nhận được ref.
- **TVC07 vòng 1 (không có ref):** Muse render tô vào cảnh tốt (cong, ăn sáng, tay trước, bóng), nhưng nhãn tự chế và tô ở cảnh cầm lên lại cao như hộp kem.
  - Kết luận: phần "render trong cảnh" đã giải được bằng prompt. Phần "đúng nhãn thật" bắt buộc phải có ảnh ref đính kèm, kèm mô tả chi tiết thiết kế nhãn (nền, phác họa, băng màu, chữ có dấu).
- **TVC10 packaging_v1: ĐẠT.** Quy trình chuẩn: keyframe sinh mới với ref studio 3D → duyệt keyframe → render (dolly nhẹ, hộp đứng yên).
  - Model video giữ nhãn ổn định suốt 4s. Lỗi duy nhất: logo nhỏ trên đỉnh hộp bị đổi chữ.
  - QC nên thêm bước pixel diff từng giây giữa bản mới và bản cũ, để chứng minh chỉ đoạn được sửa thay đổi.
  - Muse ghép rất chuẩn: diff bằng 0 ở mọi giây khác.
