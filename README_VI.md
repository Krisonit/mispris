# MiSPIS – Lab 5: BOM cho Flower Shop

**Cơ sở:** file của bạn `main_new.py` + mô tả `Описание_доработки_flower_shop_задание_5_исправлено.docx`. Ứng dụng chỉ mở rộng API và PostgreSQL; **không phải sửa `catalog1.html` và không lập trình đơn hàng.**

## Các file

- `main_new_lab5.py`: bản chỉnh sửa từ backend gốc, đăng ký API BOM dưới `/bom`; giữ API cũ; chặn xóa sản phẩm/danh mục có lịch sử BOM và chặn đổi đơn vị của sản phẩm đã có phiên bản.
- `bom_lab5.py`: 10 model dữ liệu và xử lý phiên bản, BOM lồng nhau, sửa đổi, quy tắc cấu hình, lưu snapshot variant.
- `lab5_migration.sql`: thêm cột `products.is_composite` và 10 bảng mới mà không xóa catalog cũ.
- `demo_lab5.py`: tự tạo **dữ liệu kiểm thử LAB5_ trong chính catalog đang dùng**, kiểm tra cả 3 ví dụ qua REST API (lồng nhau, sửa đổi, cấu hình); không tạo bảng danh mục hoa riêng.
- `test_lab5.py`: bộ test bằng SQLite, không cần PostgreSQL; dành cho kiểm tra logic cục bộ.
- `requirements_lab5.txt`: các thư viện Python.

## 1. Sao lưu PostgreSQL trước

Mở PowerShell ở thư mục chứa file:

```powershell
# Ví dụ nếu pg_dump / psql đã có trong PATH
pg_dump -U postgres -d flower_shop_new -Fc -f backup_before_lab5.dump
```

**Không chạy migration trước khi có bản sao lưu.** Nếu database khác tên hoặc PostgreSQL dùng user khác, thay theo môi trường của bạn.

## 2. Cài đặt dependencies

```powershell
py -m pip install -r requirements_lab5.txt
```

## 3. Chạy migration một lần

```powershell
psql -U postgres -d flower_shop_new -v ON_ERROR_STOP=1 -f lab5_migration.sql
```

Migration tạo `spec_versions`, `spec_items`, `spec_changes`, `spec_config_params`, `spec_rules`, `spec_rule_conditions`, `spec_param_links`, `spec_variants`, `variant_nodes`, `variant_values`.

> Chạy migration trước khi khởi động backend vì model `Product` mới có cột `is_composite`.

## 4. Khởi động API

Đặt `main_new_lab5.py` và `bom_lab5.py` **cùng một thư mục**. Backend mới đọc thông tin kết nối từ `FLOWER_SHOP_DATABASE_URL`, không chứa password trong source:

```powershell
$env:FLOWER_SHOP_DATABASE_URL = "postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/flower_shop_new"
py -m uvicorn main_new_lab5:app --host 127.0.0.1 --port 8001 --reload
```

Nếu mật khẩu có ký tự đặc biệt, phải URL-encode; ví dụ `@` → `%40`.

Mở API docs: `http://127.0.0.1:8001/docs`, tìm nhóm `/bom/...`.

## 5. Tự tạo dữ liệu demo và xác minh API

Trong cửa sổ PowerShell khác:

```powershell
py demo_lab5.py
```

Demo sử dụng API đang chạy tại `http://127.0.0.1:8001` (đổi bằng biến `FLOWER_SHOP_API` nếu cần). Chương trình tạo hoặc tìm dữ liệu test có code `LAB5_...` trong bảng `products`, không xóa dữ liệu có sẵn. Chạy lại không tạo trùng sản phẩm/bản thông số đầu tiên.

Kết quả minh họa kỳ vọng:

- 2 × `Весенний`: **10** роз, **6** хризантем, **6** nhánh зелень, **2** giấy gói, **2 m** ruy băng.
- `Модификация B`: có bó hoa, bao bì và открытка; **không có конфеты**.
- Cấu hình `L` + `large`: **15** hoa; cấu hình `L` + `small` bị từ chối.

## 6. Thử API thủ công qua Swagger

### A. Tạo phiên bản BOM

`POST /bom/products/{product_id}/versions` (ID là sản phẩm đã có trong catalog):

```json
{
  "for_quantity": 1,
  "comment": "Базовая спецификация букета",
  "items": [
    {"component_product_id": 101, "quantity": 5},
    {"component_product_id": 102, "quantity": 1}
  ]
}
```

**Lưu ý:** `101` và `102` là ID ví dụ. Hãy thay bằng ID thực tế của hoa và cành lá trong PostgreSQL. Nếu gọi lại cùng API, một phiên bản mới được tạo; các phiên bản cũ giữ nguyên.

### B. Xem phiên bản và ID dòng BOM

`GET /bom/versions/{version_id}`

Kết quả có `items[].id`. Dùng ID này làm `target_item_id` khi loại bỏ/thay thế dòng trong modification.

### C. Tính toàn bộ nguyên liệu

`POST /bom/expand`

```json
{"version_id": 1, "quantity": 2}
```

Kết quả gồm `tree` (có các cụm lồng nhau), `leaf_summary` (tổng nguyên liệu cuối cùng), `matched_assemblies` (cụm trong một loại được chọn). Tùy chọn `category_id` để lọc cây danh mục bao gồm các con nhưng vẫn duyệt toàn bộ nhánh trung gian.

### D. Tạo modification

`POST /bom/modifications`:

```json
{
  "name": "Набор без конфет",
  "code": "MY_GIFT_WITHOUT_SWEETS",
  "base_version_id": 1,
  "items": [{"action": "exclude", "target_item_id": 10}]
}
```

Thay `base_version_id`, `target_item_id` bằng ID thực tế. Modification kế thừa phiên bản cơ sở đã chọn, không thay đổi sản phẩm gốc.

### E. Cấu hình tham số và điều kiện

Khi tạo phiên bản mới, có thể gửi `config_params`, `rules` và `param_links` cùng lúc. Ví dụ rút gọn: tham số `SIZE` phải tồn tại trong bảng `parameters`, và giá trị `M` phải có trong `enum_values` nếu là tham số enum.

```json
{
  "items": [{"component_product_id": 101, "quantity": 5}],
  "config_params": [{"parameter_code": "SIZE", "is_required": true}],
  "rules": [{
    "rule_name": "Размер M = 9 цветов",
    "action": "quantity",
    "target_position_num": 1,
    "result_quantity": 9,
    "conditions": [{"parameter_code": "SIZE", "operator": "eq", "value_text": "M"}]
  }]
}
```

Khi mở BOM bằng `POST /bom/expand`, truyền `params`:

```json
{"version_id": 1, "quantity": 1, "params": {"SIZE": "M"}}
```

API chấp nhận `operator` gồm `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`; điều kiện trong cùng `group_num` nối AND, các nhóm khác nhau nối OR. Rule `forbid` báo lỗi và chặn lưu biến thể. Có thể đặt `node_values` theo đường dẫn BOM (ví dụ `{ "3/15": {"SIZE": "L"} }`) để chọn tham số riêng cho sản phẩm lồng nhau. `param_links` truyền tường minh tham số cha sang con, không suy đoán theo tên.

### F. Lưu một biến thể bất biến

`POST /bom/variants`:

```json
{"name":"Букет M", "version_id":1, "quantity":1, "params":{"SIZE":"M"}}
```

`GET /bom/variants/{variant_id}` sẽ đọc snapshot đã lưu, **không tính lại từ phiên bản mới nhất**.

### G. Lịch sử thay đổi

`GET /bom/products/{product_id}/history`

## 7. SQL để trình diễn trên PostgreSQL

```sql
-- Các phiên bản sản phẩm
SELECT p.name, sv.id_spec_version, sv.version_num,
       sv.base_version_id, sv.for_quantity, sv.created_at
FROM spec_versions sv JOIN products p ON p.id_product=sv.product_id
ORDER BY sv.product_id, sv.version_num;

-- Các dòng BOM với thành phần và số lượng
SELECT sv.id_spec_version, si.id_spec_item, si.position_num,
       si.action, p.name AS component, si.quantity
FROM spec_items si
JOIN spec_versions sv ON sv.id_spec_version=si.spec_version_id
LEFT JOIN spec_versions cv ON cv.id_spec_version=si.component_version_id
LEFT JOIN products p ON p.id_product=cv.product_id
ORDER BY sv.id_spec_version, si.position_num;

-- Lịch sử thay đổi
SELECT sv.product_id, sv.version_num, sc.action, sc.subject_key,
       sc.old_value, sc.new_value, sc.comment
FROM spec_changes sc JOIN spec_versions sv ON sv.id_spec_version=sc.spec_version_id
ORDER BY sc.changed_at, sc.id_change;

-- Snapshot variant đã lưu
SELECT v.id_variant, v.name, root.id_node AS root_node, root.spec_version_id
FROM spec_variants v JOIN variant_nodes root ON root.id_node=v.root_node_id;
```

## 8. Kiểm tra logic tự động

```powershell
py -m pytest -q test_lab5.py
```

Bộ test dùng SQLite riêng, không cần chạy server. Đã chạy **10 test tự động thành công**: cây nhiều cấp, cộng trùng vật liệu, sửa đổi A/B, snapshot bất biến, tham số enum và giới hạn, truyền tham số cha–con, rule xung đột, thành phần optional, lọc nhóm, số âm và số lượng phân số ở đơn vị nguyên. Một lượt kiểm thử tích hợp với API gốc trên SQLite cũng thành công.

## 9. Hạn chế cần biết

- Chưa kiểm thử kết nối với database PostgreSQL thật của bạn trong môi trường này. Trước khi nộp, chạy demo và lưu ảnh `Swagger /docs`, SQL và kết quả trên máy của bạn.
- Những phiên bản đã lưu coi như bất biến; thay đổi bằng cách gửi **một phiên bản mới gồm toàn bộ danh sách items/config/rules** (đối với phiên bản gốc). Modification lưu các **delta** dựa trên phiên bản cơ sở đã ghim. Không có endpoint sửa trực tiếp một phiên bản cũ.
- Không có giao diện chọn cấu hình, quản lý đơn hàng, nhập kho, hệ thống đổi đơn vị phức tạp, duyệt/phê duyệt phiên bản hoặc hệ thống xác thực người dùng; tài liệu không yêu cầu các phần này.
- Giá sản phẩm (`Product.price`) trong chương trình gốc vẫn là số nguyên; việc sửa loại tiền tệ nằm ngoài phạm vi lab BOM này.
- Database cần có đủ `Unit` hợp lệ cho các sản phẩm BOM. Nếu dữ liệu cũ thiếu đơn vị hoặc `ParamType`, chương trình sẽ trả lỗi giải thích để bạn bổ sung.

## 10. Các lưu ý để báo cáo và bảo vệ bằng tiếng Nga

> **Мы расширили существующий справочник изделий подсистемой BOM. Состав хранится в отдельных версиях спецификации; каждая версия неизменна.**
>
> **Модификации наследуют состав конкретной версии основы и применяют изменения по цепочке.**
>
> **Сводный расход считается рекурсивно; одинаковые конечные компоненты суммируются.**
>
> **Параметры конфигурации и правила хранятся в БД, а не жёстко задаются в коде Python.**
>
> **Сохранённые варианты содержат снимок выбранного состава и не меняются после обновления исходной спецификации.**
