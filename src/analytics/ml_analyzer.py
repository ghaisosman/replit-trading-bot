
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
    """Machine Learning analyzer for trading strategy optimization"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.models_dir = Path("trading_data/ml_models")
        self.models_dir.mkdir(exist_ok=True, parents=True)

        # ML models
        self.profitability_model = None  # Predict if trade will be profitable
        self.pnl_model = None           # Predict PnL amount
        self.duration_model = None      # Predict trade duration

        # Feature scalers
        self.scaler = StandardScaler()
        self.label_encoders = {}

        # Feature importance tracking
        self.feature_importance = {}

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

            if len(df) < 10:
                self.logger.warning("⚠️ Insufficient data for ML analysis (need at least 10 trades)")
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
            df['is_weekend'] = df['day_of_week'].isin([5, 6]).astype(int)
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

            if len(df) < 20:
                return {"error": f"Insufficient data for training - need at least 20 trades, got {len(df)}"}

            results = {
                "dataset_size": int(len(df)),
                "features_count": int(len(df.columns))
            }

            # Define features (exclude target variables)
            target_columns = ['pnl_usdt', 'pnl_percentage', 'was_profitable', 'duration_minutes']
            feature_columns = [col for col in df.columns if col not in target_columns]

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

            # Select only features used in training
            feature_columns = [col for col in feature_df.columns 
                             if col not in ['pnl_usdt', 'pnl_percentage', 'was_profitable', 'duration_minutes']]

            # Ensure all required features are present
            X = feature_df[feature_columns].fillna(0)

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

# Global ML analyzer instance
ml_analyzer = MLTradeAnalyzer()
