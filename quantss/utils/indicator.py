"""
技术指标计算模块
===============

提供基于 Polars 的高性能技术指标计算函数，支持向量化计算。
"""

from enum import nonmember
import numpy as np
import polars as pl


class AtomicIndicator:
    """
    原子指标计算类。
    
    提供基础的技术分析指标计算方法，所有方法均返回 Polars Expr，
    支持链式调用和向量化计算。
    """
    def RD(expr: pl.Expr, D: int = 2) -> pl.Expr:   
        return expr.round(D)

    @staticmethod
    def RET(S: pl.Expr, N=1) -> pl.Expr:  
        return S.slice(-N, 1)

    @staticmethod
    def ABS(S) -> pl.Expr:
        return S.abs()

    @staticmethod
    def LN(S) -> pl.Expr:       
        return S.log()

    @staticmethod
    def POW(S: pl.Expr, N) -> pl.Expr:    
        return S.pow(N) 

    @staticmethod
    def SQRT(S: pl.Expr) -> pl.Expr:    
        return S.sqrt() 

    @staticmethod
    def SIN(S: pl.Expr) -> pl.Expr:     
        return S.sin()       

    @staticmethod
    def COS(S: pl.Expr) -> pl.Expr:     
        return S.cos()        

    @staticmethod
    def TAN(S: pl.Expr) -> pl.Expr:      
        return S.tan()  

    @staticmethod
    def MAX(S1: pl.Expr, S2: pl.Expr) -> pl.Expr: 
        # 对比两个表达式或列的元素最大值
        return pl.max_horizontal(S1, S2)

    @staticmethod
    def MIN(S1: pl.Expr, S2: pl.Expr) -> pl.Expr: 
        # 对比两个表达式或列的元素最小值
        return pl.min_horizontal(S1, S2)

    @staticmethod
    def IF(S: pl.Expr, A: pl.Expr, B: pl.Expr) -> pl.Expr:  
        # 条件状态机：当 S 为 True 返回 A，否则返回 B
        return pl.when(S).then(A).otherwise(B)

    @staticmethod
    def REF(S: pl.Expr, N=1) -> pl.Expr:     
        # 向前平移 N 日数据
        return S.shift(N)

    @staticmethod
    def DIFF(S: pl.Expr, N=1) -> pl.Expr:    
        # 一阶/N阶差分
        return S.diff(n=N)
        
    @staticmethod 
    def STD(S: pl.Expr, N) -> pl.Expr:           
        # 滚动总体标准差 (ddof=0)
        return S.rolling_std(window_size=N, ddof=0)

    @staticmethod 
    def SUM(S: pl.Expr, N) -> pl.Expr:     
        # N>0 滚动求和，N=0 累计求和
        return S.rolling_sum(window_size=N) if N > 0 else S.cum_sum()

    @staticmethod 
    def CONST(S: pl.Expr) -> pl.Expr:           
        # 用最后一行的值填充整列
        return S.last()

    @staticmethod 
    def HHV(S: pl.Expr, N) -> pl.Expr:             
        # 滚动最大值
        return S.rolling_max(window_size=N)

    @staticmethod 
    def LLV(S: pl.Expr, N) -> pl.Expr:    
        # 滚动最小值
        return S.rolling_min(window_size=N)

    @staticmethod 
    def HHVBARS(S: pl.Expr, N) -> pl.Expr:        
        # 滚动计算最高点至今的周期数 (含当前行，最高点为 0)
        return S.rolling_map(lambda x: N - 1 - x.arg_max(), window_size=N)

    @staticmethod 
    def LLVBARS(S: pl.Expr, N) -> pl.Expr:       
        # 滚动计算最低点至今的周期数
        return S.rolling_map(lambda x: N - 1 - x.arg_min(), window_size=N)

    @staticmethod 
    def MA(S: pl.Expr, N: int) -> pl.Expr:
        # 滚动简单算术平均
        return S.rolling_mean(window_size=N)

    @staticmethod 
    def EMA(S: pl.Expr, N) -> pl.Expr:         
        # 指数平滑移动平均
        return S.ewm_mean(span=N, adjust=False)
    
    @staticmethod  
    def SMA(S: pl.Expr, N, M=1) -> pl.Expr:
        # 通达信/同花顺标准 SMA 算法 (alpha = M / N)
        return S.ewm_mean(alpha=M/N, adjust=False)

    @staticmethod 
    def WMA(S: pl.Expr, N) -> pl.Expr:         
        # 加权移动平均 (避免底层 map，采用序列化生成权重算子)
        weights = list(range(1, N + 1))
        return S.rolling_map(lambda x: x.dot(weights) / sum(weights), window_size=N)

    @staticmethod  
    def DMA(S: pl.Expr, A) -> pl.Expr:
        # 如果 A 是常数，将其包装为表达式
        if not isinstance(A, pl.Expr):
            A = pl.lit(A)

        # 使用 map_batches 在底层直接操作具体序列，利用 NumPy 极速完成递归
        def _dma_calc(series_list: list[pl.Series]) -> pl.Series:
            x_arr = series_list[0].to_numpy()
            a_arr = series_list[1].to_numpy()
            
            # 初始化结果数组
            y_arr = np.zeros_like(x_arr, dtype=np.float64)   
            if len(x_arr) == 0:
                return pl.Series(y_arr)   

            # 第一个值初始化
            y_arr[0] = x_arr[0]
            
            # 核心递归循环 (NumPy 底层循环速度非常快)
            for i in range(1, len(x_arr)):
                a = a_arr[i]
                # 兼容处理：若权重出现 NaN，则沿用前一日值
                if np.isnan(a):
                    y_arr[i] = y_arr[i-1]
                else:
                    y_arr[i] = a * x_arr[i] + (1.0 - a) * y_arr[i-1]         
            return pl.Series(y_arr)

        # 将 S 和 A 打包组合成一个结构体传给 _dma_calc 处理
        return pl.map_batches([S, A], _dma_calc)
 
    @staticmethod 
    def AVEDEV(S: pl.Expr, N) -> pl.Expr:    
        # 平均绝对偏差 (Mean Absolute Deviation)
        return S.rolling_map(
            lambda x: np.abs(x - x.mean()).mean(), 
            window_size=N
        )

    @staticmethod 
    def SLOPE(S: pl.Expr, N) -> pl.Expr:        
        # 滚动线性回归斜率：使用最小二乘法封闭解公式，规避 polyfit 性能损耗
        x = np.arange(N)
        x_mean = x.mean()
        x_dev = x - x_mean
        var_x = (x_dev ** 2).sum()

        return S.rolling_map(
            lambda y: (y * x_dev).sum() / var_x, 
            window_size=N
        )

    @staticmethod 
    def FORCAST(S: pl.Expr, N) -> pl.Expr: 
        # 滚动线性回归预测值：Y_hat = intercept + slope * (N - 1)
        x = np.arange(N)
        x_mean = x.mean()
        x_dev = x - x_mean
        var_x = (x_dev ** 2).sum()

        def _get_forecast(y):
            slope = (y * x_dev).sum() / var_x
            intercept = y.mean() - slope * x_mean
            return intercept + slope * (N - 1)

        return S.rolling_map(_get_forecast, window_size=N)

    @staticmethod 
    def LAST(S: pl.Expr, A, B) -> pl.Expr:    
        # 检验条件：从倒数第 B 期开始往前，连续 A 日满足条件 S
        # 转换为表达式写法：向前位移 B 日后，计算滚动求和是否等于有效窗口 A
        return (
            S.cast(pl.Int32)                   # 将布尔条件转为 1 或 0
            .shift(B)                                   # 排除最新的 B 周期时间窗口
            .rolling_sum(window_size=A) == A            # 判断 A 周期内是否全为 1 (True)
        )

RD = AtomicIndicator.RD
RET = AtomicIndicator.RET
ABS = AtomicIndicator.ABS     
LN = AtomicIndicator.LN     
POW = AtomicIndicator.POW     
SQRT = AtomicIndicator.SQRT  
SIN = AtomicIndicator.SIN
COS = AtomicIndicator.COS
TAN = AtomicIndicator.TAN   
SUM = AtomicIndicator.SUM
MAX = AtomicIndicator.MAX
MIN = AtomicIndicator.MIN
IF = AtomicIndicator.IF
REF = AtomicIndicator.REF
DIFF = AtomicIndicator.DIFF
STD = AtomicIndicator.STD
SUM = AtomicIndicator.SUM
CONST = AtomicIndicator.CONST
HHV = AtomicIndicator.HHV
LLV = AtomicIndicator.LLV
HHVBARS = AtomicIndicator.HHVBARS
LLVBARS = AtomicIndicator.LLVBARS
MA = AtomicIndicator.MA
SMA = AtomicIndicator.SMA
EMA = AtomicIndicator.EMA
WMA = AtomicIndicator.WMA
DMA = AtomicIndicator.DMA
AVEDEV = AtomicIndicator.AVEDEV
SLOPE = AtomicIndicator.SLOPE
FORCAST = AtomicIndicator.FORCAST
LAST = AtomicIndicator.LAST

class SignalIndicator():

    @staticmethod 
    def COUNT(S: pl.Expr, N) -> pl.Expr:               
        # 统计 N 周期内满足条件的次数 (S 为布尔或 0/1)
        return S.cast(pl.Int32).rolling_sum(window_size=N) if N > 0 else S.cast(pl.Int32).cum_sum()

    @staticmethod 
    def EVERY(S: pl.Expr, N) -> pl.Expr:                
        # N 周期内是否一直满足条件
        return S.cast(pl.Int32).rolling_sum(window_size=N) == N

    @staticmethod 
    def EXIST(S: pl.Expr, N) -> pl.Expr:
        # N 周期内是否存在满足条件的情况
        return S.cast(pl.Int32).rolling_sum(window_size=N) > 0
    
    @staticmethod
    def FILTER(S: pl.Expr, N) -> pl.Expr:     
        # 信号过滤：触发后接下来 N 周期内信号置为 0
        def _filter_loop(s_series: pl.Series) -> pl.Series:
            s_arr = s_series.to_numpy().astype(bool)
            for i in range(len(s_arr)):
                if s_arr[i]:
                    s_arr[i + 1 : i + 1 + N] = False
            return pl.Series(s_arr, dtype=pl.Boolean)
            
        return S.map_batches(_filter_loop)

    @staticmethod 
    def BARSLAST(S: pl.Expr) -> pl.Expr:    
        # 上一次条件满足至今的周期数
        # 原理：生成单调递增序列，在满足条件处记录序号，用 forward_fill 前向填充后做差
        idx = pl.int_range(0, pl.len(), dtype=pl.Int32)
        condition_idx = pl.when(S).then(idx).otherwise(None)
        return idx - condition_idx.forward_fill()

    @staticmethod
    def BARSLASTCOUNT(S: pl.Expr) -> pl.Expr:                
        # 条件连续成立的周期数 (不成立则清零，重新累计)
        # 原理：利用累计求和在不成立处生成分组标签，再计算组内累计值
        is_zero = (~S).cast(pl.Int32)
        group_id = is_zero.cum_sum()
        return S.cast(pl.Int32).cum_sum().over(group_id)
    
    @staticmethod
    def BARSSINCEN(S: pl.Expr, N) -> pl.Expr:             
        # N 周期内第一次满足条件至今的周期数
        return S.rolling_map(
            lambda x: N - 1 - np.argmax(x) if np.any(x) else 0, 
            window_size=N
        ).fill_null(0).cast(pl.Int32)
    
    @staticmethod
    def CROSS(S1: pl.Expr, S2: pl.Expr) -> pl.Expr:             
        # 金叉/上穿：上一周期 S1 <= S2 且 当前周期 S1 > S2
        return (S1.shift(1) <= S2.shift(1)) & (S1 > S2)
        
    @staticmethod
    def LONGCROSS(S1: pl.Expr, S2: pl.Expr, N) -> pl.Expr:                   
        # 维持 N 周期空头后金叉：前 N 周期 S1 < S2，当前周期 S1 > S2
        # 直接复用上面重构好的 LAST 条件机制
        last_s1_low = (S1 < S2).cast(pl.Int32).shift(1).rolling_sum(window_size=N) == N
        return last_s1_low & (S1 > S2)
        
    @staticmethod
    def VALUEWHEN(S: pl.Expr, X) -> pl.Expr:            
        # 条件成立时的取值，后续周期保持该值直到下次条件成立
        return pl.when(S).then(X).otherwise(None).forward_fill()

    @staticmethod
    def BETWEEN(S: pl.Expr, A, B) -> pl.Expr:    
        # S 处于 A 和 B 之间 (支持 A > B 或 A < B)
        return ((A < S) & (S < B)) | ((A > S) & (S > B))

    @staticmethod
    def TOPRANGE(S: pl.Expr) -> pl.Expr:            
        # 当前值是近多少周期内的最大值
        def _toprange(s_series: pl.Series) -> pl.Series:
            arr = s_series.to_numpy()
            rt = np.zeros(len(arr), dtype=np.int32)
            for i in range(1, len(arr)):
                # 倒序查找第一个大于等于当前值的索引位置
                idx = np.where(arr[:i] >= arr[i])[0]
                rt[i] = i - idx[-1] - 1 if len(idx) > 0 else i
            return pl.Series(rt)
        return S.map_batches(_toprange)

    @staticmethod
    def LOWRANGE(S: pl.Expr) -> pl.Expr:             
        # 当前值是近多少周期内的最小值
        def _lowrange(s_series: pl.Series) -> pl.Series:
            arr = s_series.to_numpy()
            rt = np.zeros(len(arr), dtype=np.int32)
            for i in range(1, len(arr)):
                # 倒序查找第一个小于等于当前值的索引位置
                idx = np.where(arr[:i] <= arr[i])[0]
                rt[i] = i - idx[-1] - 1 if len(idx) > 0 else i
            return pl.Series(rt)
        return S.map_batches(_lowrange)

COUNT = SignalIndicator.COUNT
EVERY = SignalIndicator.EVERY
EXIST = SignalIndicator.EXIST
FILTER = SignalIndicator.FILTER
BARSLAST = SignalIndicator.BARSLAST
BARSLASTCOUNT = SignalIndicator.BARSLASTCOUNT
BARSSINCEN = SignalIndicator.BARSSINCEN
CROSS = SignalIndicator.CROSS
LONGCROSS = SignalIndicator.LONGCROSS
VALUEWHEN= SignalIndicator.VALUEWHEN
BETWEEN = SignalIndicator.BETWEEN
TOPRANGE = SignalIndicator.TOPRANGE
LOWRANGE = SignalIndicator.LOWRANGE

class TechnicalIndicator():

    @staticmethod
    def MACD(CLOSE, SHORT=12, LONG=26, M=9):
        DIF = EMA(CLOSE, SHORT) - EMA(CLOSE, LONG)  
        DEA = EMA(DIF,M)      
        MACD = (DIF - DEA) * 2
        return RD(DIF), RD(DEA), RD(MACD)

    @staticmethod
    def KDJ(CLOSE, HIGH, LOW, N=9, M1=3, M2=3):        
        RSV = (CLOSE - LLV(LOW, N)) / (HHV(HIGH, N) - LLV(LOW, N)) * 100
        K = EMA(RSV, (M1 * 2 - 1))    
        D = EMA(K, (M2 * 2 - 1))        
        J = K * 3 - D * 2
        return K, D, J

    @staticmethod
    def RSI(CLOSE, N=24):                         
        DIF = CLOSE - REF(CLOSE, 1) 
        return RD(SMA(MAX(DIF, 0), N) / SMA(ABS(DIF), N) * 100)  

    @staticmethod
    def WR(CLOSE, HIGH, LOW, N=10, N1=6):         
        WR = (HHV(HIGH, N) - CLOSE) / (HHV(HIGH, N) - LLV(LOW, N)) * 100
        WR1 = (HHV(HIGH, N1) - CLOSE) / (HHV(HIGH, N1) - LLV(LOW, N1)) * 100
        return RD(WR), RD(WR1)

    @staticmethod
    def BIAS(CLOSE, L1=6, L2=12, L3=24):         
        BIAS1 = (CLOSE - MA(CLOSE, L1)) / MA(CLOSE, L1) * 100
        BIAS2 = (CLOSE - MA(CLOSE, L2)) / MA(CLOSE, L2) * 100
        BIAS3 = (CLOSE - MA(CLOSE, L3)) / MA(CLOSE, L3) * 100
        return RD(BIAS1), RD(BIAS2), RD(BIAS3)

    @staticmethod
    def BOLL(CLOSE, N=20, P=2):                     
        MID = MA(CLOSE, N) 
        UPPER = MID + STD(CLOSE, N) * P
        LOWER = MID - STD(CLOSE, N) * P
        return RD(UPPER), RD(MID), RD(LOWER)    

    @staticmethod
    def PSY(CLOSE, N=12, M=6):  
        PSY = COUNT(CLOSE > REF(CLOSE, 1), N) / N * 100
        PSYMA = MA(PSY, M)
        return RD(PSY), RD(PSYMA)

    @staticmethod
    def CCI(CLOSE, HIGH, LOW, N=14):  
        TP = (HIGH + LOW + CLOSE) / 3
        return (TP - MA(TP, N)) / (0.015 * AVEDEV(TP, N))

    @staticmethod            
    def ATR(CLOSE, HIGH, LOW, N=20):                   
        TR = MAX(MAX((HIGH - LOW), ABS(REF(CLOSE, 1) - HIGH)), ABS(REF(CLOSE, 1) - LOW))
        return MA(TR, N)

    @staticmethod
    def BBI(CLOSE, M1=3, M2=6, M3=12, M4=20):            
        return (MA(CLOSE, M1) + MA(CLOSE, M2) + MA(CLOSE, M3) + MA(CLOSE, M4)) / 4    

    @staticmethod
    def DMI(CLOSE, HIGH, LOW, M1=14, M2=6):               
        TR = SUM(MAX(MAX(HIGH - LOW, ABS(HIGH - REF(CLOSE, 1))), ABS(LOW - REF(CLOSE, 1))), M1)
        HD = HIGH - REF(HIGH, 1)     
        LD = REF(LOW, 1) - LOW
        DMP = SUM(IF((HD > 0) & (HD > LD), HD, 0), M1)
        DMM = SUM(IF((LD > 0) & (LD > HD), LD, 0), M1)
        PDI = DMP * 100 / TR         
        MDI = DMM * 100 / TR
        ADX = MA(ABS(MDI - PDI) / (PDI + MDI) * 100, M2)
        ADXR = (ADX + REF(ADX, M2)) / 2
        return PDI, MDI, ADX, ADXR  

    @staticmethod
    def TAQ(HIGH, LOW, N):                               
        UP = HHV(HIGH, N)    
        DOWN = LLV(LOW, N)    
        MID = (UP + DOWN) / 2
        return UP, MID, DOWN

    @staticmethod
    def KTN(CLOSE, HIGH, LOW, N=20, M=10):               
        MID = EMA((HIGH + LOW + CLOSE) / 3, N)
        ATRN = TechnicalIndicator.ATR(CLOSE, HIGH, LOW, M)
        UPPER = MID + 2 * ATRN   
        LOWER = MID - 2 * ATRN
        return UPPER, MID, LOWER       
    
    @staticmethod
    def TRIX(CLOSE, M1=12, M2=20):                    
        TR = EMA(EMA(EMA(CLOSE, M1), M1), M1)
        TRIX = (TR - REF(TR, 1)) / REF(TR, 1) * 100
        TRMA = MA(TRIX, M2)
        return TRIX, TRMA

    @staticmethod
    def VR(CLOSE, VOL, M1=26):                         
        LC = REF(CLOSE, 1)
        return SUM(IF(CLOSE > LC, VOL, 0), M1) / SUM(IF(CLOSE <= LC, VOL, 0), M1) * 100
    
    @staticmethod
    def CR(CLOSE, HIGH, LOW, N=20):                        
        MID = REF(HIGH + LOW + CLOSE,1) / 3
        return SUM(MAX(0, HIGH - MID), N) / SUM(MAX(0, MID - LOW), N) * 100  

    @staticmethod
    def EMV(HIGH, LOW, VOL, N=14, M=9):                   
        VOLUME = MA(VOL, N) / VOL       
        MID = 100 * (HIGH + LOW - REF(HIGH + LOW, 1)) / (HIGH + LOW)
        EMV = MA(MID * VOLUME * (HIGH - LOW) / MA(HIGH - LOW, N), N)    
        MAEMV = MA(EMV, M)
        return EMV, MAEMV

    @staticmethod
    def DPO(CLOSE, M1=20, M2=10, M3=6):                 
        DPO = CLOSE - REF(MA(CLOSE, M1), M2)    
        MADPO = MA(DPO, M3)
        return DPO, MADPO

    @staticmethod
    def BRAR(OPEN, CLOSE, HIGH, LOW, M1=26):                
        AR = SUM(HIGH - OPEN, M1) / SUM(OPEN - LOW, M1) * 100
        BR = SUM(MAX(0, HIGH - REF(CLOSE, 1)), M1) / SUM(MAX(0, REF(CLOSE, 1) - LOW), M1) * 100
        return AR, BR

    @staticmethod
    def DFMA(CLOSE, N1=10, N2=50, M=10):                  
        DIF=MA(CLOSE, N1) - MA(CLOSE, N2) 
        DIFMA = MA(DIF, M)   
        return DIF, DIFMA

    @staticmethod
    def MTM(CLOSE, N=12, M=6):                             
        MTM = CLOSE - REF(CLOSE, N)         
        MTMMA = MA(MTM, M)
        return MTM, MTMMA

    @staticmethod
    def MASS(HIGH, LOW, N1=9, N2=25, M=6):                  
        MASS=SUM(MA(HIGH - LOW, N1) / MA(MA(HIGH - LOW, N1), N1), N2)
        MA_MASS=MA(MASS, M)
        return MASS, MA_MASS
    
    @staticmethod
    def ROC(CLOSE, N=12, M=6):                            
        ROC = 100 * (CLOSE - REF(CLOSE, N)) / REF(CLOSE, N)    
        MAROC = MA(ROC, M)
        return ROC, MAROC  

    @staticmethod
    def EXPMA(CLOSE, N1=12, N2=50):                        
        return EMA(CLOSE, N1), EMA(CLOSE, N2)

    @staticmethod
    def OBV(CLOSE, VOL):                                  
        return SUM(IF(CLOSE > REF(CLOSE, 1), VOL, IF(CLOSE < REF(CLOSE, 1), -VOL, 0)), 0) / 10000

    @staticmethod
    def MFI(CLOSE, HIGH, LOW, VOL, N=14):                    
        TYP = (HIGH + LOW + CLOSE) / 3
        V1=SUM(IF(TYP > REF(TYP, 1), TYP * VOL, 0), N) / SUM(IF(TYP < REF(TYP, 1), TYP * VOL, 0), N)  
        return 100 - (100 / (1 + V1))     
    
    @staticmethod
    def ASI(OPEN, CLOSE, HIGH, LOW, M1=26, M2=10):           
        LC = REF(CLOSE, 1)      
        AA = ABS(HIGH - LC)     
        BB = ABS(LOW - LC)
        CC = ABS(HIGH - REF(LOW, 1))
        DD = ABS(LC - REF(OPEN, 1))
        R = IF((AA > BB) & (AA > CC), AA + BB / 2 + DD / 4, IF((BB > CC) & (BB > AA), BB + AA / 2 + DD / 4, CC + DD / 4))
        X = (CLOSE - LC + (CLOSE - OPEN) / 2 + LC - REF(OPEN, 1))
        SI = 16 * X / R * MAX(AA, BB)
        ASI = SUM(SI, M1)
        ASIT = MA(ASI, M2)
        return ASI, ASIT   

    @staticmethod
    def XSII(CLOSE, HIGH, LOW, N=102, M=7):             
        AA  = MA((2 * CLOSE + HIGH + LOW) / 4, 5)          
        TD1 = AA * N / 100   
        TD2 = AA * (200 - N) / 100
        CC = ABS((2 * CLOSE + HIGH + LOW) / 4 - MA(CLOSE, 20))/MA(CLOSE, 20)
        DD = DMA(CLOSE, CC)    
        TD3 = (1 + M / 100 ) * DD      
        TD4 = (1 - M / 100) * DD
        return TD1, TD2, TD3, TD4  

MACD = TechnicalIndicator.MACD
KDJ = TechnicalIndicator.KDJ
RSI = TechnicalIndicator.RSI
WR = TechnicalIndicator.WR
BIAS = TechnicalIndicator.BIAS
BOLL = TechnicalIndicator.BOLL
PSY = TechnicalIndicator.PSY
CCI = TechnicalIndicator.CCI
ATR = TechnicalIndicator.ATR
BBI = TechnicalIndicator.BBI
DMI = TechnicalIndicator.DMI
TAQ = TechnicalIndicator.TAQ
KTN = TechnicalIndicator.KTN
TRIX = TechnicalIndicator.TRIX
VR = TechnicalIndicator.VR
CR = TechnicalIndicator.CR
EMV = TechnicalIndicator.EMV
DPO = TechnicalIndicator.DPO
BRAR = TechnicalIndicator.BRAR
DFMA = TechnicalIndicator.DFMA
MTM = TechnicalIndicator.MTM
MASS = TechnicalIndicator.MASS
ROC = TechnicalIndicator.ROC
EXPMA = TechnicalIndicator.EXPMA
OBV = TechnicalIndicator.OBV
MFI = TechnicalIndicator.MFI
ASI = TechnicalIndicator.ASI
XSII = TechnicalIndicator.XSII

class CustomIndicator():
    
    @staticmethod
    def W_JX(OPEN, HIGH, LOW, CLOSE):
        AA = SMA(CLOSE, 2, 1)
        BB = SMA(LOW, 5, 2)
        JXB = (AA - BB <= 0.003) & (REF(CLOSE, 1) > 0)
        JXT = SMA(OPEN, 2, 1) > SMA(HIGH, 21, 2) * 1.05
        return JXB, JXT

    @staticmethod
    def W_TD(OPEN, HIGH, LOW, CLOSE):
        VAR3 = MA(CLOSE, 5) * 1.01
        VAR4 = MA(OPEN, 8) * 1.01
        VAR5 = (MA(HIGH, 5) + MA(LOW, 5) + MA(CLOSE, 5) + MA(OPEN, 5) + \
                MA(HIGH, 3) + MA(LOW, 3) + MA(CLOSE, 3) + MA(OPEN, 3) + \
                MA(HIGH, 2) + MA(LOW, 2) + MA(CLOSE, 2) + MA(OPEN, 2) + \
                HIGH + LOW + CLOSE + OPEN) / 16
        VAR6 = IF(VAR4 > VAR5, VAR4, VAR5)
        VAR7 = IF(VAR4 < VAR5, VAR4, VAR5)
        VAR8 = 3 / 100
        TDT1 = VAR5 > MA(VAR6, 5) * (1 + VAR8)
        TDT2 = VAR3 > MA(VAR6, 5) * (1 + VAR8)
        TDB = (
            (VAR5 - MA(VAR7, 5) * (1 - VAR8) < 0.038) & \
            (CLOSE / REF(CLOSE, 1) > 0.903) & \
            ((CLOSE / REF(CLOSE, 1) > 0.952) | (CLOSE / REF(CLOSE, 1) < 0.948))
            ) > 0
        return TDB, TDT1, TDT2
    
    @staticmethod
    def W_GL(CLOSE):
        BIAS60, _, _ = BIAS(CLOSE, 60, 120, 250)
        GLT = BIAS60 > 30
        GLB = BIAS60 < -20
        GLGT = BIAS60 > 50
        GLGB = BIAS60 < -30
        return GLB, GLGB, GLT, GLGT

    @staticmethod
    def calculate_nmm(CLOSE, period=40):
        weights = 100000 / np.sqrt(np.arange(1, period + 1))
        sum_weights = weights.sum()
        
        # 1. 先 log，再 shift，最后【统一填充 0】确保绝对没有 Null
        # 注意：顺序很重要，必须在 rolling_sum 之前确保数据全为数值
        log_p_shifted = CLOSE.log().shift(1).fill_null(0)
        log_p_current = CLOSE.log().fill_null(0)
        
        # 2. 计算
        weighted_sum = log_p_shifted.rolling_sum(
            window_size=period,
            weights=weights[::-1].copy(),
            center=False
        ).fill_null(0) 

        nmm = (log_p_current * sum_weights - weighted_sum) / period
        NMMB = nmm < -3000
        NMMT = nmm > 3000
        return nmm, NMMB, NMMT

    @staticmethod
    def calculate_nmr(CLOSE: pl.Expr, period=100):
        # 1. 预计算权重
        j = np.arange(1, period + 1)
        weights = 1000 * (np.sqrt(j) - np.sqrt(j - 1))
        sum_weights = weights.sum()
        
        # 2. 预处理数据：计算 log 并处理 null
        # 先 log 再 shift，最后用 .fill_null(0) 兜底，确保没有空值进入 rolling_sum
        log_p_current = CLOSE.log().fill_null(0)
        log_p_shifted = CLOSE.log().shift(1).fill_null(0)
        
        # 3. 带权重的滑动窗口计算
        weighted_sum = log_p_shifted.rolling_sum(
            window_size=period,
            weights=weights[::-1].copy(), # 逆序匹配 Polars 窗口顺序 [旧 -> 新]
            center=False
        ).fill_null(0) # 填充滑动窗口初期产生的空值
        
        # 4. 组合公式：log(P_i) * sum(w) - sum(log(P_{i-j}) * w_j)
        return (log_p_current * sum_weights - weighted_sum)

W_JX = CustomIndicator.W_JX
W_TD = CustomIndicator.W_TD
W_GL = CustomIndicator.W_GL
NMM = CustomIndicator.calculate_nmm
NMR = CustomIndicator.calculate_nmr

class AdjustIndicator():

    @staticmethod
    def calculate_forward_factors_from_dividends(df_price: pl.DataFrame, df_factors: pl.DataFrame) -> pl.DataFrame:
        # 基础检查：若输入为空，直接返回全 1.0 的因子表
        if df_price.is_empty():
            return pl.DataFrame({"trade_date": [], "forward_factor": []}, schema={"trade_date": df_price.schema["trade_date"], "forward_factor": pl.Float64})
        if df_factors.is_empty():
            return df_price.select(["trade_date"]).with_columns(pl.lit(1.0).alias("forward_factor"))

        # ===================== 步骤 1：处理价格序列与前一日收盘价 =====================
        # 强制按日期升序，并利用 shift(1) 向量化获取前一日收盘价
        price_sorted = df_price.sort("trade_date").select([
            pl.col("trade_date"),
            pl.col("close"),
            pl.col("close").shift(1).alias("prev_close")
        ])

        # ===================== 步骤 2：单位换算与除权表清洗 =====================
        factors_cleaned = (
            df_factors
            .filter(pl.col("trade_date").is_in(price_sorted["trade_date"])) # 取交集
            .select([
                pl.col("trade_date"),
                (pl.col("dividend") / 10.0).alias("D"),
                (pl.col("bonus_ratio") / 10.0).alias("BR"),
                (pl.col("rights_ratio") / 10.0).alias("RR"),
                pl.col("rights_price").alias("RP")
            ])
        )

        if factors_cleaned.is_empty():
            return df_price.select(["trade_date"]).with_columns(pl.lit(1.0).alias("forward_factor"))

        # ===================== 步骤 3：连接数据并计算单次调整系数 =====================
        # 将清洗后的分红数据右连接到对齐的价格序列上
        calc_df = (
            factors_cleaned
            .join(price_sorted, on="trade_date", how="right")
            .sort("trade_date") # 确保连接后时序依然升序
        )

        # ===================== 步骤 4 & 5：核心除权价公式过滤与向量化计算 =====================
        calc_df = calc_df.with_columns([
            pl.when(
                pl.col("prev_close").is_not_null() & (pl.col("prev_close") > 0) & pl.col("D").is_not_null()
            )
            .then(
                # ✅ 通达信官方标准除权价 / 前收盘价 = 调整系数
                ((pl.col("prev_close") - pl.col("D") + pl.col("RR") * pl.col("RP")) / 
                (1.0 + pl.col("BR") + pl.col("RR")).clip(lower_bound=1.0)) / pl.col("prev_close")
            )
            .otherwise(1.0)
            .alias("adjust_ratio")
        ])

        # ===================== 步骤 6：前复权因子生成 - 反向累乘 =====================
        # 原理：前复权影响的是除权日【之前】的所有历史价格。
        # 1. shift(-1) 将当天的除权系数作用到历史节点
        # 2. 从未来向历史反向累乘（在 Polars 中通过对倒序序列进行 cum_prod，再倒序还原实现）
        result_df = calc_df.with_columns(
            pl.col("adjust_ratio")
            .shift(-1)
            .fill_null(1.0)
            .reverse()
            .cum_prod()
            .reverse()
            .alias("forward_factor")
        ).select(["trade_date", "forward_factor"])

        # ===================== 最终步骤：恢复用户传入的原始 df_price 顺序 =====================
        return df_price.select(["trade_date"]).join(result_df, on="trade_date", how="left")

calculate_forward_factors_from_dividends = AdjustIndicator.calculate_forward_factors_from_dividends