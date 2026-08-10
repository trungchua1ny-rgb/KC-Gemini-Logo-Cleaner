# KC Gemini Logo Cleaner

Công cụ Windows xử lý hàng loạt logo nhìn thấy ở góc phải dưới ảnh do Gemini/Nano Banana tạo. Ảnh được xử lý trên máy và file nguồn không bị chỉnh sửa.

> Phạm vi: chỉ xử lý dấu/logo nhìn thấy. Công cụ không xóa SynthID ẩn hoặc thay đổi nguồn gốc nội dung AI. Chỉ sử dụng với ảnh bạn có quyền chỉnh sửa.

## Tính năng

- Xử lý PNG, JPG, JPEG, WebP, BMP và TIFF theo thư mục.
- Quét thư mục con và giữ nguyên cấu trúc thư mục đầu ra.
- Tự xác định vùng logo Gemini góc phải dưới, co giãn theo độ phân giải; không cần bấm chọn điểm.
- AI LaMa inpainting dùng vùng ngữ cảnh rộng để phục hồi vật thể, đường nét và texture tự nhiên hơn.
- Chỉ compositing vùng mask; các pixel ngoài vùng xử lý được giữ nguyên.
- Model AI khoảng 93 MB được tải một lần và chạy local; ảnh người dùng không được tải lên dịch vụ xử lý.
- Texture Patch, Telea và Navier–Stokes được giữ làm phương án dự phòng.
- Xem trước ảnh gốc và kết quả, dừng batch, giữ metadata khi định dạng hỗ trợ.
- Không ghi đè ảnh nguồn và tạo `processing-report.json` sau mỗi lần chạy.
- Hỗ trợ đường dẫn Windows có dấu và khoảng trắng.

## Chạy nhanh trên Windows

Yêu cầu: Python 3.10 trở lên.

1. Tải hoặc clone repository.
2. Bấm đúp `run.bat`.
3. Lần đầu công cụ tự tạo `.venv`, cài thư viện và tải model AI nếu chưa có.
4. Chọn thư mục ảnh nguồn.
5. Kiểm tra preview trên một vài ảnh.
6. Bấm **Xử lý toàn bộ ảnh**.

Kết quả mặc định:

```text
<thư mục nguồn>\KC_Logo_Cleaned\
```

## Preset mặc định

Preset được hiệu chỉnh từ ảnh Gemini/Google Flow 1376×768 thực tế:

- Chiều rộng vùng logo: 5.2% ảnh.
- Chiều cao vùng logo: 9.4% ảnh.
- Lề phải: 4.7%.
- Lề dưới: 8.9%.
- Padding an toàn: 0.8% cạnh ngắn.
- Mask: hình chữ nhật bo góc.
- Thuật toán: AI LaMa inpainting.

Chỉ mở **Tinh chỉnh nâng cao** nếu Google thay đổi vị trí hoặc kích thước logo.

## Dòng lệnh

```powershell
python -m kc_logo_cleaner.cli "D:\AnhGemini"
```

Chọn output riêng:

```powershell
python -m kc_logo_cleaner.cli "D:\AnhGemini" --output "D:\AnhDaXuLy"
```

## Kiểm thử

```powershell
python -m unittest discover -s tests -v
```

## Đóng gói Windows

Chạy `build-exe.bat`. Kết quả nằm trong:

```text
dist\KC Gemini Logo Cleaner\
```

## Giới hạn

- Kết quả tốt nhất khi logo nhỏ và nằm đúng preset góc phải dưới.
- AI cải thiện đáng kể vùng có đường nét và vật thể, nhưng không thể khôi phục chính xác 100% chi tiết gốc đã bị logo ghi đè.
- Chữ nhỏ, khuôn mặt hoặc chi tiết hình học rất phức tạp ngay dưới logo vẫn cần kiểm tra preview.
- Công cụ không tự suy đoán logo ở vị trí khác.
