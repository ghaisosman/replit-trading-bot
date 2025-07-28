# CursorBot - Multi-Strategy Cryptocurrency Trading Bot

A sophisticated multi-strategy cryptocurrency trading bot built with Python, featuring real-time market analysis, automated trading, and a comprehensive web dashboard.

## 🚀 Features

### Core Trading Capabilities
- **Multi-Strategy Support**: Smart Money, MACD Divergence, RSI Oversold, and Engulfing Pattern strategies
- **Real-time Market Analysis**: Live price feeds and technical indicator calculations
- **Automated Trade Execution**: Intelligent order management with stop-loss and take-profit
- **Position Management**: Advanced position tracking and orphan detection
- **Risk Management**: Configurable leverage, margin limits, and daily trade limits

### Web Dashboard
- **Real-time Monitoring**: Live position tracking and balance updates
- **Strategy Management**: Enable/disable strategies and adjust parameters
- **Trade History**: Comprehensive trade logging and analytics
- **Performance Metrics**: PnL tracking and strategy performance analysis

### Technical Features
- **Binance Integration**: Full Binance Futures API support
- **Telegram Notifications**: Real-time trading alerts and status updates
- **Database Persistence**: Local JSON storage with backup capabilities
- **Error Recovery**: Robust error handling and automatic recovery
- **Deployment Ready**: Supports Render, Replit, and other cloud platforms

## 📋 Prerequisites

- Python 3.8+
- Binance API credentials
- Telegram Bot Token (optional)

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/ghaisosman/cursorbot.git
   cd cursorbot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   Create a `.env` file in the root directory:
   ```env
   BINANCE_API_KEY=your_binance_api_key
   BINANCE_SECRET_KEY=your_binance_secret_key
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_CHAT_ID=your_chat_id
   BINANCE_TESTNET=true  # Set to false for mainnet
   BINANCE_FUTURES=true
   ```

4. **Configure trading environment**
   Edit `trading_data/environment_config.json`:
   ```json
   {
     "BINANCE_TESTNET": "true",
     "BINANCE_FUTURES": "true"
   }
   ```

## 🚀 Usage

### Development Mode
```bash
python main.py
```
Access the web dashboard at `http://localhost:5000`

### Production Deployment
The bot automatically detects deployment environments (Render, Replit) and adjusts accordingly.

## 📊 Strategies

### Smart Money Liquidity Hunt
- Identifies liquidity sweeps and market maker activities
- Volume spike confirmation
- Session-based trading (London/New York)
- Daily trade limits

### MACD Divergence
- Detects MACD divergence patterns
- Trend confirmation filters
- Configurable parameters

### RSI Oversold
- RSI oversold condition detection
- Reversal signal generation
- Risk management integration

### Engulfing Pattern
- Candlestick pattern recognition
- Volume confirmation
- Multiple timeframe analysis

## 🔧 Configuration

### Strategy Configuration
Each strategy can be configured through the web dashboard:
- Margin allocation
- Leverage settings
- Stop-loss and take-profit levels
- Trading session filters

### Risk Management
- Maximum concurrent trades per strategy
- Daily trade limits
- Balance multiplier requirements
- Position size limits

## 📈 Monitoring

### Web Dashboard Features
- Real-time bot status
- Active positions overview
- Balance and PnL tracking
- Strategy performance metrics
- Trade history and analytics

### Telegram Integration
- Trade entry/exit notifications
- Daily performance reports
- Error alerts and warnings
- Strategy status updates

## 🛡️ Safety Features

- **Testnet Support**: Safe testing environment
- **Error Recovery**: Automatic recovery from failures
- **Orphan Detection**: Identifies and recovers orphaned positions
- **Rate Limiting**: API call protection
- **Data Validation**: Comprehensive input validation

## 📁 Project Structure

```
cursorbot/
├── src/
│   ├── binance_client/     # Binance API integration
│   ├── config/            # Configuration management
│   ├── data_fetcher/      # Market data retrieval
│   ├── execution_engine/  # Trade execution and management
│   ├── reporting/         # Telegram and logging
│   ├── strategy_processor/ # Strategy implementation
│   └── utils/             # Utility functions
├── trading_data/          # Database and configuration files
├── static/               # Web dashboard assets
├── web_dashboard.py      # Flask web application
├── main.py              # Bot entry point
└── requirements.txt     # Python dependencies
```

## ⚠️ Important Notes

- **Testnet First**: Always test on Binance testnet before mainnet
- **API Permissions**: Ensure API keys have futures trading permissions
- **Risk Management**: Configure appropriate risk parameters
- **Monitoring**: Regularly check bot status and performance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## ⚠️ Disclaimer

This software is for educational and research purposes. Trading cryptocurrencies involves substantial risk of loss. Use at your own risk and never invest more than you can afford to lose.

## 🆘 Support

For issues and questions:
- Check the documentation
- Review error logs
- Test on testnet first
- Contact support through GitHub issues
