# -*- coding: utf-8 -*-
import gspread
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
    st.error(f"❌ Failed to open Google Sheet or tab.\n\nError:\n{e}")
    st.stop()

# Step 3: Load data into a DataFrame
try:
    data = worksheet.get_all_records(head=2)
    df = pd.DataFrame(data)
    df.columns = df.columns.str.strip().str.replace(' ', '_')
    df['Created_Time'] = pd.to_datetime(df['Created_Time'])
except Exception as e:
    st.error(f"❌ Failed to load or process worksheet data.\n\nError:\n{e}")
    st.stop()

# Step 4: Filter last 10 calendar days (including today)
today = pd.Timestamp.now().normalize()
start_date = today - pd.Timedelta(days=9)  # Includes today as the 10th day
end_date = today

weekly_df = df[(df['Created_Time'] >= start_date) & (df['Created_Time'] <= end_date)]

if weekly_df.empty:
    st.warning("⚠️ No data available for the last 10 days.")
    st.stop()
    
# Step 5: Dark mode-friendly dashboard title
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
    plot_bgcolor='rgba(20,20,20,1)',
    paper_bgcolor='rgba(30,30,30,1)',
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
    plot_bgcolor='rgba(20,20,20,1)',
    paper_bgcolor='rgba(30,30,30,1)',
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

# Nested Donut Pie Chart: Engagement Breakdown
fig_donut = go.Figure(go.Sunburst(
    labels=['Clicks', 'Reactions', 'Post Clicks', 'Like Reactions', 'Love Reactions'],
    parents=['', '', 'Clicks', 'Reactions', 'Reactions'],
    values=[total_clicks, total_reactions, total_clicks, total_likes, total_loves],
    branchvalues="total",
    marker=dict(
        colors=[
            '#2C3E50',       # Inner Clicks
            '#424242',       # Inner Reactions
            '#5DADE2',       # Post Clicks (soft blue)
            '#1877F2',       # Like Reactions (Facebook blue)
            '#D81B60'        # Love Reactions (magenta)
        ],
        line=dict(color='rgba(255,255,255,0.1)', width=2)
    ),
    hovertemplate='<b>%{label}</b><br>Value: %{value}<extra></extra>',
    insidetextorientation='radial',
    maxdepth=2
))

fig_donut.update_layout(
    margin=dict(t=20, l=10, r=10, b=20),
    paper_bgcolor='rgba(15,15,15,1)',
    plot_bgcolor='rgba(15,15,15,1)',
    font=dict(color='#CCCCCC', family='Segoe UI'),
    uniformtext=dict(minsize=12, mode='hide')
)

st.plotly_chart(fig_donut, use_container_width=True)


# 🔗 Clickable Post Table – Preserves original look, polished
st.markdown(
    """
    <div style='text-align: center; padding-top: 20px; padding-bottom: 10px;'>
        <span style='font-size: 20px; font-family: "Segoe UI", sans-serif; font-weight: 600; color: #FFFFFF;'>
            🔗 Top Links Clicked Posts
        </span>
    </div>
    """,
    unsafe_allow_html=True
)

# Step 1: Select and sort by clicks
link_table = weekly_df[['Created_Time', 'Content', 'Post_Clicks', 'Total_Reactions', 'Permanent_Link']].copy()
link_table = link_table.sort_values(by='Post_Clicks', ascending=False)  # <-- this line sorts it

# Step 2: Make links clickable
link_table['Permanent_Link'] = link_table['Permanent_Link'].apply(
    lambda url: f'<a href="{url}" target="_blank">View Post</a>'
)

# Step 3: Render the table
st.write(link_table.to_html(escape=False, index=False), unsafe_allow_html=True)

# Use Google Sheet instead of local file for timestamp tracking
TIMESTAMP_SHEET_URL = "https://docs.google.com/spreadsheets/d/1PWMPIPELb_wOKZ0Oqmh0YppQPt_pvUjJaXQn9tp4G-o"
TIMESTAMP_TAB_NAME = "Sheet1"  # or rename if needed
timestamp_sheet = client.open_by_url(TIMESTAMP_SHEET_URL).worksheet(TIMESTAMP_TAB_NAME)

def should_send_email_gsheet(days_interval=4):
    try:
        last_sent_str = timestamp_sheet.acell('A1').value
        now = pd.Timestamp.now()

        if last_sent_str:
            last_sent = pd.to_datetime(last_sent_str)
            diff_days = (now - last_sent).days
            if diff_days < days_interval:
                st.info(f"⏱️ Last email was sent {diff_days} days ago. Email will be sent after {days_interval - diff_days} more day(s).")
                return False

        # ✅ More than 4 days passed or cell was empty
        timestamp_sheet.update_acell('A1', now.isoformat())
        return True

    except Exception as e:
        st.warning(f"⚠️ Error accessing timestamp sheet: {e}")
        return False
    
# Step 8: Email Automation (every 3 days using session state)
if should_send_email_gsheet():
    try:
        sender_email = st.secrets["GMAIL_USER"]
        password = st.secrets["GMAIL_PASS"]
        receiver_emails = ["priyankadesai1999@gmail.com", "tom.basey@gmail.com"]

        message = MIMEMultipart("alternative")
        message["Subject"] = "📊 Facebook Dashboard Link"
        message["From"] = sender_email
        message["To"] = ", ".join(receiver_emails)

        text = f"Hello,\n\nYour Facebook Insights Dashboard is ready.\n\nView Dashboard: {DASHBOARD_URL}\n\nRegards,\nInsights Bot"
        html = f"""
        <html>
          <body>
            <p>Hello,<br><br>
               Your <b>Facebook Insights Dashboard</b> is ready.<br>
               <a href="{DASHBOARD_URL}" target="_blank">Click here to view the dashboard</a>.<br><br>
               Regards,<br>
               Insights Bot
            </p>
          </body>
        </html>
        """

        part1 = MIMEText(text, "plain")
        part2 = MIMEText(html, "html")
        message.attach(part1)
        message.attach(part2)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, password)
            server.sendmail(sender_email, receiver_emails, message.as_string())

        st.success("📧 Email sent successfully!")

    except Exception as e:
        st.error(f"❌ Failed to send email.\n\nError:\n{e}")
else:
    st.info("✅ No email sent today. It's not time yet.")



