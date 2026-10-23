# Installed indicator and function catalogue

TA-Lib Python wrapper 0.6.8: **158 functions**. Includes indicators, candlestick patterns and mathematical utilities. Generated from installed function metadata; this is the implemented catalogue, not every proprietary indicator in existence.

Use Market analysis > Indicator library in the app. Parameters are editable. Warm-up and invalid numeric-domain values remain missing. A candlestick code is not a probability. BETA/CORREL compare explicitly selected OHLCV columns; an index comparison requires separately aligned benchmark data. MAVP currently accepts an explicitly constant period schedule.

The expanded lab uses the compiled TA-Lib backend. The existing C++ evidence/backtest engine has its own documented initialization conventions. This lab does not change those strategy rules.

Upstream: [TA-Lib Python](https://github.com/TA-Lib/ta-lib-python), [TA-Lib function documentation](https://ta-lib.org/functions/).

## Cycle Indicators (5)

| Function | Description | Default parameters |
| --- | --- | --- |
| HT_DCPERIOD | Hilbert Transform - Dominant Cycle Period | None |
| HT_DCPHASE | Hilbert Transform - Dominant Cycle Phase | None |
| HT_PHASOR | Hilbert Transform - Phasor Components | None |
| HT_SINE | Hilbert Transform - SineWave | None |
| HT_TRENDMODE | Hilbert Transform - Trend vs Cycle Mode | None |

## Math Operators (11)

| Function | Description | Default parameters |
| --- | --- | --- |
| ADD | Vector Arithmetic Add | None |
| DIV | Vector Arithmetic Div | None |
| MAX | Highest value over a specified period | timeperiod=30 |
| MAXINDEX | Index of highest value over a specified period | timeperiod=30 |
| MIN | Lowest value over a specified period | timeperiod=30 |
| MININDEX | Index of lowest value over a specified period | timeperiod=30 |
| MINMAX | Lowest and highest values over a specified period | timeperiod=30 |
| MINMAXINDEX | Indexes of lowest and highest values over a specified period | timeperiod=30 |
| MULT | Vector Arithmetic Mult | None |
| SUB | Vector Arithmetic Subtraction | None |
| SUM | Summation | timeperiod=30 |

## Math Transform (15)

| Function | Description | Default parameters |
| --- | --- | --- |
| ACOS | Vector Trigonometric ACos | None |
| ASIN | Vector Trigonometric ASin | None |
| ATAN | Vector Trigonometric ATan | None |
| CEIL | Vector Ceil | None |
| COS | Vector Trigonometric Cos | None |
| COSH | Vector Trigonometric Cosh | None |
| EXP | Vector Arithmetic Exp | None |
| FLOOR | Vector Floor | None |
| LN | Vector Log Natural | None |
| LOG10 | Vector Log10 | None |
| SIN | Vector Trigonometric Sin | None |
| SINH | Vector Trigonometric Sinh | None |
| SQRT | Vector Square Root | None |
| TAN | Vector Trigonometric Tan | None |
| TANH | Vector Trigonometric Tanh | None |

## Momentum Indicators (30)

| Function | Description | Default parameters |
| --- | --- | --- |
| ADX | Average Directional Movement Index | timeperiod=14 |
| ADXR | Average Directional Movement Index Rating | timeperiod=14 |
| APO | Absolute Price Oscillator | fastperiod=12, slowperiod=26, matype=0 |
| AROON | Aroon | timeperiod=14 |
| AROONOSC | Aroon Oscillator | timeperiod=14 |
| BOP | Balance Of Power | None |
| CCI | Commodity Channel Index | timeperiod=14 |
| CMO | Chande Momentum Oscillator | timeperiod=14 |
| DX | Directional Movement Index | timeperiod=14 |
| MACD | Moving Average Convergence/Divergence | fastperiod=12, slowperiod=26, signalperiod=9 |
| MACDEXT | MACD with controllable MA type | fastperiod=12, fastmatype=0, slowperiod=26, slowmatype=0, signalperiod=9, signalmatype=0 |
| MACDFIX | Moving Average Convergence/Divergence Fix 12/26 | signalperiod=9 |
| MFI | Money Flow Index | timeperiod=14 |
| MINUS_DI | Minus Directional Indicator | timeperiod=14 |
| MINUS_DM | Minus Directional Movement | timeperiod=14 |
| MOM | Momentum | timeperiod=10 |
| PLUS_DI | Plus Directional Indicator | timeperiod=14 |
| PLUS_DM | Plus Directional Movement | timeperiod=14 |
| PPO | Percentage Price Oscillator | fastperiod=12, slowperiod=26, matype=0 |
| ROC | Rate of change : ((price/prevPrice)-1)*100 | timeperiod=10 |
| ROCP | Rate of change Percentage: (price-prevPrice)/prevPrice | timeperiod=10 |
| ROCR | Rate of change ratio: (price/prevPrice) | timeperiod=10 |
| ROCR100 | Rate of change ratio 100 scale: (price/prevPrice)*100 | timeperiod=10 |
| RSI | Relative Strength Index | timeperiod=14 |
| STOCH | Stochastic | fastk_period=5, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0 |
| STOCHF | Stochastic Fast | fastk_period=5, fastd_period=3, fastd_matype=0 |
| STOCHRSI | Stochastic Relative Strength Index | timeperiod=14, fastk_period=5, fastd_period=3, fastd_matype=0 |
| TRIX | 1-day Rate-Of-Change (ROC) of a Triple Smooth EMA | timeperiod=30 |
| ULTOSC | Ultimate Oscillator | timeperiod1=7, timeperiod2=14, timeperiod3=28 |
| WILLR | Williams' %R | timeperiod=14 |

## Overlap Studies (17)

| Function | Description | Default parameters |
| --- | --- | --- |
| BBANDS | Bollinger Bands | timeperiod=5, nbdevup=2.0, nbdevdn=2.0, matype=0 |
| DEMA | Double Exponential Moving Average | timeperiod=30 |
| EMA | Exponential Moving Average | timeperiod=30 |
| HT_TRENDLINE | Hilbert Transform - Instantaneous Trendline | None |
| KAMA | Kaufman Adaptive Moving Average | timeperiod=30 |
| MA | Moving average | timeperiod=30, matype=0 |
| MAMA | MESA Adaptive Moving Average | fastlimit=0.5, slowlimit=0.05 |
| MAVP | Moving average with variable period | minperiod=2, maxperiod=30, matype=0 |
| MIDPOINT | MidPoint over period | timeperiod=14 |
| MIDPRICE | Midpoint Price over period | timeperiod=14 |
| SAR | Parabolic SAR | acceleration=0.02, maximum=0.2 |
| SAREXT | Parabolic SAR - Extended | startvalue=0.0, offsetonreverse=0.0, accelerationinitlong=0.02, accelerationlong=0.02, accelerationmaxlong=0.2, accelerationinitshort=0.02, accelerationshort=0.02, accelerationmaxshort=0.2 |
| SMA | Simple Moving Average | timeperiod=30 |
| T3 | Triple Exponential Moving Average (T3) | timeperiod=5, vfactor=0.7 |
| TEMA | Triple Exponential Moving Average | timeperiod=30 |
| TRIMA | Triangular Moving Average | timeperiod=30 |
| WMA | Weighted Moving Average | timeperiod=30 |

## Pattern Recognition (61)

| Function | Description | Default parameters |
| --- | --- | --- |
| CDL2CROWS | Two Crows | None |
| CDL3BLACKCROWS | Three Black Crows | None |
| CDL3INSIDE | Three Inside Up/Down | None |
| CDL3LINESTRIKE | Three-Line Strike  | None |
| CDL3OUTSIDE | Three Outside Up/Down | None |
| CDL3STARSINSOUTH | Three Stars In The South | None |
| CDL3WHITESOLDIERS | Three Advancing White Soldiers | None |
| CDLABANDONEDBABY | Abandoned Baby | penetration=0.3 |
| CDLADVANCEBLOCK | Advance Block | None |
| CDLBELTHOLD | Belt-hold | None |
| CDLBREAKAWAY | Breakaway | None |
| CDLCLOSINGMARUBOZU | Closing Marubozu | None |
| CDLCONCEALBABYSWALL | Concealing Baby Swallow | None |
| CDLCOUNTERATTACK | Counterattack | None |
| CDLDARKCLOUDCOVER | Dark Cloud Cover | penetration=0.5 |
| CDLDOJI | Doji | None |
| CDLDOJISTAR | Doji Star | None |
| CDLDRAGONFLYDOJI | Dragonfly Doji | None |
| CDLENGULFING | Engulfing Pattern | None |
| CDLEVENINGDOJISTAR | Evening Doji Star | penetration=0.3 |
| CDLEVENINGSTAR | Evening Star | penetration=0.3 |
| CDLGAPSIDESIDEWHITE | Up/Down-gap side-by-side white lines | None |
| CDLGRAVESTONEDOJI | Gravestone Doji | None |
| CDLHAMMER | Hammer | None |
| CDLHANGINGMAN | Hanging Man | None |
| CDLHARAMI | Harami Pattern | None |
| CDLHARAMICROSS | Harami Cross Pattern | None |
| CDLHIGHWAVE | High-Wave Candle | None |
| CDLHIKKAKE | Hikkake Pattern | None |
| CDLHIKKAKEMOD | Modified Hikkake Pattern | None |
| CDLHOMINGPIGEON | Homing Pigeon | None |
| CDLIDENTICAL3CROWS | Identical Three Crows | None |
| CDLINNECK | In-Neck Pattern | None |
| CDLINVERTEDHAMMER | Inverted Hammer | None |
| CDLKICKING | Kicking | None |
| CDLKICKINGBYLENGTH | Kicking - bull/bear determined by the longer marubozu | None |
| CDLLADDERBOTTOM | Ladder Bottom | None |
| CDLLONGLEGGEDDOJI | Long Legged Doji | None |
| CDLLONGLINE | Long Line Candle | None |
| CDLMARUBOZU | Marubozu | None |
| CDLMATCHINGLOW | Matching Low | None |
| CDLMATHOLD | Mat Hold | penetration=0.5 |
| CDLMORNINGDOJISTAR | Morning Doji Star | penetration=0.3 |
| CDLMORNINGSTAR | Morning Star | penetration=0.3 |
| CDLONNECK | On-Neck Pattern | None |
| CDLPIERCING | Piercing Pattern | None |
| CDLRICKSHAWMAN | Rickshaw Man | None |
| CDLRISEFALL3METHODS | Rising/Falling Three Methods | None |
| CDLSEPARATINGLINES | Separating Lines | None |
| CDLSHOOTINGSTAR | Shooting Star | None |
| CDLSHORTLINE | Short Line Candle | None |
| CDLSPINNINGTOP | Spinning Top | None |
| CDLSTALLEDPATTERN | Stalled Pattern | None |
| CDLSTICKSANDWICH | Stick Sandwich | None |
| CDLTAKURI | Takuri (Dragonfly Doji with very long lower shadow) | None |
| CDLTASUKIGAP | Tasuki Gap | None |
| CDLTHRUSTING | Thrusting Pattern | None |
| CDLTRISTAR | Tristar Pattern | None |
| CDLUNIQUE3RIVER | Unique 3 River | None |
| CDLUPSIDEGAP2CROWS | Upside Gap Two Crows | None |
| CDLXSIDEGAP3METHODS | Upside/Downside Gap Three Methods | None |

## Price Transform (4)

| Function | Description | Default parameters |
| --- | --- | --- |
| AVGPRICE | Average Price | None |
| MEDPRICE | Median Price | None |
| TYPPRICE | Typical Price | None |
| WCLPRICE | Weighted Close Price | None |

## Statistic Functions (9)

| Function | Description | Default parameters |
| --- | --- | --- |
| BETA | Beta | timeperiod=5 |
| CORREL | Pearson's Correlation Coefficient (r) | timeperiod=30 |
| LINEARREG | Linear Regression | timeperiod=14 |
| LINEARREG_ANGLE | Linear Regression Angle | timeperiod=14 |
| LINEARREG_INTERCEPT | Linear Regression Intercept | timeperiod=14 |
| LINEARREG_SLOPE | Linear Regression Slope | timeperiod=14 |
| STDDEV | Standard Deviation | timeperiod=5, nbdev=1.0 |
| TSF | Time Series Forecast | timeperiod=14 |
| VAR | Variance | timeperiod=5, nbdev=1.0 |

## Volatility Indicators (3)

| Function | Description | Default parameters |
| --- | --- | --- |
| ATR | Average True Range | timeperiod=14 |
| NATR | Normalized Average True Range | timeperiod=14 |
| TRANGE | True Range | None |

## Volume Indicators (3)

| Function | Description | Default parameters |
| --- | --- | --- |
| AD | Chaikin A/D Line | None |
| ADOSC | Chaikin A/D Oscillator | fastperiod=3, slowperiod=10 |
| OBV | On Balance Volume | None |
