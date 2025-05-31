import gspread														# -*- coding: utf-8 -*-import gspread
import pandas as pd
import duckdb
import streamlit as st
import plotly.express as px
import smtplib
import plotly.graph_objects as go
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from oauth2client.service_account import ServiceAccountCredentials
import json
from pathlib import Path
import numpy as np
from plotly.subplots import make_subplots
import re
from collections import defaultdict

# Step 1: Authenticate with Google Sheets API
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(st.secrets["GOOGLE_CREDENTIALS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Step 2: Open the spreadsheet by URL
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1apkZJsJHEd1HfDoHBAx9cPM-BmJxjIRiagB_F5KehHo/edit"
DASHBOARD_URL = "https://facebook-insights-dashboard-elxpadltekfwuqpbur66q2.streamlit.app/"
TAB_NAME = "Facebook: Post Insights"

try:
    spreadsheet = client.open_by_url(SPREADSHEET_URL)
    worksheet = spreadsheet.worksheet(TAB_NAME)
except Exception as e:
    st.error(f"\u274c Failed to open Google Sheet or tab.\n\nError:\n{e}")
    st.stop()

# # Step 3: Load data into a DataFrame while dropping duplicate headers entirely
# try:
#     raw_headers = worksheet.row_values(2)
#     seen = set()
#     filtered_headers = []
#     for col in raw_headers:
#         if col not in seen:
#             seen.add(col)
#             filtered_headers.append(col)

#     data = worksheet.get_all_records(head=2, expected_headers=filtered_headers)
#     df = pd.DataFrame(data)

#     df.columns = pd.Index(filtered_headers).str.strip().str.replace(' ', '_').str.replace('.', '_')
#     df['Created_Time'] = pd.to_datetime(df['Created_Time'])

# except Exception as e:
#     st.error(f"\u274c Failed to load or process worksheet data.\n\nError:\n{e}")
#     st.stop()

raw_headers = worksheet.row_values(2)
data_rows = worksheet.get_all_values()[2:]  # Skip first two rows (headers)

# Create initial DataFrame
df_raw = pd.DataFrame(data_rows, columns=raw_headers)

# Remove empty rows
df_raw.replace('', pd.NA, inplace=True)
df_raw.dropna(how='all', inplace=True)

# Convert all numeric-looking data to actual numbers
df_raw = df_raw.apply(lambda col: pd.to_numeric(col, errors='ignore'))

# Strip and standardize column names
df_raw.columns = df_raw.columns.str.strip().str.replace(' ', '_').str.replace('.', '_')

# Detect duplicates
col_map = defaultdict(list)
for idx, name in enumerate(df_raw.columns):
    col_map[name].append(idx)

df = pd.DataFrame()  # Final DataFrame

# For each column name, average duplicates or take as-is
for col_name, idx_list in col_map.items():
    if len(idx_list) == 1:
        df[col_name] = df_raw.iloc[:, idx_list[0]]
    else:
        numeric_cols = [pd.to_numeric(df_raw.iloc[:, idx], errors='coerce') for idx in idx_list]
        mean_series = pd.concat(numeric_cols, axis=1).mean(axis=1)
        df[col_name] = np.ceil(mean_series)

# Convert 'Created_Time' safely
df['Created_Time'] = pd.to_datetime(df['Created_Time'], errors='coerce')

# Extract URLs from =HYPERLINK("url", "label") formulas in Google Sheets
def extract_hyperlinks_from_formula_using_api(worksheet, df_index):
    # Use built-in gspread method to get raw formulas
    formulas = worksheet.get(f"A3:A{len(df_index) + 2}", value_render_option='FORMULA')
    
    url_pattern = r'HYPERLINK\("([^"]+)"'

    hyperlinks = []
    for row in formulas:
        if row:
            cell = row[0]
            match = re.search(url_pattern, cell)
            if match:
                hyperlinks.append(match.group(1))
            else:
                hyperlinks.append(None)
        else:
            hyperlinks.append(None)

    # Return Series with matching index
    return pd.Series(hyperlinks, index=df_index)

# Add the hyperlink column to df
df['Hyperlink'] = extract_hyperlinks_from_formula_using_api(worksheet, df.index)


# 🛠️ Debug: Show extracted hyperlinks with corresponding Content
debug_hyperlinks = extract_hyperlinks_from_formula_using_api(worksheet, df.index)

# Show as a table to verify
debug_table = pd.DataFrame({
    "Created_Time": df['Created_Time'],
    "Content": df['Content'],
    "Extracted_Hyperlink": debug_hyperlinks
})

st.subheader("🔍 Debug: Extracted Hyperlink Table")
st.dataframe(debug_table)


# Step 4: Filter last 10 calendar days (including today)
today = pd.Timestamp.now().normalize()
start_date = today - pd.Timedelta(days=9)
end_date = today

weekly_df = df[(df['Created_Time'] >= start_date) & (df['Created_Time'] <= end_date)]

if weekly_df.empty:
    st.warning("⚠️ No data available for the last 10 days.")
    st.stop()

# Step 5: Dashboard title
week_range = f"{start_date.date()} to {end_date.date()}"

st.markdown(f"""
    <div style='text-align: center;'>
        <h2 style='margin-bottom: 0; color: #FFFFFF;'>📊 Facebook Weekly Insights Dashboard</h2>
        <p style='font-size: 17px; color: #AAAAAA; margin-top: 4px;'>Week Range: <strong style='color: #FFFFFF;'>{week_range}</strong></p>
    </div>
""", unsafe_allow_html=True)

# Step 6: KPI Metrics
total_clicks = int(weekly_df['Post_Clicks'].sum())
total_reactions = int(weekly_df['Total_Reactions'].sum())
total_reach = int(weekly_df['Total_Reach'].sum())
total_likes = int(weekly_df['Total_Like_Reactions'].sum())
total_loves = int(weekly_df['Total_Love_Reactions'].sum())
total_impressions = int(weekly_df['Total_Impressions'].sum())

# Step 6: Styled KPI Metrics in dark mode-friendly cards
st.markdown("""
<style>
.kpi-bar {{
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    background: linear-gradient(145deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 20px;
    box-shadow: 0 6px 18px rgba(0,0,0,0.4);
    padding: 40px 20px;
    margin: 25px 0;
    gap: 24px;
}}
.kpi-item {{
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    width: 180px;
    height: 120px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    text-align: center;
    padding: 10px;
    box-shadow: inset 0 0 10px rgba(0,0,0,0.2);
    transition: transform 0.3s ease, box-shadow 0.3s ease;
}}
.kpi-item:hover {{
    transform: scale(1.05);
    box-shadow: 0 8px 20px rgba(0,0,0,0.5);
}}
.kpi-label {{
    font-size: 18px;
    font-weight: 500;
    color: #cccccc;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 160px;
}}
.kpi-value {{
    font-size: 30px;
    font-weight: 700;
    color: #ffffff;
    margin-top: 6px;
}}
@media (max-width: 768px) {{
    .kpi-item {{
        width: 100%;
    }}
}}
</style>

<div class="kpi-bar">
    <div class="kpi-item">
        <div class="kpi-label">🖱️ Total Clicks</div>
        <div class="kpi-value">{clicks}</div>
    </div>
    <div class="kpi-item">
        <div class="kpi-label">👍 Total Reactions</div>
        <div class="kpi-value">{reactions}</div>
    </div>
    <div class="kpi-item">
        <div class="kpi-label">🌍 Total Reach</div>
        <div class="kpi-value">{reach}</div>
    </div>
    <div class="kpi-item">
        <div class="kpi-label">❤️ Love Reactions</div>
        <div class="kpi-value">{loves}</div>
    </div>
    <div class="kpi-item">
        <div class="kpi-label">👍 Like Reactions</div>
        <div class="kpi-value">{likes}</div>
    </div>
    <div class="kpi-item">
        <div class="kpi-label">👁️ Impressions</div>
        <div class="kpi-value">{impressions}</div>
    </div>
</div>
""".format(
    clicks=f"{total_clicks:,}",
    reactions=f"{total_reactions:,}",
    reach=f"{total_reach:,}",
    loves=f"{total_loves:,}",
    likes=f"{total_likes:,}",
    impressions=f"{total_impressions:,}"
), unsafe_allow_html=True)

# Step 7: SQL Summary Table (Daily Summary)
try:
    duckdb.register("weekly_df", weekly_df)
    summary_df = duckdb.query("""
        SELECT
            CAST(Created_Time AS DATE) AS Created_Date,
            SUM(Post_Clicks) AS Total_Clicks,
            SUM(Total_Reactions) AS Total_Reactions,
            SUM(Total_Reach) AS Total_Reach,
            SUM(Total_Like_Reactions) AS Total_Likes,
            SUM(Total_Love_Reactions) AS Total_Loves,
            SUM(Total_Impressions) AS Total_Impressions
        FROM weekly_df
        GROUP BY Created_Date
        ORDER BY Created_Date
    """).to_df()
except Exception as e:
    st.error(f"❌ SQL query failed.\n\nError:\n{e}")
    st.stop()

# Add correct weekday name and index in pandas (timezone-safe and reliable)
summary_df['Day_Name'] = pd.to_datetime(summary_df['Created_Date']).dt.day_name()
summary_df['Day_Of_Week'] = pd.to_datetime(summary_df['Created_Date']).dt.weekday  # 0=Monday, 6=Sunday

# Chart 1: Daily Reaction Types Breakdown
custom_colors = ['#1877F2', '#D81B60']

# Add post content per day to summary_df
weekly_df['Created_Date'] = weekly_df['Created_Time'].dt.date
# Posts that got likes
likes_by_day = (
    weekly_df[weekly_df['Total_Like_Reactions'] > 0]
    .groupby('Created_Date')['Content']
    .apply(lambda x: '<br>'.join(x))
    .reset_index()
    .rename(columns={'Content': 'Like_Posts'})
)
# Posts that got loves
loves_by_day = (
    weekly_df[weekly_df['Total_Love_Reactions'] > 0]
    .groupby('Created_Date')['Content']
    .apply(lambda x: '<br>'.join(x))
    .reset_index()
    .rename(columns={'Content': 'Love_Posts'})
)
summary_df['Created_Date'] = pd.to_datetime(summary_df['Created_Date']).dt.date
summary_df = summary_df.merge(likes_by_day, on='Created_Date', how='left')
summary_df = summary_df.merge(loves_by_day, on='Created_Date', how='left')

st.markdown(
    """
    <div style='text-align: center; padding-top: 20px; padding-bottom: 10px;'>
        <span style='font-size: 20px; font-family: "Segoe UI", sans-serif; font-weight: 600; color: #FFFFFF;'>
            💬 Daily Reaction Type Breakdown
        </span>
    </div>
    """,
    unsafe_allow_html=True
)
# Create bar chart
fig_reactions = px.bar(
    summary_df,
    x='Created_Date',
    y=['Total_Likes', 'Total_Loves'],
    title=' ',
    labels={"value": "Count", "variable": "Reaction Type", "Created_Date": "Date"},
    barmode='group')
    
# Add hover data
fig_reactions.data[0].customdata = summary_df[['Like_Posts']].values  # For Total_Likes
fig_reactions.data[0].hovertemplate = '%{x}<br><b>Total_Likes:</b> %{y}<br><b>Liked Posts:</b><br>%{customdata[0]}<extra></extra>'

fig_reactions.data[1].customdata = summary_df[['Love_Posts']].values  # For Total_Loves
fig_reactions.data[1].hovertemplate = '%{x}<br><b>Total_Loves:</b> %{y}<br><b>Loved Posts:</b><br>%{customdata[0]}<extra></extra>'

# Assign your custom colors to each trace
fig_reactions.data[0].marker.color = custom_colors[0]  # Total_Likes → #C9184A
fig_reactions.data[1].marker.color = custom_colors[1]  # Total_Loves → #FF758F
# Chart layout styling
fig_reactions.update_layout(
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    title_font=dict(size=22, color='#FFFFFF'),
    font=dict(family="Segoe UI, sans-serif", size=14, color='#CCCCCC'),
    legend_title_text='Reactions',
    xaxis=dict(title='Date', showgrid=False, tickangle=0),
    yaxis=dict(title='Count', gridcolor='rgba(255,255,255,0.05)'),
    legend=dict(orientation='h', yanchor='bottom', y=1.1, xanchor='right', x=1),
    margin=dict(l=60, r=40, t=80, b=60),
    bargap=0.35
)
st.plotly_chart(fig_reactions, use_container_width=True)

# Chart 2: Total Impressions vs Reach (Daily Aggregated with Hover)
# Step 1: Aggregate daily impressions, reach, and combine post content
daily_summary = (
    weekly_df
    .groupby(weekly_df['Created_Time'].dt.date)
    .agg({
        'Total_Impressions': 'sum',
        'Total_Reach': 'sum',
        'Content': lambda x: '<br>'.join(x)
    })
    .reset_index()
    .rename(columns={'Created_Time': 'Date', 'Content': 'Post_Contents'})
)

# Step 2: Add readable date labels (e.g., "May 7, 2025") for x-axis
daily_summary['Date_Label'] = pd.to_datetime(daily_summary['Date']).dt.strftime('%b %d, %Y')
# Step 3: Create figure
fig_impressions = go.Figure()
# Step 4: Invisible trace to show post content in unified hover
fig_impressions.add_trace(go.Scatter(
    x=daily_summary['Date_Label'],
    y=[0.001] * len(daily_summary),
    mode='markers',
    name='',
    text=daily_summary['Post_Contents'],
    hovertemplate='<b>Posts:</b><br>%{text}<extra></extra>',
    marker=dict(size=0.1, opacity=0.001, color='rgba(0,0,0,0)'),
    showlegend=False,
    hoverlabel=dict(namelength=0)
))
# Step 5: Impressions line
fig_impressions.add_trace(go.Scatter(
    x=daily_summary['Date_Label'],
    y=daily_summary['Total_Impressions'],
    mode='lines+markers',
    name='📊 Impressions',
    line=dict(color='#FFB300', width=2),
    marker=dict(size=6),
    hovertemplate='<b>Impressions:</b> %{y}<extra></extra>'
))
# Step 6: Reach line
fig_impressions.add_trace(go.Scatter(
    x=daily_summary['Date_Label'],
    y=daily_summary['Total_Reach'],
    mode='lines+markers',
    name='👥 Reach',
    line=dict(color='#43A047', width=2),
    marker=dict(size=6),
    hovertemplate='<b>Reach:</b> %{y}<extra></extra>'
))

st.markdown(
    """
    <div style='text-align: center; padding-top: 20px; padding-bottom: 10px;'>
        <span style='font-size: 20px; font-family: "Segoe UI", sans-serif; font-weight: 600; color: #FFFFFF;'>
            📈 Total Impressions vs Reach 
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# Step 7: Layout styling
fig_impressions.update_layout(
    title=' ',
    xaxis_title='Date',
    yaxis_title='Count',
    hovermode='x unified',
    title_font=dict(size=20, color='#FFFFFF'),
    font=dict(color='#CCCCCC'),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    margin=dict(l=60, r=40, t=80, b=60),
    legend=dict(orientation='h', yanchor='bottom', y=1.1, xanchor='right', x=1)
)
# Step 8: Show chart in Streamlit
st.plotly_chart(fig_impressions, use_container_width=True)

# Chart 3: Top engaged posts
# Step 1: Create engagement score
weekly_df['Engagement_Score'] = (
    weekly_df['Total_Impressions'] +
    weekly_df['Total_Reach'] +
    weekly_df['Total_Like_Reactions'] +
    weekly_df['Total_Love_Reactions'] +
    weekly_df['Post_Clicks']
)

# Step 2: Sort top 10
top_engaged_posts = weekly_df.sort_values(by='Engagement_Score', ascending=False).head(10).copy()

st.markdown(
    """
    <div style='text-align: center; padding-top: 20px; padding-bottom: 10px;'>
        <span style='font-size: 20px; font-family: "Segoe UI", sans-serif; font-weight: 600; color: #FFFFFF;'>
            🏆 Top 10 Posts by Total Engagement
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# Step 3: Create horizontal bar chart with gradient coloring
fig_bar = px.bar(
    top_engaged_posts.iloc[::-1],  # Reverse so highest is on top
    x='Engagement_Score',
    y='Content',
    orientation='h',
    title=' ',
    color='Engagement_Score',
    color_continuous_scale='Cividis',  # Try 'Inferno', 'Viridis', 'Turbo' too
    labels={'Content': 'Post', 'Engagement_Score': 'Engagement Score'}
)

# Step 4: Dark theme + styling
fig_bar.update_layout(
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    title_font=dict(size=20, color='#FFFFFF'),
    font=dict(color='#CCCCCC', size=13),
    margin=dict(l=100, r=40, t=80, b=60),
    coloraxis_colorbar=dict(title='Engagement')
)

# Step 5: Detailed hover breakdown
fig_bar.update_traces(
    customdata=top_engaged_posts.iloc[::-1][[
        'Total_Impressions',
        'Total_Reach',
        'Total_Like_Reactions',
        'Total_Love_Reactions',
        'Post_Clicks'
    ]],
    hovertemplate=(
        '<b>Post:</b> %{y}<br>'
        '👁 Impressions: %{customdata[0]}<br>'
        '📢 Reach: %{customdata[1]}<br>'
        '👍 Likes: %{customdata[2]}<br>'
        '❤️ Loves: %{customdata[3]}<br>'
        '🖱 Clicks: %{customdata[4]}<br>'
        '<b>Total Score:</b> %{x}<extra></extra>'
    )
)
# Step 6: Show in Streamlit
st.plotly_chart(fig_bar, use_container_width=True)

# -- Conversion Metrics Calculations --
click_through_rate = (total_clicks / total_impressions) * 100 if total_impressions > 0 else 0
conversion_intent_rate = (total_clicks / total_reach) * 100 if total_reach > 0 else 0

emotional_posts = weekly_df[(weekly_df['Total_Like_Reactions'] > 0) | (weekly_df['Total_Love_Reactions'] > 0)]
emotional_impressions = emotional_posts['Total_Impressions'].sum()
emotional_post_count = len(emotional_posts)
eem_score = (emotional_impressions / emotional_post_count) if emotional_post_count > 0 else 0

# -- Title --
st.markdown("""
    <div style='text-align: center; padding-top: 30px; padding-bottom: 10px;'>
        <span style='font-size: 22px; font-weight: 600; color: #FFFFFF;'>
            📈 Conversion & Emotional KPIs
        </span>
    </div>
""", unsafe_allow_html=True)

# -- Custom KPI Card Style --
st.markdown(f"""
<style>
.kpi-row {{
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 20px;
    margin-top: 15px;
    margin-bottom: 30px;
}}
.kpi-box {{
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: 16px;
    width: 250px;
    height: 130px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    padding: 12px;
    box-shadow: inset 0 0 10px rgba(0,0,0,0.25);
}}
.kpi-box:hover {{
    transform: scale(1.05);
    box-shadow: 0 8px 20px rgba(0,0,0,0.5);
}}
.kpi-title {{
    font-size: 16px;
    font-weight: 600;
    color: #cccccc;
    margin-bottom: 4px;
    text-align: center;
    word-break: break-word;
}}
.kpi-value {{
    font-size: 26px;
    font-weight: 700;
    color: #ffffff;
    margin-bottom: 4px;
}}
.kpi-desc {{
    font-size: 12px;
    color: #999999;
    text-align: center;
    max-width: 220px;
    word-break: break-word;
}}
</style>

<div class="kpi-row">
    <div class="kpi-box">
        <div class="kpi-title">🚀 Click-Through Rate</div>
        <div class="kpi-value">{click_through_rate:.2f}%</div>
        <div class="kpi-desc">Percent of impressions that led to a click</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-title">💖 Emotional Engagement</div>
        <div class="kpi-value">{eem_score:,.2f}</div>
        <div class="kpi-desc">Avg impressions on posts with likes/loves</div>
    </div>
    <div class="kpi-box">
        <div class="kpi-title">📩 Conversion Intent Rate</div>
        <div class="kpi-value">{conversion_intent_rate:.2f}%</div>
        <div class="kpi-desc">Percent of reached users who clicked</div>
    </div>
</div>
""", unsafe_allow_html=True)

#Chart 4: Donut Nested Pie chart
st.markdown(
    """
    <div style='text-align: center; padding-top: 20px; padding-bottom: 10px;'>
        <span style='font-size: 20px; font-family: "Segoe UI", sans-serif; font-weight: 600; color: #FFFFFF;'>
            🍩 Nested Donut Chart – True Engagement Breakdown
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# === Data ===
post_clicks = int(weekly_df['Post_Clicks'].sum())
like_reactions = int(weekly_df['Total_Like_Reactions'].sum())
love_reactions = int(weekly_df['Total_Love_Reactions'].sum())
impressions = int(weekly_df['Total_Impressions'].sum())
reach = int(weekly_df['Total_Reach'].sum())

clicks_total = post_clicks
reactions_total = like_reactions + love_reactions
views_total = impressions + reach

# === Labels and colors
# Inner ring: detailed breakdown
inner_labels = ['Post Clicks', 'Like Reactions', 'Love Reactions', 'Impressions', 'Reach']
inner_values = [post_clicks, like_reactions, love_reactions, impressions, reach]
inner_colors = ['#C25F9E', '#1877F2', '#D81B60', '#D4B727', '#40C047']

# Outer ring: summary
outer_labels = ['Clicks', 'Reactions', 'Views']
outer_values = [clicks_total, reactions_total, views_total]
outer_colors = ['#C25F9E', '#EA6C3B', '#1BCABE']

# === Chart build
fig_nested = go.Figure()

# Outer ring (summary)
fig_nested.add_trace(go.Pie(
    labels=outer_labels,
    values=outer_values,
    hole=0.4,
    marker=dict(colors=outer_colors, line=dict(color='#111', width=1)),
    hovertemplate='<b>%{label}</b><br>Total: %{value}<br>Percent: %{percent}<extra></extra>',
    textinfo='none',
    domain={'x': [0, 1], 'y': [0, 1]},
    showlegend=True,
    name='Summary Group'
))

# Inner ring (detailed)
fig_nested.add_trace(go.Pie(
    labels=inner_labels,
    values=inner_values,
    hole=0.7,
    marker=dict(colors=inner_colors, line=dict(color='#111', width=1)),
    hovertemplate='<b>%{label}</b><br>Value: %{value}<br>Percent: %{percent}<extra></extra>',
    textinfo='none',
    domain={'x': [0, 1], 'y': [0, 1]},
    showlegend=True,
    name='Detailed Breakdown'
))

# Layout
fig_nested.update_layout(
    width=750,
    height=500,
    margin=dict(t=60, l=40, r=40, b=60),
    plot_bgcolor='rgba(0,0,0,0)',
    paper_bgcolor='rgba(0,0,0,0)',
    font=dict(color='#E0E0E0', family='Segoe UI'),
    annotations=[
        dict(text='Engagement', x=0.5, y=0.5, font_size=18, showarrow=False, font_color='white')
    ],
    legend=dict(
        orientation='v',
        yanchor='middle',
        y=0.5,
        xanchor='right',
        x=1.1,
        bgcolor='rgba(0,0,0,0)',
        font=dict(size=13)
    )
)
st.plotly_chart(fig_nested, use_container_width=False)

# ✅ Add Day_Name column if not already created
weekly_df['Day_Name'] = weekly_df['Created_Time'].dt.day_name()

# ✅ Calculate Engagement Score if not already calculated
if 'Engagement_Score' not in weekly_df.columns:
    weekly_df['Engagement_Score'] = (
        weekly_df['Total_Impressions'] +
        weekly_df['Total_Reach'] +
        weekly_df['Total_Like_Reactions'] +
        weekly_df['Total_Love_Reactions'] +
        weekly_df['Post_Clicks']
    )

# ✅ Get weekday order based on appearance in data
weekday_order = (
    weekly_df[['Day_Name', 'Created_Time']]
    .drop_duplicates()
    .sort_values('Created_Time')
    .drop_duplicates(subset='Day_Name', keep='first')['Day_Name']
    .tolist()
)

# ✅ Compute average engagement by weekday
avg_engagement_by_day = (
    weekly_df.groupby('Day_Name')['Engagement_Score']
    .mean()
    .reset_index()
)

# ✅ Categorize + Sort weekdays based on appearance order
avg_engagement_by_day['Day_Name'] = pd.Categorical(
    avg_engagement_by_day['Day_Name'], categories=weekday_order, ordered=True
)
avg_engagement_by_day = avg_engagement_by_day.sort_values('Day_Name')

# ✅ Get best day and score
best_row = avg_engagement_by_day.loc[avg_engagement_by_day['Engagement_Score'].idxmax()]
best_day = best_row['Day_Name']
best_score = round(best_row['Engagement_Score'], 2)

# ✅ Display it
st.markdown(f"""
<div style='
    background: linear-gradient(145deg, #1f1f1f, #2c2c2c);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 25px;
    margin-top: 10px;
    text-align: center;
    box-shadow: 0 6px 18px rgba(0,0,0,0.4);
'>
    <span style='font-size: 22px; font-weight: 600; color: #FFFFFF;'>📅 Best Day to Post</span><br>
    <span style='font-size: 28px; font-weight: bold; color: #4CAF50;'>{best_day}</span><br>
    <span style='font-size: 16px; color: #AAAAAA;'>Avg. Engagement Score: {best_score}</span>
</div>
""", unsafe_allow_html=True)

# 🔗 Clickable Post Table – Preserves original look, polished
st.markdown(
    """
    <div style='text-align: center; padding-top: 40px; padding-bottom: 30px;'>
        <span style='font-size: 20px; font-family: "Segoe UI", sans-serif; font-weight: 600; color: #FFFFFF;'>
            🔗 Top Links Clicked Posts
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# Step 1: Select and sort by clicks
link_table = weekly_df[['Created_Time', 'Content', 'Post_Clicks', 'Total_Reactions', 'Hyperlink']].copy()
link_table = link_table.sort_values(by='Post_Clicks', ascending=False)  # <-- this line sorts it

# Step 2: Make links clickable
link_table['Hyperlink'] = link_table['Hyperlink'].apply(
    lambda url: f'<a href="{url}" target="_blank">View Post</a>'
)

# Step 3: Render the table
st.write(link_table.to_html(escape=False, index=False), unsafe_allow_html=True)

# === Timestamp Logic ===
def should_send_email_gsheet(days_interval=4):
    try:
        TIMESTAMP_SHEET_URL = "https://docs.google.com/spreadsheets/d/1PWMPIPELb_wOKZ0Oqmh0YppQPt_pvUjJaXQn9tp4G-o"
        TIMESTAMP_TAB_NAME = "Sheet1"
        timestamp_sheet = client.open_by_url(TIMESTAMP_SHEET_URL).worksheet(TIMESTAMP_TAB_NAME)

        last_sent_str = timestamp_sheet.acell('A1').value
        now = pd.Timestamp.now()

        if last_sent_str:
            last_sent = pd.to_datetime(last_sent_str)
            diff_days = (now - last_sent).days
            if diff_days < days_interval:
                st.info(f"⏱️ Last email was sent {diff_days} days ago.")
                return False

        timestamp_sheet.update_acell('A1', now.isoformat())
        return True

    except Exception as e:
        st.warning(f"⚠️ Error accessing timestamp sheet: {e}")
        return False

# === Email Automation ===
if should_send_email_gsheet():
    try:
        sender_email = st.secrets["GMAIL_USER"]
        password = st.secrets["GMAIL_PASS"]
        receiver_emails = ["priyankadesai1999@gmail.com", "tom.basey@gmail.com"]

        message = MIMEMultipart()
        message["Subject"] = "📊 Facebook Dashboard Link"
        message["From"] = sender_email
        message["To"] = ", ".join(receiver_emails)

        body = f"""
        Hello,

        Your Facebook Insights Dashboard is ready.

        🔗 View Dashboard: {DASHBOARD_URL}

        Best,
        Insights Bot
        """
        message.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_emails, message.as_string())

        st.success("📧 Email with dashboard link sent successfully!")

    except Exception as e:
        st.error(f"❌ Failed to send email.\n\nError:\n{e}")
else:
    st.info("✅ No email sent today. It's not time yet.") 
