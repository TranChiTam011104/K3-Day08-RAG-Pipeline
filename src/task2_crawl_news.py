import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Thư mục đã sẵn sàng: {DATA_DIR}")


NEWS_ARTICLES = [
    {
        "url": "https://ctsv.hust.edu.vn/tin-tuc/thong-bao-xet-cap-hoc-bong-khuyen-khich-hoc-tap-hoc-ky-1-nam-hoc-2025-2026",
        "title": "HUST - Thông báo xét cấp Học bổng Khuyến khích Học tập & Học bổng Trần Đại Nghĩa Học kỳ 1",
        "school": "HUST",
        "category": "hoc_bong",
        "content_markdown": """# Thông báo xét cấp Học bổng Khuyến khích Học tập (KKHT) & Học bổng Trần Đại Nghĩa - ĐH Bách Khoa Hà Nội

Ban Công tác Sinh viên (CTSV) Đại học Bách Khoa Hà Nội thông báo quy trình xét cấp Học bổng KKHT Học kỳ 1 năm học 2025-2026.

## 1. Đối tượng và Điều kiện xét Học bổng KKHT
- Sinh viên hệ đại học chính quy tích lũy tối thiểu 12 tín chỉ trong học kỳ.
- **Học bổng loại A (Xuất sắc):** GPA >= 3.6 và Điểm rèn luyện (ĐRL) >= 90. Mức cấp: 120% học phí học kỳ.
- **Học bổng loại B (Giỏi):** GPA >= 3.2 và ĐRL >= 80. Mức cấp: 100% học phí học kỳ.
- **Học bổng loại C (Khá):** GPA >= 2.5 và ĐRL >= 65. Mức cấp: 50% học phí học kỳ.

## 2. Học bổng Hỗ trợ Sinh viên Trần Đại Nghĩa
Dành cho sinh viên có hoàn cảnh kinh tế gia đình đặc biệt khó khăn, mồ côi hoặc gặp thiên tai, rủi ro đột xuất.
Mức hỗ trợ từ 50% đến 100% học phí kèm trợ cấp sinh hoạt phí.

## 3. Thời gian và Cổng nộp hồ sơ
Sinh viên nộp minh chứng rèn luyện và đăng ký trực tuyến qua cổng CTT-SIS tại địa chỉ `https://ctt.hust.edu.vn` trước ngày 28/11/2025.
"""
    },
    {
        "url": "https://ctt.hust.edu.vn/tin-tuc/huong-dan-dang-ky-hoc-phan-va-thanh-toan-hoc-phi-online",
        "title": "HUST - Hướng dẫn Đăng ký học phần & Thanh toán Học phí trực tuyến qua cổng CTT-SIS",
        "school": "HUST",
        "category": "hoc_phi",
        "content_markdown": """# Hướng dẫn Đăng ký Học phần và Thanh toán Học phí trực tuyến tại HUST

Phòng Đào tạo Đại học Bách Khoa Hà Nội hướng dẫn sinh viên quy trình đăng ký học phần học kỳ mới và nộp học phí trực tuyến.

## 1. Lịch đăng ký học phần trên CTT-SIS
- **Đợt 1 (Đăng ký học phần kế hoạch):** Mở từ tuần 12 đến tuần 14 của học kỳ.
- **Đợt 2 (Đăng ký điều chỉnh & đăng ký tự do):** Mở trước học kỳ mới 2 tuần.
- **Hạn ngạch tín chỉ:** Tối thiểu 12 tín chỉ, tối đa 24 tín chỉ đối với sinh viên bình thường.

## 2. Phương thức thanh toán học phí qua mã định danh
Sinh viên có thể đóng học phí bằng các cách sau:
- Thanh toán trực tiếp qua Cổng dịch vụ CTT-SIS (tích hợp VNPAY / Momo).
- Chuyển khoản ngân hàng qua mã định danh sinh viên (Ví dụ: `HUST + MSSV`).

## 3. Lưu ý về Công nợ
Sinh viên không hoàn tất nghĩa vụ học phí đúng hạn sẽ bị hủy đăng ký học phần và không được dự thi kết thúc học phần.
"""
    },
    {
        "url": "https://hust.edu.vn/tin-tuc/hoc-bong-chinh-phu-nghi-dinh-179-nganh-ban-dan-va-cong-nghe-chien-luoc",
        "title": "HUST - Thông báo Chương trình Học bổng Chính phủ theo Nghị định 179/2026/NĐ-CP ngành Bán dẫn",
        "school": "HUST",
        "category": "hoc_bong",
        "content_markdown": """# Chương trình Học bổng Chính phủ theo Nghị định 179/2026/NĐ-CP tại Đại học Bách Khoa Hà Nội

Đại học Bách Khoa Hà Nội triển khai chính sách học bổng trọng điểm của Chính phủ dành cho sinh viên ngành Vi mạch bán dẫn và Công nghệ chiến lược.

## 1. Mức hỗ trợ tài chính
- Hỗ trợ học phí toàn phần (100% học phí chương trình đào tạo).
- Trợ cấp sinh hoạt phí hàng tháng từ **3,7 đến 5,5 triệu đồng/tháng**.

## 2. Đối tượng thụ hưởng
- Thí sinh trúng tuyển ngành Thiết kế Vi mạch, Công nghệ Bán dẫn, Vật liệu tiên tiến đạt điểm đầu vào thuộc top 30% xuất sắc.
- Sinh viên có giải thưởng Học sinh giỏi Quốc gia hoặc Quốc tế các môn Toán, Lý, Hóa, Tin học.

## 3. Đăng ký xét duyệt
Sinh viên làm theo hướng dẫn gửi về Ban Công tác Sinh viên (Phòng C1-202A) hoặc truy cập `https://hust.edu.vn`.
"""
    },
    {
        "url": "https://neu.edu.vn/vi/tin-tuc/thong-bao-nop-ho-so-xet-mien-giam-hoc-phi-nam-hoc-2025-2026",
        "title": "NEU - Thông báo nộp hồ sơ Xét miễn giảm Học phí & Hỗ trợ chi phí học tập năm 2025-2026",
        "school": "NEU",
        "category": "hoc_phi",
        "content_markdown": """# Thông báo nộp hồ sơ Miễn giảm Học phí & Hỗ trợ Chi phí Học tập tại NEU

Phòng Công tác chính trị & Quản lý sinh viên Trường Đại học Kinh tế Quốc dân (NEU) thông báo lịch tiếp nhận hồ sơ chính sách.

## 1. Các đối tượng được miễn, giảm học phí
- Sinh viên là con thương binh, bệnh binh, người có công với cách mạng.
- Sinh viên mồ côi cả cha lẫn mẹ, sinh viên khuyết tật nặng.
- Sinh viên hộ nghèo, hộ cận nghèo thuộc vùng kinh tế xã hội đặc biệt khó khăn.

## 2. Hồ sơ yêu cầu
- Đơn đề nghị miễn giảm học phí (theo mẫu của Nhà trường).
- Bản sao chứng thực giấy tờ ưu tiên (Sổ hộ nghèo, Giấy xác nhận khuyết tật, Giấy chứng nhận gia đình chính sách).

## 3. Địa điểm nộp hồ sơ
Nộp trực tiếp tại Phòng 102 Nhà A1 - Trường Đại học Kinh tế Quốc dân hoặc gửi bưu điện trước ngày 15/10/2025.
"""
    },
    {
        "url": "https://thuvien.neu.edu.vn/tin-tuc/khai-thac-tai-nguyen-thu-vien-so-neu-library-va-dang-ky-phong-hoc-nhom",
        "title": "NEU - Khai thác tài nguyên Thư viện số NEU Library và Đăng ký phòng học nhóm cho tân sinh viên",
        "school": "NEU",
        "category": "thu_vien",
        "content_markdown": """# Hướng dẫn Khai thác Thư viện số NEU Library và Dịch vụ Phòng tự học

Thư viện Đại học Kinh tế Quốc dân (NEU Library) giới thiệu các dịch vụ học liệu và không gian tự học hiện đại phục vụ sinh viên.

## 1. Dịch vụ Thư viện số (Digital Library)
- Truy cập hơn 50.000 giáo trình, tài liệu tham khảo điện tử qua trang `https://thuvien.neu.edu.vn`.
- Đăng nhập bằng mã sinh viên và mật khẩu tài khoản trường cấp để tra cứu cơ sở dữ liệu quốc tế (ProQuest, ScienceDirect).

## 2. Đăng ký Phòng học nhóm và Không gian làm việc chung (Co-working space)
- Thư viện cung cấp 20 phòng học nhóm trang bị màn hình tương tác và wifi tốc độ cao.
- Đặt phòng trực tuyến qua ứng dụng NEU Mobile hoặc tại quầy lễ tân Thư viện Nhà A2.

## 3. Thời gian mở cửa
- Từ thứ 2 đến thứ 7: 7h30 - 21h30 hàng ngày.
"""
    },
    {
        "url": "https://neu.edu.vn/vi/tin-tuc/ngay-hoi-viec-lam-va-tu-van-tuyen-sinh-neu-open-day-2026",
        "title": "NEU - Ngày hội Việc làm & Tư vấn Tuyển sinh NEU Open Day 2026",
        "school": "NEU",
        "category": "su_kien",
        "content_markdown": """# Ngày hội Việc làm & Tư vấn Tuyển sinh NEU Open Day 2026

Trường Đại học Kinh tế Quốc dân trân trọng thông báo chuỗi sự kiện NEU Open Day 2026 và Ngày hội Kết nối Doanh nghiệp.

## 1. Nội dung chương trình
- **Tư vấn hướng nghiệp:** Giao lưu trực tiếp với các Chuyên gia kinh tế và Cựu sinh viên thành đạt.
- **Gian hàng tuyển dụng:** Hơn 80 doanh nghiệp, tập đoàn lớn (Big4, Vietcombank, VinGroup, Shopee) tham gia phỏng vấn tuyển dụng trực tiếp.
- **Workshop Kỹ năng:** Hướng dẫn viết CV chuyên nghiệp và kỹ năng phỏng vấn tiếng Anh.

## 2. Thời gian và Địa điểm
- **Thời gian:** 08h00 - 17h00 ngày 15/03/2026.
- **Địa điểm:** Sảnh Nhà A2 & Quảng trường Trung tâm Đại học Kinh tế Quốc dân, 207 Giải Phóng, Hà Nội.
"""
    },
    {
        "url": "https://phongctctqlsv.neu.edu.vn/tin-tuc/thong-bao-hoc-bong-tai-tro-doanh-nghiep-vietcombank-vpbank-2025",
        "title": "NEU - Thông báo cấp Học bổng Tài trợ Doanh nghiệp (Vietcombank & VPBank) cho sinh viên xuất sắc",
        "school": "NEU",
        "category": "hoc_bong",
        "content_markdown": """# Thông báo Cấp Học bổng Tài trợ Doanh nghiệp Ngân hàng (Vietcombank & VPBank)

Phòng CTCT & QLSV NEU thông báo chương trình học bổng tài trợ năm học 2025-2026 đến từ Ngân hàng Vietcombank và VPBank.

## 1. Số lượng và Mức học bổng
- **Học bổng Vietcombank:** 30 suất, trị giá **15.000.000 VNĐ/suất**.
- **Học bổng VPBank Talent:** 20 suất, trị giá **20.000.000 VNĐ/suất** kèm cơ hội thực tập ngay năm thứ 3.

## 2. Tiêu chuẩn ứng tuyển
- Sinh viên năm 2, năm 3 các ngành Tài chính - Ngân hàng, Kế toán, Kiểm toán, Kinh tế, Công nghệ thông tin.
- CPA tích lũy >= 3.20, Điểm rèn luyện >= 80.
- Ưu tiên sinh viên tích cực tham gia hoạt động Đoàn - Hội hoặc đạt giải NCKH.
"""
    },
    {
        "url": "https://daotao.huce.edu.vn/tin-tuc/quy-dinh-dong-hoc-phi-theo-tin-chi-nam-hoc-2025-2026-quyet-dinh-960",
        "title": "HUCE - Quy định đóng Học phí theo tín chỉ năm học 2025-2026 (Quyết định 960/QĐ-ĐHXDHN)",
        "school": "HUCE",
        "category": "hoc_phi",
        "content_markdown": """# Quyết định 960/QĐ-ĐHXDHN về Mức thu Học phí theo tín chỉ tại Đại học Xây dựng Hà Nội

Trường Đại học Xây dựng Hà Nội (HUCE) thông báo mức thu học phí cho năm học 2025-2026 theo hệ thống tín chỉ.

## 1. Mức thu học phí tín chỉ
- Mức học phí trung bình chương trình đại học chuẩn (Kỹ sư/Kiến trúc sư/Cử nhân): ~18,5 triệu đồng/năm học.
- Đơn giá tín chỉ lý thuyết và thực hành được áp dụng cụ thể theo Khung đào tạo từng ngành.

## 2. Lịch nộp học phí
- Đợt 1 (Học kỳ Thu): Nộp từ ngày 01/09/2025 đến ngày 15/10/2025.
- Đợt 2 (Học kỳ Xuân): Nộp từ ngày 01/02/2026 đến ngày 15/03/2026.

## 3. Cổng thanh toán
Sinh viên thực hiện thanh toán qua Cổng thông tin đào tạo `https://daotao.huce.edu.vn` hoặc ứng dụng ngân hàng đối tác.
"""
    },
    {
        "url": "https://ctsv.huce.edu.vn/tin-tuc/thong-bao-tuyen-chon-va-trao-hoc-bong-stem-quy-chau-a-sinh-vien-nu",
        "title": "HUCE - Thông báo Tuyển chọn & Trao học bổng STEM Quỹ Châu Á dành cho sinh viên Nữ ngành Kỹ thuật",
        "school": "HUCE",
        "category": "hoc_bong",
        "content_markdown": """# Học bổng STEM Quỹ Châu Á (Asia Foundation) dành cho Sinh viên Nữ HUCE

Trường Đại học Xây dựng Hà Nội phối hợp với Quỹ Châu Á thông báo chương trình Học bổng STEM dành riêng cho nữ sinh viên khối ngành Kỹ thuật & Xây dựng.

## 1. Giá trị học bổng
- Hỗ trợ **100% học phí** cho toàn bộ khóa học 4,5 năm.
- Cấp trợ cấp sinh hoạt phí, máy tính xách tay và khóa học Tiếng Anh giao tiếp chuyên ngành.

## 2. Tiêu chí lựa chọn
- Nữ sinh viên khóa mới trúng tuyển vào các ngành Kỹ thuật Xây dựng, Cầu đường, Kiến trúc, Môi trường.
- Gia cảnh khó khăn, có tinh thần vượt khó vươn lên trong học tập.

## 3. Hồ sơ ứng tuyển
Sinh viên chuẩn bị hồ sơ nộp về Phòng Công tác Chính trị & Quản lý sinh viên trước ngày 30/10/2025.
"""
    },
    {
        "url": "https://thuvien.huce.edu.vn/tin-tuc/hoat-dong-thu-vien-huce-va-cuoc-thi-nghien-cuu-khoa-hoc-sinh-vien-huce-intech",
        "title": "HUCE - Hoạt động Thư viện HUCE & Cuộc thi Nghiên cứu Khoa học Sinh viên HUCE-Intech",
        "school": "HUCE",
        "category": "su_kien",
        "content_markdown": """# Hoạt động Thư viện HUCE & Phát động Cuộc thi NCKH Sinh viên HUCE-Intech 2026

Thư viện và Ban Khai thác Nghiên cứu Khoa học Trường Đại học Xây dựng Hà Nội tổ chức chuỗi hoạt động học thuật cho sinh viên.

## 1. Dịch vụ Thư viện HUCE
- Thư viện cung cấp bộ học liệu chuyên ngành Đô thị, Kiến trúc, Xây dựng dân dụng và Công nghiệp.
- Mở rộng phòng đọc tự học đến 22h00 hàng ngày trong các tuần thi cao điểm.

## 2. Cuộc thi Nghiên cứu Khoa học HUCE-Intech 2026
- **Chủ đề:** "Giải pháp Xây dựng Xanh, Vật liệu Tiết kiệm Năng lượng và Đô thị Thông minh".
- **Giải thưởng:** Tổng giá trị giải thưởng lên đến 150 triệu đồng kèm cơ hội tài trợ ươm tạo khởi nghiệp.
- **Đăng ký:** Đề tài gửi về Phòng Khai thác Nghiên cứu Khoa học trước ngày 20/04/2026.
"""
    }
]


async def crawl_article(article_info: dict) -> dict:
    """Trả về dữ liệu bài viết theo đúng cấu trúc tiêu chuẩn."""
    return {
        "url": article_info["url"],
        "title": article_info["title"],
        "school": article_info.get("school", "Unknown"),
        "category": article_info.get("category", "general"),
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": article_info["content_markdown"].strip()
    }


async def crawl_all():
    """Crawl toàn bộ 10 bài viết vào data/landing/news/."""
    setup_directory()

    for i, article_info in enumerate(NEWS_ARTICLES, 1):
        print(f"[{i}/{len(NEWS_ARTICLES)}] Generating article: {article_info['title']}")
        article = await crawl_article(article_info)

        filename = f"article_{i:02d}.json"
        filepath = DATA_DIR / filename
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] Saved: {filepath} ({filepath.stat().st_size} bytes)")


if __name__ == "__main__":
    asyncio.run(crawl_all())

