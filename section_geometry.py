"""
section_geometry.py
격자(grid) 기반 단면 형상 관련 함수 모음
- 연결성 검사 (BFS, 4-방향)
- 격자 → 실제 좌표 변환
- 단면 시각화
"""
import numpy as np
from collections import deque


def is_connected(grid):
    """
    격자 내 모든 스트립(값 1 또는 2)이 상하좌우 4-연결로
    하나의 덩어리를 이루는지 확인한다.

    Returns:
        True  - 연결된 단일 형상 (또는 스트립 없음 → False)
        False - 분리된 형상 존재
    """
    rows, cols = grid.shape
    occupied = (grid > 0)

    positions = list(zip(*np.where(occupied)))
    if len(positions) == 0:
        return False   # 스트립 없음 → 유효하지 않음
    if len(positions) == 1:
        return True    # 스트립 1개 → 연결됨

    visited = np.zeros((rows, cols), dtype=bool)
    start = positions[0]
    queue = deque([start])
    visited[start] = True
    count = 1

    directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # 상하좌우

    while queue:
        r, c = queue.popleft()
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            if 0 <= nr < rows and 0 <= nc < cols:
                if not visited[nr, nc] and occupied[nr, nc]:
                    visited[nr, nc] = True
                    count += 1
                    queue.append((nr, nc))

    return count == len(positions)


def count_strips(grid):
    """스트립 개수 반환 (값 1 또는 2인 셀 수)"""
    return int(np.sum(grid > 0))


def grid_to_positions(grid, cell_size):
    """
    격자를 실제 좌표 목록으로 변환.

    좌표 규칙 (구조공학 관례 — i=0이 하단):
      x_c = (j + 0.5) * cell_size
      y_c = (rows - i - 0.5) * cell_size

    Returns:
        list of (row, col, orientation, x_center, y_center)
    """
    rows, cols = grid.shape
    result = []
    for i in range(rows):
        for j in range(cols):
            val = int(grid[i, j])
            if val > 0:
                x_c = (j + 0.5) * cell_size
                y_c = (rows - i - 0.5) * cell_size
                result.append((i, j, val, x_c, y_c))
    return result


def plot_section(grid, cell_size, strip_b, strip_h, title='Section', save_path=None):
    """
    단면 형상을 시각화하고 저장.

    색상 구분:
      파란색 (#4472C4) — 값=1 기본 방향
      주황색 (#ED7D31) — 값=2  90도 회전

    Args:
        grid      : numpy 2D array
        cell_size : 격자 셀 크기 (mm)
        strip_b   : 스트립 기본 x-폭 (mm)
        strip_h   : 스트립 기본 y-높이 (mm)
        title     : 그래프 제목
        save_path : 이미지 저장 경로 (None이면 화면 표시)
    """
    import matplotlib.pyplot as plt
    import matplotlib.patches as patches

    rows, cols = grid.shape
    fig, ax = plt.subplots(figsize=(4, 4))

    for i in range(rows):
        for j in range(cols):
            val = int(grid[i, j])
            if val == 0:
                continue

            x_c = (j + 0.5) * cell_size
            y_c = (rows - i - 0.5) * cell_size

            if val == 1:
                bx, by = strip_b, strip_h
                color = '#4472C4'
            else:
                bx, by = strip_h, strip_b
                color = '#ED7D31'

            # 사각형 좌하단 좌표
            x0 = x_c - bx / 2
            y0 = y_c - by / 2

            rect = patches.Rectangle(
                (x0, y0), bx, by,
                linewidth=1, edgecolor='black',
                facecolor=color, alpha=0.85
            )
            ax.add_patch(rect)

    # 보조 격자선
    for i in range(rows + 1):
        ax.axhline(i * cell_size, color='gray', linewidth=0.3, alpha=0.5)
    for j in range(cols + 1):
        ax.axvline(j * cell_size, color='gray', linewidth=0.3, alpha=0.5)

    ax.set_xlim(0, cols * cell_size)
    ax.set_ylim(0, rows * cell_size)
    ax.set_aspect('equal')
    ax.set_title(title, fontsize=8)
    ax.set_xlabel('x (mm)')
    ax.set_ylabel('y (mm)')

    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=100, bbox_inches='tight')
        plt.close()
    else:
        plt.show()
