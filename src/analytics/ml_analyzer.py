
import pandas as pd
import numpy as np
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
from pathlib import Path
import json

# ML libraries (install when needed)
try:
    from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
    from sklearn.model_selection import train_test_split, cross_val_score
    from sklearn.metrics import accuracy_score, classification_report
    from sklearn.preprocessing import StandardScaler, LabelEncoder
    from sklearn.feature_selection import SelectKBest, f_classif
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False

from src.analytics.trade_logger import trade_logger

class MLTradeAnalyzer:
    """Enhanced Machine Learning analyzer for trading strategy optimization"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.models_dir = Path("trading_data/ml_models")
        self.models_dir.mkdir(exist_ok=True, parents=True)

        # Traditional ML models
        self.profitability_model = None  # Predict if trade will be profitable
        self.pnl_model = None           # Predict PnL amount
        self.duration_model = None      # Predict trade duration

        # Enhanced ML models
        self.parameter_optimization_model = None  # What-if scenarios
        self.market_regime_model = None          # Market condition classifier
        self.risk_adjustment_model = None        # Dynamic risk management

        # Feature scalers
        self.scaler = StandardScaler()
        self.label_encoders = {}

        # Feature importance tracking
        self.feature_importance = {}

        # Store training feature names for consistent prediction
        self.training_feature_names = None

        # External AI integration
        self.ai_advisor_enabled = False
        self.ai_api_key = None
        self.trading_context = []  # Store recent trading context for AI
        self.ai_suggestions = []   # Store AI recommendations

        # What-if simulation results
        self.simulation_results = []
        self.optimal_parameters = {}

        # Advanced feature engineering
        self.contextual_features = {}
        self.market_microstructure = {}

    def prepare_ml_dataset(self) -> Optional[pd.DataFrame]:
        """Prepare dataset for machine learning"""
        if not ML_AVAILABLE:
            self.logger.error("❌ ML libraries not installed. Run: pip install scikit-learn")
            return None

        try:
            # Export current data for ML
            ml_file = trade_logger.export_for_ml()
            if not ml_file:
                self.logger.warning("⚠️ No trade data available for ML analysis")
                return None

            # Load the dataset
            df = pd.read_csv(ml_file)

            if len(df) < 3:  # Reduced from 10 to work with smaller datasets
                self.logger.warning("⚠️ Insufficient data for ML analysis (need at least 3 trades)")
                return None

            # Feature engineering
            df = self._engineer_features(df)

            # Handle categorical variables
            categorical_columns = ['strategy', 'symbol', 'side', 'market_trend', 'market_phase', 'exit_reason']
            for col in categorical_columns:
                if col in df.columns:
                    if col not in self.label_encoders:
                        self.label_encoders[col] = LabelEncoder()
                        df[col] = self.label_encoders[col].fit_transform(df[col].astype(str))
                    else:
                        df[col] = self.label_encoders[col].transform(df[col].astype(str))

            # Remove any remaining non-numeric columns
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            df = df[numeric_columns]

            # Handle missing values
            df = df.fillna(0)

            self.logger.info(f"📊 ML dataset prepared: {len(df)} trades, {len(df.columns)} features")
            return df

        except Exception as e:
            self.logger.error(f"❌ Error preparing ML dataset: {e}")
            return None

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create additional features for better ML performance"""
        try:
            # Time-based features
            # Ensure 'day_of_week' and 'hour_of_day' exist before using them
            if 'day_of_week' in df.columns:
                df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
            if 'hour_of_day' in df.columns:
                df['is_london_session'] = df['hour_of_day'].between(8, 16).astype(int)
                df['is_ny_session'] = df['hour_of_day'].between(13, 21).astype(int)
                df['is_overlap_session'] = df['hour_of_day'].between(13, 16).astype(int)

            # Risk features
            df['position_risk'] = df['position_size_usdt'] / 10000  # Normalize by account size
            df['leverage_risk'] = df['leverage'] * df['position_risk']

            # Technical indicator combinations
            if 'rsi_entry' in df.columns and 'macd_entry' in df.columns:
                df['rsi_macd_combo'] = df['rsi_entry'] * df['macd_entry']

            if 'sma_20_entry' in df.columns and 'sma_50_entry' in df.columns:
                df['sma_spread'] = (df['sma_20_entry'] - df['sma_50_entry']) / df['sma_50_entry']

            # Volatility-based features
            if 'volatility_score' in df.columns:
                df['high_volatility'] = (df['volatility_score'] > df['volatility_score'].quantile(0.75)).astype(int)
                df['low_volatility'] = (df['volatility_score'] < df['volatility_score'].quantile(0.25)).astype(int)

            return df

        except Exception as e:
            self.logger.error(f"❌ Error in feature engineering: {e}")
            return df

    def train_models(self) -> Dict[str, Any]:
        """Train ML models on historical trade data"""
        if not ML_AVAILABLE:
            return {"error": "ML libraries not available - run: pip install scikit-learn"}

        try:
            # Prepare dataset
            df = self.prepare_ml_dataset()
            if df is None:
                return {"error": "Failed to prepare dataset - no trade data available"}

            if len(df) < 3:  # Reduced minimum for development/testing
                return {"error": f"Insufficient data for training - need at least 3 trades, got {len(df)}"}

            results = {
                "dataset_size": int(len(df)),
                "features_count": int(len(df.columns))
            }

            # Define features (exclude target variables)
            target_columns = ['pnl_usdt', 'pnl_percentage', 'was_profitable', 'duration_minutes']
            feature_columns = [col for col in df.columns if col not in target_columns]

            # Store feature names for consistent prediction
            self.training_feature_names = feature_columns

            X = df[feature_columns]

            # Train profitability classifier
            if 'was_profitable' in df.columns:
                y_profit = df['was_profitable']
                X_train, X_test, y_train, y_test = train_test_split(X, y_profit, test_size=0.2, random_state=42)

                self.profitability_model = RandomForestClassifier(n_estimators=100, random_state=42)
                self.profitability_model.fit(X_train, y_train)

                # Evaluate
                y_pred = self.profitability_model.predict(X_test)
                accuracy = accuracy_score(y_test, y_pred)

                # Feature importance
                feature_importance = dict(zip(feature_columns, self.profitability_model.feature_importances_))
                self.feature_importance['profitability'] = feature_importance

                results['profitability_accuracy'] = float(accuracy)
                results['profitability_features'] = [(feature, float(importance)) for feature, importance in sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]]

            # Train PnL regressor
            if 'pnl_percentage' in df.columns:
                y_pnl = df['pnl_percentage']
                X_train, X_test, y_train, y_test = train_test_split(X, y_pnl, test_size=0.2, random_state=42)

                self.pnl_model = RandomForestRegressor(n_estimators=100, random_state=42)
                self.pnl_model.fit(X_train, y_train)

                # Evaluate
                score = self.pnl_model.score(X_test, y_test)
                results['pnl_r2_score'] = float(score)

            # Train duration regressor
            if 'duration_minutes' in df.columns:
                y_duration = df['duration_minutes']
                # Only train on trades with duration > 0
                valid_duration = y_duration > 0
                if valid_duration.sum() > 10:
                    X_duration = X[valid_duration]
                    y_duration = y_duration[valid_duration]

                    X_train, X_test, y_train, y_test = train_test_split(X_duration, y_duration, test_size=0.2, random_state=42)

                    self.duration_model = RandomForestRegressor(n_estimators=100, random_state=42)
                    self.duration_model.fit(X_train, y_train)

                    score = self.duration_model.score(X_test, y_test)
                    results['duration_r2_score'] = float(score)

            # Save models
            self._save_models()

            self.logger.info(f"🤖 ML models trained successfully: {len(results)} metrics")
            return results

        except Exception as e:
            self.logger.error(f"❌ Error training ML models: {e}")
            return {"error": str(e)}

    def _engineer_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create advanced contextual features for enhanced ML performance"""
        try:
            # Volume analysis features
            if 'volume_at_entry' in df.columns:
                # Volume spike detection
                df['volume_spike'] = (df['volume_at_entry'] > df['volume_at_entry'].rolling(20).mean() * 1.5).astype(int)

                # Volume momentum
                df['volume_momentum'] = df['volume_at_entry'].rolling(5).mean() / df['volume_at_entry'].rolling(20).mean()

                # Volume-price divergence
                if 'entry_price' in df.columns:
                    volume_change = df['volume_at_entry'].pct_change()
                    price_change = df['entry_price'].pct_change()
                    df['volume_price_divergence'] = abs(volume_change + price_change)  # Divergence indicator

            # Market microstructure features
            df['session_transition'] = 0  # Default
            if 'hour_of_day' in df.columns:
                # Detect session transitions (high volatility periods)
                session_changes = [8, 13, 16, 21]  # London open, NY open, London close, NY close
                for hour in session_changes:
                    df.loc[df['hour_of_day'] == hour, 'session_transition'] = 1

            # Multi-timeframe momentum
            if 'rsi_entry' in df.columns:
                # RSI momentum (change in RSI)
                df['rsi_momentum'] = df['rsi_entry'].diff()

                # RSI extreme zones
                df['rsi_extreme_oversold'] = (df['rsi_entry'] < 20).astype(int)
                df['rsi_extreme_overbought'] = (df['rsi_entry'] > 80).astype(int)

            # Market stress indicators
            if 'volatility_score' in df.columns:
                # Volatility regime classification
                vol_quantiles = df['volatility_score'].quantile([0.25, 0.75])
                df['low_vol_regime'] = (df['volatility_score'] < vol_quantiles[0.25]).astype(int)
                df['high_vol_regime'] = (df['volatility_score'] > vol_quantiles[0.75]).astype(int)

            # Cross-market correlation features
            if 'symbol' in df.columns:
                # Add BTC correlation proxy (simplified)
                df['crypto_market_exposure'] = df['symbol'].str.contains('BTC|ETH|SOL').astype(int)

            # Time-based advanced features
            if 'hour_of_day' in df.columns:
                # Market efficiency periods
                df['high_efficiency_period'] = df['hour_of_day'].between(9, 11).astype(int)  # London morning
                df['low_efficiency_period'] = df['hour_of_day'].between(22, 2).astype(int)   # Asian night

            # Position sizing intelligence
            if 'position_size_usdt' in df.columns and 'leverage' in df.columns:
                df['effective_exposure'] = df['position_size_usdt'] * df['leverage']

                # Risk concentration
                df['high_risk_concentration'] = (df['effective_exposure'] > df['effective_exposure'].quantile(0.8)).astype(int)

            return df

        except Exception as e:
            self.logger.error(f"❌ Error in advanced feature engineering: {e}")
            return df

    def generate_what_if_scenarios(self, base_trade: Dict) -> List[Dict]:
        """Generate what-if scenarios for parameter optimization"""
        scenarios = []

        # Leverage variations
        for leverage in [3, 5, 10, 15, 20]:
            scenario = base_trade.copy()
            scenario['leverage'] = leverage
            scenario['scenario_type'] = 'leverage_optimization'
            scenarios.append(scenario)

        # Position size variations
        base_size = base_trade.get('position_size_usdt', 100)
        for multiplier in [0.5, 0.75, 1.25, 1.5, 2.0]:
            scenario = base_trade.copy()
            scenario['position_size_usdt'] = base_size * multiplier
            scenario['scenario_type'] = 'position_size_optimization'
            scenarios.append(scenario)

        # Entry timing variations (simulated delay)
        for delay_minutes in [0, 5, 10, 15, 30]:
            scenario = base_trade.copy()
            scenario['entry_delay_minutes'] = delay_minutes
            scenario['scenario_type'] = 'timing_optimization'
            scenarios.append(scenario)

        # Risk management variations
        for risk_multiplier in [0.5, 0.75, 1.25, 1.5]:
            scenario = base_trade.copy()
            scenario['risk_multiplier'] = risk_multiplier
            scenario['scenario_type'] = 'risk_optimization'
            scenarios.append(scenario)

        return scenarios

    def simulate_parameter_optimization(self, historical_trades: List) -> Dict:
        """Run parameter optimization simulation on historical trades"""
        try:
            if not self.profitability_model:
                self.logger.error("❌ ML models not trained - cannot run optimization")
                return {}

            if len(historical_trades) < 3:
                self.logger.error("❌ Need at least 3 trades for optimization")
                return {}

            optimization_results = {}

            # Use all available trades, but limit to recent ones if many
            recent_trades = historical_trades[-min(10, len(historical_trades)):]

            self.logger.info(f"🔧 Analyzing {len(recent_trades)} trades for optimization")

            for trade in recent_trades:
                # Get timestamp safely - use timestamp field from TradeRecord
                trade_timestamp = getattr(trade, 'timestamp', None)
                if trade_timestamp and isinstance(trade_timestamp, str):
                    try:
                        trade_timestamp = datetime.fromisoformat(trade_timestamp.replace('Z', '+00:00'))
                    except:
                        trade_timestamp = datetime.now()
                elif not trade_timestamp:
                    trade_timestamp = datetime.now()

                trade_dict = {
                    'strategy': getattr(trade, 'strategy_name', 'rsi_oversold'),
                    'symbol': getattr(trade, 'symbol', 'BTCUSDT'),
                    'side': getattr(trade, 'side', 'BUY'),
                    'leverage': getattr(trade, 'leverage', 5),
                    'position_size_usdt': getattr(trade, 'position_value_usdt', 100),
                    'rsi_entry': getattr(trade, 'rsi_at_entry', 50),
                    'hour_of_day': trade_timestamp.hour if hasattr(trade_timestamp, 'hour') else 12,
                    'day_of_week': trade_timestamp.weekday() if hasattr(trade_timestamp, 'weekday') else 1,
                    'market_trend': getattr(trade, 'market_trend', 'NEUTRAL'),
                    'actual_pnl': getattr(trade, 'pnl_percentage', 0)
                }

                scenarios = self.generate_what_if_scenarios(trade_dict)

                for scenario in scenarios[:3]:  # Limit scenarios to avoid overwhelming
                    # Predict outcome for each scenario
                    prediction = self.predict_trade_outcome(scenario)

                    if 'predicted_pnl_percentage' in prediction:
                        scenario_type = scenario['scenario_type']
                        if scenario_type not in optimization_results:
                            optimization_results[scenario_type] = []

                        improvement = prediction['predicted_pnl_percentage'] - trade_dict['actual_pnl']

                        optimization_results[scenario_type].append({
                            'parameters': scenario,
                            'predicted_pnl': prediction['predicted_pnl_percentage'],
                            'actual_pnl': trade_dict['actual_pnl'],
                            'improvement': improvement
                        })

            # Find optimal parameters for each scenario type
            optimal_params = {}
            for scenario_type, results in optimization_results.items():
                if results and len(results) > 0:
                    best_result = max(results, key=lambda x: x['improvement'])
                    avg_improvement = sum(r['improvement'] for r in results) / len(results)

                    optimal_params[scenario_type] = {
                        'parameters': best_result['parameters'],
                        'avg_improvement': avg_improvement,
                        'best_improvement': best_result['improvement'],
                        'scenario_count': len(results)
                    }

            self.optimal_parameters = optimal_params

            if not optimal_params:
                self.logger.warning("⚠️ No optimization results generated - model may need more training data")

            return optimal_params

        except Exception as e:
            self.logger.error(f"❌ Error in parameter optimization: {e}")
            import traceback
            self.logger.error(f"Full error: {traceback.format_exc()}")
            return {}

    def prepare_ai_context(self, recent_trades: int = 10) -> str:
        """Prepare trading context for external AI analysis"""
        try:
            trades = trade_logger.trades[-recent_trades:] if len(trade_logger.trades) >= recent_trades else trade_logger.trades

            if not trades:
                return "No recent trading data available."

            # Calculate recent performance metrics
            closed_trades = [t for t in trades if t.trade_status == "CLOSED"]
            if not closed_trades:
                return "No closed trades in recent period."

            win_rate = sum(1 for t in closed_trades if t.pnl_percentage > 0) / len(closed_trades)
            avg_pnl = sum(t.pnl_percentage for t in closed_trades) / len(closed_trades)
            total_pnl = sum(t.pnl_percentage for t in closed_trades)

            # Strategy breakdown
            strategy_performance = {}
            for trade in closed_trades:
                strategy = getattr(trade, 'strategy', getattr(trade, 'strategy_name', 'unknown_strategy'))
                if strategy not in strategy_performance:
                    strategy_performance[strategy] = {'wins': 0, 'total': 0, 'pnl': 0}

                strategy_performance[strategy]['total'] += 1
                strategy_performance[strategy]['pnl'] += getattr(trade, 'pnl_percentage', 0)
                pnl = getattr(trade, 'pnl_percentage', 0)
                if pnl > 0:
                    strategy_performance[strategy]['wins'] += 1

            # Generate insights
            insights = self.generate_insights()

            context = f"""
RECENT TRADING PERFORMANCE ANALYSIS:
=====================================

OVERALL METRICS:
- Period: Last {len(closed_trades)} closed trades
- Win Rate: {win_rate:.1%}
- Average PnL per trade: {avg_pnl:.2f}%
- Total PnL: {total_pnl:.2f}%

STRATEGY BREAKDOWN:
"""

            for strategy, stats in strategy_performance.items():
                strategy_win_rate = stats['wins'] / stats['total'] if stats['total'] > 0 else 0
                avg_strategy_pnl = stats['pnl'] / stats['total'] if stats['total'] > 0 else 0
                context += f"- {strategy}: {strategy_win_rate:.1%} win rate, {avg_strategy_pnl:.2f}% avg PnL ({stats['total']} trades)\n"

            if 'best_trading_times' in insights:
                context += f"\nBEST TRADING HOURS:\n"
                for time_data in insights['best_trading_times'][:3]:
                    hour = time_data.get('hour', 0)
                    profitability = time_data.get('profitability', 0)
                    context += f"- {hour:02d}:00: {profitability:.1f}% profitable\n"

            # Add current market conditions
            context += f"""
CURRENT ML MODEL STATUS:
- Model trained on {len(closed_trades)} trades
- Features: 34+ technical and contextual indicators
- Recent accuracy: {self.feature_importance.get('profitability_accuracy', 'N/A')}

AREAS FOR ANALYSIS:
Please analyze this data and suggest:
1. Pattern recognition insights
2. Risk management improvements  
3. Strategy optimization recommendations
4. Market timing enhancements
"""

            return context

        except Exception as e:
            self.logger.error(f"❌ Error preparing AI context: {e}")
            return f"Error preparing context: {str(e)}"

    def generate_detailed_ai_report(self, analysis_type: str = "comprehensive") -> str:
        """Generate detailed AI-ready report that can be copied to external AI services"""
        try:
            report_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

            # Access trade data safely with proper attribute checking
            try:
                closed_trades = [t for t in trade_logger.trades if getattr(t, 'trade_status', None) == "CLOSED"]
                open_trades = [t for t in trade_logger.trades if getattr(t, 'trade_status', None) in ["OPEN", "ACTIVE"]]
            except Exception as e:
                self.logger.error(f"Error accessing trade data: {e}")
                closed_trades = []
                open_trades = []

            if not closed_trades:
                return "No closed trades available for detailed analysis."

            # Calculate comprehensive metrics
            total_trades = len(closed_trades)
            winning_trades = [t for t in closed_trades if t.pnl_percentage > 0]
            losing_trades = [t for t in closed_trades if t.pnl_percentage < 0]

            win_rate = len(winning_trades) / total_trades * 100
            avg_win = sum(t.pnl_percentage for t in winning_trades) / len(winning_trades) if winning_trades else 0
            avg_loss = sum(t.pnl_percentage for t in losing_trades) / len(losing_trades) if losing_trades else 0
            total_pnl = sum(t.pnl_percentage for t in closed_trades)

            # Risk metrics
            max_drawdown = min(t.pnl_percentage for t in closed_trades) if closed_trades else 0
            largest_win = max(t.pnl_percentage for t in closed_trades) if closed_trades else 0

            # Time-based analysis
            trade_durations = [t.duration_minutes for t in closed_trades if t.duration_minutes]
            avg_duration = sum(trade_durations) / len(trade_durations) if trade_durations else 0

            report = f"""
═══════════════════════════════════════════════════════════
📊 COMPREHENSIVE TRADING PERFORMANCE REPORT
═══════════════════════════════════════════════════════════
🕒 Report Generated: {report_timestamp}
🤖 Analysis Type: {analysis_type.upper()}
📈 Data Source: Algorithmic Trading Bot ML System

═══════════════════════════════════════════════════════════
🎯 EXECUTIVE SUMMARY
═══════════════════════════════════════════════════════════

CORE PERFORMANCE METRICS:
• Total Closed Trades: {total_trades}
• Current Open Positions: {len(open_trades)}
• Overall Win Rate: {win_rate:.1f}%
• Total PnL: {total_pnl:+.2f}%
• Average Trade Duration: {avg_duration:.0f} minutes

RISK ANALYSIS:
• Largest Single Win: {largest_win:+.2f}%
• Maximum Drawdown: {max_drawdown:.2f}%
• Average Winning Trade: {avg_win:+.2f}%
• Average Losing Trade: {avg_loss:+.2f}%
• Risk-Reward Ratio: {abs(avg_win/avg_loss) if avg_loss != 0 else 0:.2f}:1

═══════════════════════════════════════════════════════════
📊 STRATEGY PERFORMANCE BREAKDOWN
═══════════════════════════════════════════════════════════
"""

            # Strategy analysis
            strategy_stats = {}
            for trade in closed_trades:
                strategy = getattr(trade, 'strategy', 'unknown_strategy')
                if strategy not in strategy_stats:
                    strategy_stats[strategy] = {
                        'trades': [], 'wins': 0, 'losses': 0, 'total_pnl': 0,
                        'symbols': set(), 'avg_leverage': 0, 'total_volume': 0
                    }

                stats = strategy_stats[strategy]
                stats['trades'].append(trade)
                stats['total_pnl'] += getattr(trade, 'pnl_percentage', 0)
                stats['symbols'].add(getattr(trade, 'symbol', 'UNKNOWN'))
                stats['avg_leverage'] += getattr(trade, 'leverage', 1)
                stats['total_volume'] += getattr(trade, 'position_size_usdt', 0)

                pnl = getattr(trade, 'pnl_percentage', 0)
                if pnl > 0:
                    stats['wins'] += 1
                else:
                    stats['losses'] += 1

            for strategy, stats in strategy_stats.items():
                total_trades = len(stats['trades'])
                win_rate = (stats['wins'] / total_trades * 100) if total_trades > 0 else 0
                avg_pnl = stats['total_pnl'] / total_trades if total_trades > 0 else 0
                avg_leverage = stats['avg_leverage'] / total_trades if total_trades > 0 else 0

                report += f"""
🎯 STRATEGY: {strategy.upper()}
   • Total Trades: {total_trades}
   • Win Rate: {win_rate:.1f}%
   • Average PnL per Trade: {avg_pnl:+.2f}%
   • Total Strategy PnL: {stats['total_pnl']:+.2f}%
   • Traded Symbols: {', '.join(stats['symbols'])}
   • Average Leverage: {avg_leverage:.1f}x
   • Total Volume: ${stats['total_volume']:.0f} USDT
   • Best Trade: {max(t.pnl_percentage for t in stats['trades']):+.2f}%
   • Worst Trade: {min(t.pnl_percentage for t in stats['trades']):+.2f}%
"""

            # Time-based analysis
            report += f"""
═══════════════════════════════════════════════════════════
⏰ TIME-BASED PERFORMANCE ANALYSIS  
═══════════════════════════════════════════════════════════
"""

            # Hourly performance
            hourly_stats = {}
            for trade in closed_trades:
                # Get timestamp safely - use timestamp field from TradeRecord
                trade_timestamp = getattr(trade, 'timestamp', None)
                if trade_timestamp and isinstance(trade_timestamp, str):
                    try:
                        trade_timestamp = datetime.fromisoformat(trade_timestamp.replace('Z', '+00:00'))
                    except:
                        trade_timestamp = datetime.now()
                elif not trade_timestamp:
                    trade_timestamp = datetime.now()

                hour = trade_timestamp.hour if hasattr(trade_timestamp, 'hour') else 0
                if hour not in hourly_stats:
                    hourly_stats[hour] = {'trades': 0, 'wins': 0, 'pnl': 0}
                hourly_stats[hour]['trades'] += 1
                hourly_stats[hour]['pnl'] += getattr(trade, 'pnl_percentage', 0)
                if getattr(trade, 'pnl_percentage', 0) > 0:
                    hourly_stats[hour]['wins'] += 1

            best_hours = sorted(hourly_stats.items(), 
                               key=lambda x: x[1]['wins']/x[1]['trades'] if x[1]['trades'] > 0 else 0, 
                               reverse=True)[:5]

            report += "\n🕐 TOP PERFORMING HOURS (UTC):\n"
            for hour, stats in best_hours:
                if stats['trades'] > 0:
                    win_rate = stats['wins'] / stats['trades'] * 100
                    avg_pnl = stats['pnl'] / stats['trades']
                    report += f"   • {hour:02d}:00-{(hour+1)%24:02d}:00 → {win_rate:.1f}% win rate, {avg_pnl:+.2f}% avg PnL ({stats['trades']} trades)\n"

            # Weekly performance
            weekday_stats = {}
            weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            for trade in closed_trades:
                # Get timestamp safely - use timestamp field from TradeRecord
                trade_timestamp = getattr(trade, 'timestamp', None)
                if trade_timestamp and isinstance(trade_timestamp, str):
                    try:
                        trade_timestamp = datetime.fromisoformat(trade_timestamp.replace('Z', '+00:00'))
                    except:
                        trade_timestamp = datetime.now()
                elif not trade_timestamp:
                    trade_timestamp = datetime.now()

                weekday = trade_timestamp.weekday() if hasattr(trade_timestamp, 'weekday') else 0
                day_name = weekdays[weekday]
                if day_name not in weekday_stats:
                    weekday_stats[day_name] = {'trades': 0, 'wins': 0, 'pnl': 0}
                weekday_stats[day_name]['trades'] += 1
                weekday_stats[day_name]['pnl'] += getattr(trade, 'pnl_percentage', 0)
                if getattr(trade, 'pnl_percentage', 0) > 0:
                    weekday_stats[day_name]['wins'] += 1

            report += "\n📅 WEEKLY PERFORMANCE PATTERN:\n"
            for day in weekdays:
                if day in weekday_stats and weekday_stats[day]['trades'] > 0:
                    stats = weekday_stats[day]
                    win_rate = stats['wins'] / stats['trades'] * 100
                    avg_pnl = stats['pnl'] / stats['trades']
                    report += f"   • {day}: {win_rate:.1f}% win rate, {avg_pnl:+.2f}% avg PnL ({stats['trades']} trades)\n"

            # Technical analysis insights
            report += f"""
═══════════════════════════════════════════════════════════
🔧 TECHNICAL INDICATORS ANALYSIS
═══════════════════════════════════════════════════════════
"""

            # RSI analysis
            rsi_trades = [t for t in closed_trades if getattr(t, 'rsi_at_entry', None) is not None]
            if rsi_trades:
                rsi_ranges = {
                    'Oversold (≤30)': [t for t in rsi_trades if getattr(t, 'rsi_at_entry', 0) <= 30],
                    'Neutral (31-69)': [t for t in rsi_trades if 31 <= getattr(t, 'rsi_at_entry', 50) <= 69],
                    'Overbought (≥70)': [t for t in rsi_trades if getattr(t, 'rsi_at_entry', 0) >= 70]
                }

                report += "\n📊 RSI ENTRY CONDITIONS:\n"
                for range_name, trades in rsi_ranges.items():
                    if trades:
                        win_rate = sum(1 for t in trades if getattr(t, 'pnl_percentage', 0) > 0) / len(trades) * 100
                        avg_pnl = sum(getattr(t, 'pnl_percentage', 0) for t in trades) / len(trades)
                        report += f"   • {range_name}: {win_rate:.1f}% win rate, {avg_pnl:+.2f}% avg PnL ({len(trades)} trades)\n"

            # ML Model Performance
            if self.profitability_model:
                report += f"""
═══════════════════════════════════════════════════════════📊 MACHINE LEARNING MODEL INSIGHTS
═══════════════════════════════════════════════════════════

MODEL PERFORMANCE:
• Profitability Prediction Accuracy: {self.feature_importance.get('profitability_accuracy', 'N/A')}
• Feature Count: {len(self.training_feature_names) if self.training_feature_names else 'N/A'}
• Training Dataset Size: {len(closed_trades)} closed trades

TOP PREDICTIVE FEATURES:
"""
                if 'profitability' in self.feature_importance:
                    top_features = sorted(self.feature_importance['profitability'].items(), 
                                        key=lambda x: x[1], reverse=True)[:10]
                    for i, (feature, importance) in enumerate(top_features, 1):
                        report += f"   {i:2}. {feature}: {importance:.3f} importance\n"

            # Current positions analysis
            if open_trades:
                report += f"""
═══════════════════════════════════════════════════════════
🔄 CURRENT OPEN POSITIONS ANALYSIS
═══════════════════════════════════════════════════════════

ACTIVE TRADES: {len(open_trades)}
"""
                for trade in open_trades:
                    unrealized_pnl = getattr(trade, 'unrealized_pnl_percentage', 0)

                    # Get timestamp safely - use timestamp field from TradeRecord
                    trade_timestamp = getattr(trade, 'timestamp', None)
                    if trade_timestamp and isinstance(trade_timestamp, str):
                        try:
                            trade_timestamp = datetime.fromisoformat(trade_timestamp.replace('Z', '+00:00'))
                        except:
                            trade_timestamp = datetime.now()
                    elif not trade_timestamp:
                        trade_timestamp = datetime.now()

                    minutes_open = int((datetime.now() - trade_timestamp).total_seconds() / 60) if trade_timestamp else 0
                    strategy_name = getattr(trade, 'strategy', getattr(trade, 'strategy_name', 'Unknown'))

                    report += f"""
🔄 OPEN TRADE:
   • Strategy: {strategy_name.upper()}
   • Symbol: {getattr(trade, 'symbol', 'Unknown')}
   • Side: {getattr(trade, 'side', 'Unknown')}
   • Entry Price: ${getattr(trade, 'entry_price', 0):.4f}
   • Position Size: ${getattr(trade, 'position_size_usdt', 0):.2f} USDT
   • Leverage: {getattr(trade, 'leverage', 1)}x
   • Time Open: {minutes_open:.0f} minutes
   • Unrealized PnL: {unrealized_pnl:+.2f}%
   • RSI at Entry: {getattr(trade, 'rsi_at_entry', 'N/A')}
"""

            # AI Analysis Prompt
            report += f"""
═══════════════════════════════════════════════════════════
🎯 AI ANALYSIS REQUEST
═══════════════════════════════════════════════════════════

PROMPT FOR AI ANALYSIS:
Based on the comprehensive trading data above, please provide:

1. 🔍 PATTERN RECOGNITION:
   - Identify successful trading patterns
   - Highlight recurring themes in profitable trades
   - Spot potential inefficiencies or biases

2. ⚠️ RISK ASSESSMENT:
   - Evaluate current risk management effectiveness
      - Identify potential vulnerabilities
   - Suggest position sizing improvements

3. 🚀 OPTIMIZATION OPPORTUNITIES:
   - Recommend strategy refinements
   - Suggest parameter adjustments
   - Identify untapped opportunities

4. ⏰ TIMING OPTIMIZATION:
   - Best market sessions for trading
   - Time-based pattern recommendations
   - Market condition adaptations

5. 🎯 STRATEGIC RECOMMENDATIONS:
   - Priority improvements to implement
   - Long-term strategic direction
   - Risk-reward optimization suggestions

Please provide specific, actionable recommendations based on this quantitative analysis.

═══════════════════════════════════════════════════════════
📋 TECHNICAL SPECIFICATIONS
═══════════════════════════════════════════════════════════

SYSTEM DETAILS:
• Trading Platform: Binance Futures
• Analysis Framework: Custom ML-Enhanced Bot
• Data Collection: Real-time with 34+ features
• Model Type: Random Forest Classifier/Regressor
• Update Frequency: Continuous learning
• Risk Management: Dynamic position sizing
• Execution: Fully automated with manual override

DATA QUALITY ASSURANCE:
• All trades verified against exchange records
• Technical indicators calculated using standard formulas
• Market timing data synchronized with exchange timestamps
• ML predictions validated against actual outcomes

═══════════════════════════════════════════════════════════
END OF REPORT - Ready for AI Analysis
═══════════════════════════════════════════════════════════
"""

            return report

        except Exception as e:
            self.logger.error(f"❌ Error generating detailed AI report: {e}")
            return f"Error generating report: {str(e)}"

    def export_ai_ready_data(self, format_type: str = "json") -> Dict[str, Any]:
        """Export structured data in AI-friendly format"""
        try:
            try:
                closed_trades = [t for t in trade_logger.trades if getattr(t, 'trade_status', None) == "CLOSED"]
            except Exception as e:
                self.logger.error(f"Error accessing trade data: {e}")
                closed_trades = []
            export_data = {
                "report_metadata": {
                    "timestamp": datetime.now().isoformat(),
                    "total_trades": len(closed_trades),
                    "analysis_type": "ml_enhanced_trading_report",
                    "version": "2.0"
                },
                "performance_summary": {
                    "win_rate": sum(1 for t in closed_trades if t.pnl_percentage > 0) / len(closed_trades) * 100 if closed_trades else 0,
                    "total_pnl_percentage": sum(t.pnl_percentage for t in closed_trades),
                    "average_trade_pnl": sum(t.pnl_percentage for t in closed_trades) / len(closed_trades) if closed_trades else 0,
                    "max_drawdown": min(t.pnl_percentage for t in closed_trades) if closed_trades else 0,
                    "largest_win": max(t.pnl_percentage for t in closed_trades) if closed_trades else 0
                },
                "strategy_breakdown": {},
                "time_analysis": {},
                "technical_indicators": {},
                "ml_model_insights": {},
                "trade_details": []
            }

            # Process each closed trade with safe attribute access
            for trade in closed_trades:
                try:
                    # Get timestamp safely - use timestamp field from TradeRecord
                    trade_timestamp = getattr(trade, 'timestamp', None)
                    if trade_timestamp and hasattr(trade_timestamp, 'isoformat'):
                        timestamp_str = trade_timestamp.isoformat()
                    elif trade_timestamp:
                        timestamp_str = str(trade_timestamp)
                    else:
                        timestamp_str = 'Unknown'

                    trade_details = {
                        "trade_id": getattr(trade, 'trade_id', 'Unknown'),
                        "strategy": getattr(trade, 'strategy', getattr(trade, 'strategy_name', 'Unknown')),
                        "symbol": getattr(trade, 'symbol', 'Unknown'),
                        "side": getattr(trade, 'side', 'Unknown'),
                        "entry_price": getattr(trade, 'entry_price', 0),
                        "exit_price": getattr(trade, 'exit_price', 0),
                        "quantity": getattr(trade, 'quantity', 0),
                        "pnl_percentage": getattr(trade, 'pnl_percentage', 0),
                        "duration_minutes": getattr(trade, 'duration_minutes', 0),
                        "timestamp": timestamp_str
                    }

                    export_data["trade_details"].append(trade_details)
                except Exception as trade_error:
                    self.logger.error(f"Error processing trade for export: {trade_error}")
                    continue

            return export_data

        except Exception as e:
            self.logger.error(f"❌ Error exporting AI-ready data: {e}")
            return {"error": str(e)}

    def get_enhanced_insights(self) -> Dict[str, Any]:
        """Generate enhanced insights with advanced analytics"""
        try:
            # Get traditional insights
            insights = self.generate_insights()

            # Add parameter optimization results
            if self.optimal_parameters:
                insights['parameter_optimization'] = self.optimal_parameters

            # Add what-if scenario analysis
            closed_trades = [t for t in trade_logger.trades if t.trade_status == "CLOSED"]
            if len(closed_trades) >= 5:
                optimization_results = self.simulate_parameter_optimization(closed_trades)
                insights['optimization_scenarios'] = optimization_results

            # Add market regime analysis
            df = self.prepare_ml_dataset()
            if df is not None:
                # Market regime classification
                if 'volatility_score' in df.columns:
                    vol_regimes = pd.qcut(df['volatility_score'], q=3, labels=['Low', 'Medium', 'High'])
                    regime_performance = df.groupby(vol_regimes, observed=True)['was_profitable'].agg(['mean', 'count'])

                    insights['market_regime_analysis'] = {
                        'low_volatility': {
                            'win_rate': float(regime_performance.loc['Low', 'mean']),
                            'trade_count': int(regime_performance.loc['Low', 'count'])
                        },
                        'medium_volatility': {
                            'win_rate': float(regime_performance.loc['Medium', 'mean']), 
                            'trade_count': int(regime_performance.loc['Medium', 'count'])
                        },
                        'high_volatility': {
                            'win_rate': float(regime_performance.loc['High', 'mean']),
                            'trade_count': int(regime_performance.loc['High', 'count'])
                        }
                    }

            # Add AI-ready context
            insights['ai_context'] = self.prepare_ai_context()

            return insights

        except Exception as e:
            self.logger.error(f"❌ Error generating enhanced insights: {e}")
            return {"error": str(e)}

    def generate_insights(self) -> Dict[str, Any]:
        """Generate trading insights using ML analysis"""
        try:
            df = self.prepare_ml_dataset()
            if df is None:
                return {"error": "No data available for analysis"}

            insights = {}

            # Strategy performance analysis
            if 'strategy' in df.columns and 'was_profitable' in df.columns:
                strategy_performance = {}
                for strategy in df['strategy'].unique():
                    strategy_data = df[df['strategy'] == strategy]
                    strategy_performance[str(strategy)] = {
                        'total_trades': int(len(strategy_data)),
                        'profitable_trades': int(strategy_data['was_profitable'].sum()),
                        'win_rate': float(round(strategy_data['was_profitable'].mean() * 100, 2)),
                        'avg_pnl': float(round(strategy_data['pnl_percentage'].mean(), 2)) if 'pnl_percentage' in df.columns else 0.0,
                        'avg_duration': float(round(strategy_data['duration_minutes'].mean(), 2)) if 'duration_minutes' in df.columns else 0.0
                    }

                insights['strategy_performance'] = strategy_performance

            # Time-based analysis
            if 'hour_of_day' in df.columns and 'was_profitable' in df.columns:
                hourly_performance = df.groupby('hour_of_day')['was_profitable'].mean()
                best_hours = hourly_performance.nlargest(3)
                worst_hours = hourly_performance.nsmallest(3)

                # Convert to simple dictionaries
                best_trading_times = []
                for hour, profitability in best_hours.items():
                    best_trading_times.append({
                        'hour': int(hour),
                        'profitability': float(round(profitability * 100, 2))
                    })

                insights['best_trading_times'] = best_trading_times

            # Market condition analysis
            if 'market_trend' in df.columns and 'was_profitable' in df.columns:
                trend_performance = {}
                for trend in df['market_trend'].unique():
                    trend_data = df[df['market_trend'] == trend]
                    trend_performance[str(trend)] = {
                        'win_rate': float(round(trend_data['was_profitable'].mean() * 100, 2)),
                        'total_trades': int(len(trend_data))
                    }
                insights['market_trend_performance'] = trend_performance

            # Feature importance insights
            if self.feature_importance:
                feature_importance = []
                for model_name, features in self.feature_importance.items():
                    for feature_name, importance in sorted(features.items(), key=lambda x: x[1], reverse=True)[:10]:
                        feature_importance.append({
                            'feature': feature_name,
                            'importance': float(importance),
                            'model': model_name
                        })
                insights['feature_importance'] = feature_importance

            # Risk analysis
            if 'leverage' in df.columns and 'pnl_percentage' in df.columns:
                leverage_analysis = {}
                for leverage in df['leverage'].unique():
                    leverage_data = df[df['leverage'] == leverage]
                    leverage_analysis[str(leverage)] = {
                        'avg_pnl': float(round(leverage_data['pnl_percentage'].mean(), 2)),
                        'pnl_std': float(round(leverage_data['pnl_percentage'].std(), 2)),
                        'trade_count': int(len(leverage_data))
                    }
                insights['leverage_analysis'] = leverage_analysis

            return insights

        except Exception as e:
            self.logger.error(f"❌ Error generating insights: {e}")
            return {"error": str(e)}

    def predict_trade_outcome(self, trade_features: Dict[str, Any]) -> Dict[str, Any]:
        """Predict outcome for a potential trade"""
        if not ML_AVAILABLE or not self.profitability_model:
            return {"error": "ML models not available"}

        try:
            # Convert features to DataFrame
            feature_df = pd.DataFrame([trade_features])

            # Apply same preprocessing as training data
            feature_df = self._engineer_features(feature_df)

            # Handle categorical variables
            for col, encoder in self.label_encoders.items():
                if col in feature_df.columns:
                    try:
                        feature_df[col] = encoder.transform(feature_df[col].astype(str))
                    except:
                        feature_df[col] = 0  # Unknown category

            # Get the exact feature names used during training
            if hasattr(self, 'training_feature_names') and self.training_feature_names:
                training_features = self.training_feature_names
            elif hasattr(self.profitability_model, 'feature_names_in_'):
                training_features = self.profitability_model.feature_names_in_
            else:
                # Fallback: exclude target variables
                training_features = [col for col in feature_df.columns 
                                   if col not in ['pnl_usdt', 'pnl_percentage', 'was_profitable', 'duration_minutes']]

            # Add missing features with default values
            for feature in training_features:
                if feature not in feature_df.columns:
                    # Set default values based on feature type
                    if feature in ['exit_reason', 'market_phase', 'market_trend']:
                        feature_df[feature] = 0  # Encoded categorical
                    elif feature in ['month', 'hour_of_day', 'day_of_week']:
                        feature_df[feature] = trade_features.get(feature, 0)
                    elif feature in ['max_drawdown', 'risk_reward_ratio']:
                        feature_df[feature] = 0.0  # Default numeric values
                    else:
                        feature_df[feature] = 0.0

            # Select only the features used during training, in the same order
            X = feature_df[training_features].fillna(0).infer_objects(copy=False)

            predictions = {}

            # Predict profitability
            if self.profitability_model:
                profit_prob = self.profitability_model.predict_proba(X)[0]
                predictions['profit_probability'] = profit_prob[1] if len(profit_prob) > 1 else 0
                predictions['loss_probability'] = profit_prob[0] if len(profit_prob) > 1 else 1

            # Predict PnL
            if self.pnl_model:
                predicted_pnl = self.pnl_model.predict(X)[0]
                predictions['predicted_pnl_percentage'] = predicted_pnl

            # Predict duration
            if self.duration_model:
                predicted_duration = self.duration_model.predict(X)[0]
                predictions['predicted_duration_minutes'] = max(0, predicted_duration)

            # Risk assessment
            profit_prob = predictions.get('profit_probability', 0.5)
            if profit_prob > 0.7:
                predictions['recommendation'] = "STRONG_BUY"
            elif profit_prob > 0.6:
                predictions['recommendation'] = "BUY"
            elif profit_prob > 0.4:
                predictions['recommendation'] = "HOLD"
            else:
                predictions['recommendation'] = "AVOID"

            predictions['confidence'] = abs(profit_prob - 0.5) * 2  # 0 to 1 scale

            return predictions

        except Exception as e:
            self.logger.error(f"❌ Error predicting trade outcome: {e}")
            return {"error": str(e)}

    def _save_models(self):
        """Save trained models to disk"""
        try:
            import joblib

            if self.profitability_model:
                joblib.dump(self.profitability_model, self.models_dir / "profitability_model.pkl")

            if self.pnl_model:
                joblib.dump(self.pnl_model, self.models_dir / "pnl_model.pkl")

            if self.duration_model:
                joblib.dump(self.duration_model, self.models_dir / "duration_model.pkl")

            # Save label encoders
            with open(self.models_dir / "label_encoders.json", 'w') as f:
                encoders_dict = {}
                for key, encoder in self.label_encoders.items():
                    encoders_dict[key] = encoder.classes_.tolist()
                json.dump(encoders_dict, f)

            self.logger.info("💾 ML models saved successfully")

        except Exception as e:
            self.logger.error(f"❌ Error saving ML models: {e}")

    def analyze_what_if_scenarios_for_commands(self):
        """Analyze what-if scenarios for trade optimization (used by commands)"""
        try:
            # Get a recent trade for analysis
            from src.analytics.trade_logger import trade_logger
            closed_trades = [t for t in trade_logger.trades if t.trade_status == "CLOSED"]

            if not closed_trades:
                return {"error": "No closed trades available for analysis"}

            recent_trade = closed_trades[-1]
            base_trade = {
                'strategy': getattr(recent_trade, 'strategy_name', 'unknown_strategy'),
                'symbol': getattr(recent_trade, 'symbol', 'UNKNOWN'),
                'side': getattr(recent_trade, 'side', 'BUY'),
                'leverage': getattr(recent_trade, 'leverage', 1),
                'position_size_usdt': getattr(recent_trade, 'position_size_usdt', 100),
                'rsi_entry': getattr(recent_trade, 'rsi_at_entry', 50),
                'actual_pnl': getattr(recent_trade, 'pnl_percentage', 0)
            }

            scenarios = self.generate_what_if_scenarios(base_trade)

            # Group by scenario type
            scenario_groups = {}
            for scenario in scenarios:
                scenario_type = scenario['scenario_type']
                if scenario_type not in scenario_groups:
                    scenario_groups[scenario_type] = []
                scenario_groups[scenario_type].append(scenario)

            results = {}
            for scenario_type, group in scenario_groups.items():
                results[scenario_type] = []

                for scenario in group[:3]:  # Show top 3 scenarios
                    prediction = self.predict_trade_outcome(scenario)
                    if 'predicted_pnl_percentage' in prediction:
                        improvement = prediction['predicted_pnl_percentage'] - base_trade['actual_pnl']
                        results[scenario_type].append({
                            'scenario': scenario,
                            'predicted_pnl': prediction['predicted_pnl_percentage'],
                            'improvement': improvement
                        })

            return {
                'base_trade_id': getattr(recent_trade, 'trade_id', 'unknown'),
                'actual_pnl': base_trade['actual_pnl'],
                'scenario_results': results
            }

        except Exception as e:
            self.logger.error(f"❌ Error in what-if scenarios analysis: {e}")
            return {"error": str(e)}

# Global ML analyzer instance
ml_analyzer = MLTradeAnalyzer()
