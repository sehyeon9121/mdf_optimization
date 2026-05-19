"""
postprocess.py
결과 후처리 모듈
- 단면 결과를 CSV로 저장
- 단면 형상 이미지 저장
"""
import os
import numpy as np
import pandas as pd
from section_geometry import plot_section


def save_results_to_csv(results, save_path):
    """
    단면 결과 목록을 CSV로 저장.

    저장 컬럼:
      name, grid, strip_count, A, cx, cy, Ix, Iy, cost, efficiency

    grid 컬럼은 2D 리스트를 문자열로 저장한다.
    (OpenSeesPy 연동 시 ast.literal_eval로 복원 가능)

    Args:
        results   : list of dict
        save_path : 저장 경로 (.csv)
    """
    if not results:
        print(f"  저장할 결과 없음: {save_path}")
        return

    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    rows = []
    for r in results:
        rows.append({
            'name':        r.get('name', ''),
            'grid':        str(r.get('grid', '')),
            'strip_count': r['strip_count'],
            'A':           r['A'],
            'cx':          r['cx'],
            'cy':          r['cy'],
            'Ix':          r['Ix'],
            'Iy':          r['Iy'],
            'cost':        r['cost'],
            'efficiency':  r['efficiency'],
        })

    df = pd.DataFrame(rows)
    df.to_csv(save_path, index=False, encoding='utf-8-sig')
    print(f"  저장 완료: {save_path} ({len(df)}개)")


def save_section_images(results, config, strip, output_dir, max_images=10):
    """
    상위 단면 형상을 PNG 이미지로 저장.

    Args:
        results    : list of dict
        config     : 설정 dict
        strip      : MDFStrip 인스턴스
        output_dir : 이미지 저장 폴더
        max_images : 최대 저장 이미지 수
    """
    os.makedirs(output_dir, exist_ok=True)
    cell_size = config['grid']['cell_size']

    for i, r in enumerate(results[:max_images]):
        grid = np.array(r['grid'])
        name = r.get('name', f'section_{i:04d}')

        # 제목에 핵심 지표 포함
        title = (
            f"{name}\n"
            f"A={r['A']:.1f}mm²  Ix={r['Ix']:.1f}  Iy={r['Iy']:.1f}\n"
            f"cost={r['cost']}  eff={r['efficiency']:.4f}"
        )

        save_path = os.path.join(output_dir, f"{name}.png")
        plot_section(
            grid, cell_size, strip.b, strip.h,
            title=title, save_path=save_path
        )

    print(f"  이미지 저장 완료: {output_dir} ({min(len(results), max_images)}개)")
