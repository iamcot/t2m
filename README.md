# t2m

Tool làm video ngắn cho anyLEARN bằng AI: viết kịch bản, đọc giọng, quay site ở khung điện thoại, dựng video 9:16 (HTML → PNG → ffmpeg), phụ đề tô từng từ, nhạc nền; người duyệt xong mới xuất file cho Facebook / TikTok / YouTube / Zalo hoặc gửi lên Khám phá (bài chờ duyệt trong back office).

Kế hoạch và tiến độ nằm ở repo anyLEARN: `plans/19-marketing-t2m.md` (task 19.B* là của repo này) và `plans/PROGRESS.md`, Giai đoạn 5.

## Cài trên Mac

```bash
brew install ffmpeg python@3.12
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev,whisper]'      # whisper: căn phụ đề chính xác (mlx-whisper, chỉ Apple Silicon)
playwright install chromium
cp t2m.example.toml t2m.toml         # điền số điện thoại tài khoản demo và Studio
export T2M_DEMO_PASSWORD=...         # mật khẩu chỉ để trong môi trường
```

Giọng tiếng Việt miễn phí của macOS: System Settings > Accessibility > Spoken Content > System voice > Manage Voices > Tiếng Việt > **Linh**. Nghe thử: `t2m voices try ro_rang`.

## Làm một video

```bash
t2m new briefs/2026-11-04-tim-kiem.toml --day 20261104   # tạo job từ brief
t2m script 20261104-tim-kiem-thong-minh                    # AI viết kịch bản (mặc định claude -p) + kiểm tra
t2m record 20261104-tim-kiem-thong-minh                    # quay các shot trên site bằng tài khoản demo
t2m render 20261104-tim-kiem-thong-minh                    # giọng, cảnh, phụ đề, nhạc -> final.mp4, poster.jpg
t2m review 20261104-tim-kiem-thong-minh                    # đọc lại kịch bản, caption, mở video
t2m approve 20261104-tim-kiem-thong-minh --by "Tên người duyệt"
t2m publish 20261104-tim-kiem-thong-minh                   # jobs/<id>/export: video, poster, .srt, caption từng kênh có UTM
t2m publish 20261104-tim-kiem-thong-minh --to explore      # gửi lên Khám phá bằng tài khoản Studio (chờ duyệt)
```

- Sửa câu: mở `jobs/<id>/script.json`, sửa, chạy lại `t2m render` (giọng chỉ đọc lại cảnh có chữ đổi). Hoặc viết JSON tay rồi `t2m script <id> --from file.json`.
- Bản nháp không cần giọng thật: `t2m render <id> --voice nhap` (im lặng, đúng thời lượng).
- Quay lại một shot: `t2m record <id> --shot loc-tuoi`.
- Chi phí AI: `t2m usage` (bảng `ai_usage` trong `t2m.db`).

## Brief

File TOML do người làm viết (ví dụ `briefs/2026-11-04-tim-kiem.toml`): template, chủ đề, góc nói, link, chiến dịch (`utm_campaign`), ghi chú, khóa được nhắc (`[[items]]` id + tên + giá, kiểm tra với API), giọng theo nhân vật (`[voices]`) và các **shot** quay màn hình. Shot là thao tác thật trên site (`goto`, `tap`, `type`, `scroll`, `wait`, `press`) với selector Playwright, vì AI không đoán được selector. AI chỉ viết lời đọc, chữ trên hình, thứ tự cảnh và caption.

Tài khoản demo dùng dữ liệu `scripts/seed_today_demo.sql` của repo anyLEARN, không bao giờ dữ liệu khách thật.

## Kiểm tra tự động (`t2m check`)

- Số chữ lời đọc: 140 đến 170 cho 60 giây (tính theo độ dài template).
- Viết đúng "anyLEARN", "anyPoint" (không "điểm"), "Leo Xu".
- Lời hứa: chỉ "giá bằng hoặc rẻ hơn tại trường", hoàn tiền chỉ khi "lớp không mở"; câu tuyệt đối (rẻ nhất, cam kết, 100%...) bị nhắc.
- Tên và giá khóa trong brief khớp API.
- Shot được dùng phải có trong brief, link phải là đường dẫn trên anylearn.vn.

`render` và `approve` từ chối khi còn lỗi (render có `--force` cho bản nháp).

## Giọng đọc

`config/voices.toml`: mỗi hồ sơ là nhà TTS + giọng + tốc độ + cao độ. Template chọn giọng người dẫn (`ro_rang` cho giới thiệu tính năng, `am_tram` cho khoa học / lịch sử, `tre_nhi_nhanh` cho hài / đố vui), brief đổi được theo nhân vật. Nhà TTS: `say` (macOS, miễn phí), `fpt` (FPT.AI, `FPT_TTS_API_KEY`), `silent` (nháp). Thêm nhà mới: một class có `synthesize(text, profile, out)` trong `src/t2m/tts/providers.py`. Không nhân bản giọng trẻ em thật.

## Dựng video

1080x1920, 30 fps. Cảnh `card`: HTML (font Be Vietnam Pro, màu thương hiệu, Leo) chụp bằng Playwright, đẩy chậm bằng `zoompan`. Cảnh `screen`: bản quay site đặt trong khung điện thoại, tiêu đề phía trên. Chuyển cảnh `xfade`, phụ đề ASS tô từng từ (mốc thời gian từ mlx-whisper khi có, không thì chia theo độ dài chữ), nhạc nền trong `assets/music/` tự hạ khi có giọng (`sidechaincompress`), `loudnorm` -14 LUFS, mã hóa `h264_videotoolbox` trên Mac. Ảnh chụp từng shot nằm ở `jobs/<id>/carousel/` để làm bài carousel.

## Chưa làm

Các template nội dung khác (19.B5), ảnh chế / truyện nhiều khung (19.B6), trang duyệt FastAPI và đăng thẳng lên YouTube / Facebook / TikTok (19.B7), `t2m stats` và `t2m plan` theo số liệu (19.B8, cần UTM của 19.A4). Link công khai Khám phá `/fun/explore/{id}/{slug}` cần 19.A3 bên anyLEARN; trước đó caption trỏ về link của brief. Tài khoản creator "anyLEARN Studio" dùng mật khẩu đăng nhập cho tới khi có khóa API cho máy (19.A6).

## Test

```bash
pytest
```

Test dựng video đầu cuối (`tests/test_render_e2e.py`) cần ffmpeg và Chromium của Playwright; nó quay một trang giả trong `tests/fixtures/`, không gọi site thật.
