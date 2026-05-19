"""
materials.py
MDF Strip 재료 및 단면 기본 특성 정의
"""
import yaml
import os


def load_config(config_path=None):
    """config.yaml 파일을 읽어 설정값 반환"""
    if config_path is None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


class MDFStrip:
    """
    MDF Strip 단일 단면 특성 클래스

    배치 방향:
      값=1: 기본 방향  → x-폭=b(4mm), y-높이=h(6mm)
      값=2: 90도 회전 → x-폭=h(6mm), y-높이=b(4mm)
    """

    def __init__(self, config=None):
        if config is None:
            config = load_config()

        strip_cfg = config['strip']
        self.b = strip_cfg['b']              # 4 mm
        self.h = strip_cfg['h']              # 6 mm
        self.cost = strip_cfg['cost_per_unit']  # 10

        # 방향별 (x-폭 bx, y-높이 by)
        self.dims = {
            1: (self.b, self.h),   # (4, 6)
            2: (self.h, self.b),   # (6, 4)
        }

    def get_dims(self, orientation):
        """배치 방향(1 or 2)에 따른 (bx, by) 반환"""
        return self.dims[orientation]

    def local_inertia(self, orientation):
        """
        배치 방향에 따른 국소 단면 2차 모멘트 반환

        Ix_local = bx * by^3 / 12  (x축 기준 휨 저항)
        Iy_local = by * bx^3 / 12  (y축 기준 휨 저항)

        Returns: (Ix_local, Iy_local) in mm^4
        """
        bx, by = self.get_dims(orientation)
        Ix_local = bx * by**3 / 12
        Iy_local = by * bx**3 / 12
        return Ix_local, Iy_local

    def area(self):
        """단면적 (mm^2) — 방향 무관"""
        return self.b * self.h  # 4 * 6 = 24 mm^2
