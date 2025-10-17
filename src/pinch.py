import cv2
import numpy as np
import mediapipe as mp
import time
from collections import deque

# --- Connect 4 Logic ---
class Connect4:
    def __init__(self, cols=7, rows=6):
        self.cols = cols
        self.rows = rows
        self.board = np.zeros((rows, cols), dtype=np.int8)
        self.current_player = 1
        self.winner = 0

    def reset(self):
        self.board.fill(0)
        self.current_player = 1
        self.winner = 0

    def valid_moves(self):
        return [c for c in range(self.cols) if self.board[0, c] == 0]

    def drop(self, col):
        if self.board[0, col] != 0:
            return False, None
        for r in range(self.rows - 1, -1, -1):
            if self.board[r, col] == 0:
                self.board[r, col] = self.current_player
                placed_row = r
                break
        self.check_win(placed_row, col)
        self.current_player = 1 if self.current_player == 2 else 2
        return True, placed_row

    def check_win(self, r, c):
        player = self.board[r, c]
        if player == 0:
            return False
        dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
        for dr, dc in dirs:
            count = 1
            # forward
            rr, cc = r + dr, c + dc
            while 0 <= rr < self.rows and 0 <= cc < self.cols and self.board[rr, cc] == player:
                count += 1
                rr += dr
                cc += dc
            # backward
            rr, cc = r - dr, c - dc
            while 0 <= rr < self.rows and 0 <= cc < self.cols and self.board[rr, cc] == player:
                count += 1
                rr -= dr
                cc -= dc
            if count >= 4:
                self.winner = player
                return True
        return False


# --- Mediapipe Hand Setup ---
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


def render_board(board: Connect4, width, height):
    """Draw the board as an overlay image."""
    rows, cols = board.rows, board.cols
    cell_w = width // cols
    cell_h = height // rows

    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (30, 90, 180)  # blue background

    for r in range(rows):
        for c in range(cols):
            cx = int((c + 0.5) * cell_w)
            cy = int((r + 0.5) * cell_h)
            radius = int(min(cell_w, cell_h) * 0.38)
            cv2.circle(img, (cx, cy), radius, (230, 230, 230), -1)
            if board.board[r, c] == 1:
                cv2.circle(img, (cx, cy), radius - 4, (0, 0, 255), -1)
            elif board.board[r, c] == 2:
                cv2.circle(img, (cx, cy), radius - 4, (255, 0, 0), -1)
    return img


def board_point_to_col(x, width, cols=7):
    """Convert an x-coordinate to board column."""
    cell_w = width / cols
    return max(0, min(cols - 1, int(x // cell_w)))


def main():
    res = 1080
    if(res == 1080):
        screen_w, screen_h = 1920, 1080
        board_w, board_h = 840, 720
    else:
        screen_w, screen_h = 1280, 720
        board_w, board_h = 700, 600

    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, screen_w)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, screen_h)

    if not cap.isOpened():
        print("Could not open webcam.")
        return

    c4 = Connect4()
    grabbed_chip = None
    pinch_history = deque(maxlen=5)
    last_grab_time = 0
    falling = []

    # Board area parameters
    board_x, board_y = int(screen_w / 2 - board_w / 2), int(screen_h / 2 - board_h / 3)

    with mp_hands.Hands(
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5,
        max_num_hands=1
    ) as hands:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.flip(frame, 1)
            h, w = frame.shape[:2]

            # Crop or scale board overlay region
            board_overlay = render_board(c4, board_w, board_h)

            # Process hand
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = hands.process(rgb)

            pinch_detected = False
            pinch_pos = None

            if results.multi_hand_landmarks:
                hand = results.multi_hand_landmarks[0]
                mp_drawing.draw_landmarks(frame, hand, mp_hands.HAND_CONNECTIONS)

                # Get thumb tip (4) and index tip (8)
                ix = int(hand.landmark[8].x * w)
                iy = int(hand.landmark[8].y * h)
                tx = int(hand.landmark[4].x * w)
                ty = int(hand.landmark[4].y * h)
                dist = np.hypot(ix - tx, iy - ty)

                # Pinch threshold
                thresh = w * 0.05
                if dist < thresh:
                    pinch_detected = True
                    pinch_pos = np.array([(ix + tx) / 2, (iy + ty) / 2])

            # Smooth pinch position
            if pinch_pos is not None:
                pinch_history.append(pinch_pos)
                pinch_pos = np.mean(pinch_history, axis=0)
            else:
                pinch_history.clear()

            # ---- Grab/Drag/Release logic ----
            now = time.time()
            if grabbed_chip is None:
                if pinch_detected and (now - last_grab_time) > 2.0:
                    # Start new grab
                    if pinch_pos is not None:
                        px, py = pinch_pos
                        if py < board_y:  # allow grabbing only near top
                            grabbed_chip = {
                                "player": c4.current_player,
                                "pos": np.array([px - board_x, py], dtype=float)
                            }
                            last_grab_time = now
            else:
                # Dragging
                if pinch_detected and pinch_pos is not None:
                    px, py = pinch_pos
                    grabbed_chip["pos"][0] = px - board_x
                    grabbed_chip["pos"][1] = np.clip(py, 0, board_y - 20)

                else:
                    # Released
                    if(grabbed_chip["pos"][0] > 0 and grabbed_chip["pos"][0] < board_w and grabbed_chip["pos"][1] < board_y):
                        print(board_x, board_x + board_w, grabbed_chip["pos"][0])
                        col = board_point_to_col(grabbed_chip["pos"][0], board_w, c4.cols)
                        success, row = c4.drop(col)
                        if success:
                            falling.append({
                                "player": grabbed_chip["player"],
                                "x": (col + 0.5) * (board_w / c4.cols),
                                "y": 0,
                                "target_y": (row + 0.5) * (board_h / c4.rows),
                                "t": 0.0
                            })
                        grabbed_chip = None
                        last_grab_time = now
                    else:
                        # Cancel grab if released outside board
                        grabbed_chip = None
                        last_grab_time = now

            # Animate falling chips
            for chip in falling:
                chip["t"] += 0.08
                chip["y"] = min(chip["target_y"], chip["y"] + 20)

            falling = [ch for ch in falling if ch["y"] < ch["target_y"]]

            # Draw the board overlay on frame
            # Overlay the board at (board_x, board_y) with size (board_w, board_h)
            roi = frame[board_y:board_y + board_h, board_x:board_x + board_w]
            blended = cv2.addWeighted(roi, 0.5, board_overlay, 0.5, 0)
            frame[board_y:board_y + board_h, board_x:board_x + board_w] = blended

            # Draw grabbed or falling chips
            cell_w = board_w / c4.cols
            cell_h = board_h / c4.rows
            radius = int(min(cell_w, cell_h) * 0.30)
            if grabbed_chip is not None:
                cx = int(grabbed_chip["pos"][0] + board_x)
                cy = int(grabbed_chip["pos"][1])
                color = (0, 0, 255) if grabbed_chip["player"] == 1 else (255, 0, 0)
                cv2.circle(frame, (cx, cy), radius, color, -1)

            for chip in falling:
                cx = int(chip["x"] + board_x)
                cy = int(chip["y"] + board_y)
                color = (0, 0, 255) if chip["player"] == 1 else (255, 0, 0)
                cv2.circle(frame, (cx, cy), radius, color, -1)

            # Info text
            if c4.winner:
                msg = f"Player {c4.winner} wins! Press R to reset."
            else:
                msg = f"Player {c4.current_player}'s turn"
            cv2.putText(frame, msg, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            # Debug: show pinch
            if pinch_pos is not None:
                cv2.circle(frame, (int(pinch_pos[0]), int(pinch_pos[1])), 10, (0, 255, 255), -1)

            cv2.imshow("Connect 4 (Hand Tracking)", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            if key == ord("r"):
                c4.reset()
                falling.clear()

    cap.release()
    cv2.destroyAllWindows()

main()
