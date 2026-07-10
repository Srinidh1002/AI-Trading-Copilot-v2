import streamlit as st


def top_layout():

    left, right = st.columns([3, 1])

    return left, right


def bottom_layout():

    left, right = st.columns(2)

    return left, right