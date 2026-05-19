"""
visualizer.py
box_core 단면 2D 시각화 및 PNG 저장 모듈

도면 구성:
  - 외부 직사각형  : MDF 벽 (나무색 #C8A87A)
  - 내부 공동      : 빈 공간 (흰색)
  - 수평 리브      : MDF 리브 (연파란색 #A0C4FF)
  - 치수선         : width, depth 표시
  - 제목           : 단면 파라미터 및 주요 특성 수치
"""
import os
import matplotlib.pyplot as plt
import matplotlib.patches as patches


def draw_section(candidate, output_path):
    """
    box_core 단면 하나를 2D로 그리고 PNG 파일로 저장한다.

    리브 위치 계산:
      내부 공동을 (rib_count + 1) 등분한 지점에 리브 중심을 배치.
      리브 높이 = 벽 두께(t).

    Args:
        candidate   (dict): width, depth, thickness, rib_count 및 계산된 특성 포함
        output_path (str) : 저장할 PNG 파일 전체 경로
    """
    w = candidate['width']
    d = candidate['depth']
    t = candidate['thickness']
    r = candidate['rib_count']

    inner_w = w - 2 * t   # 내부 공동 폭
    inner_d = d - 2 * t   # 내부 공동 깊이

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.set_aspect('equal')
    ax.axis('off')

    # ── 외부 박스 (MDF 벽 영역 포함 전체) ───────────────────────
    outer = patches.Rectangle(
        (0, 0), w, d,
        linewidth=1.5,
        edgecolor='black',
        facecolor='#C8A87A'   # 나무색
    )
    ax.add_patch(outer)

    # ── 내부 공동 (재료가 없는 빈 공간) ─────────────────────────
    inner = patches.Rectangle(
        (t, t), inner_w, inner_d,
        linewidth=1,
        edgecolor='#888888',
        facecolor='white'
    )
    ax.add_patch(inner)

    # ── 수평 리브 ────────────────────────────────────────────────
    if r > 0:
        spacing = inner_d / (r + 1)   # 리브 중심 간격
        for i in range(1, r + 1):
            # 리브 중심의 y좌표 (외부 박스 하단 기준)
            rib_center_y = t + spacing * i
            # 리브 하단 y좌표
            rib_bottom_y = rib_center_y - t / 2
            rib = patches.Rectangle(
                (t, rib_bottom_y), inner_w, t,
                linewidth=1,
                edgecolor='#555555',
                facecolor='#A0C4FF'   # 연파란색
            )
            ax.add_patch(rib)

    # ── 치수선: width ─────────────────────────────────────────────
    margin = max(w, d) * 0.18    # 그림 여백
    dim_y  = -margin * 0.55      # 치수선 y위치 (단면 아래)
    ax.annotate(
        '', xy=(w, dim_y), xytext=(0, dim_y),
        arrowprops=dict(arrowstyle='<->', color='black', lw=1.2)
    )
    ax.text(w / 2, dim_y - margin * 0.2, f'{w} mm',
            ha='center', va='top', fontsize=8)

    # ── 치수선: depth ─────────────────────────────────────────────
    dim_x = w + margin * 0.55    # 치수선 x위치 (단면 오른쪽)
    ax.annotate(
        '', xy=(dim_x, d), xytext=(dim_x, 0),
        arrowprops=dict(arrowstyle='<->', color='black', lw=1.2)
    )
    ax.text(dim_x + margin * 0.15, d / 2, f'{d} mm',
            ha='left', va='center', fontsize=8, rotation=90)

    # ── 축 범위 설정 ──────────────────────────────────────────────
    ax.set_xlim(-margin, w + margin * 1.5)
    ax.set_ylim(-margin, d + margin * 0.5)

    # ── 제목: 단면 파라미터 및 주요 특성 ────────────────────────
    title_lines = [
        f"[box_core]  {w} × {d} mm  t={t} mm  rib={r}",
        f"A = {candidate['area_mm2']} mm²    W = {candidate['weight_kg']:.4f} kg",
        f"Ix = {candidate['Ix_mm4']:,.0f} mm⁴    Iy = {candidate['Iy_mm4']:,.0f} mm⁴",
        f"score = {candidate['score']:,.2f}",
    ]
    ax.set_title('\n'.join(title_lines), fontsize=9, pad=12, linespacing=1.6)

    # ── 저장 ──────────────────────────────────────────────────────
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  저장됨: {output_path}")


def save_top_sections(top_sections, image_dir):
    """
    상위 단면 목록을 순서대로 PNG 파일로 저장한다.

    파일명 형식:
      rank01_box_core_100x150_t10_rib2.png

    Args:
        top_sections (list): score 기준으로 정렬된 단면 dict 목록
        image_dir    (str) : 이미지를 저장할 폴더 경로
    """
    os.makedirs(image_dir, exist_ok=True)

    for rank, sec in enumerate(top_sections, start=1):
        # 파일명에 주요 파라미터를 포함해 식별하기 쉽게 구성
        filename = (
            f"rank{rank:02d}_{sec['type']}"
            f"_{sec['width']}x{sec['depth']}"
            f"_t{sec['thickness']}"
            f"_rib{sec['rib_count']}.png"
        )
        output_path = os.path.join(image_dir, filename)
        draw_section(sec, output_path)
