"""Tests for the dot validation gate and iterative auto-repair loop.

Will cover: invoking ``dot`` in dry-run mode against an AI-modified
DOT file before any image is rendered, parsing dot's stderr to
identify mechanically fixable error classes (unbalanced braces or
quotes, malformed pos= / bb= values, unknown attributes that can be
stripped, stray tokens at a given line), iterating fix-and-revalidate
with strict forward-progress termination, and falling back to the
original pre-optimization DOT when the retry budget is exhausted.

Stub file for now — DOT validation ships in a later phase.
"""
