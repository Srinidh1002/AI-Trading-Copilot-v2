# services/trading/adaptive_learning_engine.py
# FIXED - Added missing imports

import asyncio
import logging
import json
import os
from pathlib import Path  # <-- ADD THIS
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import numpy as np
from dataclasses import dataclass, field, asdict
from collections import deque

logger = logging.getLogger(__name__)

# ============================================================
# 1. TRADE RECORD & LEARNING DATA
# ============================================================

@dataclass
class TradeRecord:
    """Complete record of every trade for learning"""
    symbol: str
    option_type: str
    entry_price: float
    exit_price: float
    entry_time: datetime
    exit_time: datetime
    pnl_percent: float
    pnl_absolute: float
    quantity: int
    lots: int
    regime: str
    indicators: Dict
    market_context: Dict
    exit_reason: str
    holding_seconds: float
    trade_score: float = 0.0
    improvement_notes: str = ""

@dataclass
class DailyPerformance:
    """Daily performance metrics"""
    date: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_pnl: float = 0.0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_drawdown: float = 0.0
    best_trade: float = 0.0
    worst_trade: float = 0.0
    t1_hits: int = 0
    t2_hits: int = 0
    t3_hits: int = 0
    regime_distribution: Dict = field(default_factory=dict)
    indicator_performance: Dict = field(default_factory=dict)
    improvement_suggestions: List[str] = field(default_factory=list)

@dataclass
class LearningParameters:
    """Self-learning parameters that evolve"""
    min_trend_strength: float = 0.6
    min_confidence: float = 0.50
    rsi_entry_low: float = 30
    rsi_entry_high: float = 70
    breakout_threshold: float = 0.2
    t1_modifier: float = 1.0
    t2_modifier: float = 1.0
    t3_modifier: float = 1.0
    stop_loss_modifier: float = 1.0
    risk_per_trade: float = 2.0
    max_lots_per_trade: int = 5
    trend_weight: float = 1.0
    rsi_weight: float = 1.0
    macd_weight: float = 1.0
    volume_weight: float = 0.5
    market_bias_weight: float = 0.8
    regime_weight: float = 1.2
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    adaptation_count: int = 0


# ============================================================
# 2. SELF-LEARNING ENGINE
# ============================================================

class SelfLearningEngine:
    """Self-improving AI that learns from every trade"""
    
    def __init__(self, data_dir: str = "data/learning"):
        self.data_dir = Path(data_dir)  # <-- Now Path is defined
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.trade_history = []
        self.parameters = self._load_parameters()
        self.daily_performance = self._load_daily_performance()
        self.performance_history = self._load_performance_history()
        self.learning_cycles = 0
        
        self.strategies = self._initialize_strategies()
        self.strategy_performance = {}
        
        logger.info("[AI] Self-Learning Engine initialized")
        
    def _load_parameters(self) -> LearningParameters:
        """Load or create learning parameters"""
        param_file = self.data_dir / "learning_parameters.json"
        if param_file.exists():
            try:
                with open(param_file, 'r') as f:
                    data = json.load(f)
                    return LearningParameters(**data)
            except:
                pass
        return LearningParameters()
    
    def _save_parameters(self):
        """Save learning parameters"""
        param_file = self.data_dir / "learning_parameters.json"
        with open(param_file, 'w') as f:
            json.dump(asdict(self.parameters), f, indent=2, default=str)
    
    def _load_daily_performance(self) -> Dict:
        """Load today's performance"""
        today = datetime.now().strftime('%Y-%m-%d')
        perf_file = self.data_dir / f"performance_{today}.json"
        if perf_file.exists():
            try:
                with open(perf_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'trades': [], 'metrics': {}}
    
    def _load_performance_history(self) -> List:
        """Load historical performance"""
        hist_file = self.data_dir / "performance_history.json"
        if hist_file.exists():
            try:
                with open(hist_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def _save_performance_history(self):
        """Save performance history"""
        hist_file = self.data_dir / "performance_history.json"
        with open(hist_file, 'w') as f:
            json.dump(self.performance_history, f, indent=2, default=str)
    
    def _initialize_strategies(self) -> Dict:
        """Initialize strategy pool"""
        return {
            'trend_following': {
                'active': True,
                'weight': 1.0,
                'description': 'Follows SMA alignments',
                'conditions': ['trend_strength > 0.6', 'rsi between 40-60']
            },
            'breakout': {
                'active': True,
                'weight': 1.0,
                'description': 'Trades breakouts from consolidation',
                'conditions': ['volatility < 0.3', 'breakout confirmed']
            },
            'rsi_reversal': {
                'active': True,
                'weight': 0.8,
                'description': 'Reversals from overbought/oversold',
                'conditions': ['rsi > 70 or rsi < 30']
            },
            'market_bias': {
                'active': True,
                'weight': 1.0,
                'description': 'Follows overall market bias',
                'conditions': ['strong_bias', 'rsi > 40 for call']
            },
            'momentum': {
                'active': True,
                'weight': 0.8,
                'description': 'Momentum based entry',
                'conditions': ['macd_signal', 'volume_rising']
            }
        }
    
    def record_trade(self, trade: Dict) -> TradeRecord:
        """Record a completed trade for learning"""
        record = TradeRecord(
            symbol=trade.get('symbol', ''),
            option_type=trade.get('option_type', ''),
            entry_price=trade.get('entry_price', 0),
            exit_price=trade.get('exit_price', 0),
            entry_time=trade.get('entry_time', datetime.now()),
            exit_time=trade.get('exit_time', datetime.now()),
            pnl_percent=trade.get('pnl_percent', 0),
            pnl_absolute=trade.get('pnl_absolute', 0),
            quantity=trade.get('quantity', 0),
            lots=trade.get('lots', 0),
            regime=trade.get('regime', 'NEUTRAL'),
            indicators=trade.get('indicators', {}),
            market_context=trade.get('market_context', {}),
            exit_reason=trade.get('reason', ''),
            holding_seconds=trade.get('holding_seconds', 0),
            trade_score=self._calculate_trade_score(trade)
        )
        
        self.trade_history.append(record)
        self._update_daily_performance(record)
        self._learn_from_trade(record)
        
        return record
    
    def _calculate_trade_score(self, trade: Dict) -> float:
        """Calculate a score for the trade (0-100)"""
        score = 50
        
        pnl = trade.get('pnl_percent', 0)
        if pnl > 0:
            score += min(pnl * 20, 30)
        else:
            score -= min(abs(pnl) * 10, 20)
        
        if trade.get('tier') == 'T1':
            score += 10
        elif trade.get('tier') == 'T2':
            score += 20
        elif trade.get('tier') == 'T3':
            score += 30
        
        hold_time = trade.get('holding_seconds', 0)
        if 30 < hold_time < 300:
            score += 5
        
        if trade.get('reason') in ['ALL_TARGETS_HIT', 'PROFIT_TARGET']:
            score += 10
        elif trade.get('reason') == 'STOP_LOSS':
            score -= 10
        
        return max(0, min(100, score))
    
    def _update_daily_performance(self, record: TradeRecord):
        """Update daily performance metrics"""
        today = datetime.now().strftime('%Y-%m-%d')
        
        if today not in self.daily_performance:
            self.daily_performance[today] = {'trades': [], 'metrics': {}}
        
        self.daily_performance[today]['trades'].append(asdict(record))
        
        trades = self.daily_performance[today]['trades']
        winning = [t for t in trades if t['pnl_percent'] > 0]
        losing = [t for t in trades if t['pnl_percent'] <= 0]
        
        metrics = {
            'total_trades': len(trades),
            'winning_trades': len(winning),
            'losing_trades': len(losing),
            'total_pnl': sum(t['pnl_absolute'] for t in trades),
            'win_rate': (len(winning) / len(trades) * 100) if trades else 0,
            'avg_win': sum(t['pnl_absolute'] for t in winning) / len(winning) if winning else 0,
            'avg_loss': sum(t['pnl_absolute'] for t in losing) / len(losing) if losing else 0,
            't1_hits': sum(1 for t in trades if t.get('tier') == 'T1'),
            't2_hits': sum(1 for t in trades if t.get('tier') == 'T2'),
            't3_hits': sum(1 for t in trades if t.get('tier') == 'T3')
        }
        self.daily_performance[today]['metrics'] = metrics
        
        perf_file = self.data_dir / f"performance_{today}.json"
        with open(perf_file, 'w') as f:
            json.dump(self.daily_performance[today], f, indent=2, default=str)
    
    def _learn_from_trade(self, record: TradeRecord):
        """The core learning function"""
        self.learning_cycles += 1
        logger.info(f"[AI] Learning from trade #{self.learning_cycles}")
        
        if record.pnl_percent > 0:
            self._reinforce_successful_patterns(record)
        else:
            self._avoid_failure_patterns(record)
        
        self._adjust_parameters()
        self._update_strategy_weights()
        self._save_parameters()
        self._save_performance_history()
        self._log_learning_summary()
    
    def _reinforce_successful_patterns(self, record: TradeRecord):
        """Reinforce patterns that led to winning trades"""
        indicators = record.indicators
        
        if indicators.get('rsi', 50) < 40 and record.option_type == 'CALL':
            self.parameters.rsi_weight *= 1.05
        elif indicators.get('rsi', 50) > 60 and record.option_type == 'PUT':
            self.parameters.rsi_weight *= 1.05
        
        if record.regime == 'TRENDING' and record.pnl_percent > 0.2:
            self.parameters.regime_weight *= 1.03
        
        if record.exit_reason == 'T1':
            self.parameters.t1_modifier *= 1.02
        elif record.exit_reason == 'T2':
            self.parameters.t2_modifier *= 1.02
        elif record.exit_reason == 'T3':
            self.parameters.t3_modifier *= 1.02
        
        logger.info(f"[AI] Reinforced: {record.symbol} {record.option_type} | P&L: {record.pnl_percent:.2f}%")
    
    def _avoid_failure_patterns(self, record: TradeRecord):
        """Learn from losing trades"""
        indicators = record.indicators
        
        if indicators.get('rsi', 50) < 40 and record.option_type == 'PUT':
            self.parameters.rsi_weight *= 0.95
        elif indicators.get('rsi', 50) > 60 and record.option_type == 'CALL':
            self.parameters.rsi_weight *= 0.95
        
        if record.regime == 'CONSOLIDATION':
            self.parameters.stop_loss_modifier *= 1.02
        
        logger.info(f"[AI] Learned from loss: {record.symbol} | P&L: {record.pnl_percent:.2f}%")
    
    def _adjust_parameters(self):
        """Self-adjust parameters based on recent performance"""
        recent_trades = self.trade_history[-20:] if len(self.trade_history) >= 20 else self.trade_history
        if not recent_trades:
            return
        
        wins = sum(1 for t in recent_trades if t.pnl_percent > 0)
        win_rate = (wins / len(recent_trades)) * 100
        
        if win_rate > 60 and self.parameters.min_confidence > 0.45:
            self.parameters.min_confidence = max(0.45, self.parameters.min_confidence - 0.01)
        elif win_rate < 40 and self.parameters.min_confidence < 0.65:
            self.parameters.min_confidence = min(0.65, self.parameters.min_confidence + 0.01)
        
        avg_pnl = sum(t.pnl_percent for t in recent_trades) / len(recent_trades)
        if avg_pnl > 0.15:
            self.parameters.risk_per_trade = min(3.0, self.parameters.risk_per_trade * 1.02)
        elif avg_pnl < 0:
            self.parameters.risk_per_trade = max(1.0, self.parameters.risk_per_trade * 0.98)
        
        self.parameters.adaptation_count += 1
        self.parameters.last_updated = datetime.now().isoformat()
    
    def _update_strategy_weights(self):
        """Update strategy weights based on performance"""
        recent_trades = self.trade_history[-50:] if len(self.trade_history) >= 50 else self.trade_history
        
        for strategy in self.strategies:
            strategy_trades = [t for t in recent_trades if t.indicators.get('strategy') == strategy]
            if strategy_trades:
                wins = sum(1 for t in strategy_trades if t.pnl_percent > 0)
                win_rate = wins / len(strategy_trades) if strategy_trades else 0.5
                
                current_weight = self.strategies[strategy]['weight']
                new_weight = current_weight * (0.9 + win_rate * 0.2)
                self.strategies[strategy]['weight'] = max(0.3, min(1.5, new_weight))
    
    def _log_learning_summary(self):
        """Log learning summary"""
        total_trades = len(self.trade_history)
        winning = sum(1 for t in self.trade_history if t.pnl_percent > 0)
        win_rate = (winning / total_trades * 100) if total_trades > 0 else 0
        
        logger.info(f"""
[AI] LEARNING SUMMARY (Cycle {self.learning_cycles})
  Total Trades: {total_trades}
  Win Rate: {win_rate:.1f}%
  Confidence Threshold: {self.parameters.min_confidence:.2f}
  Risk per Trade: {self.parameters.risk_per_trade:.1f}%
  T1 Modifier: {self.parameters.t1_modifier:.2f}
  T2 Modifier: {self.parameters.t2_modifier:.2f}
  T3 Modifier: {self.parameters.t3_modifier:.2f}
  
[AI] Strategy Weights:
  Trend Following: {self.strategies['trend_following']['weight']:.2f}
  Breakout: {self.strategies['breakout']['weight']:.2f}
  RSI Reversal: {self.strategies['rsi_reversal']['weight']:.2f}
  Market Bias: {self.strategies['market_bias']['weight']:.2f}
  Momentum: {self.strategies['momentum']['weight']:.2f}
""")
    
    def get_enhanced_signal(self, indicators: Dict, regime: str, market_bias: str) -> Dict:
        """Get enhanced trading signal with AI learning"""
        base_signal = self._generate_base_signal(indicators, regime, market_bias)
        
        if base_signal['signal'] == 'TRADE':
            base_signal['confidence'] = self._enhance_confidence(base_signal, indicators)
            base_signal['targets'] = self._enhance_targets(base_signal, regime)
            base_signal['strategy'] = self._select_best_strategy(indicators, regime)
            base_signal['learning_cycle'] = self.learning_cycles
            base_signal['improvement'] = self._get_improvement_notes(base_signal)
        
        return base_signal
    
    def _generate_base_signal(self, indicators: Dict, regime: str, market_bias: str) -> Dict:
        """Generate base signal"""
        return {
            'signal': 'WAIT',
            'confidence': 0,
            'reason': 'Base signal generated',
            'regime': regime,
            'market_bias': market_bias
        }
    
    def _enhance_confidence(self, signal: Dict, indicators: Dict) -> float:
        """Enhance confidence using learned parameters"""
        base_confidence = signal.get('confidence', 0.5)
        
        if indicators.get('trend_strength', 0) > 0.7:
            base_confidence += 0.05
        
        if indicators.get('rsi', 50) < 35 or indicators.get('rsi', 50) > 65:
            base_confidence += 0.05
        
        if signal.get('regime') == 'TRENDING':
            base_confidence *= self.parameters.regime_weight
        
        return min(1.0, base_confidence)
    
    def _enhance_targets(self, signal: Dict, regime: str) -> Dict:
        """Enhance targets based on learning"""
        base_targets = signal.get('targets', {'T1': 0, 'T2': 0, 'T3': 0})
        
        if regime == 'CONSOLIDATION':
            t1_mod = 0.8
            t2_mod = 0.8
            t3_mod = 0.8
        elif regime == 'TRENDING':
            t1_mod = 1.0
            t2_mod = 1.0
            t3_mod = 1.0
        else:
            t1_mod = self.parameters.t1_modifier
            t2_mod = self.parameters.t2_modifier
            t3_mod = self.parameters.t3_modifier
        
        entry = signal.get('entry_price', 0)
        return {
            'T1': entry * (1 + (0.15 * t1_mod / 100)),
            'T2': entry * (1 + (0.30 * t2_mod / 100)),
            'T3': entry * (1 + (0.50 * t3_mod / 100))
        }
    
    def _select_best_strategy(self, indicators: Dict, regime: str) -> str:
        """Select the best strategy based on current conditions and learning"""
        scores = {}
        
        for strategy, data in self.strategies.items():
            if not data['active']:
                continue
            
            score = data['weight']
            
            if strategy == 'trend_following' and regime == 'TRENDING':
                score *= 1.2
            elif strategy == 'breakout' and regime == 'CONSOLIDATION':
                score *= 1.3
            elif strategy == 'rsi_reversal' and (indicators.get('rsi', 50) < 35 or indicators.get('rsi', 50) > 65):
                score *= 1.2
            elif strategy == 'market_bias' and indicators.get('market_bias') in ['STRONGLY_BULLISH', 'STRONGLY_BEARISH']:
                score *= 1.1
            
            scores[strategy] = score
        
        if scores:
            return max(scores, key=scores.get)
        return 'trend_following'
    
    def _get_improvement_notes(self, signal: Dict) -> str:
        """Generate improvement notes for the trade"""
        notes = []
        strategy = signal.get('strategy', 'unknown')
        confidence = signal.get('confidence', 0)
        
        notes.append(f"Strategy: {strategy}")
        notes.append(f"Confidence: {confidence:.2f}")
        notes.append(f"Learning Cycle: {self.learning_cycles}")
        
        if strategy == 'rsi_reversal':
            notes.append("RSI reversal strategy - watch for target hits")
        elif strategy == 'breakout':
            notes.append("Breakout strategy - confirm volume")
        elif strategy == 'trend_following':
            notes.append("Trend following - align with market bias")
        
        return " | ".join(notes)
    
    def get_performance_metrics(self) -> Dict:
        """Get comprehensive performance metrics"""
        total_trades = len(self.trade_history)
        winning = sum(1 for t in self.trade_history if t.pnl_percent > 0)
        
        return {
            'total_trades': total_trades,
            'winning_trades': winning,
            'win_rate': (winning / total_trades * 100) if total_trades > 0 else 0,
            'total_pnl': sum(t.pnl_absolute for t in self.trade_history),
            'learning_cycles': self.learning_cycles,
            'parameters': asdict(self.parameters),
            'strategy_weights': {s: d['weight'] for s, d in self.strategies.items()},
            'daily_performance': self._load_daily_performance(),
            'best_trade': max(self.trade_history, key=lambda t: t.pnl_percent) if self.trade_history else None,
            'worst_trade': min(self.trade_history, key=lambda t: t.pnl_percent) if self.trade_history else None
        }


# ============================================================
# 3. ADAPTIVE LEARNING ENGINE (Wrapper)
# ============================================================

class AdaptiveLearningEngine:
    """Wrapper to integrate AI learning with main trading engine"""
    
    def __init__(self):
        self.learning_engine = SelfLearningEngine()
        self.last_report_time = datetime.now()
        
    def analyze_pre_market(self, context: Dict) -> Dict:
        """Analyze pre-market with learning context"""
        metrics = self.learning_engine.get_performance_metrics()
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'market_bias': context.get('market_bias', 'NEUTRAL'),
            'recommended_market': context.get('recommended_market', 'BOTH'),
            'learning_cycle': self.learning_engine.learning_cycles,
            'today_goal': self._generate_daily_goal(metrics),
            'yesterday_performance': self._get_yesterday_summary()
        }
        
        logger.info(f"[AI] Pre-market analysis completed with learning cycle {self.learning_engine.learning_cycles}")
        return report
    
    def _generate_daily_goal(self, metrics: Dict) -> str:
        """Generate daily trading goal based on learning"""
        win_rate = metrics.get('win_rate', 0)
        
        if win_rate < 40:
            return "Focus on high probability setups (confidence > 0.6)"
        elif win_rate < 60:
            return "Maintain current strategy, look for T2/T3 targets"
        else:
            return "Take more aggressive positions, target T3"
    
    def _get_yesterday_summary(self) -> Dict:
        """Get yesterday's performance summary"""
        yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        if yesterday in self.learning_engine.daily_performance:
            return self.learning_engine.daily_performance[yesterday]
        return {'trades': 0, 'profit': 0, 'win_rate': 0}
    
    def enhance_signal(self, signal: Dict, indicators: Dict) -> Dict:
        """Enhance trading signal with AI learning"""
        regime = signal.get('regime', 'NEUTRAL')
        market_bias = signal.get('market_bias', 'NEUTRAL')
        
        return self.learning_engine.get_enhanced_signal(indicators, regime, market_bias)
    
    def record_trade_result(self, trade: Dict):
        """Record trade result for learning"""
        self.learning_engine.record_trade(trade)
        logger.info(f"[AI] Trade recorded for learning: {trade.get('symbol')} P&L: {trade.get('pnl_percent', 0):.2f}%")
    
    def get_learning_report(self) -> str:
        """Get comprehensive learning report"""
        metrics = self.learning_engine.get_performance_metrics()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║           AI LEARNING & PERFORMANCE REPORT                  ║
╠══════════════════════════════════════════════════════════════╣
║                                                              ║
║  📊 TRADING METRICS:                                        ║
║    Total Trades: {metrics['total_trades']}                                 ║
║    Win Rate: {metrics['win_rate']:.1f}%                                    ║
║    Total P&L: ₹{metrics['total_pnl']:.2f}                                  ║
║    Learning Cycles: {metrics['learning_cycles']}                           ║
║                                                              ║
║  🎯 STRATEGY WEIGHTS:                                       ║
║    Trend Following: {metrics['strategy_weights'].get('trend_following', 0):.2f}               ║
║    Breakout: {metrics['strategy_weights'].get('breakout', 0):.2f}                         ║
║    RSI Reversal: {metrics['strategy_weights'].get('rsi_reversal', 0):.2f}                       ║
║    Market Bias: {metrics['strategy_weights'].get('market_bias', 0):.2f}                         ║
║    Momentum: {metrics['strategy_weights'].get('momentum', 0):.2f}                            ║
║                                                              ║
║  📈 TARGET MODIFIERS:                                       ║
║    T1: {metrics['parameters']['t1_modifier']:.2f}                                         ║
║    T2: {metrics['parameters']['t2_modifier']:.2f}                                         ║
║    T3: {metrics['parameters']['t3_modifier']:.2f}                                         ║
║    Stop Loss: {metrics['parameters']['stop_loss_modifier']:.2f}                              ║
║                                                              ║
║  💡 RECOMMENDATION:                                         ║
║    {self._generate_daily_goal(metrics)}                         ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
        return report
