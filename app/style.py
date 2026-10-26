"""Small presentation layer for the ivory, forest and brass research desk."""

import streamlit as st


def apply_style() -> None:
    st.html("""
    <style>
    .stMainBlockContainer {max-width: 1450px; padding-top: 4.5rem; padding-bottom: 3rem;}
    h1 {letter-spacing: -.035em; line-height: 1.15;}
    h2, h3 {letter-spacing: -.02em;}
    [data-testid="stMetric"] {background: #FFFCF5; border-color: #DED7C8; padding: 1rem;}
    [data-testid="stMetricLabel"] {font-size: .8rem; color: #607065;}
    [data-testid="stMetricValue"] {font-size: clamp(1.25rem, 2.2vw, 1.9rem);}
    [data-testid="stForm"] {background: #FBF8F1; border-color: #D9D2C3;}
    [data-testid="stSidebar"] h1 {font-size: 2rem;}
    [data-testid="stSidebar"] hr {border-color: #496153;}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap: .55rem;}
    [data-testid="stSegmentedControl"] button {font-size: .85rem; padding: .4rem .7rem;}
    [data-testid="stDataFrame"] {border: 1px solid #DED7C8; border-radius: 5px;}
    @media (max-width: 800px) {
      .stMainBlockContainer {padding: 4.5rem 1rem 2rem;}
      h1 {font-size: 2rem !important;}
      [data-testid="stMetric"] {padding: .7rem;}
      [data-testid="stSegmentedControl"] button {padding: .35rem .5rem;}
      .st-key-overview_metrics [data-testid="stHorizontalBlock"] {display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .6rem;}
      .st-key-overview_metrics [data-testid="stColumn"] {width: 100% !important; min-width: 0 !important;}
      .st-key-overview_actions [data-testid="stHorizontalBlock"] {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .6rem;}
      .st-key-overview_actions [data-testid="stColumn"] {width: 100% !important; min-width: 0 !important;}
      :is(.st-key-backtest_metrics, .st-key-risk_metrics, .st-key-scenario_metrics)
        [data-testid="stHorizontalBlock"] {display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .6rem;}
      :is(.st-key-backtest_metrics, .st-key-risk_metrics, .st-key-scenario_metrics)
        [data-testid="stColumn"] {width: 100% !important; min-width: 0 !important;}
    }
    </style>
    """)
