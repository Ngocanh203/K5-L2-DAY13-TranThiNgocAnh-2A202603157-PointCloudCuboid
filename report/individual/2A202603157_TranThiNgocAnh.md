# Báo cáo Day 13 — Trần Thị Ngọc Ánh, 2A202603157

## 1. Kết luận trước

- **Mã học viên:** `2A202603157`
- **Task CVAT:** `D13-2A202603157`
- **Job CVAT:** `18`
- **Số frame:** 10
- **Tổng số cuboid dạng Shape:** 118
- **Frame có ít cuboid nhất:** `s03f32`, với 5 cuboid
- **Kết quả tự kiểm:** 17/118 cuboid có cảnh báo

Danh sách frame gồm `s01f38`, `s01f59`, `s02f23`, `s02f40`, `s03f01`, `s03f32`, `s04f31`, `s04f56`, `s05f11` và `s05f36`. Frame đầu có 10 cuboid. Cả 10 frame đều đạt số lượng tối thiểu theo yêu cầu.

Cuboid được lưu dưới dạng Shape cho từng frame. Trong CVAT, khung **Top** dùng để kiểm tra vị trí và hướng, còn **Side** và **Front** dùng để kiểm tra chiều cao và đáy hộp. Tùy chọn **Cuboid orientation** giúp xác định hướng mũi tên. Sau khi lưu nhãn, lệnh `sync` xuất Bảng A, ảnh xem trước và phiếu tự kiểm. Các cảnh báo giúp xác định những hộp cần xem lại.

## 2. Đọc frame (Bước 2)

Trong hệ tọa độ VF, `+x` hướng sang trái xe thu dữ liệu, `+y` hướng ra phía sau và `+z` hướng lên. Phía trước xe là hướng `−y`.

Ảnh minh chứng cho hai frame đọc kỹ được đặt tên `t1-s01f38-3d.jpg`, `t1-s01f38-top.jpg`, `t1-s01f59-3d.jpg` và `t1-s01f59-top.jpg`. Ảnh nhìn từ trên xuống cần đánh dấu phía trước (`−y`), `+x` và `+y`.

| Frame | Hướng trong Top | Mặt đường | Vật xa nhất đọc được | Loại vật và vùng khuất | Cụm chưa đọc được |
|---|---|---|---|---|---|
| `s01f38` | `−y` về phía trước, `+x` sang trái, `+y` ra sau | Gần phẳng, khoảng `z = −1,7 m` | Xe con ở khoảng 47 m | Có xe con và người đi bộ. Một số cụm nằm ở hai bên và phía sau xe thu dữ liệu. | Các cụm rất thưa trong khoảng 30–50 m. |
| `s01f59` | `−y` về phía trước, `+x` sang trái, `+y` ra sau | Gần phẳng. Đáy các hộp gần nằm quanh `−1,6` đến `−1,8 m`. | Khoảng 41 m | Chủ yếu là xe con, có người đi bộ ở xa. Các vật phía sau cần đối chiếu với góc nhìn từ trên xuống. | Các vật ở xa chỉ còn vài điểm và khó nhận dạng. |

Ảnh camera giúp nhận ra loại vật, phân biệt đầu và đuôi xe, đồng thời quan sát phần vật bị che. Point cloud LiDAR giúp xác định tâm vật trong không gian, đo kích thước theo mét và kiểm tra độ cao đáy hộp so với mặt đường. Khi lướt các frame còn lại, phạm vi quan sát gồm phía trước, hai bên và phía sau xe thu dữ liệu.

| Frame lướt | Ghi chú |
|---|---|
| `s02f23` | Có nhiều xe con. Một số cuboid có cảnh báo đáy cao, cần xem lại ở Side và Front. |
| `s02f40` | Chủ yếu là xe con, ngoài ra có người đi bộ và xe hai bánh có người lái. Vật ở xa có ít điểm hơn. |
| `s03f01` | Có nhiều xe con ở gần. Phiếu tự kiểm đánh dấu một số hộp có đáy cao hơn mặt đường ước tính. |
| `s03f32` | Có `Car`, `Bus`, `Cyclist` và `Pedestrian`. Frame có 5 cuboid. |
| `s04f31` | Nhiều xe con ở gần, ngoài ra có xe buýt và xe hai bánh có người lái. |
| `s04f56` | Có `Car`, `Cyclist` và một hộp `Bus` ở rất xa. Các hộp xa khó xác nhận vì cụm điểm thưa. |
| `s05f11` | Có nhiều xe con ở các khoảng cách khác nhau, phù hợp để so sánh số điểm trong hộp. |
| `s05f36` | Có xe con và xe tải. Các cụm điểm ở xa thưa hơn rõ rệt. |

## 3. Ba cuboid có hướng dẫn (Bước 3)

Ảnh minh chứng gồm `t2-a-car.jpg`, `t2-b-bus-truck.jpg` và `t2-c-ped-cyclist.jpg`.

| Vật | Frame, idx | Class | Yaw | Đáy cuboid | Kiểm trên Top, Side, Front và camera | Kích thước dài × rộng × cao |
|---|---|---|---:|---|---|---|
| Xe con gần | `s01f38` #1 | `Car` | 271,4° | −1,719 m, sát mặt đường | Đã kiểm | 4,785 × 1,974 × 1,373 m. Chiều cao hơi thấp so với khoảng tham chiếu của sedan. |
| Xe buýt | `s03f32` #2 | `Bus` | 271,5° | −1,274 m. Cần đối chiếu với mặt đường ngay dưới xe. | Đã kiểm | 12,488 × 2,941 × 3,589 m. Chiều rộng và chiều cao lớn hơn khoảng tham chiếu của xe buýt thường. |
| Người đi bộ | `s01f38` #7 | `Pedestrian` | 265,3° | −1,125 m. Vật ở xa nên khó xác định mặt đường tại vị trí chân. | Đã kiểm | 0,888 × 0,760 × 1,673 m, phù hợp với khoảng tham chiếu cho người lớn. |

Các cụm quá thưa hoặc chưa đủ căn cứ để nhận dạng được bỏ qua. Chưa có số liệu định lượng từ vòng hiệu chuẩn để so sánh với các học viên khác.

## 4. Bốn hiện tượng chất lượng (Bước 4)

Các nguyên nhân trong bảng là giả thuyết dựa trên hình dạng và mật độ điểm quan sát được.

| Hiện tượng | Frame, ảnh và nguồn | Giả thuyết về nguyên nhân | Quan sát | Cách xử lý khi gán nhãn |
|---|---|---|---|---|
| Bóng che | `s05f11`, `t4-1-bong-che.jpg`, task cá nhân | Một vật ở gần có thể chắn tia LiDAR chiếu tới vùng phía sau. | Vùng sau vật có ít điểm hơn các vùng bên cạnh. | Bật `occluded` khi xác nhận vật bị che một phần. Chỉ mở rộng hộp đến phần có căn cứ suy ra. |
| Thưa ở xa | `s04f56`, `t4-2-thua-o-xa.jpg`, task cá nhân | Các tia LiDAR cách nhau xa hơn khi khoảng cách tăng. | Hộp `s04f56` #8 cách khoảng 50,0 m và chỉ chứa 11 điểm. | Dùng mốc nhìn thấy khoảng 15–20% thể tích để cân nhắc. Nếu điểm quá thưa và thiếu căn cứ từ hình dạng hoặc camera, bỏ qua và ghi `LOW_VISIBILITY`. |
| Phản xạ thấp hoặc ít điểm bất thường | `s05f11`, `t4-3-phan-xa-thap.jpg`, task cá nhân | Bề mặt tối, kính hoặc góc phản xạ có thể làm giảm số điểm thu được. | Một số hộp ở xa có ít điểm hơn đáng kể so với hộp gần cùng lớp. Khoảng cách cũng có thể giải thích sự khác biệt này. | Đối chiếu camera và cụm điểm xung quanh trước khi chỉnh hộp. Ghi phản xạ thấp dưới dạng giả thuyết. |
| Điểm lạ | `s02f23`, `t4-4-diem-la.jpg`, task cá nhân | Có thể do nhiễu đo hoặc phản xạ từ bề mặt khác. | Một số điểm nằm rời rạc và chưa tạo thành hình dạng có thể nhận biết. | Bỏ qua các điểm rời. Chỉ giữ hộp khi hình dạng cụm điểm hoặc camera cung cấp đủ căn cứ. |

## 5. Số đo từ cuboid (Bước 5)

Độ cao đáy hộp được tính bằng `z − h/2`. `dist_m` là khoảng cách ngang từ LiDAR đến tâm hộp, còn `r` là khoảng cách 3D đến cùng vị trí.

| Cuboid | z (m) | h (m) | z đáy (m) | dist_m (m) | r (m) | Yaw (°) | Nhận xét |
|---|---:|---:|---:|---:|---:|---:|---|
| `s01f38` #1 `Car` | −1,032 | 1,373 | −1,719 | 6,15 | 6,236 | 271,4 | Đáy sát mặt đường. |
| `s01f59` #1 `Car` | −0,916 | 1,454 | −1,643 | 3,00 | 3,133 | 271,3 | Đáy sát mặt đường. Đây là hộp gần nhất. |
| `s04f56` #11 `Bus` | −1,158 | 2,884 | −2,600 | 79,19 | 79,197 | 263,4 | Hộp nằm ngoài phạm vi 50 m và có cảnh báo về kích thước, hướng. |

Hộp gần nhất là `s01f59` #1, với khoảng cách ngang 3,00 m và khoảng cách 3D 3,133 m. Hộp xa nhất là `s04f56` #11, với khoảng cách ngang 79,19 m và khoảng cách 3D 79,197 m. Hộp này nằm ngoài phạm vi chấm của lab.

Đối chiếu Bảng 4.3, kích thước 0,888 × 0,760 × 1,673 m của `s01f38` #7 nằm trong khoảng tham chiếu cho người lớn. Xe con `s01f38` #1 có kích thước 4,785 × 1,974 × 1,373 m. Chiều dài nằm trong khoảng tham chiếu của sedan, chiều rộng nhỉnh hơn và chiều cao thấp hơn một chút. Xe cùng chiều ở `s01f38` #4 có yaw 270,0°. Xe ngược chiều ở `s05f11` #6 có yaw 90,2°.

| Cuboid | Khoảng cách ngang (m) | Số điểm trong hộp |
|---|---:|---:|
| `s01f59` #1 `Car` | 3,0 | 3.238 |
| `s05f11` #3 `Car` | 18,9 | 594 |
| `s04f31` #7 `Car` | 40,6 | 74 |
| `s04f56` #8 `Car` | 50,0 | 11 |

Trong bốn ví dụ trên, số điểm giảm từ 3.238 ở 3,0 m xuống còn 11 ở 50,0 m. Xu hướng này phù hợp với đường cong tham khảo của lab. Càng xa LiDAR, càng khó xác định biên vật chỉ từ cụm điểm.

Sau khi chạy `preview` và `selfcheck`, các trường hợp cần xem lại gồm hộp có đáy cao ở `s02f23`, `s03f01` và `s05f36`, hộp có kích thước bất thường ở `s01f59`, `s04f56` và `s05f11`, cùng hộp `Bus` ở `s04f31` #9 có nhiều điểm sát ngoài mép. Ba hộp `s01f59` #12, `s04f56` #10 và `s04f56` #11 có `length < width`. Cần đối chiếu mũi tên yaw với chiều dọc của vật trong CVAT.

**Đổi kiểm:** Chưa ghi nhận MSSV của bạn đổi kiểm và hai số liệu được đối chiếu.

## 6. Ý nghĩa của nhãn, cách dùng AI và điều còn chưa chắc

### a. Vì sao nhãn 3D dùng đơn vị mét?

Mô hình cần vị trí, kích thước và khoảng cách của vật trong không gian. Đơn vị mét giúp biểu diễn các đại lượng này theo kích thước thực. Cùng một chiếc xe có thể chiếm nhiều hoặc ít pixel tùy khoảng cách và góc camera, dù kích thước thực của xe vẫn giữ nguyên.

### b. Vì sao vật thưa điểm cần quy tắc riêng?

Ở xa, một vật có thể chỉ còn vài điểm LiDAR. Khi biên vật chưa rõ, việc ước lượng toàn bộ cuboid từ những điểm rời dễ làm hộp sai kích thước hoặc sai hướng. Quy tắc về mức độ quan sát giúp quyết định khi nào còn đủ căn cứ để vẽ và khi nào nên bỏ qua.

### c. Cách dùng AI và điều còn chưa chắc

- **ChatGPT:** Hỗ trợ tìm hiểu guideline, cài công cụ và xử lý lỗi khi chạy lệnh.
- **Nguồn số liệu:** Bảng A và phiếu tự kiểm được xuất từ task `D13-2A202603157` bằng lệnh `sync`.

Các trường hợp còn chưa chắc gồm những vật rất xa hoặc bị che, hướng của ba hộp có `length < width` và nguyên nhân của các vùng ít điểm hoặc điểm lạ. 
