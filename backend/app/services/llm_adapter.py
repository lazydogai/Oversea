from __future__ import annotations

from typing import Any


class MockLLMAdapter:
    def analyze_voc(self, products: list[dict[str, Any]]) -> dict[str, Any]:
        _ = products
        return {
            "pain_points": [
                "底座不稳，轻微碰撞就会移位",
                "亮度段数不足，阅读与睡眠模式切换不顺",
                "按键太小，晚上使用不直观",
            ],
            "selling_points": [
                "多段亮度调节",
                "可夹式与桌面式双场景",
                "USB 供电方便",
            ],
            "visual_style": [
                "极简黑白",
                "细长灯臂",
                "高对比产品图",
            ],
        }
