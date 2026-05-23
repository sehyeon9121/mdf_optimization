"""
visualize_system_layouts.py
시나리오별 대표 시스템 배치 시각화 (4기둥 + 코어 평면도)

출력: outputs/system_layouts/
  layout_01_minimum.png      최소 기준안
  layout_02_economy.png      경제형 추천안
  layout_03_baseline.png     기준형 추천안
  layout_04_safety.png       안전형 추천안
  layout_05_overdesign.png   과설계 비교안
  combined_all_layouts.png   5개 통합
"""

import os
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Circle, FancyBboxPatch, RegularPolygon
from matplotlib.lines import Line2D

# 한글 폰트 설정 (Windows)
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
OUT_DIR   = os.path.join(BASE_DIR, 'outputs', 'system_layouts')

# build_system_candidates.py와 동일하게 맞춰야 함
COST_MODE = 'floor_by_floor'   # 'floor_by_floor' | 'continuous'

# ── 기준 평면 정보 ───────────────────────────────────────────────
COL_POS = {
    'C1': (0,   0  ),
    'C2': (150, 0  ),
    'C3': (0,   150),
    'C4': (150, 150),
}
CORE_POS = (75, 75)
SPAN     = 150

# ── N별 색상 / 반지름 ────────────────────────────────────────────
N_FACE = {3: '#90CAF9', 4: '#1976D2', 5: '#388E3C', 6: '#F57C00', 7: '#7B1FA2'}
N_EDGE = {3: '#1565C0', 4: '#0D47A1', 5: '#1B5E20', 6: '#E65100', 7: '#4A148C'}
N_RAD  = {3: 9.0, 4: 10.5, 5: 12.5, 6: 14.5, 7: 16.5}   # mm 단위

# ── 5개 대표안 정의 ──────────────────────────────────────────────
LAYOUTS = [
    {
        'fname':  'layout_01_minimum',
        'title':  'N4 Balanced Uniform ×4  |  Core: None',
        'role':   '♛  최소 기준안',
        'badge':  '#1565C0',
        'arr':    'uniform_4',
        'columns': {
            'C1': {'tag':'N4_bal_90','N':4,'rot':90,'Ix':2608, 'Iy':2608, 'cost':60},
            'C2': {'tag':'N4_bal_90','N':4,'rot':90,'Ix':2608, 'Iy':2608, 'cost':60},
            'C3': {'tag':'N4_bal_90','N':4,'rot':90,'Ix':2608, 'Iy':2608, 'cost':60},
            'C4': {'tag':'N4_bal_90','N':4,'rot':90,'Ix':2608, 'Iy':2608, 'cost':60},
        },
        'core': None,
        'metrics': {
            'total_cost':240, 'total_cost_cont':220, 'min_I':10432,
            'sum_Ix':10432, 'sum_Iy':10432,
            'Ix_Iy':1.0000, 'norm_ecc':0.0000, 'risk':'low',
        },
        'thresh': 10432, 'thresh_label': 'economy',
    },
    {
        'fname':  'layout_02_economy',
        'title':  'N5+N3 Balanced Diagonal Pair  |  Core: None',
        'role':   '★  경제형 추천안',
        'badge':  '#2E7D32',
        'arr':    'diag_pair',
        'columns': {
            'C1': {'tag':'N5_bal_0', 'N':5,'rot': 0,'Ix':7960, 'Iy':7920, 'cost':70},
            'C2': {'tag':'N3_bal_90','N':3,'rot':90,'Ix':1736, 'Iy':1776, 'cost':40},
            'C3': {'tag':'N3_bal_90','N':3,'rot':90,'Ix':1736, 'Iy':1776, 'cost':40},
            'C4': {'tag':'N5_bal_0', 'N':5,'rot': 0,'Ix':7960, 'Iy':7920, 'cost':70},
        },
        'core': None,
        'metrics': {
            'total_cost':240, 'total_cost_cont':220, 'min_I':19392,
            'sum_Ix':19392, 'sum_Iy':19392,
            'Ix_Iy':1.0000, 'norm_ecc':0.0000, 'risk':'low',
        },
        'thresh': 10432, 'thresh_label': 'economy',
    },
    {
        'fname':  'layout_03_baseline',
        'title':  'N7+N3 Balanced Diagonal Pair  |  Core: None',
        'role':   '★  기준형 추천안',
        'badge':  '#E65100',
        'arr':    'diag_pair',
        'columns': {
            'C1': {'tag':'N7_bal_0', 'N':7,'rot': 0,'Ix':21641,'Iy':21601,'cost':100},
            'C2': {'tag':'N3_bal_90','N':3,'rot':90,'Ix':1736, 'Iy':1776, 'cost':40},
            'C3': {'tag':'N3_bal_90','N':3,'rot':90,'Ix':1736, 'Iy':1776, 'cost':40},
            'C4': {'tag':'N7_bal_0', 'N':7,'rot': 0,'Ix':21641,'Iy':21601,'cost':100},
        },
        'core': None,
        'metrics': {
            'total_cost':280, 'total_cost_cont':270, 'min_I':46754,
            'sum_Ix':46754, 'sum_Iy':46754,
            'Ix_Iy':1.0000, 'norm_ecc':0.0000, 'risk':'low',
        },
        'thresh': 31680, 'thresh_label': 'baseline',
    },
    {
        'fname':  'layout_04_safety',
        'title':  'N7_bal_0 + N7_bal_90 Diagonal Pair  |  Core: None',
        'role':   '★  안전형 추천안',
        'badge':  '#7B1FA2',
        'arr':    'diag_pair',
        'columns': {
            'C1': {'tag':'N7_bal_0', 'N':7,'rot': 0,'Ix':21641,'Iy':21601,'cost':100},
            'C2': {'tag':'N7_bal_90','N':7,'rot':90,'Ix':21601,'Iy':21641,'cost':100},
            'C3': {'tag':'N7_bal_90','N':7,'rot':90,'Ix':21601,'Iy':21641,'cost':100},
            'C4': {'tag':'N7_bal_0', 'N':7,'rot': 0,'Ix':21641,'Iy':21601,'cost':100},
        },
        'core': None,
        'metrics': {
            'total_cost':400, 'total_cost_cont':380, 'min_I':86485,
            'sum_Ix':86485, 'sum_Iy':86485,
            'Ix_Iy':1.0000, 'norm_ecc':0.0000, 'risk':'low',
        },
        'thresh': 86404, 'thresh_label': 'safety',
    },
    {
        'fname':  'layout_05_overdesign',
        'title':  'N7 Balanced Uniform ×4  |  Core: Strong (Ix=Iy=40,000)',
        'role':   '⚠  과설계 비교안',
        'badge':  '#455A64',
        'arr':    'uniform_4',
        'columns': {
            'C1': {'tag':'N7_bal_0','N':7,'rot':0,'Ix':21641,'Iy':21601,'cost':100},
            'C2': {'tag':'N7_bal_0','N':7,'rot':0,'Ix':21641,'Iy':21601,'cost':100},
            'C3': {'tag':'N7_bal_0','N':7,'rot':0,'Ix':21641,'Iy':21601,'cost':100},
            'C4': {'tag':'N7_bal_0','N':7,'rot':0,'Ix':21641,'Iy':21601,'cost':100},
        },
        'core': {'label':'Strong', 'Ix':40000, 'Iy':40000, 'cost':160},
        'metrics': {
            'total_cost':560, 'total_cost_cont':540, 'min_I':126404,
            'sum_Ix':126564, 'sum_Iy':126404,
            'Ix_Iy':1.0013, 'norm_ecc':0.0000, 'risk':'low',
        },
        'thresh': 86404, 'thresh_label': 'safety',
    },
]


# ─────────────────────────────────────────────────────────────────
# 단일 레이아웃 그리기
# ─────────────────────────────────────────────────────────────────
def draw_one(layout, ax_plan, ax_info):
    cols    = layout['columns']
    core    = layout['core']
    m       = layout['metrics']
    arr     = layout['arr']
    thresh  = layout['thresh']

    # ── Floor plan ───────────────────────────────────────────────
    ax_plan.set_xlim(-52, 207)
    ax_plan.set_ylim(-52, 207)
    ax_plan.set_aspect('equal')
    ax_plan.axis('off')

    # 배경 사각형
    bg = FancyBboxPatch((-48, -48), 255, 255,
                        boxstyle='round,pad=3', linewidth=0,
                        facecolor='#FAFAFA', zorder=0)
    ax_plan.add_patch(bg)

    # 프레임 선 (기둥 연결)
    fx = [0, 150, 150, 0, 0]
    fy = [0, 0, 150, 150, 0]
    ax_plan.plot(fx, fy, color='#424242', linewidth=2.0, zorder=2)

    # diag_pair: 대각선 쌍 표시
    if arr == 'diag_pair':
        ax_plan.plot([0, 150], [0, 150], '--', color='#B0BEC5',
                     linewidth=1.2, alpha=0.7, zorder=1, label='diag A')
        ax_plan.plot([150, 0], [0, 150], ':', color='#B0BEC5',
                     linewidth=1.2, alpha=0.7, zorder=1, label='diag B')

    # 치수선 (하단)
    ax_plan.annotate('', xy=(150, -30), xytext=(0, -30),
                     arrowprops=dict(arrowstyle='<->', color='#757575', lw=1.2))
    ax_plan.text(75, -38, 'L = 150 mm', ha='center', va='top',
                 fontsize=8.5, color='#616161')

    # 치수선 (우측)
    ax_plan.annotate('', xy=(185, 150), xytext=(185, 0),
                     arrowprops=dict(arrowstyle='<->', color='#757575', lw=1.2))
    ax_plan.text(193, 75, 'L = 150 mm', ha='left', va='center',
                 fontsize=8.5, color='#616161', rotation=90)

    # 기둥 레이블 오프셋 (외부 텍스트 위치)
    lbl_off = {
        'C1': (-1, -1),   # 좌하: 왼쪽 아래
        'C2': ( 1, -1),   # 우하: 오른쪽 아래
        'C3': (-1,  1),   # 좌상: 왼쪽 위
        'C4': ( 1,  1),   # 우상: 오른쪽 위
    }
    lbl_d = 34   # 레이블 거리 (mm)

    for cname, col in cols.items():
        x, y      = COL_POS[cname]
        n         = col['N']
        r         = N_RAD[n]
        fc        = N_FACE[n]
        ec        = N_EDGE[n]
        dx, dy    = lbl_off[cname]

        # 기둥 원
        circ = Circle((x, y), r, facecolor=fc, edgecolor=ec,
                      linewidth=2.2, zorder=5)
        ax_plan.add_patch(circ)

        # 원 안: N값 + 회전 기호
        rot_sym = '→' if col['rot'] == 0 else '↑'   # → or ↑
        ax_plan.text(x, y + 2.5, f'N{n}',
                     ha='center', va='center', fontsize=9,
                     fontweight='bold', color='white', zorder=6)
        ax_plan.text(x, y - 4.5, rot_sym,
                     ha='center', va='center', fontsize=9,
                     color='white', alpha=0.9, zorder=6)

        # 외부 레이블 박스
        lx = x + dx * lbl_d
        ly = y + dy * lbl_d
        ha = 'right' if dx < 0 else 'left'
        va = 'top'   if dy < 0 else 'bottom'

        lbl = (f"{cname}\n"
               f"{col['tag']}\n"
               f"rot = {col['rot']}°\n"
               f"Ix = {col['Ix']:,}\n"
               f"Iy = {col['Iy']:,}")
        ax_plan.text(lx, ly, lbl,
                     ha=ha, va=va, fontsize=7.5,
                     bbox=dict(boxstyle='round,pad=0.35',
                               facecolor='white', edgecolor=ec,
                               linewidth=1.2, alpha=0.95),
                     zorder=7)

        # 연결선 (원 외곽 → 레이블)
        angle = np.arctan2(dy, dx)
        cx_e  = x + r * np.cos(angle)
        cy_e  = y + r * np.sin(angle)
        ax_plan.plot([cx_e, lx + (-0.12 if dx < 0 else 0.12) * lbl_d],
                     [cy_e, ly + (-0.12 if dy < 0 else 0.12) * lbl_d],
                     '-', color=ec, linewidth=0.8, alpha=0.55, zorder=4)

    # 코어 마커
    if core:
        cx, cy = CORE_POS
        core_r = 13.5
        diamond = RegularPolygon((cx, cy), 4, radius=core_r,
                                 orientation=np.pi / 4,
                                 facecolor='#FF8F00', edgecolor='#BF360C',
                                 linewidth=2.0, zorder=5)
        ax_plan.add_patch(diamond)
        ax_plan.text(cx, cy + 1.5, 'CORE',
                     ha='center', va='center', fontsize=7.5,
                     fontweight='bold', color='white', zorder=6)
        ax_plan.text(cx, cy - 4.5, core['label'],
                     ha='center', va='center', fontsize=6.5,
                     color='white', alpha=0.9, zorder=6)
        core_desc = (f"core: {core['label']}\n"
                     f"Ix = {core['Ix']:,}\n"
                     f"Iy = {core['Iy']:,}\n"
                     f"cost = {core['cost']}")
        ax_plan.text(cx + 22, cy - 22, core_desc,
                     ha='left', va='top', fontsize=7.5,
                     bbox=dict(boxstyle='round,pad=0.35',
                               facecolor='#FFF8E1', edgecolor='#FF8F00',
                               linewidth=1.2, alpha=0.95),
                     zorder=7)
    else:
        cx, cy = CORE_POS
        # 코어 없음: 십자 표시
        ax_plan.plot(cx, cy, '+', markersize=14, color='#B0BEC5',
                     markeredgewidth=2.2, zorder=5)
        ax_plan.text(cx, cy + 16, '(no core)', ha='center', va='bottom',
                     fontsize=7.5, color='#90A4AE', style='italic')

    # CM=CR 마커 (빨간 X)
    ax_plan.plot(75, 75, 'x', markersize=9, color='#E53935',
                 markeredgewidth=2.0, zorder=8)
    ax_plan.text(75 + 7, 75 + 7, 'CM = CR\n(75, 75)',
                 fontsize=7, color='#E53935', zorder=8)

    # ── Info panel ───────────────────────────────────────────────
    ax_info.axis('off')

    margin = (m['min_I'] - thresh) / thresh * 100

    # 역할 배지
    role_box = FancyBboxPatch((0.0, 0.86), 1.0, 0.13,
                              boxstyle='round,pad=0.01',
                              transform=ax_info.transAxes,
                              facecolor=layout['badge'], edgecolor='none',
                              zorder=2, clip_on=False)
    ax_info.add_patch(role_box)
    ax_info.text(0.5, 0.925, layout['role'],
                 transform=ax_info.transAxes,
                 ha='center', va='center', fontsize=11,
                 fontweight='bold', color='white', zorder=3)

    # 구분선
    ax_info.plot([0, 1], [0.84, 0.84], color='#E0E0E0',
                 linewidth=1.0, transform=ax_info.transAxes, clip_on=False)

    # 지표 항목
    def row(ax, y, label, value, vc='#212121', bold=False):
        ax.text(0.04, y, label,
                transform=ax.transAxes, fontsize=8.5,
                va='top', color='#757575')
        ax.text(0.52, y, value,
                transform=ax.transAxes, fontsize=8.5,
                va='top', color=vc,
                fontweight='bold' if bold else 'normal')

    y = 0.82
    dy = 0.072

    row(ax_info, y, '배치 패턴', arr, bold=True); y -= dy
    row(ax_info, y, '기둥 조합',
        f"C1=C4: N{cols['C1']['N']}  |  C2=C3: N{cols['C2']['N']}"
        if arr == 'diag_pair' else
        f"N{cols['C1']['N']} (전체 동일)"); y -= dy

    y -= 0.01   # 공백
    row(ax_info, y, 'min_system_I',
        f"{m['min_I']:,} mm⁴", '#1565C0', bold=True); y -= dy

    mcolor = '#2E7D32' if margin >= 0 else '#C62828'
    row(ax_info, y, f"  {layout['thresh_label']} 임계값",
        f"{thresh:,} mm⁴"); y -= dy
    row(ax_info, y, '  임계값 대비 여유',
        f"+{margin:.1f}%" if margin >= 0 else f"{margin:.1f}%",
        mcolor, bold=True); y -= dy

    y -= 0.01
    row(ax_info, y, 'Σ Ix',  f"{m['sum_Ix']:,} mm⁴"); y -= dy
    row(ax_info, y, 'Σ Iy',  f"{m['sum_Iy']:,} mm⁴"); y -= dy
    row(ax_info, y, 'Ix / Iy',  f"{m['Ix_Iy']:.4f}"); y -= dy

    y -= 0.01
    fbf_cost  = m['total_cost']           # total_cost_floor_sep
    cont_cost = m.get('total_cost_cont', m['total_cost'])

    # 현재 COST_MODE에 맞는 항목을 굵게/컬러로 강조
    if COST_MODE == 'floor_by_floor':
        row(ax_info, y, '층별분리 cost [선택]', f"{fbf_cost}원", '#E65100', bold=True); y -= dy
        row(ax_info, y, '연속제작 cost',        f"{cont_cost}원  (-{fbf_cost - cont_cost}원)", '#9E9E9E'); y -= dy
    else:
        row(ax_info, y, '층별분리 cost',        f"{fbf_cost}원", '#9E9E9E'); y -= dy
        row(ax_info, y, '연속제작 cost [선택]', f"{cont_cost}원  (-{fbf_cost - cont_cost}원)", '#1565C0', bold=True); y -= dy

    if core:
        row(ax_info, y, '  기둥 비용', f"{fbf_cost - core['cost']}원" if COST_MODE == 'floor_by_floor' else f"{cont_cost - core['cost']}원")
        y -= dy
        row(ax_info, y, '  코어 비용', f"{core['cost']}원"); y -= dy

    y -= 0.01
    row(ax_info, y, 'norm_ecc',   f"{m['norm_ecc']:.4f}"); y -= dy
    risk_color = '#2E7D32' if m['risk'] == 'low' else '#C62828'
    row(ax_info, y, 'torsion_risk', m['risk'].upper(), risk_color, bold=True)
    y -= dy

    # diag_pair 원리 메모
    if arr == 'diag_pair':
        note_y = max(y - 0.06, 0.01)
        ax_info.text(0.04, note_y,
                     "diag_pair 원리:\n"
                     "C1=C4, C2=C3 대각 배치\n"
                     "⇒ 어떤 기둥 조합에도\n"
                     "   CR = CM 수학적 보장",
                     transform=ax_info.transAxes,
                     fontsize=7.8, va='top', color='#37474F',
                     bbox=dict(boxstyle='round,pad=0.4',
                               facecolor='#E8F5E9',
                               edgecolor='#A5D6A7', linewidth=1.1))


# ─────────────────────────────────────────────────────────────────
# 개별 그림 저장
# ─────────────────────────────────────────────────────────────────
def save_individual(layout):
    fig = plt.figure(figsize=(13, 6.2))
    fig.patch.set_facecolor('white')

    # 상단 타이틀
    fig.suptitle(layout['title'], fontsize=12, fontweight='bold',
                 y=0.98, color='#212121')

    ax_plan = fig.add_axes([0.01, 0.04, 0.56, 0.90])
    ax_info = fig.add_axes([0.60, 0.04, 0.39, 0.90])

    draw_one(layout, ax_plan, ax_info)

    path = os.path.join(OUT_DIR, layout['fname'] + '.png')
    plt.savefig(path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    print(f"  saved: {os.path.basename(path)}")


# ─────────────────────────────────────────────────────────────────
# 통합 그림 저장 (2×3, 마지막 칸 = 범례)
# ─────────────────────────────────────────────────────────────────
def save_combined():
    fig = plt.figure(figsize=(26, 15))
    fig.patch.set_facecolor('white')
    fig.suptitle('MDF 4-Column System Layouts — Design Scenario Comparison',
                 fontsize=15, fontweight='bold', y=0.995, color='#212121')

    positions = [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1)]  # (col, row)
    n_cols, n_rows = 3, 2
    W, H = 1 / n_cols, 1 / n_rows
    pad_x, pad_y = 0.005, 0.01

    for idx, layout in enumerate(LAYOUTS):
        c, r = positions[idx]
        # row 0 = 상단 → matplotlib y: row 0 = 아래쪽. 뒤집기
        r_inv = n_rows - 1 - r
        left   = c * W + pad_x
        bottom = r_inv * H + pad_y
        w      = W - 2 * pad_x
        h      = H - 2 * pad_y

        ax_plan = fig.add_axes([left,          bottom,      w * 0.60, h])
        ax_info = fig.add_axes([left + w*0.61, bottom,      w * 0.38, h])

        # 서브타이틀
        ax_plan.set_title(f"[{idx+1}] {layout['title']}",
                          fontsize=8.5, pad=5, color='#424242')
        draw_one(layout, ax_plan, ax_info)

    # 6번째 칸: 범례
    c, r = 2, 1
    r_inv = n_rows - 1 - r
    left   = c * W + pad_x
    bottom = r_inv * H + pad_y
    ax_leg = fig.add_axes([left, bottom, W - 2*pad_x, H - 2*pad_y])
    ax_leg.axis('off')

    ax_leg.text(0.5, 0.96, 'Legend', ha='center', va='top',
                fontsize=13, fontweight='bold', color='#212121',
                transform=ax_leg.transAxes)

    # N별 색상 범례
    ax_leg.text(0.05, 0.86, 'Strip count (N)',
                fontsize=10, fontweight='bold', color='#424242',
                transform=ax_leg.transAxes)
    n_entries = [(3,'N=3 (low cost)'), (4,'N=4 (baseline)'),
                 (5,'N=5 (safe)'), (6,'N=6'), (7,'N=7 (high perf)')]
    for i, (n, label) in enumerate(n_entries):
        y_leg = 0.78 - i * 0.095
        patch = mpatches.Circle((0.09, y_leg + 0.03), 0.04,
                                transform=ax_leg.transAxes,
                                facecolor=N_FACE[n], edgecolor=N_EDGE[n],
                                linewidth=1.5)
        ax_leg.add_patch(patch)
        ax_leg.text(0.17, y_leg + 0.055, label,
                    transform=ax_leg.transAxes,
                    fontsize=9, va='center', color='#212121')

    # 배치 패턴 설명
    ax_leg.text(0.05, 0.32, 'Arrangement',
                fontsize=10, fontweight='bold', color='#424242',
                transform=ax_leg.transAxes)
    ax_leg.text(0.05, 0.24,
                'uniform_4:  C1=C2=C3=C4=A\n'
                'diag_pair:  C1=C4=A, C2=C3=B\n'
                '  → CR = CM guaranteed\n'
                '  (zero torsion, any combo)',
                transform=ax_leg.transAxes, fontsize=9, va='top',
                color='#37474F',
                bbox=dict(boxstyle='round,pad=0.5', facecolor='#E8F5E9',
                          edgecolor='#A5D6A7'))

    # 기호 설명
    ax_leg.text(0.05, 0.07,
                '+ = CM = CR position (75, 75 mm)\n'
                '◇ = Core (if present)\n'
                '→ = 0° rotation,  ↑ = 90° rotation',
                transform=ax_leg.transAxes, fontsize=8.5, va='bottom',
                color='#616161')

    path = os.path.join(OUT_DIR, 'combined_all_layouts.png')
    plt.savefig(path, dpi=130, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    print(f"  saved: combined_all_layouts.png")


# ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    print("=" * 60)
    print("  시스템 배치 시각화")
    print("=" * 60)

    for layout in LAYOUTS:
        save_individual(layout)

    save_combined()

    print()
    print(f"  출력 폴더: {OUT_DIR}")
    print()


if __name__ == '__main__':
    main()
