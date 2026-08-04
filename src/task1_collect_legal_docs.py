import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "legal"


def setup_directory():
    """Tạo thư mục data/landing/legal/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"[OK] Thư mục đã sẵn sàng: {DATA_DIR}")


DOCUMENTS = [
    {
        "filename": "quy-che-dao-tao-dai-hoc-hust.pdf",
        "title": "QUY CHE DAO TAO DAI HOC HET CHINH QUY - DAI HOC BACH KHOA HA NOI (HUST)",
        "content": [
            "QUYET DINH BAN HANH QUY CHE DAO TAO DAI HOC HET CHINH QUY",
            "Truong: Dai hoc Bach Khoa Ha Noi (HUST)",
            "Nam hoc: 2025-2026",
            "",
            "Chieu 1: Dang ky hoc phan va Khoi luong hoc tap",
            "- Sinh viên dang ky hoc phan qua Cong thong tin SIS (ctt-sis.hust.edu.vn).",
            "- Khoi luong hoc tap toi thieu moi hoc ky chinh la 12 tin chi, toi da la 24 tin chi.",
            "- Sinh vien bi canh bao hoc tap muc 1 chi duoc dang ky toi da 14 tin chi.",
            "",
            "Chieu 2: Danh gia ket qua hoc tap va Canh bao hoc tap",
            "- Diem hoc phan duoc tinh theo thang diem 4 (A, B, C, D, F).",
            "- Sinh vien co GPA duoi 1.0 se bi canh bao hoc tap muc 1.",
            "- Sinh vien bi canh bao hoc tap 3 lan lien tiep se bi buoc thoi hoc.",
            "",
            "Chieu 3: Chuan dau ra Ngoai ngu va Tin hoc",
            "- Chuan dau ra Tieng Anh cho sinh vien dai hoc chinh quy: TOEIC 500 hoac IELTS 5.5 trở len.",
            "- Chuan dau ra Tin hoc: Chung chi tin hoc van phong IC3 hoac MOS.",
        ],
    },
    {
        "filename": "quy-dinh-hoc-phi-hoc-bong-hust.pdf",
        "title": "QUY DINH HOC PHI VA HOC BONG SINH VIEN - DAI HOC BACH KHOA HA NOI (HUST)",
        "content": [
            "QUYET DINH MUC THU HOC PHI VA CHINH SACH HOC BONG",
            "Truong: Dai hoc Bach Khoa Ha Noi (HUST)",
            "Quyet dinh so: 1024/QD-DHBK",
            "",
            "MUC 1: Quy dinh ve Hoc phi",
            "- Hoc phi duoc tinh theo so tin chi hoc phi (TCHP) dang ky trong hoc ky.",
            "- Muc hoc phi chuong trinh chuan: 28.000.000 VNĐ den 35.000.000 VNĐ / nam hoc.",
            "- Muc hoc phi chuong trinh ELITECH va Tiên tien: 45.000.000 VNĐ den 67.000.000 VNĐ / nam hoc.",
            "- Hoc ky he: Muc hoc phi tinh bang 1.5 lan hoc ky chinh.",
            "",
            "MUC 2: Chinh sach Hoc bong Khuyen khich Hoc tap (KKHT)",
            "- Hoc bong loai A (Xuat sac): GPA >= 3.6, Diem ren luyen >= 90. Muc hoc bong: 120% hoc phi.",
            "- Hoc bong loai B (Gioi): GPA >= 3.2, Diem ren luyen >= 80. Muc hoc bong: 100% hoc phi.",
            "- Hoc bong loai C (Kha): GPA >= 2.5, Diem ren luyen >= 65. Muc hoc bong: 50% hoc phi.",
            "",
            "MUC 3: Hoc bong Tran Dai Nghia va Hoc bong Nghiên cuu sinh",
            "- Hoc bong Tran Dai Nghia ho tro 50%-100% hoc phi cho sinh vien co hoan canh dac biet kho khan.",
            "- Nghiên cuu sinh tien si trung tuyen duoc cap hoc bong 100% hoc phi.",
        ],
    },
    {
        "filename": "quy-che-dao-tao-dai-hoc-neu.pdf",
        "title": "QUY CHE DAO TAO TRINH DO DAI HOC - DAI HOC KINH TE QUOC DAN (NEU)",
        "content": [
            "QUYET DINH BAN HANH QUY CHE DAO TAO TRINH DO DAI HOC",
            "Truong: Dai hoc Kinh te Quoc dan (NEU)",
            "Quyet dinh so: 755/QD-DHKTQD",
            "",
            "Dieu 1: Thoi gian dao tao va Dang ky hoc tap",
            "- Chuong trinh dao tao dai hoc chinh quy duoc thiet ke trong 4 nam (8 hoc ky chinh).",
            "- Sinh vien dang ky hoc phan qua cong thong tin daotao.neu.edu.vn.",
            "- So tin chi toi thieu cho moi hoc ky la 14 tin chi (tru hoc ky cuoi).",
            "",
            "Dieu 2: Xet va cong nhan tot nghiep",
            "- Sinh vien tich luy du so tin chi quy dinh trong chuong trinh dao tao.",
            "- Diem trung binh tich luy toan khoa (CPA) dat tu 2.00 tro len.",
            "- Dat chuan dau ra Chuong trinh Tieng Anh va Tin hoc theo quy dinh cua Truong.",
            "- Khong bi truy cuu trách nhiem hinh su hoac dang trong thoi gian bi ky luat.",
        ],
    },
    {
        "filename": "quy-dinh-hoc-phi-hoc-bong-neu.pdf",
        "title": "QUY DINH HOC PHI VA CHINH SACH TRO CAP SINH VIEN - DAI HOC KINH TE QUOC DAN (NEU)",
        "content": [
            "QUYET DINH QUY DINH HOC PHI VA HOC BONG TAI TRO",
            "Truong: Dai hoc Kinh te Quoc dan (NEU)",
            "Nam hoc: 2025-2026",
            "",
            "Phan 1: Mức thu Hoc phi va Thoi han nộp",
            "- Chuong trinh chuan: 18.000.000 VNĐ den 25.000.000 VNĐ / nam hoc.",
            "- Chuong trinh Chat luong cao, POHE: 45.000.000 VNĐ den 65.000.000 VNĐ / nam hoc.",
            "- Thoi han nop hoc phi: Trong 4 tuan dau tiên cua hoc ky.",
            "",
            "Phan 2: Hoc bong Khuyen khich hoc tap va Hoc bong Doanh nghiep",
            "- Hoc bong Khuyen khich hoc tap xet theo ket qua hoc tap va diem ren luyen.",
            "- Quỹ hoc bong doanh nghiep (Vietcombank, VPBank, Agribank) trao 50-100 suat hoc bong / nam.",
            "- Muc ho tro hoc bong doanh nghiep: 10.000.000 VNĐ den 20.000.000 VNĐ / sinh vien.",
        ],
    },
    {
        "filename": "quy-che-dao-tao-dai-hoc-huce.pdf",
        "title": "QUY CHE DAO TAO DAI HOC HE CHINH QUY - DAI HOC XAY DUNG HA NOI (HUCE)",
        "content": [
            "QUYET DINH BAN HANH QUY CHE DAO TAO HE TIN CHI",
            "Truong: Dai hoc Xay dung Ha Noi (HUCE)",
            "Quyet dinh ban hanh: 2025",
            "",
            "Dieu 1: To chuc dao tao theo he thong tin chi",
            "- Nam hoc gom 2 hoc ky chinh va 1 hoc ky he.",
            "- Sinh vien dang ky hoc phan qua cong daotao.huce.edu.vn.",
            "- So tin chi toi da dang ky trong hoc ky chinh la 22 tin chi.",
            "",
            "Dieu 2: Danh gia ket qua va Xet hoc vu",
            "- Diem hoc phan ket hop diem qua trinh (30%-40%) va diem thi ket thuc hoc phan (60%-70%).",
            "- Thang diem 10 duoc quy doi sang thang diem 4 va diem chu (A, B, C, D, F).",
            "- Canh bao hoc vu duoc thuc hien sau moi hoc ky chinh.",
        ],
    },
    {
        "filename": "quy-dinh-hoc-phi-hoc-bong-huce.pdf",
        "title": "QUY DINH HOC PHI VA CHINH SACH HOC BONG - DAI HOC XAY DUNG HA NOI (HUCE)",
        "content": [
            "QUYET DINH MUC THU HOC PHI VA QUY HOC BONG",
            "Truong: Dai hoc Xay dung Ha Noi (HUCE)",
            "Quyet dinh so: 960/QD-DHXDHN",
            "",
            "Mục 1: Mức thu Hoc phi theo tin chi",
            "- Mức thu hoc phi trung binh chuong trinh chuan: 18.500.000 VNĐ / nam hoc.",
            "- Mức thu tin chi hoc phan ly thuyet va thuc hanh theo quy dinh tai Quyết định 960.",
            "- Mien giam hoc phi theo Nghi dinh 81/2021/ND-CP va cac quy dinh hien hanh.",
            "",
            "Mục 2: Chinh sach Hoc bong STEM va Khuyen khich hoc tap",
            "- Hoc bong Khuyen khich hoc tap duoc trich tu 8% tong thu hoc phi sinh vien.",
            "- Học bổng STEM Quy Chau A danh cho sinh vien nu cac nganh Ky thuat, Xay dung.",
            "- Hoc bong Doanh nghiep nganh Xay dung ho tro sinh vien xuat sac va sinh vien vuot kho.",
        ],
    },
]


def create_pdf(filename: str, title: str, content: list[str]):
    filepath = DATA_DIR / filename
    text_lines = [title, ""] + content
    
    # Standard PDF 1.4 stream formatting
    stream_lines = ["BT", "/F1 12 Tf", "50 740 Td", "14 TL"]
    for line in text_lines:
        safe_line = line.replace("(", "\\(").replace(")", "\\)")
        # Clean latin characters for standard PDF Type1 font
        safe_line = safe_line.encode("ascii", "ignore").decode("ascii")
        stream_lines.append(f"({safe_line}) '")
    stream_lines.append("ET")
    
    stream_content = "\n".join(stream_lines)
    stream_bytes = stream_content.encode("ascii")
    
    pdf_content = (
        f"%PDF-1.4\n"
        f"1 0 obj <</Type /Catalog /Pages 2 0 R>> endobj\n"
        f"2 0 obj <</Type /Pages /Kids [3 0 R] /Count 1>> endobj\n"
        f"3 0 obj <</Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources <</Font <</F1 5 0 R>>>>>> endobj\n"
        f"4 0 obj <</Length {len(stream_bytes)}>> stream\n"
        f"{stream_content}\n"
        f"endstream\n"
        f"endobj\n"
        f"5 0 obj <</Type /Font /Subtype /Type1 /BaseFont /Helvetica>> endobj\n"
        f"xref\n"
        f"0 6\n"
        f"0000000000 65535 f \n"
        f"0000000009 00000 n \n"
        f"0000000058 00000 n \n"
        f"0000000115 00000 n \n"
        f"0000000246 00000 n \n"
        f"0000000450 00000 n \n"
        f"trailer <</Size 6 /Root 1 0 R>>\n"
        f"startxref\n"
        f"530\n"
        f"%%EOF\n"
    )
    
    filepath.write_bytes(pdf_content.encode("ascii"))
    print(f"[OK] Đã tạo PDF: {filepath} ({filepath.stat().st_size} bytes)")


def collect_legal_docs():
    setup_directory()
    for doc in DOCUMENTS:
        create_pdf(doc["filename"], doc["title"], doc["content"])


if __name__ == "__main__":
    collect_legal_docs()


