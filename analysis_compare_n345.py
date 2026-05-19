"""
analysis_compare_n345.py
N=3 (저비용 비교안) / N=4 (최소 만족안) / N=5 (안전 여유안) 비교 분석

실행:
    python analysis_compare_n345.py

출력:
    outputs/compare_n345/
        n3_cand_01.png ~ 05.png     N=3 대표 후보 격자 이미지
        n4_cand_01.png ~ 05.png     N=4 대표 후보 격자 이미지
        n5_cand_01.png ~ 05.png     N=5 대표 후보 격자 이미지
        compare_all.png             3×5 통합 비교 이미지
        compare_n345.xlsx           비교표
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
IXY_WIDE  = (0.80, 1.25)   # analysis.py 동일 기본 필터
IXY_TIGHT = (0.95, 1.05)   # 우선 확인 범위
TOP_K     = 5              # N별 대표 후보 수
GRID_ROWS = 5
GRID_COLS = 5


def load_config():
    path = os.path.join(BASE_DIR, 'config.yaml')
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def sep(title=''):
    print("=" * 66)
    if title:
        print(f"  {title}")
        print("=" * 66)


# ─────────────────────────────────────────────────────────────────
# 전수탐색 (N=3, 4, 5)
# ─────────────────────────────────────────────────────────────────
def enumerate_n(target_n, config, strip):
    """N개 strip의 모든 연결 배치 × 모든 방향 조합 탐색."""
    rows    = config['grid']['rows']
    cols    = config['grid']['cols']
    n_cells = rows * cols
    results = []

    for positions in combinations(range(n_cells), target_n):
        # BFS 연결성 검사 (방향 무관)
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
# 후보 선정
# ─────────────────────────────────────────────────────────────────
def select_candidates(results, top_k=TOP_K):
    """
    Ix/Iy 균형 우선 → min_I 내림차순 → 다양성 확보 (min_I 값별 1개씩 우선)
    tight 범위(0.95~1.05) 후보가 top_k 이상이면 그 안에서만 선정.
    """
    rows = []
    for r in results:
        Ix, Iy = r['Ix'], r['Iy']
        if Iy <= 0:
            continue
        ratio = Ix / Iy
        rows.append({
            'name':        r['name'],
            'strip_count': r['strip_count'],
            'cost':        r['cost'],
            'Ix':          Ix,
            'Iy':          Iy,
            'Ix/Iy':       round(ratio, 4),
            'min_I':       min(Ix, Iy),
            'efficiency':  r['efficiency'],
            'grid':        r['grid'],
        })

    df = pd.DataFrame(rows)
    df = df[df['Ix/Iy'].between(*IXY_WIDE)].copy()
    if df.empty:
        return df

    tight = df[df['Ix/Iy'].between(*IXY_TIGHT)]
    pool  = tight if len(tight) >= top_k else df
    pool  = pool.sort_values(['min_I', 'efficiency'], ascending=[False, False])

    # min_I 값이 다른 후보를 우선 수집 → 다양성
    seen, out = {}, []
    for _, row in pool.iterrows():
        key = round(row['min_I'], 0)
        if key not in seen:
            seen[key] = True
            out.append(row)
            if len(out) >= top_k:
                break

    # 부족 시 나머지로 보충 (같은 min_I여도 다른 grid)
    if len(out) < top_k:
        used = {r['name'] for r in out}
        for _, row in pool.iterrows():
            if row['name'] not in used:
                out.append(row)
                used.add(row['name'])
                if len(out) >= top_k:
                    break

    return pd.DataFrame(out).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────
# 평가 함수
# ─────────────────────────────────────────────────────────────────
def assess_symmetry(grid):
    """배치 패턴(위치)의 대칭성을 판단한다 (방향값 무시)."""
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
    """배치 형태로 제작 용이성을 판단한다."""
    g   = np.array(grid)
    pos = list(zip(*np.where(g > 0)))
    if not pos:
        return "-"
    nr = len(set(r for r, c in pos))
    nc = len(set(c for r, c in pos))
    if nr == 1 or nc == 1:  return "직선형 (최고)"
    if nr <= 2 or nc <= 2:  return "L/T형 (보통)"
    return "분산형 (주의)"


def assess_connectivity(grid):
    """배치 형태를 직관적 이름으로 분류한다."""
    g   = np.array(grid)
    pos = [(r, c) for r in range(g.shape[0])
                   for c in range(g.shape[1]) if g[r, c] > 0]
    if not pos:
        return "-"
    nr = len(set(r for r, c in pos))
    nc = len(set(c for r, c in pos))
    n  = len(pos)
    if nr == 1:             return f"가로 직선 ({n}칸)"
    if nc == 1:             return f"세로 직선 ({n}칸)"
    if nr == 2 and nc == 2: return "2×2 블록"
    if nr == 2:             return "가로 2줄"
    if nc == 2:             return "세로 2줄"
    return f"{nr}행×{nc}열 분산"


# ─────────────────────────────────────────────────────────────────
# 격자 이미지
# ─────────────────────────────────────────────────────────────────
C_MAP = {0: '#F0F0F0', 1: '#2166AC', 2: '#D6604D'}
L_MAP = {1: 'H', 2: 'V'}


def _draw_grid(ax, grid, rows=GRID_ROWS, cols=GRID_COLS, fontsize=11):
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


def plot_single(grid, title, save_path):
    """개별 후보 격자 이미지 저장."""
    fig, ax = plt.subplots(figsize=(3.6, 3.9))
    _draw_grid(ax, grid, fontsize=11)
    ax.set_title(title, fontsize=8, pad=5)

    legend_els = [
        patches.Patch(facecolor='#2166AC', label='H : 가로 strip (4×6 mm)'),
        patches.Patch(facecolor='#D6604D', label='V : 세로 strip (6×4 mm)'),
        patches.Patch(facecolor='#F0F0F0', edgecolor='#444444', label='빈칸'),
    ]
    ax.legend(handles=legend_els, loc='upper center',
              bbox_to_anchor=(0.5, -0.02), ncol=1,
              fontsize=6.5, framealpha=0.9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def plot_combined(dfs, save_path):
    """3행(N=3/4/5) × TOP_K열 통합 비교 이미지."""
    n_rows = 3
    n_cols = TOP_K
    fig, axes = plt.subplots(n_rows, n_cols,
                             figsize=(3.0 * n_cols, 3.8 * n_rows))

    row_meta = {
        0: (3, 'N=3  저비용 비교안'),
        1: (4, 'N=4  최소 만족안'),
        2: (5, 'N=5  안전 여유안'),
    }

    for row_idx in range(n_rows):
        n, row_label = row_meta[row_idx]
        df = dfs[n]
        for col_idx in range(n_cols):
            ax = axes[row_idx][col_idx]
            if col_idx >= len(df):
                ax.axis('off')
                continue

            r = df.iloc[col_idx]
            _draw_grid(ax, r['grid'], fontsize=8)

            subtitle = (f"{r['name']}\n"
                        f"min_I={r['min_I']:,.0f}  Ix/Iy={r['Ix/Iy']:.4f}\n"
                        f"eff={r['efficiency']:.2f}  {r['symmetry']}")
            ax.set_title(subtitle, fontsize=7, pad=4)

            if col_idx == 0:
                ax.set_ylabel(row_label, fontsize=9,
                              fontweight='bold', labelpad=8)

    # 공통 범례
    legend_els = [
        patches.Patch(facecolor='#2166AC', label='H : 가로'),
        patches.Patch(facecolor='#D6604D', label='V : 세로'),
        patches.Patch(facecolor='#F0F0F0', edgecolor='#444444', label='빈칸'),
    ]
    fig.legend(handles=legend_els, loc='lower center',
               ncol=3, fontsize=9, framealpha=0.9,
               bbox_to_anchor=(0.5, -0.01))

    fig.suptitle('N=3 / N=4 / N=5  대표 후보 비교  (5×5 격자)',
                 fontsize=13, fontweight='bold', y=1.01)
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
          f"  {'min_I':>10}  {'eff':>8}  {'대칭성':^10}  {'제작':^10}  연결 형태")
    print(f"  {'-'*86}")
    for i, (_, r) in enumerate(df.iterrows(), 1):
        print(f"  {i:>2}  {r['name']:^14}  {int(r['cost']):>5}"
              f"  {r['Ix/Iy']:>7.4f}"
              f"  {r['min_I']:>10,.1f}"
              f"  {r['efficiency']:>8.4f}"
              f"  {r['symmetry']:^10}"
              f"  {r['fabrication']:^10}"
              f"  {r['connectivity']}")
    print()


# ─────────────────────────────────────────────────────────────────
# 비교표 Excel 저장
# ─────────────────────────────────────────────────────────────────
def save_comparison(dfs, path):
    meta = {
        3: ('N=3', '저비용 비교안'),
        4: ('N=4', '최소 만족안'),
        5: ('N=5', '안전 여유안'),
    }
    rows = []
    for n in [3, 4, 5]:
        tag, cat = meta[n]
        for i, (_, r) in enumerate(dfs[n].iterrows(), 1):
            rows.append({
                '분류':            tag,
                '후보 구분':       cat,
                '후보 번호':       i,
                '후보명':          r['name'],
                'cost (원)':       int(r['cost']),
                'Ix (mm4)':        round(r['Ix'], 1),
                'Iy (mm4)':        round(r['Iy'], 1),
                'Ix/Iy':           r['Ix/Iy'],
                'min(Ix,Iy) mm4':  round(r['min_I'], 1),
                'efficiency':      round(r['efficiency'], 4),
                '대칭성':          r['symmetry'],
                '제작 용이성':     r['fabrication'],
                '연결 형태':       r['connectivity'],
                '이미지 파일':     f"n{n}_cand_{i:02d}.png",
            })

    out = pd.DataFrame(rows)
    out.to_excel(path, index=False)
    print(f"  비교표: {os.path.basename(path)}")


# ─────────────────────────────────────────────────────────────────
# main
# ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(COMPARE_DIR, exist_ok=True)
    config = load_config()
    strip  = MDFStrip(config)

    sep("N=3 / N=4 / N=5  대표 후보 비교 분석")
    print("  N=3  저비용 비교안  |  N=4  최소 만족안  |  N=5  안전 여유안")
    print(f"  Ix/Iy 필터: 기본 {IXY_WIDE} / 우선 {IXY_TIGHT}")
    print(f"  N별 대표 후보: {TOP_K}개")
    print()

    # ── 전수탐색 ────────────────────────────────────────────────
    dfs = {}
    for n in [3, 4, 5]:
        print(f"  N={n} 전수탐색 중...", end=' ', flush=True)
        results = enumerate_n(n, config, strip)
        print(f"유효 단면 {len(results):,}개")
        df = select_candidates(results, top_k=TOP_K)
        df['symmetry']     = df['grid'].apply(assess_symmetry)
        df['fabrication']  = df['grid'].apply(assess_fabrication)
        df['connectivity'] = df['grid'].apply(assess_connectivity)
        dfs[n] = df
    print()

    # ── 콘솔 출력 ───────────────────────────────────────────────
    sep("선정 후보 목록")
    labels = {
        3: 'N=3  저비용 비교안',
        4: 'N=4  최소 만족안',
        5: 'N=5  안전 여유안',
    }
    for n in [3, 4, 5]:
        print_candidates(dfs[n], labels[n])

    # ── 개별 이미지 저장 ─────────────────────────────────────────
    sep("격자 이미지 저장")
    for n in [3, 4, 5]:
        for i, (_, r) in enumerate(dfs[n].iterrows(), 1):
            title = (f"{r['name']}  (N={n}  cost={int(r['cost'])}원)\n"
                     f"min_I={r['min_I']:,.1f} mm4   Ix/Iy={r['Ix/Iy']:.4f}\n"
                     f"efficiency={r['efficiency']:.4f}   {r['symmetry']}\n"
                     f"연결: {r['connectivity']}   {r['fabrication']}")
            fname = f"n{n}_cand_{i:02d}.png"
            fpath = os.path.join(COMPARE_DIR, fname)
            plot_single(r['grid'], title, fpath)
            print(f"  {fname}")
    print()

    # ── 통합 비교 이미지 ─────────────────────────────────────────
    combined_path = os.path.join(COMPARE_DIR, 'compare_all.png')
    plot_combined(dfs, combined_path)
    print()

    # ── 비교표 저장 ───────────────────────────────────────────────
    sep("비교표 저장")
    save_comparison(dfs, os.path.join(COMPARE_DIR, 'compare_n345.xlsx'))
    print()

    # ── 분류별 요약 ───────────────────────────────────────────────
    sep("분류별 요약 (대표 후보 #1 기준)")
    n4_max_minI = dfs[4]['min_I'].max()

    for n, label in [(3, '저비용 비교안'), (4, '최소 만족안'), (5, '안전 여유안')]:
        best = dfs[n].iloc[0]
        vs_n4 = best['min_I'] / n4_max_minI * 100
        print(f"  N={n}  [{label}]")
        print(f"    cost           : {int(best['cost'])}원")
        print(f"    min(Ix,Iy)     : {best['min_I']:,.1f} mm4"
              f"  (N=4 대비 {vs_n4:.1f}%)")
        print(f"    Ix/Iy          : {best['Ix/Iy']:.4f}")
        print(f"    efficiency     : {best['efficiency']:.4f}")
        print(f"    대칭성         : {best['symmetry']}")
        print(f"    제작 용이성    : {best['fabrication']}")
        print(f"    연결 형태      : {best['connectivity']}")
        print()

    sep("완료")
    print(f"  저장 폴더: outputs/compare_n345/")
    print(f"  이미지   : n3_cand_01~05.png, n4_cand_01~05.png, n5_cand_01~05.png")
    print(f"  통합     : compare_all.png")
    print(f"  비교표   : compare_n345.xlsx")
    print()


if __name__ == '__main__':
    main()
