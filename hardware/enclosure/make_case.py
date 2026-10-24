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
# ⚠️ 2026-10-21 第二轮（3D 打印试装后修正）。第一版只量了裸 PCB（83.8×73），
#    漏掉按钮/接口凸起 → 装不下、孔位偏。以下基准按**含凸起的总外廓**实测。
PCB_W = 83.8            # 裸板宽（屏幕"与板同宽"仍按它）
PCB_L = 73.0            # 裸板长
TOTAL_W = 88.0          # 总宽：端子插口凸起端 → USB-A/按键凸起端（实测）
TOTAL_L = 75.5          # 总长：PCB 上缘 → 底边接口凸起端（实测）
PROT_LEFT = 2.0         # 端子侧凸起：腔体左内壁基准 → PCB 左缘（估）
PIN_PROT = 4.2          # 板底焊针长：USB-C 口心 = 最低凸起 +5mm ⇒ 反推 4.2
CLEAR = 1.0             # 单边余量（旧 0.6 太紧，且吸收树脂打印收缩）
WALL = 2.5              # 侧壁厚
FLOOR = 3.0             # 底板厚
STD_H = 6.0             # 屏幕铜柱高（穿板，板下也露出）
BOARD_T = 1.6           # 板厚
SCREEN_TOP_Z = 14.0     # 板面到屏幕顶面的高度差（实测）

# 竖直基准（全部从壳底面 Z=0 起算 —— 旧版开孔漏加了 FLOOR，整体偏低 3mm）
Z_BOARD_BOT = FLOOR + PIN_PROT          # 板背面（焊针落在底板上）
Z_BOARD_TOP = Z_BOARD_BOT + BOARD_T     # 板面
Z_USBC = FLOOR + 5.0                    # USB-C 口心：最低凸起 +5mm（实测）
RIM_Z = Z_BOARD_TOP + SCREEN_TOP_Z + 1.4   # 口沿 ≈ 24.2
TOP_T = 3.0             # 面框厚
SKIRT_H = 8.0           # 面框裙边高（扣在外壁上）
SKIRT_T = 2.2           # 裙边厚

# 铜柱（屏幕柱穿板，底板留孔兼作柱端让位）
# ⚠️ 2026-10-24 第三轮：板子实际孔距 79×48.5，打印件量出来 77.5×48（收缩），
#    且整组孔离 USB-C 侧远了 1mm（板上 4mm / 壳上 5mm）。三项一起修：
#    ① 孔距按收缩率反补偿；② 整组往 USB-C 侧（+Y）移 1mm；③ 孔径放大到 φ4.2
#    （铜柱插口实测 φ3，旧 φ3.4 只剩 0.2mm 余量，一有误差就顶死）。
STD_DX = 80.5           # 79 × (79/77.5) —— 收缩补偿
STD_DY = 49.0           # 48.5 × (48.5/48) —— 收缩补偿
STD_X0 = 2.4            # 左柱中心距 PCB 左缘
STD_Y0 = 21.1           # 下排锚定：板上 69.1 + 1.0（往 USB-C 侧）；上排 = 70.1-49 = 21.1
STD_HOLE = 4.2          # φ3 铜柱 + 单边 0.6mm 余量

# 屏幕（面板外形）
SCR_LEN = 56.0          # 实测
SCR_OFF_Y = 17.0        # 屏幕顶边距 PCB 上缘
# 屏幕宽度 = PCB 宽（与板同宽）

# ---- 各接口开孔（2026-10-21 卡尺实测）----
# 底边（USB-C/TF/LCD&TP）：X 参考点 = **端子插口凸起端**（腔体左内壁 + CLEAR）
USBC1_X0, USBC2_X0 = 12.5, 26.0   # 两个 USB-C 左缘（实测 21.5/35 是最左缘→换算）
USBC_W = 9.0                       # 实测口长 9
TF_X0, TF_W = 41.0, 15.0           # 实测最左缘 56、长 15
LCD_X0, LCD_W = 62.5, 13.5         # 实测最左缘 76、长 13.5（第一版漏开！）

# 右边（USB-A + K1/K2/K3）：参考 = **PCB 下缘**（底边角点）往上量
USBA_Y_FROM_BOT = 41.0             # USB-A 中心
KEY_YS_FROM_BOT = (8.5, 16.0, 23.5)  # K1/K2/K3 中心（K1 离下缘最近）
USBA_W, USBA_H = 14.0, 6.5         # 单层开口（宽 × 高，默认）
KEY_D = 3.5                        # 按键过孔（旧 3.2 偏紧）

# 左边（端子组）：用户定"口开大 5mm 就能用" → 两端各放 2.5
TERM_Y0, TERM_Y1 = 22.8, 58.9      # 端子组沿 PCB 上缘起算的跨度（实测 35 长）
TERM_MARGIN = 2.5                  # 开口两侧各加宽
TERM_H = 7.0                       # 端子高出板面（实测）

IN_W = TOTAL_W + 2 * CLEAR      # 内腔（按含凸起总外廓）
IN_L = TOTAL_L + 2 * CLEAR
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
            cx = WALL + CLEAR + PROT_LEFT + STD_X0 + ix * STD_DX
            cy = WALL + CLEAR + STD_Y0 + iy * STD_DY
            m = m - cyl(cx, cy, -1, FLOOR + 1, STD_HOLE)

    bx = WALL + CLEAR + PROT_LEFT   # PCB 左缘 X（腔体左内壁基准 + 端子凸起）
    by = WALL + CLEAR               # PCB 上缘 Y
    bz = Z_BOARD_BOT                # 板背面 Z（板面 = bz + BOARD_T）

    # 左壁（X=0 侧，端子侧）：端子组开口（两端各放 TERM_MARGIN）
    m = m - box(-1, by + TERM_Y0 - TERM_MARGIN, Z_BOARD_TOP - 0.5,
                WALL + 1, by + TERM_Y1 + TERM_MARGIN, Z_BOARD_TOP + TERM_H + 0.5)
    # 右壁（X=OUT_W 侧）：USB-A + K1/K2/K3（位置实测"距 PCB 下缘"→ 换算到上缘基准）
    usba_y = by + PCB_L - USBA_Y_FROM_BOT
    m = m - box(OUT_W - WALL - 1, usba_y - USBA_W / 2, Z_BOARD_TOP - 0.5,
                OUT_W + 1, usba_y + USBA_W / 2, Z_BOARD_TOP + USBA_H)
    for d in KEY_YS_FROM_BOT:
        ky = by + PCB_L - d
        m = m - cyl_x(OUT_W - WALL / 2, ky, Z_BOARD_TOP + 1.0, WALL + 2, KEY_D)
    # 底边（Y=OUT_L 侧）：两个 USB-C + TF + LCD&TP
    #   X 参考 = 端子插口凸起端（腔体左内壁 + CLEAR），与用户实测基准一致
    x0 = WALL + CLEAR
    port_z0, port_z1 = Z_USBC - 2.25, Z_USBC + 2.25   # 口心 ±2.25（含余量）
    for x_left in (USBC1_X0, USBC2_X0):
        m = m - box(x0 + x_left, OUT_L - WALL - 1, port_z0,
                    x0 + x_left + USBC_W, OUT_L + 1, port_z1)
    m = m - box(x0 + TF_X0, OUT_L - WALL - 1, port_z0,
                x0 + TF_X0 + TF_W, OUT_L + 1, port_z1)
    m = m - box(x0 + LCD_X0, OUT_L - WALL - 1, port_z0,
                x0 + LCD_X0 + LCD_W, OUT_L + 1, port_z1)
    # 后壁（Y=0 侧）：顶部条带完全敞开（排针/按键/喇叭都在板上方露出）
    #   —— 不做开口：条带在内侧，外壳只留口沿，不挡视线。

    # 面框固定：两侧各 2 个 M3 自攻孔（孔心 = 口沿下 5mm）
    zs = RIM_Z - 5.0
    for (yy, xx) in ((by + 8, 0), (by + 8, OUT_W), (by + PCB_L - 8, 0), (by + PCB_L - 8, OUT_W)):
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

    bx = WALL + CLEAR + PROT_LEFT
    by = WALL + CLEAR
    # ① 顶部条带窗口：X 内腔全宽，Y 板缘到屏幕顶边前（排针/按键/喇叭露出）
    m = m - box(SKIRT_T + 1.5, by + 2.0, RIM_Z - 1, OUT_W - SKIRT_T - 1.5,
                by + SCR_OFF_Y - 1.5, RIM_Z + TOP_T + 1)
    # ② 屏幕窗口：横跨内腔（屏幕与板同宽），两侧各压 2.5mm、近边压到屏幕顶边、
    #    远边与板边留 2mm 卡边
    m = m - box(bx + 2.5, by + SCR_OFF_Y - 1.5, RIM_Z - 1,
                bx + PCB_W - 2.5, by + SCR_OFF_Y + SCR_LEN - 1.0, RIM_Z + TOP_T + 1)
    # 面框固定孔（与底壳侧壁对应）
    zs = RIM_Z - 5.0
    for (yy, xx) in ((by + 8, 0), (by + 8, OUT_W), (by + PCB_L - 8, 0), (by + PCB_L - 8, OUT_W)):
        cx = SKIRT_T / 2 if xx == 0 else OUT_W - SKIRT_T / 2
        m = m - cyl_x(cx, yy, zs, SKIRT_T + 2, 3.4)
    return m


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    b = to_mesh(build_bottom())
    t = to_mesh(build_top())
    # 备用变体：USB 双层叠口（改常量后重出）
    global USBA_H
    saved, USBA_H = USBA_H, 13.5
    b_dual = to_mesh(build_bottom())
    USBA_H = saved
    for name, mesh in (("case_bottom.stl", b), ("case_top.stl", t),
                       ("case_bottom_usb_dual.stl", b_dual)):
        p = f"{out}/{name}"
        mesh.export(p)
        print(f"{p}: {len(mesh.faces)} 面, 体积 {mesh.volume/1000:.1f} cm3, "
              f"包围盒 {np.round(mesh.bounds[1]-mesh.bounds[0],1)}")
    print(f"外壳外廓: {OUT_W:.1f} × {OUT_L:.1f} × {RIM_Z+TOP_T:.1f} mm")


if __name__ == "__main__":
    main()
