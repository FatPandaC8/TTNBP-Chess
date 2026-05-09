# Chess Engine Evaluation Module

Module này chịu trách nhiệm thực hiện **Static Evaluation** (Lượng giá tĩnh) cho bàn cờ. Nó trả về một điểm số số nguyên đại diện cho lợi thế của một bên dựa trên vị trí các quân cờ hiện tại.

## Các kỹ thuật sử dụng

### 1. Tapered Evaluation (Lượng giá phân tầng)
Cờ vua có các giai đoạn khác nhau (Khai cuộc, Trung cuộc, Tàn cuộc). Một quân Mã ở giữa bàn cờ rất mạnh trong Khai cuộc nhưng có thể kém quan trọng hơn một quân Tốt đang tiến sát phong cấp ở Tàn cuộc.
*   **Opening Score:** Điểm số tính theo bảng mã Khai cuộc.
*   **Endgame Score:** Điểm số tính theo bảng mã Tàn cuộc.
*   **Phase:** Biến đếm giai đoạn dựa trên số lượng quân còn lại trên bàn (Tối đa là 24).
*   **Interpolation:** Sử dụng công thức nội suy để chuyển mượt mà giữa hai giai đoạn:

$$Score = \frac{(OpeningScore \times Phase) + (EndgameScore \times (24 - Phase))}{24}$$

### 2. Piece-Square Tables (PST)
Sử dụng các mảng 64 phần tử để định nghĩa giá trị của từng loại quân cờ tại từng ô cụ thể. 
*   **Quân Trắng:** Được tính điểm trực tiếp theo chỉ số ô.
*   **Quân Đen:** Được tính bằng cách lật ngược bàn cờ qua phép toán `sq ^ 56` để đảm bảo tính đối xứng về mặt vị trí so với quân Trắng.

### 3. Bitboard Acceleration
Thay vì lặp qua 64 ô cờ (rất chậm trong Python), engine sử dụng `board.pieces(piece_type, color)`. Hàm này truy cập trực tiếp vào cấu trúc dữ liệu **Bitboard** của thư viện `python-chess`, giúp tăng tốc độ vòng lặp lên gấp nhiều lần bằng cách bỏ qua các ô trống.

---

## 🛠 Cấu trúc Class `Evaluator`

### Phương thức `evaluate(board)`
Đây là hàm điều phối chính để tính toán điểm số cuối cùng.

| Tham số | Kiểu dữ liệu | Mô tả |
| :--- | :--- | :--- |
| `board` | `ChessBoard` | Trạng thái hiện tại của bàn cờ (kế thừa từ chess.Board). |
| **Trả về** | `int` | Điểm số theo góc nhìn của người cầm quân (Side to move). |

**Logic xử lý:**
1.  **Khởi tạo:** Đặt điểm Khai cuộc, Tàn cuộc và Phase về 0.
2.  **Vòng lặp quân cờ:** Duyệt từ Pawn (1) đến King (6).
3.  **Lượng giá quân Trắng:** Cộng điểm từ bảng PST Khai cuộc/Tàn cuộc tương ứng với vị trí quân.
4.  **Lượng giá quân Đen:** Lật chỉ số ô cờ, trừ điểm từ bảng PST để đại diện cho ưu thế của đối thủ.
5.  **Tính toán nội suy:** Kết hợp điểm dựa trên biến `phase` hiện tại của ván đấu.
6.  **NegaMax Normalization:** Nếu là lượt của quân Đen, đảo ngược dấu (`-score`) vì thuật toán NegaMax luôn tìm kiếm điểm số tối đa cho người đang thực hiện nước đi.

---

## Trọng số qua giai đoạn 
Mỗi quân cờ khi xuất hiện trên bàn cờ sẽ đóng góp vào tổng giá trị `phase` (tổng cộng tối đa là 24):
*   **Mã (Knight):** 1 đơn vị.
*   **Tượng (Bishop):** 1 đơn vị.
*   **Xe (Rook):** 2 đơn vị.
*   **Hậu (Queen):** 4 đơn vị.
*   **Tốt & Vua:** 0 đơn vị (Không đóng góp vào việc đẩy nhanh giai đoạn tàn cuộc).

---

## Cách sử dụng

```python
from engine.evaluation.evaluator import Evaluator
import chess

board = chess.Board()
evaluator = Evaluator()

# Lấy điểm số hiện tại (tính bằng centipawns)
score = evaluator.evaluate(board)

print(f"Evalscore: {score}")