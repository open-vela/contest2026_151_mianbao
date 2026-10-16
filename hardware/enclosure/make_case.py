#!/usr/bin/env python3
"""DshanPixVela-Devkit 外壳生成器（屏幕朝上三明治结构）。

为什么是脚本而不是手工建模：这台板子的官方资料里**没有机械数据**（原理图/IC 手册/
照片，仅此而已，见 README）。所以尺寸来自两处：
  1. 用户卡尺实测（板 83.8×73、铜柱 79×48.5、屏幕 56 长/偏移 18、端子 35×7、USB-A
     13×5.5、USB-C 8.5×3、TF 15×2、按键 7.7 间距/φ2.1、屏面高 14……见 README 表）；
  2. 背面照片按板宽标定后读出的**沿边位置**（端子 22.8~58.9、USB-A 中心 33.5、
     K1/K2/K3 63.7/56.1/47.8、USB-C 16.5 与 34.8、TF 53 等）。
实测数据回填/微调后重跑本脚本即可。

坐标系（与背面照片一致）：
  X 0→83.8 板宽，Y 0→73 板长（Y 增大方向是 USB-C/TF 那条边），Z 0 = 外壳底面。
  板子坐在 6mm 铜柱上：Z 9→10.6；屏幕顶面 Z≈24.6；外壳口沿 Z=26；面框 26→29。

依赖：trimesh + manifold3d（pip install trimesh manifold3d）
输出：case_bottom.stl / case_top.stl（嘉立创 3D 打印可直接上传）
"""
import sys

import manifold3d as m3
import numpy as np
import trimesh

# ---------------------------------------------------------------- 尺寸参数
BOARD_W = 83.8          # 板宽（实测 83~84）
BOARD_L = 73.0          # 板长（实测）
CLEAR = 0.6             # 板与内壁间隙（单边）
WALL = 2.5              # 侧壁厚
FLOOR = 3.0             # 底板厚
STD_H = 6.0             # 铜柱高（底板面到板背面）
BOARD_T = 1.6           # 板厚
SCREEN_TOP_Z = 14.0     # 板面到屏幕顶面的高度差（实测）
RIM_Z = STD_H + BOARD_T + SCREEN_TOP_Z + 1.4   # 口沿高度 ≈ 26
TOP_T = 3.0             # 面框厚
SKIRT_H = 8.0           # 面框裙边高（扣在外壁上）
SKIRT_T = 2.2           # 裙边厚

# 铜柱（= 底板上的 4 个 M3 孔位）：间距实测 79 × 48.5
STD_DX = 79.0
STD_DY = 48.5
STD_X0 = 2.4            # 左孔中心距板左缘（按居中算：83.8-79=4.8 → 2.4/2.4）
STD_Y0 = 20.6           # 上排孔距板上缘（照片读数；下排 = 20.6+48.5 = 69.1）
STD_HOLE = 3.4          # M3 过孔

# 屏幕（面板外形）
SCR_LEN = 56.0          # 实测
SCR_OFF_Y = 17.0        # 屏幕顶边距板上缘（实测"约18"，取 17 让远边与板边齐）
# 屏幕宽度 = 板宽（实测"与板子宽一样"）→ 面框两侧只能压 1.5mm 边

# 各接口开孔（沿边位置来自背面照片读数，单位 mm；±1mm）
TERM_Y0, TERM_Y1 = 22.8, 58.9   # 端子组（CAN×2 + RS485×2）沿边跨度（实测 35 长）
TERM_H = 7.0                    # 端子高出板面（实测）
TERM_Z0 = STD_H + BOARD_T       # 从板面起
USBA_Y = 33.5                   # USB HOST（双层）中心
USBA_W, USBA_H = 14.0, 13.5     # 开口（实测单口 13×5.5，双层叠起来）
USBC_XS = (16.5, 34.8)          # 两个 USB-C 中心（照片读数）
USBC_W, USBC_H = 9.0, 3.5       # 实测 8.5×3 + 余量
TF_X = 53.0                     # TF 卡中心（照片读数）
TF_W, TF_H = 15.5, 2.4          # 实测 15×2 + 余量
KEY_YS = (63.7, 56.1, 47.8)     # K1/K2/K3 中心（间距实测 7.7）
KEY_D = 3.2                     # 按键过孔（实测帽径 2.1 + 余量）
KEY_Z = STD_H + BOARD_T + 1.0   # 孔心高度（板面上 1mm）

IN_W = BOARD_W + 2 * CLEAR      # 内腔
IN_L = BOARD_L + 2 * CLEAR
OUT_W = IN_W + 2 * WALL
OUT_L = IN_L + 2 * WALL


# ---------------------------------------------------------------- 工具
def box(x0, y0, z0, x1, y1, z1):
    return m3.Manifold.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl(cx, cy, z0, z1, d, segments=48):
    return m3.Manifold.cylinder(z1 - z0, d / 2, d / 2, segments).translate([cx, cy, z0])


def cyl_x(cx, cy, cz, length, d, segments=48):
    """沿 X 轴的圆柱（用于侧壁上的按键孔）。"""
    c = m3.Manifold.cylinder(length, d / 2, d / 2, segments)
    c = c.rotate([0, 90, 0]).translate([cx - length / 2, cy, cz])
    return c


def cyl_y(cx, cy, cz, length, d, segments=48):
    """沿 Y 轴的圆柱（用于前壁/后壁上的孔）。"""
    c = m3.Manifold.cylinder(length, d / 2, d / 2, segments)
    c = c.rotate([90, 0, 0]).translate([cx, cy - length / 2, cz])
    return c


def to_mesh(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                           faces=np.asarray(mesh.tri_verts), process=True)


# ---------------------------------------------------------------- 底壳
def build_bottom():
    solid = box(0, 0, 0, OUT_W, OUT_L, RIM_Z)
    cavity = box(WALL, WALL, FLOOR, WALL + IN_W, WALL + IN_L, RIM_Z + 1)
    m = solid - cavity

    # 底板：4 个铜柱安装孔
    for ix in (0, 1):
        for iy in (0, 1):
            cx = WALL + CLEAR + STD_X0 + ix * STD_DX
            cy = WALL + CLEAR + STD_Y0 + iy * STD_DY
            m = m - cyl(cx, cy, -1, FLOOR + 1, STD_HOLE)

    bx = WALL + CLEAR          # 板左缘 X
    by = WALL + CLEAR          # 板上缘 Y
    bz = FLOOR + STD_H         # 板背面 Z（板面 = bz + BOARD_T）

    # 左壁（X=0 侧，背面照片左缘）：端子组开口 + MIC 拾音孔
    m = m - box(-1, by + TERM_Y0, TERM_Z0 - 0.5, WALL + 1, by + TERM_Y1,
                TERM_Z0 + TERM_H + 0.5)
    # 右壁（X=OUT_W 侧）：USB-A 双层开口 + K1/K2/K3 三孔
    m = m - box(OUT_W - WALL - 1, by + USBA_Y - USBA_W / 2, TERM_Z0 - 0.5,
                OUT_W + 1, by + USBA_Y + USBA_W / 2, TERM_Z0 + USBA_H)
    for ky in KEY_YS:
        m = m - cyl_x(OUT_W - WALL / 2, by + ky, KEY_Z, WALL + 2, KEY_D)
    # 前壁（Y=OUT_L 侧）：两个 USB-C + TF 卡
    for cx in USBC_XS:
        m = m - box(bx + cx - USBC_W / 2, OUT_L - WALL - 1, TERM_Z0 - 0.5,
                    bx + cx + USBC_W / 2, OUT_L + 1, TERM_Z0 + USBC_H)
    m = m - box(bx + TF_X - TF_W / 2, OUT_L - WALL - 1, TERM_Z0 - 0.5,
                bx + TF_X + TF_W / 2, OUT_L + 1, TERM_Z0 + TF_H)
    # 后壁（Y=0 侧）：顶部条带完全敞开（排针/按键/喇叭都在板上方露出）
    #   —— 不做开口：条带在内侧，外壳只留口沿，不挡视线。

    # 面框固定：两侧各 2 个 M3 自攻孔（孔心 = 口沿下 5mm）
    zs = RIM_Z - 5.0
    for (yy, xx) in ((by + 8, 0), (by + 8, OUT_W), (by + BOARD_L - 8, 0), (by + BOARD_L - 8, OUT_W)):
        if xx == 0:
            m = m - cyl_x(WALL / 2, yy, zs, WALL + 2, 2.5)
        else:
            m = m - cyl_x(OUT_W - WALL / 2, yy, zs, WALL + 2, 2.5)
    return m


# ---------------------------------------------------------------- 面框
def build_top():
    plate = box(0, 0, RIM_Z, OUT_W, OUT_L, RIM_Z + TOP_T)
    skirt = box(0, 0, RIM_Z - SKIRT_H, OUT_W, OUT_L, RIM_Z) - \
            box(SKIRT_T, SKIRT_T, RIM_Z - SKIRT_H - 1, OUT_W - SKIRT_T, OUT_L - SKIRT_T, RIM_Z + 1)
    m = plate + skirt

    bx = WALL + CLEAR
    by = WALL + CLEAR
    # ① 顶部条带窗口：X 内腔全宽，Y 板缘到屏幕顶边前（排针/按键/喇叭露出）
    m = m - box(SKIRT_T + 1.5, by + 2.0, RIM_Z - 1, OUT_W - SKIRT_T - 1.5,
                by + SCR_OFF_Y - 1.5, RIM_Z + TOP_T + 1)
    # ② 屏幕窗口：横跨内腔（屏幕与板同宽），两侧各压 2.5mm、近边压到屏幕顶边、
    #    远边与板边留 2mm 卡边
    m = m - box(bx + 2.5, by + SCR_OFF_Y - 1.5, RIM_Z - 1,
                bx + BOARD_W - 2.5, by + SCR_OFF_Y + SCR_LEN - 1.0, RIM_Z + TOP_T + 1)
    # 面框固定孔（与底壳侧壁对应）
    zs = RIM_Z - 5.0
    for (yy, xx) in ((by + 8, 0), (by + 8, OUT_W), (by + BOARD_L - 8, 0), (by + BOARD_L - 8, OUT_W)):
        cx = SKIRT_T / 2 if xx == 0 else OUT_W - SKIRT_T / 2
        m = m - cyl_x(cx, yy, zs, SKIRT_T + 2, 3.4)
    return m


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    b = to_mesh(build_bottom())
    t = to_mesh(build_top())
    for name, mesh in (("case_bottom.stl", b), ("case_top.stl", t)):
        p = f"{out}/{name}"
        mesh.export(p)
        print(f"{p}: {len(mesh.faces)} 面, 体积 {mesh.volume/1000:.1f} cm3, "
              f"包围盒 {np.round(mesh.bounds[1]-mesh.bounds[0],1)}")
    print(f"外壳外廓: {OUT_W:.1f} × {OUT_L:.1f} × {RIM_Z+TOP_T:.1f} mm")


if __name__ == "__main__":
    main()
