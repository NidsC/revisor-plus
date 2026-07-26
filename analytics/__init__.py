"""Analytics services.

This file exists so `analytics` is a regular package. It worked before only as an
implicit namespace package, which is fragile: any other `analytics` on the path
would merge with it, and packaging tools silently skip namespace dirs.
"""
