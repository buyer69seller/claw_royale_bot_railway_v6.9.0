# tests/test_ai.py
"""Unit test untuk AI"""

import unittest
from src.ai.perception import PerceptionEngine
from src.ai.risk import RiskAssessor

class TestAI(unittest.TestCase):
    def test_perception(self):
        engine = PerceptionEngine()
        self.assertIsNotNone(engine)
    
    def test_risk(self):
        assessor = RiskAssessor()
        self.assertIsNotNone(assessor)