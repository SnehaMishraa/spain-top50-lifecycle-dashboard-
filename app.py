
import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

st.set_page_config(
    page_title="Spain Top 50 | Song Analytics",
    page_icon="🎵",
    layout="wide"
)

PROJECT_DIR = Path(__file__).resolve().parent

@st.cache_data
def load_data():
    data_dir = PROJECT_DIR / "data" / "processed"
    export_dir = PROJECT_DIR / "power_bi"

    songs = pd.read_csv(data_dir / "spain_top50_cleaned.csv")
    lifecycle = pd.read_csv(export_dir / "song_lifecycle.csv")
    stages = pd.read_csv(export_dir / "lifecycle_stages.csv")
    rotation = pd.read_csv(export_dir / "daily_rotation.csv")

    songs["date"] = pd.to_datetime(songs["date"], errors="coerce")
    rotation["date"] = pd.to_datetime(rotation["date"], errors="coerce")

    return songs, lifecycle, stages, rotation

songs, lifecycle, stages, rotation = load_data()

st.title("🎵 Spain Top 50 Songs")
st.subheader("Content Maturity, Chart Longevity & Playlist Rotation")
st.caption("Analysis period: May 2024 – November 2025")

st.sidebar.header("Dashboard Filters")

min_date = songs["date"].min().date()
max_date = songs["date"].max().date()

date_range = st.sidebar.date_input(
    "Select date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date
)

stage_options = sorted(stages["lifecycle_stage"].dropna().unique())
selected_stages = st.sidebar.multiselect(
    "Lifecycle stage",
    options=stage_options,
    default=stage_options
)

explicit_filter = st.sidebar.selectbox(
    "Explicit content",
    ["All", "Explicit", "Non-explicit"]
)

album_filter = st.sidebar.selectbox(
    "Album type",
    ["All", "Single", "Album"]
)

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

filtered_songs = songs[
    songs["date"].between(
        pd.Timestamp(start_date),
        pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
    )
].copy()

filtered_stages = stages.copy()

if selected_stages:
    filtered_stages = filtered_stages[
        filtered_stages["lifecycle_stage"].isin(selected_stages)
    ]
else:
    filtered_stages = filtered_stages.iloc[0:0]

if explicit_filter != "All":
    desired = explicit_filter == "Explicit"
    filtered_songs = filtered_songs[
        filtered_songs["is_explicit"].astype(str).str.lower().isin(
            ["true", "1"] if desired else ["false", "0"]
        )
    ]

if album_filter != "All":
    filtered_songs = filtered_songs[
        filtered_songs["album_type"].str.lower() == album_filter.lower()
    ]

st.markdown("### Key Performance Indicators")

c1, c2, c3, c4 = st.columns(4)

avg_days = lifecycle["days_on_chart"].mean()
avg_peak = lifecycle["time_to_peak_days"].mean()

valid_rotation = rotation["churn_rate_pct"].dropna()
avg_churn = valid_rotation.mean() if not valid_rotation.empty else 0

persistence = (
    lifecycle["days_on_chart"] /
    (
        (pd.to_datetime(lifecycle["last_seen"]) -
         pd.to_datetime(lifecycle["first_seen"])).dt.days + 1
    )
).mean() * 100

c1.metric("Avg. Days on Playlist", f"{avg_days:.1f}")
c2.metric("Avg. Time to Peak", f"{avg_peak:.1f} days")
c3.metric("Avg. Playlist Churn", f"{avg_churn:.2f}%")
c4.metric("Retention Stability", f"{persistence:.2f}%")

st.markdown("---")
st.caption(
    f"Showing {len(filtered_songs):,} chart observations "
    f"for the selected filters."
)

st.info("Dashboard layout and KPI cards are ready. Interactive charts are coming next.")


st.markdown("---")
st.header("📊 Playlist Lifecycle & Rotation")

# 1. Lifecycle stage distribution
left, right = st.columns(2)

with left:
    st.subheader("Lifecycle Stage Distribution")
    if not filtered_stages.empty:
        stage_counts = (
            filtered_stages.groupby("lifecycle_stage")
            .size()
            .reset_index(name="Song Count")
        )
        fig = px.bar(
            stage_counts,
            x="lifecycle_stage",
            y="Song Count",
            color="lifecycle_stage",
            title="Songs by Lifecycle Stage",
            labels={
                "lifecycle_stage": "Lifecycle Stage",
                "Song Count": "Number of Songs"
            }
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Select at least one lifecycle stage.")

# 2. Daily entries and exits
with right:
    st.subheader("Daily Playlist Rotation")
    rotation_view = rotation[
        rotation["date"].between(
            pd.Timestamp(start_date),
            pd.Timestamp(end_date)
        )
    ].copy()

    rotation_view = rotation_view.dropna(subset=["entries", "exits"])
    rotation_view = rotation_view[
        (rotation_view["entries"] != 50) |
        (rotation_view["exits"] != 0)
    ]

    if not rotation_view.empty:
        daily_long = rotation_view.melt(
            id_vars="date",
            value_vars=["entries", "exits"],
            var_name="Movement",
            value_name="Songs"
        )
        fig = px.line(
            daily_long,
            x="date",
            y="Songs",
            color="Movement",
            markers=False,
            title="Daily Entries vs. Exits"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No daily rotation data is available for this date range.")

# 3. Monthly churn
st.subheader("Monthly Playlist Churn")

monthly_view = rotation[
    rotation["date"].between(
        pd.Timestamp(start_date),
        pd.Timestamp(end_date)
    )
].dropna(subset=["churn_rate_pct"]).copy()

if not monthly_view.empty:
    monthly_view["month"] = (
        monthly_view["date"].dt.to_period("M").astype(str)
    )
    monthly_summary = (
        monthly_view.groupby("month", as_index=False)
        ["churn_rate_pct"].mean()
    )
    fig = px.bar(
        monthly_summary,
        x="month",
        y="churn_rate_pct",
        title="Average Monthly Churn Rate",
        labels={
            "month": "Month",
            "churn_rate_pct": "Average Churn Rate (%)"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

# 4. Explicit vs. non-explicit content
st.markdown("---")
st.header("🎧 Content Analysis")

left, right = st.columns(2)

with left:
    st.subheader("Explicit vs. Non-explicit")

    if not filtered_songs.empty:
        explicit_summary = (
            filtered_songs.assign(
                content_type=filtered_songs["is_explicit"].map(
                    {True: "Explicit", False: "Non-explicit",
                     "True": "Explicit", "False": "Non-explicit"}
                ).fillna("Unknown")
            )
            .groupby("content_type", as_index=False)
            .agg(
                Chart_Observations=("song", "size"),
                Avg_Popularity=("popularity", "mean")
            )
        )

        fig = px.bar(
            explicit_summary,
            x="content_type",
            y="Chart_Observations",
            color="content_type",
            title="Chart Observations by Content Type"
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Singles vs. Albums")

    if not filtered_songs.empty:
        album_summary = (
            filtered_songs.groupby("album_type", as_index=False)
            .agg(
                Chart_Observations=("song", "size"),
                Avg_Popularity=("popularity", "mean")
            )
        )
        fig = px.bar(
            album_summary,
            x="album_type",
            y="Avg_Popularity",
            color="album_type",
            title="Average Popularity by Release Type",
            labels={"Avg_Popularity": "Average Popularity Score"}
        )
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

# 5. Song duration vs. playlist longevity
st.markdown("---")
st.header("⏱️ Song Duration vs. Playlist Longevity")

metadata = (
    songs[["song", "artist", "duration_ms", "album_type"]]
    .drop_duplicates(subset=["song", "artist"])
)

longevity = metadata.merge(
    lifecycle[["song", "artist", "days_on_chart"]],
    on=["song", "artist"],
    how="inner"
)

if not longevity.empty:
    longevity["duration_minutes"] = (
        longevity["duration_ms"] / 60000
    )

    fig = px.scatter(
        longevity,
        x="duration_minutes",
        y="days_on_chart",
        color="album_type",
        hover_name="song",
        hover_data=["artist"],
        title="Does Song Duration Relate to Playlist Longevity?",
        labels={
            "duration_minutes": "Song Duration (minutes)",
            "days_on_chart": "Days on Playlist",
            "album_type": "Release Type"
        }
    )
    st.plotly_chart(fig, use_container_width=True)

st.caption(
    "Note: Spotify popularity is a score, not a stream count. "
    "Playlist observations do not represent total listening volume."
)
