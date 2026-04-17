import re
import unicodedata


def sanitize_filename(filename: str) -> str:
    """
    Chuẩn hoá tên file để dùng làm public_id trên Cloudinary:
    - Tách phần tên và phần mở rộng
    - Chuẩn hoá Unicode → bỏ dấu tiếng Việt / Latin có dấu
    - Thay khoảng trắng và ký tự đặc biệt bằng dấu gạch dưới
    - Chỉ giữ lại [a-z0-9._-]
    - Xoá dấu gạch dưới/gạch ngang thừa ở đầu/cuối

    Ví dụ:
        "Hình ảnh con heo (1).jpg"  → "hinh_anh_con_heo_1.jpg"
        "pig detect—test.mp4"       → "pig_detect_test.mp4"
        "Ảnh chụp 2024/01/01.png"  → "anh_chup_2024_01_01.png"
    """
    if not filename:
        return "file"

    # Tách tên và đuôi file
    if "." in filename:
        *parts, ext = filename.rsplit(".", 1)
        name = ".".join(parts)
        ext  = ext.lower()
    else:
        name = filename
        ext  = ""

    # Chuẩn hoá Unicode NFKD → tách ký tự base khỏi dấu
    name = unicodedata.normalize("NFKD", name)
    # Bỏ các combining characters (dấu)
    name = "".join(c for c in name if not unicodedata.combining(c))

    # Chuyển thường
    name = name.lower()

    # Thay ký tự đặc biệt + khoảng trắng → dấu gạch dưới
    name = re.sub(r"[^\w.-]", "_", name)

    # Gộp nhiều dấu gạch dưới/gạch ngang liên tiếp thành 1
    name = re.sub(r"[_\-]{2,}", "_", name)

    # Xoá dấu gạch dưới/gạch ngang ở đầu và cuối
    name = name.strip("_-")

    if not name:
        name = "file"

    return f"{name}.{ext}" if ext else name
