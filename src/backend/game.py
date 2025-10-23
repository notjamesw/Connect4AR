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
        
class Game:
    def __init__(self, res):
        self.res = res
        self.show_hands = True

        if(res == 1080):
            self.screen_w, self.screen_h = 1920, 1080
            self.board_w, self.board_h = 840, 720
        else:
            self.screen_w, self.screen_h = 1280, 720
            self.board_w, self.board_h = 560, 480
        
        # --- Mediapipe Hand Setup ---
        self.mp_hands = mp.solutions.hands
        self.mp_drawing = mp.solutions.drawing_utils

        self.connect4 = Connect4()

        self.grabbed_chip = None
        self.pinch_history = deque(maxlen=5)
        self.last_grab_time = 0
        self.falling = []

        self.board_x, self.board_y = int(self.screen_w / 2 - self.board_w / 2), int(self.screen_h / 2 - self.board_h / 3)

        self.hands = self.mp_hands.Hands(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.5,
            max_num_hands=1
        )


    def render_board(self, board: Connect4, width, height):
        """Draw the board as an overlay image."""
        rows, cols = board.rows, board.cols
        cell_w = width // cols
        cell_h = height // rows

        img = np.zeros((height, width, 3), dtype=np.uint8)
        img[:] = (200, 30, 30)  # blue background

        for r in range(rows):
            for c in range(cols):
                cx = int((c + 0.5) * cell_w)
                cy = int((r + 0.5) * cell_h)
                radius = int(min(cell_w, cell_h) * 0.38)
                cv2.circle(img, (cx, cy), radius, (230, 230, 230), -1)
                if board.board[r, c] == 1:
                    cv2.circle(img, (cx, cy), radius - 4, (0, 0, 255), -1)
                elif board.board[r, c] == 2:
                    cv2.circle(img, (cx, cy), radius - 4, (0, 255, 255), -1)
        return img


    def board_point_to_col(self, x, width, cols=7):
        """Convert an x-coordinate to board column."""
        cell_w = width / cols
        return max(0, min(cols - 1, int(x // cell_w)))

    def reset(self):
        self.connect4.reset()
        self.falling.clear()
        self.grabbed_chip = None
        self.pinch_history.clear()
        self.last_grab_time = 0

    def toggle_hands(self):
        self.show_hands = not self.show_hands

    def process_frame(self, frame, key):
        # print("DEBUG: process_frame called")
        h, w = frame.shape[:2]

        frame = cv2.flip(frame, 1)
        # Crop or scale board overlay region
        board_overlay = self.render_board(self.connect4, self.board_w, self.board_h)

        # Process hand
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.hands.process(rgb)

        pinch_detected = False
        pinch_pos = None

        # print("DEBUG: Hand landmarks processing")
        if results.multi_hand_landmarks:
            hand = results.multi_hand_landmarks[0]
            if self.show_hands:
                self.mp_drawing.draw_landmarks(frame, hand, self.mp_hands.HAND_CONNECTIONS)

            # Get thumb tip (4) and index tip (8)
            ix = int(round(hand.landmark[8].x * w))
            iy = int(round(hand.landmark[8].y * h))
            tx = int(round(hand.landmark[4].x * w))
            ty = int(round(hand.landmark[4].y * h))

            # clamp to image bounds
            ix = max(0, min(w - 1, ix))
            iy = max(0, min(h - 1, iy))
            tx = max(0, min(w - 1, tx))
            ty = max(0, min(h - 1, ty))
            dist = np.hypot(ix - tx, iy - ty)

            # Pinch threshold
            thresh = w * 0.05
            if dist < thresh:
                pinch_detected = True
                pinch_pos = np.array([(ix + tx) / 2, (iy + ty) / 2])

        # print("DEBUG: Game logic processing")
        if not self.connect4.winner:
            # Smooth pinch position
            if pinch_pos is not None:
                self.pinch_history.append(pinch_pos)
                pinch_pos = np.mean(self.pinch_history, axis=0)
            else:
                self.pinch_history.clear()

            # ---- Grab/Drag/Release logic ----
            now = time.time()
            if self.grabbed_chip is None:
                if pinch_detected and (now - self.last_grab_time) > 2.0:
                    # Start new grab
                    if pinch_pos is not None:
                        px, py = pinch_pos
                        if py < self.board_y:  # allow grabbing only near top
                            self.grabbed_chip = {
                                "player": self.connect4.current_player,
                                "pos": np.array([px - self.board_x, py], dtype=float)
                            }
                            self.last_grab_time = now
            else:
                # Dragging
                if pinch_detected and pinch_pos is not None:
                    if self.res == 1080:
                        offset = 40
                    else:
                        offset = 30
                    px, py = pinch_pos
                    self.grabbed_chip["pos"][0] = px - self.board_x
                    self.grabbed_chip["pos"][1] = np.clip(py, 0, self.board_y - offset)

                else:
                    # Released
                    if(self.grabbed_chip["pos"][0] > 0 and self.grabbed_chip["pos"][0] < self.board_w and self.grabbed_chip["pos"][1] < self.board_y):
                        # print(board_x, board_x + board_w, grabbed_chip["pos"][0]) : for debugging
                        col = self.board_point_to_col(self.grabbed_chip["pos"][0], self.board_w, self.connect4.cols)
                        success, row = self.connect4.drop(col)
                        if success:
                            self.falling.append({
                                "player": self.grabbed_chip["player"],
                                "x": (col + 0.5) * (self.board_w / self.connect4.cols),
                                "y": 0,
                                "target_y": (row + 0.5) * (self.board_h / self.connect4.rows),
                                "t": 0.0
                            })
                        self.grabbed_chip = None
                        self.last_grab_time = now
                    else:
                        # Cancel grab if released outside board
                        self.grabbed_chip = None
                        self.last_grab_time = now

            # Animate falling chips
            for chip in self.falling:
                chip["t"] += 0.08
                chip["y"] = min(chip["target_y"], chip["y"] + 20)

            self.falling = [ch for ch in self.falling if ch["y"] < ch["target_y"]]

        # Draw the board overlay on frame
        # Overlay the board at (board_x, board_y) with size (board_w, board_h)
        roi = frame[self.board_y:self.board_y + self.board_h, self.board_x:self.board_x + self.board_w]
        blended = cv2.addWeighted(roi, 0.5, board_overlay, 0.5, 0)
        frame[self.board_y:self.board_y + self.board_h, self.board_x:self.board_x + self.board_w] = blended


        # Info text
        if self.connect4.winner:
            msg = f"Player {self.connect4.winner} wins! Press R to reset."
        else:
            msg = f"Player {self.connect4.current_player}'s turn"
            # Draw grabbed or falling chips
            cell_w = self.board_w / self.connect4.cols
            cell_h = self.board_h / self.connect4.rows
            if(self.res == 1080):
                radius = int(min(cell_w, cell_h) * 0.34)
            else:
                radius = int(min(cell_w, cell_h) * 0.34)

            if self.grabbed_chip is not None:
                cx = int(self.grabbed_chip["pos"][0] + self.board_x)
                cy = int(self.grabbed_chip["pos"][1])
                color = (0, 0, 255) if self.grabbed_chip["player"] == 1 else (0, 255, 255)
                cv2.circle(frame, (cx, cy), radius, color, -1)

            for chip in self.falling:
                cx = int(chip["x"] + self.board_x)
                cy = int(chip["y"] + self.board_y)
                color = (0, 0, 255) if chip["player"] == 1 else (0, 255, 255)
                cv2.circle(frame, (cx, cy), radius, color, -1)

            # Debug: show pinch
            if pinch_pos is not None and self.show_hands:
                cv2.circle(frame, (int(pinch_pos[0]), int(pinch_pos[1])), 10, (0, 255, 255), -1)

        cv2.putText(frame, msg, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
        
        # print("DEBUG: process_frame completed")
        return frame
