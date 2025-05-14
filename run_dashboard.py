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

# Step 4: Filter last complete week (Sunday to Saturday)
today = pd.Timestamp.today().normalize()
last_sunday = today - pd.to_timedelta(today.weekday() + 1, unit='D')
previous_sunday = last_sunday - pd.Timedelta(days=7)
last_saturday = last_sunday - pd.Timedelta(days=1)

weekly_df = df[(df['Created_Time'].dt.date >= previous_sunday.date()) &
               (df['Created_Time'].dt.date <= last_saturday.date())]

if weekly_df.empty:
    st.warning("⚠️ No data available for the last complete week.")
    st.stop()

# Step 5: Dashboard Title
week_range = f"{previous_sunday.date()} to {last_saturday.date()}"
# Step 5: Dark mode-friendly dashboard title
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
metric_style = """
    <div style="
        background: linear-gradient(145deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.02));
        border: 1px solid rgba(255, 255, 255, 0.1);
        backdrop-filter: blur(8px);
        border-radius: 16px;
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.3);
        padding: 25px 15px;
        text-align: center;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    " 
    onmouseover="this.style.transform='scale(1.05)'; this.style.boxShadow='0 10px 35px rgba(0, 0, 0, 0.5)'"
    onmouseout="this.style.transform='scale(1)'; this.style.boxShadow='0 8px 30px rgba(0, 0, 0, 0.3)'"
    >
        <div style="font-size: 15px; color: #cccccc; font-weight: 500; margin-bottom: 6px;">{label}</div>
        <div style="font-size: 26px; font-weight: 700; color: #ffffff;">{value}</div>
    </div>
"""

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(metric_style.format(label="🖱️ Total Clicks", value=f"{total_clicks:,}"), unsafe_allow_html=True)
with col2:
    st.markdown(metric_style.format(label="👍 Total Reactions", value=f"{total_reactions:,}"), unsafe_allow_html=True)
with col3:
    st.markdown(metric_style.format(label="🌍 Total Reach", value=f"{total_reach:,}"), unsafe_allow_html=True)
with col1:
    st.markdown(metric_style.format(label="❤️ Love Reactions", value=f"{total_loves:,}"), unsafe_allow_html=True)
with col2:
    st.markdown(metric_style.format(label="👍 Like Reactions", value=f"{total_likes:,}"), unsafe_allow_html=True)
with col3:
    st.markdown(metric_style.format(label="👁️ Impressions", value=f"{total_impressions:,}"), unsafe_allow_html=True)


# Step 7: SQL Summary Table (Daily Summary)
try:
    duckdb.register("weekly_df", weekly_df)
    summary_df = duckdb.query("""
        SELECT
            CAST(Created_Time AS DATE) AS Created_Date,
            STRFTIME(Created_Time, '%w')::INT AS Day_Of_Week,
            STRFTIME(Created_Time, '%A') AS Day_Name,
            SUM(Post_Clicks) AS Total_Clicks,
            SUM(Total_Reactions) AS Total_Reactions,
            SUM(Total_Reach) AS Total_Reach,
            SUM(Total_Like_Reactions) AS Total_Likes,
            SUM(Total_Love_Reactions) AS Total_Loves,
            SUM(Total_Impressions) AS Total_Impressions
        FROM weekly_df
        GROUP BY Created_Date, Day_Of_Week, Day_Name
        ORDER BY Created_Date
    """).to_df()
except Exception as e:
    st.error(f"❌ SQL query failed.\n\nError:\n{e}")
    st.stop()

# Chart 1: Daily Reaction Types Breakdown
fig_reactions = px.bar(
    summary_df,
    x='Created_Date',
    y=['Total_Likes', 'Total_Loves'],
    title="💬 Daily Reaction Type Breakdown",
    labels={"value": "Count", "variable": "Reaction Type"},
)
st.plotly_chart(fig_reactions, use_container_width=True)

# Chart 2: Total Impressions vs Reach (show both even if same)
fig_impressions = go.Figure()

fig_impressions.add_trace(go.Scatter(
    x=weekly_df['Created_Time'],
    y=weekly_df['Total_Impressions'],
    mode='lines+markers',
    name='Total Impressions',
    line=dict(color='deepskyblue'),
    hovertemplate='Impressions: %{y}<br>Post: %{text}<extra></extra>',
    text=weekly_df['Content']
))

fig_impressions.add_trace(go.Scatter(
    x=weekly_df['Created_Time'],
    y=weekly_df['Total_Reach'],
    mode='lines+markers',
    name='Total Reach',
    line=dict(color='orange'),
    hovertemplate='Reach: %{y}<br>Post: %{text}<extra></extra>',
    text=weekly_df['Content']
))

fig_impressions.update_layout(
    title='📈 Total Impressions vs Reach (Hover shows both)',
    xaxis_title='Created Time',
    yaxis_title='Value',
    hovermode='x unified'
)

st.plotly_chart(fig_impressions, use_container_width=True)


# Chart 3: Top 10 Posts by Clicks
top_posts = weekly_df.sort_values(by='Post_Clicks', ascending=False).head(10)
fig3 = px.bar(
    top_posts,
    x='Content',
    y='Post_Clicks',
    title='🔥 Top 10 Posts by Clicks',
    hover_data=['Permanent_Link']
)
st.plotly_chart(fig3, use_container_width=True)

# Chart 4: Love vs Like Reactions - Pie Chart
reaction_totals = pd.DataFrame({
    'Reaction Type': ['Love Reactions', 'Like Reactions'],
    'Count': [total_loves, total_likes]
})
fig_pie = px.pie(
    reaction_totals,
    names='Reaction Type',
    values='Count',
    title='❤️ vs 👍 Reaction Distribution'
)
st.plotly_chart(fig_pie, use_container_width=True)

# Chart 5: Best Day to Post (by Impressions + Reach)
summary_df['Engagement_Score'] = summary_df['Total_Impressions'] + summary_df['Total_Reach']
best_day = summary_df.sort_values(by='Engagement_Score', ascending=False).iloc[0]['Day_Name']
st.info(f"📆 Best day to post this week based on Impressions + Reach: **{best_day}**")

# Clickable Post Table
st.subheader("🔗 Clickable Post Links")
link_table = weekly_df[['Created_Time', 'Content', 'Post_Clicks', 'Total_Reactions', 'Permanent_Link']].copy()
link_table['Permanent_Link'] = link_table['Permanent_Link'].apply(lambda url: f'<a href="{url}" target="_blank">View Post</a>')
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
        receiver_emails = ["priyankadesai1999@gmail.com", "priyankapradeepdesai@gmail.com"]

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



