"""
analysis_compare_n345.py
N=3 (저비용 비교안) / N=4 (최소 만족안) / N=5 (안전 여유안) 비교 분석

변경 사항 (2차):
  - 원본 배치 vs 중심 정렬 2-패널 시각화
  - 중심 정렬 여부 / compactness 평가 추가
  - N=5: 분산형(최고 성능) + 밀집형(compact) 분리

실행:
    python analysis_compare_n345.py

출력:
    outputs/compare_n345/
        n3_cand_01~05.png       N=3 후보 (원본+중심 정렬 2패널)
        n4_cand_01~05.png       N=4 후보
        n5_cand_01~05.png       N=5 최고 성능 후보 (분산형)
        n5_compact_01~03.png    N=5 밀집형 후보
        compare_all.png         3×5 통합 비교 (중심 정렬 기준)
        compare_n5_compact.png  N=5 밀집/분산 비교 포함 4×5 이미지
        compare_n345.xlsx       최종 비교표
"""

import os
import sys
import yaml
import warnings
from itertools import combinations, product as iproduct

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches

warnings.filterwarnings('ignore')

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR  = os.path.join(BASE_DIR, 'outputs')
COMPARE_DIR = os.path.join(OUTPUT_DIR, 'compare_n345')

sys.path.insert(0, BASE_DIR)
from materials import MDFStrip
from section_properties import compute_section_properties

# ── 설정 ─────────────────────────────────────────────────────────
IXY_WIDE         = (0.80, 1.25)
IXY_TIGHT        = (0.95, 1.05)
TOP_K            = 5
TOP_K_COMPACT_N5 = 3
GRID_ROWS        = 5
GRID_COLS        = 5


def load_config():
    with open(os.path.join(BASE_DIR, 'config.yaml'), 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def sep(title=''):
    print("=" * 68)
    if title:
        print(f"  {title}")
        print("=" * 68)


# ─────────────────────────────────────────────────────────────────
# 전수탐색
# ─────────────────────────────────────────────────────────────────
def enumerate_n(target_n, config, strip):
    rows    = config['grid']['rows']
    cols    = config['grid']['cols']
    n_cells = rows * cols
    results = []

    for positions in combinations(range(n_cells), target_n):
        pos_set = set(positions)
        visited = {positions[0]}
        queue   = [positions[0]]
        while queue:
            cell = queue.pop()
            r, c = divmod(cell, cols)
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    nb = nr * cols + nc
                    if nb in pos_set and nb not in visited:
                        visited.add(nb)
                        queue.append(nb)
        if len(visited) != target_n:
            continue

        for orientations in iproduct([1, 2], repeat=target_n):
            grid = np.zeros((rows, cols), dtype=int)
            for pos, ori in zip(positions, orientations):
                r, c = divmod(pos, cols)
                grid[r, c] = ori
            props = compute_section_properties(grid, config, strip)
            if props is None:
                continue
            props['grid'] = grid.tolist()
            props['name'] = f"n{target_n:02d}_{len(results):05d}"
            results.append(props)

    return sorted(results, key=lambda x: x['efficiency'], reverse=True)


# ─────────────────────────────────────────────────────────────────
# 격자 조작
# ─────────────────────────────────────────────────────────────────
def get_bbox(grid):
    """점유된 셀의 bounding box: (r_min, r_max, c_min, c_max) 또는 None."""
    g        = np.array(grid)
    occupied = np.where(g > 0)
    if len(occupied[0]) == 0:
        return None
    return (int(occupied[0].min()), int(occupied[0].max()),
            int(occupied[1].min()), int(occupied[1].max()))


def center_grid(grid, rows=GRID_ROWS, cols=GRID_COLS):
    """
    배치를 5×5 격자 중심(2.0, 2.0)으로 정수 단위 평행 이동.
    반환: (centered_grid, (dr, dc))
    """
    g    = np.array(grid, dtype=int)
    bbox = get_bbox(g)
    if bbox is None:
        return g.tolist(), (0, 0)

    r_min, r_max, c_min, c_max = bbox
    r_ctr = (r_min + r_max) / 2.0
    c_ctr = (c_min + c_max) / 2.0
    gctr  = (rows - 1) / 2.0   # 5×5: 2.0

    dr = round(gctr - r_ctr)
    dc = round(gctr - c_ctr)

    new_g = np.zeros((rows, cols), dtype=int)
    for r in range(rows):
        for c in range(cols):
            if g[r, c] > 0:
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols:
                    new_g[nr, nc] = g[r, c]

    return new_g.tolist(), (int(dr), int(dc))


# ─────────────────────────────────────────────────────────────────
# 평가 함수
# ─────────────────────────────────────────────────────────────────
def assess_centerness(grid):
    """원본 배치가 격자 중심에서 얼마나 떨어져 있는지 (이동 필요량)."""
    _, (dr, dc) = center_grid(grid)
    if dr == 0 and dc == 0:
        return "이미 중심 정렬"
    dist = (dr**2 + dc**2) ** 0.5
    tag  = "준중심" if dist <= 1.0 else ("편심 (경미)" if dist <= 1.5 else "편심")
    return f"{tag} ({dr:+d},{dc:+d})"


def assess_symmetry(grid):
    """점유 위치(방향 무시)의 대칭성."""
    g    = (np.array(grid) > 0).astype(int)
    lr   = np.array_equal(g, np.fliplr(g))
    ud   = np.array_equal(g, np.flipud(g))
    r180 = np.array_equal(g, np.rot90(g, 2))
    if lr and ud:  return "4중 대칭"
    if r180:       return "중심 대칭"
    if lr:         return "좌우 대칭"
    if ud:         return "상하 대칭"
    return "비대칭"


def assess_fabrication(grid):
    g   = np.array(grid)
    pos = list(zip(*np.where(g > 0)))
    if not pos: return "-"
    nr = len(set(r for r, c in pos))
    nc = len(set(c for r, c in pos))
    if nr == 1 or nc == 1:  return "직선형 (최고)"
    if nr <= 2 or nc <= 2:  return "L/T형 (보통)"
    return "분산형 (주의)"


def assess_compactness(grid):
    """
    bounding box 크기 × 실제 점유 밀도.
    반환: (label, density, bbox_area)
    """
    g    = np.array(grid)
    bbox = get_bbox(g)
    if bbox is None:
        return "비어있음", 0.0, 0
    r_min, r_max, c_min, c_max = bbox
    n         = int(np.sum(g > 0))
    r_span    = r_max - r_min + 1
    c_span    = c_max - c_min + 1
    bbox_area = r_span * c_span
    density   = n / bbox_area

    if density >= 1.0:    label = f"완전 밀집 ({r_span}x{c_span})"
    elif density >= 0.75: label = f"밀집형 ({r_span}x{c_span}, {density:.0%})"
    elif density >= 0.50: label = f"준밀집형 ({r_span}x{c_span}, {density:.0%})"
    else:                 label = f"분산형 ({r_span}x{c_span}, {density:.0%})"

    return label, density, bbox_area


def assess_connectivity(grid):
    g   = np.array(grid)
    pos = [(r, c) for r in range(g.shape[0])
           for c in range(g.shape[1]) if g[r, c] > 0]
    if not pos: return "-"
    nr  = len(set(r for r, c in pos))
    nc  = len(set(c for r, c in pos))
    n   = len(pos)
    if nr == 1:              return f"가로 직선 ({n}칸)"
    if nc == 1:              return f"세로 직선 ({n}칸)"
    if nr == 2 and nc == 2:  return "2x2 블록"
    if nr == 2:              return "가로 2줄"
    if nc == 2:              return "세로 2줄"
    return f"{nr}행x{nc}열 분산"


def enrich(df):
    """평가 컬럼을 한꺼번에 추가."""
    d = df.copy()
    d['centerness']      = d['grid'].apply(assess_centerness)
    d['symmetry']        = d['grid'].apply(assess_symmetry)
    d['fabrication']     = d['grid'].apply(assess_fabrication)
    d['connectivity']    = d['grid'].apply(assess_connectivity)
    d['compactness']     = d['grid'].apply(lambda g: assess_compactness(g)[0])
    d['compact_density'] = d['grid'].apply(lambda g: assess_compactness(g)[1])
    return d


# ─────────────────────────────────────────────────────────────────
# 후보 선정
# ─────────────────────────────────────────────────────────────────
def _build_df(results):
    rows = []
    for r in results:
        Ix, Iy = r['Ix'], r['Iy']
        if Iy <= 0: continue
        rows.append({
            'name':        r['name'],
            'strip_count': r['strip_count'],
            'cost':        r['cost'],
            'Ix':          Ix, 'Iy': Iy,
            'Ix/Iy':       round(Ix / Iy, 4),
            'min_I':       min(Ix, Iy),
            'efficiency':  r['efficiency'],
            'grid':        r['grid'],
        })
    return pd.DataFrame(rows)


def select_candidates(results, top_k=TOP_K):
    """tight Ix/Iy → min_I 내림차순, min_I 값 다양성 우선."""
    df = _build_df(results)
    df = df[df['Ix/Iy'].between(*IXY_WIDE)].copy()
    if df.empty: return df

    tight = df[df['Ix/Iy'].between(*IXY_TIGHT)]
    pool  = tight if len(tight) >= top_k else df
    pool  = pool.sort_values(['min_I', 'efficiency'], ascending=[False, False])

    seen, out = {}, []
    for _, row in pool.iterrows():
        key = round(row['min_I'], 0)
        if key not in seen:
            seen[key] = True
            out.append(row)
            if len(out) >= top_k: break

    if len(out) < top_k:
        used = {r['name'] for r in out}
        for _, row in pool.iterrows():
            if row['name'] not in used:
                out.append(row)
                used.add(row['name'])
                if len(out) >= top_k: break

    return pd.DataFrame(out).reset_index(drop=True)


def select_compact_n5(results, top_k=TOP_K_COMPACT_N5):
    """N=5 중 밀집형 (bbox_area <= 6, 즉 2×3 이하) 상위 후보."""
    df = _build_df(results)
    df = df[df['Ix/Iy'].between(*IXY_WIDE)].copy()
    if df.empty: return pd.DataFrame()

    df['_bbox_area'] = df['grid'].apply(
        lambda g: (lambda b: (b[1]-b[0]+1)*(b[3]-b[2]+1) if b else 99)(get_bbox(g))
    )
    compact = df[df['_bbox_area'] <= 6].drop(columns=['_bbox_area'])
    return (compact
            .sort_values(['min_I', 'efficiency'], ascending=[False, False])
            .head(top_k)
            .reset_index(drop=True))


# ─────────────────────────────────────────────────────────────────
# 시각화 공통
# ─────────────────────────────────────────────────────────────────
C_MAP = {0: '#F0F0F0', 1: '#2166AC', 2: '#D6604D'}
L_MAP = {1: 'H', 2: 'V'}

LEGEND_ELS = [
    patches.Patch(facecolor='#2166AC', label='H : 가로 strip (4x6 mm)'),
    patches.Patch(facecolor='#D6604D', label='V : 세로 strip (6x4 mm)'),
    patches.Patch(facecolor='#F0F0F0', edgecolor='#555555', label='빈칸'),
]


def _draw_grid_ax(ax, grid, rows=GRID_ROWS, cols=GRID_COLS, fontsize=11):
    """ax에 격자를 그린다. ax 설정 (xlim, aspect)도 함께."""
    g = np.array(grid)
    for r in range(rows):
        for c in range(cols):
            val  = int(g[r, c])
            rect = patches.Rectangle(
                (c, rows - 1 - r), 1, 1,
                linewidth=0.8, edgecolor='#444444',
                facecolor=C_MAP.get(val, '#FFFFFF')
            )
            ax.add_patch(rect)
            if val > 0:
                ax.text(c + 0.5, rows - 1 - r + 0.5, L_MAP[val],
                        ha='center', va='center',
                        fontsize=fontsize, fontweight='bold', color='white')
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows)
    ax.set_aspect('equal')
    ax.axis('off')


# ─────────────────────────────────────────────────────────────────
# 개별 이미지: 원본(좌) + 중심 정렬(우)
# ─────────────────────────────────────────────────────────────────
def plot_single(grid, title, save_path):
    centered, (dr, dc) = center_grid(grid)
    shift_note = "이미 중심 정렬" if (dr == 0 and dc == 0) else f"이동: ({dr:+d}, {dc:+d}) 셀"

    fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.2))

    _draw_grid_ax(axes[0], grid, fontsize=10)
    axes[0].set_title("원본 배치\n(탐색 결과 좌표)", fontsize=8, pad=5)

    _draw_grid_ax(axes[1], centered, fontsize=10)
    axes[1].set_title(f"중심 정렬 후\n{shift_note}", fontsize=8, pad=5)

    fig.suptitle(title, fontsize=7.5, y=1.04)
    fig.legend(handles=LEGEND_ELS, loc='lower center',
               bbox_to_anchor=(0.5, -0.05), ncol=3, fontsize=7, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


# ─────────────────────────────────────────────────────────────────
# 통합 비교 이미지 (중심 정렬 기준)
# ─────────────────────────────────────────────────────────────────
def plot_combined(rows_meta, save_path, title_suffix="중심 정렬 기준"):
    """
    rows_meta: list of (df, row_label)
    각 행에 TOP_K개 격자를 중심 정렬하여 표시.
    """
    n_rows = len(rows_meta)
    n_cols = TOP_K
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(3.0 * n_cols, 3.9 * n_rows))

    if n_rows == 1:
        axes = [axes]   # 2D로 만들기

    for row_idx, (df, row_label) in enumerate(rows_meta):
        for col_idx in range(n_cols):
            ax = axes[row_idx][col_idx]
            if col_idx >= len(df):
                ax.axis('off')
                continue

            r              = df.iloc[col_idx]
            centered, (dr, dc) = center_grid(r['grid'])
            shift_note     = "" if (dr == 0 and dc == 0) else f" [{dr:+d},{dc:+d}]"

            _draw_grid_ax(ax, centered, fontsize=7)

            subtitle = (f"{r['name']}{shift_note}\n"
                        f"min_I={r['min_I']:,.0f}  Ix/Iy={r['Ix/Iy']:.4f}\n"
                        f"eff={r['efficiency']:.2f}  {r['symmetry']}")
            ax.set_title(subtitle, fontsize=6.5, pad=4)

            if col_idx == 0:
                ax.set_ylabel(row_label, fontsize=8.5,
                              fontweight='bold', labelpad=8)

    fig.legend(handles=LEGEND_ELS, loc='lower center', ncol=3,
               fontsize=8.5, framealpha=0.9, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle(f'N=3 / N=4 / N=5  대표 후보 비교  (5x5 격자, {title_suffix})',
                 fontsize=12, fontweight='bold', y=1.01)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  통합 이미지: {os.path.basename(save_path)}")


# ─────────────────────────────────────────────────────────────────
# 콘솔 출력
# ─────────────────────────────────────────────────────────────────
def print_candidates(df, header):
    print(f"  [{header}]")
    print(f"  {'#':>2}  {'name':^14}  {'cost':>5}  {'Ix/Iy':>7}"
          f"  {'min_I':>10}  {'eff':>8}  {'중심 정렬':^16}  {'대칭성':^10}  제작")
    print(f"  {'-'*94}")
    for i, (_, r) in enumerate(df.iterrows(), 1):
        print(f"  {i:>2}  {r['name']:^14}  {int(r['cost']):>5}"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r['min_I']:>10,.1f}"
              f"  {r['efficiency']:>8.4f}"
              f"  {r['centerness']:^16}"
              f"  {r['symmetry']:^10}"
              f"  {r['fabrication']}")
    print()


# ─────────────────────────────────────────────────────────────────
# 비교표 Excel 저장
# ─────────────────────────────────────────────────────────────────
def save_comparison(records, path):
    pd.DataFrame(records).to_excel(path, index=False)
    print(f"  비교표: {os.path.basename(path)}")


# ─────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(COMPARE_DIR, exist_ok=True)
    config = load_config()
    strip  = MDFStrip(config)

    sep("N=3 / N=4 / N=5  비교 분석  (중심 정렬 + compactness)")
    print("  [확인] 원본 이미지: 탐색 결과 좌표 그대로 (좌상단 기준)")
    print("  [추가] 중심 정렬: 배치 bounding box를 5x5 격자 (2,2) 중심으로 이동")
    print("  [추가] N=5: 분산형(최고 성능) + 밀집형(bbox <= 2x3) 분리")
    print()

    # ── 전수탐색 ──────────────────────────────────────────────────
    all_results = {}
    for n in [3, 4, 5]:
        print(f"  N={n} 전수탐색 중...", end=' ', flush=True)
        res = enumerate_n(n, config, strip)
        all_results[n] = res
        print(f"유효 단면 {len(res):,}개")
    print()

    # ── 후보 선정 + 평가 ──────────────────────────────────────────
    dfs = {n: enrich(select_candidates(all_results[n])) for n in [3, 4, 5]}
    n5_compact = enrich(select_compact_n5(all_results[5]))
    has_compact = not n5_compact.empty

    # ── 콘솔 출력 ─────────────────────────────────────────────────
    sep("선정 후보 목록 (원본 배치 기준 평가)")
    print_candidates(dfs[3], "N=3  저비용 비교안")
    print_candidates(dfs[4], "N=4  최소 만족안")
    print_candidates(dfs[5], "N=5  안전 여유안 (최고 성능/분산형)")
    if has_compact:
        print_candidates(n5_compact, "N=5  밀집형 (compact, bbox <= 2x3)")

    # N=5 compactness 상세
    sep("N=5 compactness 비교")
    print(f"  {'#':>2}  {'name':^14}  {'min_I':>10}  {'밀집도':^28}  제작")
    print(f"  {'-'*72}")
    for i, (_, r) in enumerate(dfs[5].iterrows(), 1):
        print(f"  {i:>2}  {r['name']:^14}  {r['min_I']:>10,.1f}  "
              f"{r['compactness']:^28}  {r['fabrication']}")
    print()
    if has_compact:
        print("  --- N=5 밀집형 ---")
        for i, (_, r) in enumerate(n5_compact.iterrows(), 1):
            print(f"  {i:>2}  {r['name']:^14}  {r['min_I']:>10,.1f}  "
                  f"{r['compactness']:^28}  {r['fabrication']}")
    print()

    # ── 개별 이미지 저장 ─────────────────────────────────────────
    sep("격자 이미지 저장 (원본 + 중심 정렬 2패널)")
    for n in [3, 4, 5]:
        for i, (_, r) in enumerate(dfs[n].iterrows(), 1):
            title = (f"{r['name']}  (N={n}  cost={int(r['cost'])}원)\n"
                     f"min_I={r['min_I']:,.1f} mm4   Ix/Iy={r['Ix/Iy']:.4f}\n"
                     f"eff={r['efficiency']:.4f}   {r['symmetry']}   {r['compactness']}")
            fname = f"n{n}_cand_{i:02d}.png"
            plot_single(r['grid'], title, os.path.join(COMPARE_DIR, fname))
            print(f"  {fname}")

    if has_compact:
        for i, (_, r) in enumerate(n5_compact.iterrows(), 1):
            title = (f"{r['name']}  (N=5 밀집형  cost={int(r['cost'])}원)\n"
                     f"min_I={r['min_I']:,.1f} mm4   Ix/Iy={r['Ix/Iy']:.4f}\n"
                     f"eff={r['efficiency']:.4f}   {r['symmetry']}   {r['compactness']}")
            fname = f"n5_compact_{i:02d}.png"
            plot_single(r['grid'], title, os.path.join(COMPARE_DIR, fname))
            print(f"  {fname}")
    print()

    # ── 통합 비교 이미지 ─────────────────────────────────────────
    plot_combined(
        [(dfs[3], 'N=3  저비용 비교안'),
         (dfs[4], 'N=4  최소 만족안'),
         (dfs[5], 'N=5  안전 여유안')],
        os.path.join(COMPARE_DIR, 'compare_all.png'),
    )

    if has_compact:
        # N=5 compact 행을 TOP_K 크기로 맞추기 위해 빈 행 포함 DataFrame 사용
        n5c_padded = n5_compact.reindex(range(TOP_K))
        plot_combined(
            [(dfs[3],      'N=3  저비용 비교안'),
             (dfs[4],      'N=4  최소 만족안'),
             (dfs[5],      'N=5  분산형 (최고 성능)'),
             (n5c_padded,  'N=5  밀집형 (compact)')],
            os.path.join(COMPARE_DIR, 'compare_n5_compact.png'),
            title_suffix="N=5 밀집/분산 비교 포함",
        )
    print()

    # ── 비교표 ───────────────────────────────────────────────────
    sep("비교표 저장")
    n4_ref = dfs[4]['min_I'].max()
    records = []

    groups = [
        (dfs[3],      'N=3', '저비용 비교안',          'cand'),
        (dfs[4],      'N=4', '최소 만족안',              'cand'),
        (dfs[5],      'N=5', '안전 여유안 (분산형)',    'cand'),
    ]
    if has_compact:
        groups.append((n5_compact, 'N=5', '안전 여유안 (밀집형)', 'compact'))

    for df_g, tag, role, img_prefix in groups:
        for i, (_, r) in enumerate(df_g.iterrows(), 1):
            if pd.isna(r.get('name', None)): continue
            _, (dr, dc) = center_grid(r['grid'])
            is_ctr = "이미 중심" if (dr == 0 and dc == 0) else f"이동 ({dr:+d},{dc:+d})"
            records.append({
                'N':               int(r['strip_count']),
                '역할':            role,
                '후보 번호':       i,
                '후보명':          r['name'],
                'cost (원)':       int(r['cost']),
                'min(Ix,Iy) mm4':  round(r['min_I'], 1),
                'N=4 대비 강성':   f"{r['min_I']/n4_ref*100:.1f}%",
                'Ix/Iy':           r['Ix/Iy'],
                'efficiency':      round(r['efficiency'], 4),
                '중심 정렬 여부':  is_ctr,
                '대칭성':          r['symmetry'],
                '제작 용이성':     r['fabrication'],
                '연결 형태':       r['connectivity'],
                '밀집도':          r['compactness'],
                '이미지 파일':     f"n{int(r['strip_count'])}_{img_prefix}_{i:02d}.png",
            })

    save_comparison(records, os.path.join(COMPARE_DIR, 'compare_n345.xlsx'))
    print()

    # ── 분류별 요약 ───────────────────────────────────────────────
    sep("분류별 요약 (대표 후보 #1 기준)")
    entries = [
        (dfs[3],    3, '저비용 비교안'),
        (dfs[4],    4, '최소 만족안'),
        (dfs[5],    5, '안전 여유안 (분산형)'),
    ]
    if has_compact:
        entries.append((n5_compact, 5, '안전 여유안 (밀집형)'))

    for df_e, n, label in entries:
        best = df_e.iloc[0]
        if pd.isna(best.get('name')): continue
        vs_n4 = best['min_I'] / n4_ref * 100
        print(f"  N={n}  [{label}]")
        print(f"    cost           : {int(best['cost'])}원")
        print(f"    min(Ix,Iy)     : {best['min_I']:,.1f} mm4  (N=4 대비 {vs_n4:.1f}%)")
        print(f"    Ix/Iy          : {best['Ix/Iy']:.4f}")
        print(f"    efficiency     : {best['efficiency']:.4f}")
        print(f"    중심 정렬 여부 : {best['centerness']}")
        print(f"    대칭성         : {best['symmetry']}")
        print(f"    제작 용이성    : {best['fabrication']}")
        print(f"    밀집도         : {best['compactness']}")
        print()

    sep("완료")
    print(f"  저장 폴더 : outputs/compare_n345/")
    print(f"  개별 이미지: n3/4/5_cand_01~05.png  (원본+중심정렬 2패널)")
    if has_compact:
        print(f"               n5_compact_01~03.png")
    print(f"  통합 이미지: compare_all.png")
    if has_compact:
        print(f"               compare_n5_compact.png  (N=5 밀집/분산 포함)")
    print(f"  비교표    : compare_n345.xlsx")
    print()


if __name__ == '__main__':
    main()
