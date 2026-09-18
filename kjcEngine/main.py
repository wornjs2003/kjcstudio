#!/usr/bin/env python3
"""kjcEngine — 창 하나, 네모 하나.

    python kjcEngine/main.py      또는  kjcEngine/run.bat 더블클릭

흰 네모가 가운데 있고, 그 밑에 100×100 회색 판이 고정으로 놓여 있다.
창 안을 클릭하면 네모가 그 자리로 미끄러지듯 이동하고, 도착하면 멈춘다.
가는 중에 다시 클릭하면 방향을 틀어 새 목표로 간다. 판은 움직이지 않는다.
"""
import math
import sys
import tkinter as tk

# 윈도우 콘솔은 기본이 cp949 라 '—' 같은 글자에서 죽는다.
# 계산은 다 맞는데 출력 한 줄에서 죽으므로 부르는 쪽은 그냥 실패로 읽는다.
# (CLAUDE.md 「한글을 출력하는 파이썬 도구에는 이 두 줄을 넣는다」)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ─── 색 ────────────────────────────────────────────────────────────────
# 값은 여기 한 곳에만 둔다. 지금 이 색을 쓰는 곳은 이 파일뿐이라
# theme.css 로 옮기지 않았다 — 두 곳에서 쓰게 되는 순간 합친다.
# (CLAUDE.md 「같은 값은 한 곳에만 둔다」)

# ⚠️ 미정: 배경색은 룰이 없어 판단으로 둔 자리다.
#    CLAUDE.md 는 「검은 배경 사용 금지」인데 그것은 웹 사이트 테마 룰이고
#    (오래 보면 눈이 피로하다는 이유), 데스크톱 창이 거기 해당하는지는
#    정해지지 않았다. 라이트 배경(#f6f7f9)에 흰 네모는 묻혀서 안 보인다.
#    재권님이 정하시면 이 주석과 함께 지운다.
BG = "#22262b"      # 창 배경 — 미정
FG = "#ffffff"      # 네모 — 재권님 지시: 흰색
PLATE = "#4e5968"   # 회색 판 — 배경보다 밝고 네모보다 어둡게 (셋이 다 구분되게)

# ─── 크기와 속도 ───────────────────────────────────────────────────────
WIN_W, WIN_H = 640, 480     # 창 안쪽 크기 (픽셀)
BOX = 10                    # 네모 한 변 — 재권님 지시: 10×10
PLATE_W = PLATE_H = 100     # 회색 판 — 재권님 지시: 100×100
SPEED = 3.0                 # 프레임당 움직이는 픽셀
TICK = 16                   # 다음 프레임까지 ms — 약 60프레임/초


class Engine:
    """네모 하나를 목표 지점으로 옮긴다."""

    def __init__(self, root):
        self.root = root
        self.canvas = tk.Canvas(
            root, width=WIN_W, height=WIN_H, bg=BG, highlightthickness=0
        )
        self.canvas.pack()

        # 지금 자리와 가야 할 자리. 처음에는 둘이 같아서 가만히 있는다
        self.x = self.y = 0.0
        self.tx = self.ty = 0.0
        self.center()

        # 판을 네모보다 먼저 만든다 — tkinter 는 나중에 만든 것이 위에 그려진다.
        # 순서가 반대면 네모가 판 뒤로 숨는다
        self.plate = self.make_plate()

        self.box = self.canvas.create_rectangle(0, 0, 0, 0, fill=FG, width=0)
        self.draw()

        self.canvas.bind("<Button-1>", self.on_click)
        self.root.bind("<Escape>", lambda e: self.root.destroy())
        self.root.after(TICK, self.tick)

    def make_plate(self):
        """네모가 처음 서 있는 자리 바로 밑에 회색 판을 깐다. 고정이다."""
        cx = WIN_W / 2
        top = WIN_H / 2 + BOX / 2          # 네모 아래쪽 변에 붙인다
        return self.canvas.create_rectangle(
            cx - PLATE_W / 2, top,
            cx + PLATE_W / 2, top + PLATE_H,
            fill=PLATE, width=0,
        )

    def center(self):
        self.x = self.tx = WIN_W / 2
        self.y = self.ty = WIN_H / 2

    def on_click(self, event):
        """클릭한 자리를 새 목표로 삼는다. 가는 중이어도 바로 틀어진다."""
        self.tx, self.ty = float(event.x), float(event.y)

    def tick(self):
        dx = self.tx - self.x
        dy = self.ty - self.y
        dist = math.hypot(dx, dy)

        if dist <= SPEED:
            # 남은 거리가 한 걸음보다 짧다. 딱 붙이고 멈춘다 —
            # 이 처리가 없으면 목표를 지나쳤다 돌아오길 되풀이하며 떤다
            self.x, self.y = self.tx, self.ty
        else:
            self.x += dx / dist * SPEED
            self.y += dy / dist * SPEED

        self.draw()
        self.root.after(TICK, self.tick)

    def draw(self):
        half = BOX / 2
        self.canvas.coords(
            self.box,
            self.x - half, self.y - half,
            self.x + half, self.y + half,
        )


def main():
    root = tk.Tk()
    root.title("kjcEngine")
    root.resizable(False, False)
    Engine(root)
    print("kjcEngine — 창 안을 클릭하면 흰 네모가 그 자리로 갑니다. (Esc 로 닫기)")
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
