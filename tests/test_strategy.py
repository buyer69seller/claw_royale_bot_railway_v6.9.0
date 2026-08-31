# tests/test_strategy.py
"""Unit test untuk strategy"""

import unittest
from src.strategy.evaluators import alive, hp, num

class TestStrategy(unittest.TestCase):
    def test_alive(self):
        self.assertTrue(alive({"isAlive": True, "hp": 10}))
        self.assertFalse(alive({"isAlive": False, "hp": 10}))
        self.assertFalse(alive({"isAlive": True, "hp": 0}))
    
    def test_num(self):
        self.assertEqual(num("10"), 10.0)
        self.assertEqual(num("abc"), 0)
        self.assertEqual(num(5.5), 5.5)