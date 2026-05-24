"""SMA 골든/데드 크로스 전략."""
import backtesting as bt
import backtesting.lib as btlib

from core.strategies.base import Strategy, register


class _SMACrossoverBt(bt.Strategy):
    fast = 5
    slow = 20

    def init(self):
        self.sma_fast = self.I(btlib.SMA, self.data.Close, self.fast)
        self.sma_slow = self.I(btlib.SMA, self.data.Close, self.slow)

    def next(self):
        if btlib.crossover(self.sma_fast, self.sma_slow):
            self.buy()
        elif btlib.crossover(self.sma_slow, self.sma_fast):
            self.sell()


class SMACrossover(Strategy):
    name = "SMA Crossover"
    params_schema = {
        "fast": {"type": "int", "default": 5, "label": "단기 SMA", "min": 2, "max": 100},
        "slow": {"type": "int", "default": 20, "label": "장기 SMA", "min": 5, "max": 200},
    }

    def to_backtesting_class(self, params: dict):
        fast = int(params.get("fast", 5))
        slow = int(params.get("slow", 20))

        class _Configured(_SMACrossoverBt):
            pass

        _Configured.fast = fast
        _Configured.slow = slow
        return _Configured


register(SMACrossover())
