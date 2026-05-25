"""
指标计算测试模块
===============

测试 quantss.utils.indicator 模块中的技术指标计算。
"""

import pytest
import polars as pl
import numpy as np
import pandas as pd

from quantss.utils.indicator import (
    # AtomicIndicator
    RD, RET, ABS, LN, POW, SQRT,
    SUM, MAX, MIN, IF, REF, DIFF, STD, CONST,
    HHV, LLV, HHVBARS, LLVBARS, MA, SMA, EMA, WMA, DMA,
    AVEDEV, SLOPE, FORCAST, LAST,

    # SignalIndicator
    COUNT, EVERY, EXIST, FILTER, BARSLAST, BARSLASTCOUNT,
    BARSSINCEN, CROSS, LONGCROSS, VALUEWHEN, BETWEEN, TOPRANGE, LOWRANGE,

    # TechnicalIndicator
    MACD, KDJ, RSI, WR, BIAS, BOLL, PSY, CCI, ATR, BBI, DMI,
    TAQ, KTN, TRIX, VR, CR, EMV, DPO, BRAR, DFMA, MTM, MASS,
    ROC, EXPMA, OBV, MFI, ASI, XSII,

    # CustomIndicator
    W_JX, W_TD, W_GL,
)


class TestAtomicIndicator:
    """测试基础原子指标"""

    def setup_method(self):
        """设置测试数据"""
        self.df = pl.DataFrame({
            'close': pl.Series([10.0, 11.0, 10.5, 12.0, 11.5, 13.0, 12.5, 14.0, 13.5, 15.0])
        })

    def test_ma(self):
        """测试移动平均"""
        result = self.df.select(MA(pl.col('close'), 3)).to_numpy()
        assert not np.isnan(result[2][0])  # 第三个值应该有数据

    def test_ema(self):
        """测试指数移动平均"""
        result = self.df.select(EMA(pl.col('close'), 3)).to_numpy()
        assert not np.isnan(result[0][0])  # EMA 第一个值应该有数据

    def test_ref(self):
        """测试位移"""
        result = self.df.select(REF(pl.col('close'), 1)).to_numpy()
        assert np.isnan(result[0][0])  # 第一个值应该是 NaN

    def test_diff(self):
        """测试差分"""
        result = self.df.select(DIFF(pl.col('close'), 1)).to_numpy()
        assert result[1][0] == 1.0  # 11.0 - 10.0 = 1.0

    def test_hhv_llv(self):
        """测试最高最低值"""
        hhv_result = self.df.select(HHV(pl.col('close'), 3)).to_numpy()
        llv_result = self.df.select(LLV(pl.col('close'), 3)).to_numpy()
        assert hhv_result[2][0] == 11.0
        assert llv_result[2][0] == 10.0


class TestSignalIndicator:
    """测试信号指标"""

    def setup_method(self):
        """设置测试数据"""
        self.df = pl.DataFrame({
            'close': pl.Series([10.0, 11.0, 10.5, 12.0, 11.5, 13.0, 12.5, 14.0, 13.5, 15.0])
        })

    def test_cross(self):
        """测试金叉"""
        short_ma = MA(self.df['close'], 2)
        long_ma = MA(self.df['close'], 5)
        result = self.df.with_columns(CROSS(short_ma, long_ma).alias('cross')).to_numpy()
        assert result.dtype == np.float64 or result.dtype == np.int64

    def test_barslast(self):
        """测试上一次条件满足至今的周期数"""
        condition = self.df['close'] > 12.0
        result = self.df.with_columns(BARSLAST(condition).alias('barslast')).to_numpy()
        assert result[-1][-1] == 0  # 最后一个满足条件


class TestTechnicalIndicator:
    """测试技术指标"""

    def setup_method(self):
        """设置测试数据"""
        np.random.seed(42)
        n_days = 30
        dates = pl.Series(pd.date_range('2024-01-01', periods=n_days))
        close = np.cumprod(1 + np.random.normal(0, 0.02, n_days)) * 100
        high = close * (1 + np.random.uniform(0, 0.02, n_days))
        low = close * (1 - np.random.uniform(0, 0.02, n_days))
        volume = np.random.randint(100000, 500000, n_days)

        self.df = pl.DataFrame({
            'date': dates,
            'high': high,
            'low': low,
            'close': close,
            'volume': volume
        })

    def test_macd(self):
        """测试 MACD"""
        dif, dea, macd = MACD(self.df['close'])
        assert dif is not None
        assert dea is not None
        assert macd is not None

    def test_kdj(self):
        """测试 KDJ"""
        k, d, j = KDJ(self.df['close'], self.df['high'], self.df['low'])
        assert k is not None
        assert d is not None
        assert j is not None

    def test_rsi(self):
        """测试 RSI"""
        rsi = RSI(self.df['close'])
        assert rsi is not None

    def test_boll(self):
        """测试 BOLL"""
        upper, mid, lower = BOLL(self.df['close'])
        assert upper is not None
        assert mid is not None
        assert lower is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])