#!/usr/bin/env python3
"""终端风格截图渲染器：把 SQL 命令与查询结果渲染成仿真终端窗口 PNG。"""
from PIL import Image, ImageDraw, ImageFont

FONT_TTC = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"

def load_mono_cjk(size=16):
    """在 NotoSansCJK-Regular.ttc 中定位 'Noto Sans Mono CJK SC' 字体索引。"""
    for idx in range(12):
        try:
            f = ImageFont.truetype(FONT_TTC, size, index=idx)
            name = " ".join(str(x) for x in f.getname())
            if "Mono CJK SC" in name:
                return f
        except Exception:
            break
    return ImageFont.truetype(FONT_TTC, size)

# 配色（深色终端主题）
BG          = (30, 32, 40)      # 终端背景
TITLEBAR    = (44, 47, 58)      # 标题栏
TITLE_TEXT  = (200, 205, 215)
C_PROMPT    = (94, 234, 212)    # 提示符 $
C_CMD       = (235, 240, 250)   # 命令行
C_SQL       = (214, 222, 235)   # SQL 正文
C_COMMENT   = (128, 134, 148)   # SQL 注释
C_HEADER    = (97, 175, 254)    # 结果表头（蓝）
C_ROW       = (190, 198, 210)   # 数据行
C_ACCENT    = (255, 184, 108)   # 强调（橙）
C_GOOD      = (126, 217, 87)    # 绿

STYLE_COLOR = {
    "prompt": C_PROMPT, "cmd": C_CMD, "sql": C_SQL, "comment": C_COMMENT,
    "header": C_HEADER, "row": C_ROW, "accent": C_ACCENT, "good": C_GOOD,
}

def render_terminal(out_path, title, lines, font_size=16, pad=28, line_h=None):
    font = load_mono_cjk(font_size)
    line_h = line_h or int(font_size * 1.55)
    # 计算尺寸（标题也参与宽度计算，避免截断）
    max_w = font.getbbox(title)[2]
    for style, text in lines:
        bbox = font.getbbox(text)
        max_w = max(max_w, bbox[2] - bbox[0])
    win_w = max_w + pad * 2 + 24
    title_h = 44
    win_h = title_h + line_h * len(lines) + pad * 2

    img = Image.new("RGB", (win_w, win_h), BG)
    d = ImageDraw.Draw(img)

    # 标题栏
    d.rectangle([0, 0, win_w, title_h], fill=TITLEBAR)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = pad + i * 24
        cy = title_h // 2
        d.ellipse([cx - 7, cy - 7, cx + 7, cy + 7], fill=c)
    d.text((pad + 3 * 24 + 16, title_h // 2), title, font=font, fill=TITLE_TEXT, anchor="lm")

    # 内容
    y = title_h + pad
    for style, text in lines:
        if style == "prompt":  # 提示符 + 命令同行
            d.text((pad, y), "$", font=font, fill=C_PROMPT)
            d.text((pad + font_size * 1.1, y), text, font=font, fill=C_CMD)
        else:
            d.text((pad, y), text, font=font, fill=STYLE_COLOR.get(style, C_ROW))
        y += line_h

    # 细边框
    d.rectangle([0, 0, win_w - 1, win_h - 1], outline=(70, 74, 88), width=1)
    img.save(out_path)
    print("saved:", out_path, f"{img.width}x{img.height}")

if __name__ == "__main__":
    # 冒烟测试
    render_terminal("/tmp/_test.png", "user@vm: ~/skills-proof/03-sql", [
        ("prompt", "sqlite3 credit.db"),
        ("comment", "/* 业务背景：测试 */"),
        ("sql", "SELECT 1 AS ok;"),
        ("blank", ""),
        ("header", "ok"),
        ("row", "1"),
    ])
