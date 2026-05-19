"""
main.py
MDF Strip 단면 최적화 — 스트립 수별 배치 탐색 진입점

실행:
    python main.py

처리 흐름:
    N = 1 ~ 25 각각:
      N ≤ exhaustive_max (기본 6) → 전수탐색: 모든 연결 배치 × 모든 방향 조합
      N >  exhaustive_max         → GA탐색: 최대 ga_max_collect개 유효 배치 수집

    결과:
      outputs/results_by_strip_count.xlsx  — 전체 결과 (strip_count별 정렬)
      outputs/images/strip_search/         — N별 최적 단면 이미지
"""
import os
import yaml

from materials import MDFStrip
from ga_section import enumerate_all_arrangements, run_ga_by_strip_count
from postprocess import save_results_to_excel, save_section_images

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_config():
    config_path = os.path.join(BASE_DIR, 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def print_summary(best_per_n):
    """N별 최적 단면 요약 테이블 출력"""
    header = (
        f"{'N':>3}  {'탐색방법':^8}  {'발견수':>6}  "
        f"{'cost':>5}  {'Ix':>11}  {'Iy':>11}  {'Ix/Iy':>7}  {'efficiency':>11}"
    )
    print(header)
    print('-' * len(header))
    for n, method, count, best in best_per_n:
        Ix, Iy = best['Ix'], best['Iy']
        ratio = f"{Ix/Iy:.3f}" if Iy > 0 else '-'
        print(
            f"{n:>3}  {method:^8}  {count:>6}  "
            f"{best['cost']:>5}  {Ix:>11.1f}  {Iy:>11.1f}  "
            f"{ratio:>7}  {best['efficiency']:>11.4f}"
        )


def main():
    print("=" * 70)
    print("  MDF Strip 단면 최적화 — 스트립 수별 전수/GA 탐색 (N=1~25)")
    print("=" * 70)

    config = load_config()
    strip  = MDFStrip(config)

    rows          = config['grid']['rows']
    cols          = config['grid']['cols']
    n_max         = rows * cols                          # 25
    exhaustive_max = config['ga'].get('exhaustive_max', 6)
    ga_max_collect = config['ga'].get('ga_max_collect', 500)

    print(f"\n격자       : {rows}×{cols}  ({n_max}셀)")
    print(f"스트립 규격 : {strip.b}mm × {strip.h}mm  (가로=1, 세로=2)")
    print(f"단가       : {strip.cost}원/개")
    print(f"전수탐색   : N = 1 ~ {exhaustive_max}  (모든 연결 배치)")
    print(f"GA탐색     : N = {exhaustive_max+1} ~ {n_max}  (최대 {ga_max_collect}개/N)")
    print()

    all_results  = []   # 전체 결과 누적
    summary_rows = []   # 요약 출력용 (n, method, count, best)

    for n in range(1, n_max + 1):

        if n <= exhaustive_max:
            # ── 전수탐색 ────────────────────────────────────────────
            print(f"  [N={n:2d}] 전수탐색 중...", end=' ', flush=True)
            results = enumerate_all_arrangements(n, config, strip)
            method  = '전수탐색'
        else:
            # ── GA 탐색 ─────────────────────────────────────────────
            print(f"  [N={n:2d}] GA탐색 중...", end=' ', flush=True)
            results = run_ga_by_strip_count(
                config, strip, n,
                seed=42, verbose=False,
                max_collect=ga_max_collect,
            )
            method = 'GA'

        # search_type 태그 부여
        for r in results:
            r['search_type'] = method

        all_results.extend(results)

        if results:
            best = results[0]   # efficiency 내림차순 정렬 첫 번째
            Ix, Iy = best['Ix'], best['Iy']
            ratio = f"{Ix/Iy:.3f}" if Iy > 0 else '-'
            print(
                f"{len(results):>6}개 발견  |  "
                f"최적 efficiency={best['efficiency']:.4f}  "
                f"cost={best['cost']}  Ix/Iy={ratio}"
            )
            summary_rows.append((n, method, len(results), best))
        else:
            print("유효 단면 없음")

    # ── Excel 저장 ─────────────────────────────────────────────────
    excel_path = os.path.join(BASE_DIR, config['output']['excel_path'])
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    print(f"\n[저장] Excel ({len(all_results)}행) → {excel_path}")
    save_results_to_excel(all_results, excel_path)

    # ── 이미지 저장 (N별 최적 단면 1개) ───────────────────────────
    best_images = [row[3] for row in summary_rows]   # 각 N의 최적 단면
    image_dir   = os.path.join(BASE_DIR, config['output']['image_dir'])
    print(f"[저장] 이미지 ({len(best_images)}개) → {image_dir}")
    save_section_images(best_images, config, strip, image_dir, max_images=n_max)

    # ── 콘솔 요약 ─────────────────────────────────────────────────
    print(f"\n[N별 최적 단면 요약]")
    print_summary(summary_rows)
    print("\n완료!")


if __name__ == '__main__':
    main()
