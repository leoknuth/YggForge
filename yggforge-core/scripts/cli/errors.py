# -*- coding: utf-8 -*-
"""Ygg CLI 错误类型。"""


class YggError(RuntimeError):
    """路由 / 参数 / 策略相关错误，由入口 main 捕获并打印。"""
