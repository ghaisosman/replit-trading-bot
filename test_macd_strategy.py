
# File: test_macd_strategy.py

import unittest
from src.execution_engine.strategies.macd_divergence_strategy import MACDDivergenceStrategy
import pandas as pd

class TestMACDStrategy(unittest.TestCase):
    def setUp(self):
        # Setup for MACD Strategy with sample configuration
        self.config = {
            'macd_fast': 12,
            'macd_slow': 26,
            'macd_signal': 9,
            'min_histogram_threshold': 0.0001,
            'macd_entry_threshold': 0.0015,
            'macd_exit_threshold': 0.002,
            'confirmation_candles': 1,
            'margin': 50.0,
            'leverage': 5
        }
        self.strategy = MACDDivergenceStrategy(self.config)
        self.df = self._create_sample_dataframe()

    def _create_sample_dataframe(self):
        # Create a Pandas DataFrame with simulated closing prices
        data = {
            'close': [101, 102, 103, 102, 101, 105, 107, 110, 108, 107, 112],
        }
        df = pd.DataFrame(data)
        return self.strategy.calculate_indicators(df)

    def test_evaluate_entry_signal(self):
        # Test entry condition evaluation
        signal = self.strategy.evaluate_entry_signal(self.df)
        self.assertIsNotNone(signal, "No entry signal detected when there should be one")
        self.assertEqual(signal.signal_type, 'BUY', "Expected a BUY signal")

    def test_evaluate_exit_signal(self):
        # Simulate a position and test exit signal
        position = {'side': 'BUY'}
        self.df.loc[len(self.df)] = [113, 107, 106, 105, 1.0]
        exit_signal = self.strategy.evaluate_exit_signal(self.df, position)
        self.assertEqual(exit_signal, "Take Profit (MACD Peak or Zero Cross)")

if __name__ == '__main__':
    unittest.main()
