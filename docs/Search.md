# Về Search.py.

---

## 1. Các Thành phần Chính

* **SearchTimer**: Quản lý thời gian suy nghĩ. Nó kiểm tra xem Engine đã chạy quá thời gian cho phép hay chưa sau mỗi 2048 node (nút) được duyệt để đảm bảo hiệu năng.
* **Searcher**: Lớp chính thực hiện tìm kiếm, kết hợp với các bộ phận khác như:
    * `Evaluator`: Đánh giá điểm số của bàn cờ hiện tại.
    * `Transposition Table (TT)`: Bảng ghi nhớ để tránh tính toán lại các thế cờ đã gặp.
    * `History Table` & `Killer Moves`: Các kỹ thuật gợi ý nước đi tốt dựa trên lịch sử tìm kiếm.

---

## 2. Quy trình Tìm kiếm Tổng thể (`Search`)

Engine không tìm kiếm ở một độ sâu cố định ngay lập tức mà sử dụng chiến lược **Iterative Deepening** (Tìm kiếm sâu dần):
1. Bắt đầu tìm ở độ sâu 1, sau đó là 2, 3... cho đến khi đạt `depth` mục tiêu hoặc hết thời gian.
2. **Aspiration Windows**: Thay vì tìm kiếm với phạm vi điểm số vô hạn, Engine tạo một "cửa sổ" hẹp quanh điểm số của độ sâu trước đó. 
    * Nếu điểm số nằm trong cửa sổ: Tìm kiếm nhanh hơn rất nhiều.
    * Nếu điểm số vọt ra ngoài (thắng/thua bất ngờ): Engine sẽ mở rộng cửa sổ và tìm lại.

---

## 3. Thuật toán Cốt lõi (`_negamax`)

Đây là hàm đệ quy chính sử dụng khung **Negamax (Alpha-Beta Pruning)**. Các kỹ thuật tối ưu hóa bên trong bao gồm:

### a. Bảng Chuyển vị (Transposition Table)
Trước khi tính toán một thế cờ, Engine tra cứu trong bộ nhớ đệm (TT). Nếu thế cờ này đã được tính ở độ sâu tương đương hoặc sâu hơn, nó sẽ trả về kết quả ngay lập tức mà không cần tính lại.

### b. Null Move Pruning (Cắt tỉa nước đi trống)
Engine "thử" bỏ qua lượt đi của mình. Nếu ngay cả khi bỏ lượt mà đối thủ vẫn không thể làm gì có lợi, chứng tỏ thế trận hiện tại quá mạnh. Engine có thể tự tin cắt bỏ nhánh này sớm để tiết kiệm thời gian.

### c. Principal Variation Search (PVS)
Giả định rằng nước đi đầu tiên (sau khi đã sắp xếp) là nước đi tốt nhất. Engine sẽ tìm kiếm nước đầu tiên với toàn bộ tâm huyết, còn các nước sau chỉ được kiểm tra nhanh bằng một "cửa sổ hẹp" để chứng minh chúng tệ hơn nước đầu tiên.

### d. Late Move Reduction (LMR)
Engine sẽ giảm độ sâu tìm kiếm đối với các nước đi nằm ở cuối danh sách (các nước đi ít có khả năng tốt, không phải bắt quân, không chiếu vua). Nếu một nước đi bị giảm độ sâu mà vẫn tỏ ra đầy hứa hẹn, Engine mới quay lại tìm kiếm kỹ hơn ở độ sâu đầy đủ.

---

## 4. Các Kỹ thuật Bổ trợ

### Quiescence Search (Tìm kiếm tĩnh)
Để tránh "hiệu ứng đường chân trời" (khi một nước đi trông có vẻ tốt ở độ sâu cuối cùng nhưng thực ra là cái bẫy ngay sau đó), Engine thực hiện tìm kiếm thêm các nước bắt quân cho đến khi thế trận ổn định mới đưa ra điểm số cuối cùng.

### Sắp xếp Nước đi (Move Ordering)
Nâng cao hiệu quả cắt tỉa bằng cách ưu tiên thử các nước đi quan trọng trước:
1. Nước đi từ bảng chuyển vị (TT Move).
2. Các nước bắt quân có giá trị cao (MVV/LVA - chưa cài đặt hoàn thiện trong code hiện tại).
3. **Killer Moves**: Các nước đi không bắt quân nhưng từng gây ra sự thay đổi lớn ở các nhánh khác.
4. **History Heuristic**: Các nước đi có lịch sử mang lại hiệu quả cao trong suốt quá trình tìm kiếm.

---

## 5. Xử lý Kết thúc Trận đấu
* **Checkmate (Chiếu bí)**: Trả về một điểm số cực lớn (hoặc cực thấp), trừ đi số nước đi (`ply`) để Engine ưu tiên chiếu bí nhanh nhất có thể thay vì kéo dài trận đấu.
* **Stalemate (Hòa cờ)**: Trả về điểm số bằng 0 khi không còn nước đi hợp lệ nhưng không bị chiếu.
* **Luật 50 nước & Lặp lại thế cờ**: Được xử lý để trả về kết quả hòa (0 điểm).


## 6. Quy trình sẽ trông như sau : 
* **Search** sẽ bao gồm việc tạo độ sâu và khoảng tìm kiếm cho phép , sau đó **negamax** sẽ là agent có nhiệm vụ đi tìm , quét những giá trị đó, những thứ còn lại để prunning và lưu trạng thái nhằm tránh lặp lại trong negamax