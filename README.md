# KC Gemini Logo Cleaner

Công cụ Windows nhỏ gọn để xử lý hàng loạt **logo nhìn thấy ở góc phải dưới** ảnh do Gemini/Nano Banana tạo. Công cụ chạy hoàn toàn trên máy, không tải ảnh lên website và không chỉnh sửa ảnh nguồn.

> Phạm vi: chỉ xử lý dấu/logo nhìn thấy. Công cụ không tìm cách xóa SynthID ẩn hoặc thay đổi nguồn gốc nội dung AI. Chỉ sử dụng với ảnh bạn có quyền chỉnh sửa.

## Tính năng

- Chọn một thư mục và xử lý PNG, JPG, JPEG, WebP, BMP hoặc TIFF.
- Có thể quét cả thư mục con và giữ nguyên cấu trúc folder.
- Vùng logo được tính theo tỷ lệ ảnh nên hoạt động với nhiều độ phân giải.
- Xem trước vùng mask và kết quả trước khi chạy hàng loạt.
- Tự xác định vị trí logo Gemini ở góc phải dưới; không cần bấm chọn điểm.
- Có phần tinh chỉnh nâng cao dự phòng nếu Google thay đổi mẫu logo.
- Mặc định tự tìm mảng nền tương đồng gần logo để giữ đường nét và texture.
- Có Telea và Navier–Stokes làm phương án dự phòng cho ảnh quá nhỏ.
- Có thể dừng batch sau ảnh đang xử lý.
- Ảnh gốc không bị ghi đè.
- Tạo `processing-report.json` sau mỗi lần chạy.
- Hỗ trợ đường dẫn Windows có dấu và khoảng trắng.

## Chạy nhanh trên Windows

Yêu cầu: Python 3.10 trở lên.

1. Tải hoặc clone repository.
2. Bấm đúp `run.bat`.
3. Lần đầu công cụ tự tạo `.venv` và cài thư viện.
4. Chọn thư mục ảnh nguồn.
5. Xem nhanh kết quả tự động trên một vài ảnh.
6. Bấm **Xử lý toàn bộ ảnh**; không cần chọn điểm logo.

Kết quả mặc định nằm trong:

```text
<thư mục nguồn>\KC_Logo_Cleaned\
```

## Thiết lập mặc định

Preset ban đầu dành cho logo nhỏ ở góc phải dưới:

- Chiều rộng: 4.0% ảnh.
- Chiều cao: 7.5% ảnh.
- Lề phải: 5.0%.
- Lề dưới: 9.3%.
- Padding: 0.4% cạnh ngắn.
- Mask dự phòng: hình chữ nhật bo góc.
- Thuật toán mặc định: Texture Patch tự động.

Các giá trị này được hiệu chỉnh từ ảnh Gemini/Google Flow 1376×768 thực tế và tự co giãn theo độ phân giải. Chỉ mở **Tinh chỉnh nâng cao** nếu Google thay đổi vị trí logo trong tương lai.

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

## Đóng gói bản Windows

Chạy `build-exe.bat`. Kết quả nằm trong:

```text
dist\KC Gemini Logo Cleaner\
```

## Giới hạn

- Kết quả tốt nhất khi logo nhỏ và nằm cố định ở góc phải dưới.
- Nền có chữ nhỏ, khuôn mặt hoặc đường nét rất phức tạp có thể cần điều chỉnh mask và kiểm tra thủ công.
- Công cụ không tự suy đoán logo ở vị trí khác.
- Phiên bản nhẹ này dùng tìm kiếm texture cục bộ kết hợp OpenCV; chưa đóng gói mô hình LaMa dung lượng lớn.
