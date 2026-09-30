#!/usr/bin/env python3
"""展示页"显示/隐藏"的静态检查 —— 不联网、不需要浏览器、不花钱。

为什么需要它（台账 §11.33）
--------------------------
2026-09-30 发现两个**永远显示不出来**的元素：报告卡片 `#report` 和"有新消息 ↓"
按钮 `#jump`。写法都是 `el.style.display = ""` —— 而那不是"显示"，是**清除行内
样式**。这两个元素恰恰是被 **CSS 里的** `display: none` 藏起来的，于是清掉行内
样式之后那条规则重新生效，元素纹丝不动。

对照：`#doneBadge` / `#roleBadge` / `#roundBadge` 是在 **HTML 上**写
`style="display:none"`，清除行内样式就能恢复默认 —— 同一个写法，隐藏方式不同，
结果完全相反。

这类 bug 的特点：**接口数据、DOM、CSS 全都对**，只有"人打开浏览器看一眼"才能
发现。本项目没有可用的无头浏览器（§11.25 遗留里确认过 chromium 不可用），所以
退而求其次：把判据写成静态检查，至少拦住"再犯一次"。

它只回答两个问题：
  1. 有没有"用 `style.display = ""` 去显示、却被 CSS 藏着的元素"；
  2. `getElementById` 绑的 id 是不是真的存在于页面里（拼错一个字母就会静默失效）。

> ⚠️ 它是**静态检查**，不是渲染测试 —— 能拦住上面两类写法错误，拦不住布局、
> 配色、遮挡那类只有肉眼才看得出的问题。所以"打开浏览器看一眼"这一步不能省。
"""
import os
import re
import unittest

PAGE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")

# CSS 里按 id 隐藏的规则，例如：`#report { display: none; }`
_CSS_HIDDEN_RE = re.compile(r"#([A-Za-z][\w-]*)\s*\{[^}]*?display\s*:\s*none", re.S)

# `var elReport = document.getElementById("report");`
_EL_BINDING_RE = re.compile(r'var\s+(el[A-Za-z]+)\s*=\s*document\.getElementById\("([^"]+)"\)')

# `elReport.style.display = "";` —— 这个写法只在"隐藏靠行内样式"时才是显示
_SHOW_WITH_EMPTY_RE = re.compile(r'\b(el[A-Za-z]+)\.style\.display\s*=\s*""')

_STYLE_RE = re.compile(r"<style>(.*?)</style>", re.S)
_SCRIPT_RE = re.compile(r"<script>(.*?)</script>", re.S)


def load_parts(path=None):
    """返回 (整页, <style> 段, <script> 段)。

    只看这两段是有意的：正文里可能有代码示例，把整页丢进正则会误报。
    """
    with open(path or PAGE, encoding="utf-8") as fh:
        page = fh.read()
    return page, "\n".join(_STYLE_RE.findall(page)), "\n".join(_SCRIPT_RE.findall(page))


class TestPageIsReadable(unittest.TestCase):
    """先证明"读到了东西" —— 否则下面几条会因为文件读空而**全部空过**（假绿）。"""

    def test_sections_are_found(self):
        page, style, script = load_parts()
        self.assertIn('id="report"', page)
        self.assertGreater(len(style), 500, "没读到 <style> 段")
        self.assertGreater(len(script), 500, "没读到 <script> 段")

    def test_css_hidden_detector_works(self):
        """自检判据本身：`#report` / `#jump` 确实被 CSS 藏着，得认出来。"""
        _, style, _ = load_parts()
        hidden = set(_CSS_HIDDEN_RE.findall(style))
        self.assertIn("report", hidden, "判据认不出已被 CSS 藏起来的 #report，检查会空过")
        self.assertIn("jump", hidden)


class TestShowHide(unittest.TestCase):
    def test_no_element_is_shown_by_clearing_inline_style(self):
        """★ 正题：被 CSS 藏起来的元素，不能用 `style.display = ""` 去显示。"""
        _, style, script = load_parts()
        hidden = set(_CSS_HIDDEN_RE.findall(style))
        binding = dict(_EL_BINDING_RE.findall(script))       # elXxx -> id

        offenders = []
        for var in _SHOW_WITH_EMPTY_RE.findall(script):
            element_id = binding.get(var)
            if element_id in hidden:
                offenders.append(f"{var} (#{element_id})")

        self.assertEqual(
            offenders, [],
            "这些元素被 **CSS** 藏着，却用 `style.display = \"\"` 去显示 —— "
            "清掉行内样式之后 CSS 规则重新生效，它们永远不会出现："
            f"{offenders}。请改成具体的 display 值"
            "（div 用 block，button 用 inline-block）。见台账 §11.33。")

    def test_every_bound_element_exists_in_the_page(self):
        """`getElementById` 绑的 id 必须真在页面里 —— 拼错一个字母，那个变量就是
        null，后面所有操作要么静默失效、要么直接抛错。"""
        page, _, script = load_parts()
        binding = dict(_EL_BINDING_RE.findall(script))
        self.assertGreater(len(binding), 5, f"只认出 {len(binding)} 个绑定，判据可能失效了")

        missing = [f"{var} (#{element_id})" for var, element_id in binding.items()
                   if f'id="{element_id}"' not in page]
        self.assertEqual(missing, [], f"JS 绑定了页面里不存在的元素：{missing}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
