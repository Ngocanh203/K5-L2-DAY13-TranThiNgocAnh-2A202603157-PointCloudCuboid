# Báo cáo Day 13 — Trần Thị Ngọc Anh, 2A202603157

## 1. Kết luận trước

- Mã số: `2A202603157`; task: `D13-2A202603157`; job CVAT: `18`.
- Có 10 frame: `s01f38`, `s01f59`, `s02f23`, `s02f40`, `s03f01`, `s03f32`, `s04f31`, `s04f56`, `s05f11`, `s05f36`.
- Tổng cộng 118 cuboid dạng Shape. Frame ít nhất là `s03f32` với 5 cuboid; các vật rõ trong frame này ít hơn các frame còn lại.
- Phiếu tự kiểm có 17/118 cuboid bị cảnh báo. Đây là cảnh báo cần xem lại, không phải đáp án chuẩn; các trường hợp còn nghi ngờ được ghi ở mục 5 và 6.

Trong CVAT, tôi dùng khung Top để xem hướng và vị trí, Side/Front để chỉnh đáy và chiều cao, sau đó kiểm tra lại bằng `preview` trên ảnh camera. Tôi dùng Shape cho từng frame, bật Cuboid orientation để kiểm hướng mũi tên và bấm Save trước khi xuất Bảng A.

## 2. Đọc frame (Bước 2)

Hệ trục dùng trong lab là x sang trái, y ra phía sau xe, z hướng lên; phía trước xe là −y. Ảnh trong ZIP là các preview sinh trực tiếp từ task, dùng để đối chiếu cuboid và camera: `t1-s01f38-3d.jpg`, `t1-s01f38-top.jpg`, `t1-s01f59-3d.jpg`, `t1-s01f59-top.jpg`. Nếu rubric yêu cầu ảnh chụp UI CVAT đúng nghĩa, cần thay bốn file này bằng screenshot gốc trước khi nộp LMS.

| Frame | Hướng trong Top | Mặt đường | Vật xa nhất đọc được | Loại vật và vùng khuất | Cụm chưa đọc được |
|---|---|---|---:|---|---|
| `s01f38` | Phía trước ở hướng −y; +x sang trái, +y ra sau | Gần phẳng, khoảng z = −1,7 m | khoảng 47 m ở các hộp Car | Car và Pedestrian; có các cụm hai bên và phía sau | Các cụm rất thưa ở 30–50 m |
| `s01f59` | Phía trước ở hướng −y; +x sang trái, +y ra sau | Gần phẳng; các hộp gần có đáy quanh −1,6 đến −1,8 m | khoảng 41 m | Chủ yếu Car, có Pedestrian ở xa; vật phía sau cần đối chiếu Top | Vật rất xa hoặc chỉ còn ít điểm |

Ba điều camera cho biết tốt hơn là loại vật, đầu/đuôi xe và che khuất/độ tương phản. Ba điều LiDAR cho biết tốt hơn là tâm vật trong không gian, kích thước theo mét và độ cao đáy so với mặt đường. Khi lướt các frame còn lại, tôi kiểm tra cả phía trước, hai bên và phía sau thay vì chỉ nhìn cam01.

| Frame lướt | Ghi chú |
|---|---|
| `s02f23` | Nhiều Car; một số hộp có cảnh báo đáy cao, cần kiểm Side/Front. |
| `s02f40` | Chủ yếu Car, có Pedestrian và Cyclist; vật xa thưa điểm. |
| `s03f01` | Nhiều Car gần; một số đáy cần chỉnh lại. |
| `s03f32` | Có Car, Bus, Cyclist, Pedestrian; chỉ 5 cuboid rõ. |
| `s04f31` | Car dày ở gần, có Bus và Cyclist. |
| `s04f56` | Có Car, Cyclist và Bus rất xa; các hộp xa cần thận trọng. |
| `s05f11` | Nhiều Car ở nhiều khoảng cách, thuận tiện so sánh mật độ điểm. |
| `s05f36` | Có Car và Truck; điểm giảm rõ khi vật xa. |

## 3. Ba cuboid có hướng dẫn (Bước 3)

Ảnh tham chiếu: `t2-a-car.jpg`, `t2-b-bus-truck.jpg`, `t2-c-ped-cyclist.jpg`.

| Vật | Frame, idx | Class | Mũi tên yaw | Đáy | Kiểm Top/Side/Front + camera | Kích thước |
|---|---|---|---|---|---|---|
| Xe con gần | `s01f38`, #1 | Car | Có, 271,4° | −1,719 m, sát mặt đường | Đã kiểm | 4,785 × 1,974 × 1,373 m, hợp lý với Car |
| Xe buýt | `s03f32`, #2 | Bus | Có, 271,5° | −1,274 m; cần lưu ý độ dốc/đáy cao | Đã kiểm | 12,488 × 2,941 × 3,589 m, gần khoảng Bus |
| Người đi bộ | `s01f38`, #7 | Pedestrian | 265,3° | −1,125 m; hộp xa nên khó xác định mặt đường | Đã kiểm | 0,888 × 0,760 × 1,673 m, hợp lý với người lớn |

Các vật bị bỏ qua là những cụm quá thưa hoặc không đủ cơ sở phân biệt vật thật với điểm lạ; không gán một cụm điểm lẻ thành vật. Tôi không có số liệu định lượng của vòng hiệu chuẩn để so sánh với học viên khác.

## 4. Bốn hiện tượng chất lượng (Bước 4)

Nguyên nhân dưới đây là giả thuyết dựa trên hình dạng/mật độ point cloud; không khẳng định vật lý khi thiếu ảnh camera gốc.

| Hiện tượng | Frame / ảnh / nguồn | Nguyên nhân (giả thuyết) | Quan sát | Hệ quả gán nhãn |
|---|---|---|---|---|
| Bóng che | `s05f11`, `t4-1-bong-che.jpg`, task cá nhân | Xe lớn hoặc vật gần chắn tia LiDAR | Vùng phía sau vật có ít điểm hơn vùng bên cạnh | Bật `occluded`, suy luận phần bị che nhưng không nới hộp theo vùng trống |
| Thưa ở xa | `s04f56`, `t4-2-thua-o-xa.jpg`, task cá nhân | Khoảng cách lớn làm mật độ tia giảm | `s04f56` #8 cách 50,0 m chỉ có 11 điểm | Chỉ vẽ khi nhận ra được khoảng 15–20% thể tích; nếu không thì ghi LOW_VISIBILITY và bỏ qua |
| Phản xạ thấp/ít điểm | `s05f11`, `t4-3-phan-xa-thap.jpg`, task cá nhân | Bề mặt tối, kính hoặc góc phản xạ không thuận lợi | Một số hộp xa có ít điểm hơn đáng kể so với hộp gần cùng class | Ghi giả thuyết, đối chiếu camera và không dùng intensity để nới hộp quá mức |
| Điểm lạ | `s02f23`, `t4-4-diem-la.jpg`, task cá nhân | Nhiễu đo hoặc phản xạ ngoài vật | Có cụm điểm rời không tạo thành hình vật ổn định | Không gán điểm lẻ thành cuboid; chỉ giữ hộp khi có đủ hình dạng/ảnh hỗ trợ |

## 5. Số từ cuboid của tôi (Bước 5)

| Cuboid | z (m) | h (m) | z đáy (m) | dist (m) | r (m) | yaw (°) | Nhận xét |
|---|---:|---:|---:|---:|---:|---:|---|
| `s01f38` #1 Car | −1,032 | 1,373 | −1,719 | 6,15 | 6,236 | 271,4 | Chạm đường |
| `s01f59` #1 Car | −0,916 | 1,454 | −1,643 | 3,00 | 3,133 | 271,3 | Chạm đường, gần nhất |
| `s04f56` #11 Bus | −1,158 | 2,884 | −2,600 | 79,19 | 79,197 | 263,4 | Ngoài phạm vi 50 m, đáy thấp; không dùng để kết luận chất lượng chính |

Cuboid gần nhất là `s01f59` #1: `dist_m = 3,00 m`, `r = 3,133 m`. Xa nhất là `s04f56` #11: `dist_m = 79,19 m`, `r = 79,197 m`; hộp này nằm ngoài phạm vi chấm ≤50 m và bị cảnh báo kích thước/yaw.

So với Bảng 4.3, `s01f38` #7 có kích thước 0,888 × 0,760 × 1,673 m, phù hợp người lớn. `s01f38` #1 có 4,785 × 1,974 × 1,373 m: dài/rộng hợp lý cho Car, chiều cao hơi thấp so với sedan nhưng vẫn gần nhóm xe con. Xe cùng chiều phía trước có yaw gần 270° (`s01f38` #4 = 270,0°); xe ngược chiều có yaw gần 90° (`s05f11` #6 = 90,2°).

| Cuboid | dist (m) | points_in |
|---|---:|---:|
| `s01f59` #1 Car | 3,0 | 3238 |
| `s05f11` #3 Car | 18,9 | 594 |
| `s04f31` #7 Car | 40,6 | 74 |
| `s04f56` #8 Car | 50,0 | 11 |

Mật độ điểm giảm mạnh khi khoảng cách tăng: từ 3238 điểm ở 3,0 m xuống 594 điểm ở 18,9 m, 74 điểm ở 40,6 m và 11 điểm ở 50,0 m. Xu hướng này phù hợp với đường cong tham khảo của lab, nên vật xa cần quy tắc visibility riêng.

Sau `preview`/`selfcheck`, các hộp có cờ cần xem lại gồm các hộp có đáy cao ở `s02f23`, `s03f01`, `s05f36`, hộp kích thước bất thường ở `s01f59`/`s04f56`/`s05f11` và hộp Bus ở `s04f31` #9. Tôi giữ lại một số cờ vì vật ở xa hoặc point cloud không đủ chắc để chỉnh thêm mà không đoán. Ba hộp `s01f59` #12, `s04f56` #10 và `s04f56` #11 có `length < width`, vì vậy cần kiểm lại hướng mũi tên trong CVAT trước khi chốt.

Việc đổi kiểm với bạn bên cạnh chưa có thông tin MSSV trong workspace này; cần bổ sung MSSV và hai cặp số đã đối chiếu trước khi nộp chính thức.

## 6. Ý nghĩa của nhãn, cách dùng AI và điều còn chưa chắc

Model cần mét vì cuboid 3D dùng để suy ra vị trí, kích thước và khoảng cách trong không gian; pixel chỉ mô tả hình chiếu phụ thuộc camera và không cho biết độ sâu trực tiếp. Vật thưa điểm cần quy tắc riêng vì cùng một vật có thể chỉ còn vài điểm ở xa; nếu đoán theo khoảng trống, nhãn sẽ làm model học sai kích thước và độ tin cậy.

Tôi dùng AI để hỗ trợ rà soát cấu trúc repo, kiểm tra CSV, tính các đại lượng dẫn xuất và phát hiện lỗi nộp bài. Tôi không dùng AI để suy ra nhãn chuẩn hoặc thay thế việc quan sát point cloud; các con số trong báo cáo lấy từ Bảng A và phiếu tự kiểm của task.

Điều còn chưa chắc: các vật rất xa và các vùng bị che; hướng của ba hộp có `length < width`; nguyên nhân vật lý của điểm lạ/phản xạ thấp; và hai con số đổi kiểm với bạn bên cạnh chưa được ghi lại. Cần xác nhận các mục này trong CVAT/ảnh chụp trước khi nộp cuối.
