import pandas as pd
import numpy as np
import plotly.graph_objects as go
from scipy.stats import rankdata

def plot_radar_comparison(selected_player_df, comparison_df, player_name, features=None, comparison_group_name="Comparison Group", 
                          checkbox_player_df=None, checkbox_name=None):
    if features is None:
        features = selected_player_df.select_dtypes(include=np.number).columns.tolist()
        
    # Combine for ranking
    combined_df = pd.concat([selected_player_df, checkbox_player_df, comparison_df], axis=0).drop_duplicates().reset_index(drop=True)

    # True "Top X%" = player in 1st = Top 1%, in last = Top 100%
    def true_top_percentile(col):
        return (1 - rankdata(col, method="min") / len(col)) * 100

    # Compute percentiles
    scaled_df = combined_df[features].copy()
    for feature in features:
        scaled_df[feature + "_top_pct"] = true_top_percentile(scaled_df[feature])
        
    # Extract values
    player_row = scaled_df.iloc[0]
    checkbox_row = scaled_df.iloc[1]
    group_df = scaled_df.iloc[2:]

    # Radar radius = 100 - top percentile → higher = better
    player_radar_values = [100 - player_row[feature + "_top_pct"] for feature in features]
    checkbox_radar_values = [100 - checkbox_row[feature + "_top_pct"] for feature in features]
    group_radar_values = [100 - group_df[feature + "_top_pct"].mean() for feature in features]

    # Actual values
    player_actuals = [player_row[feature] for feature in features]
    checkbox_actuals = [checkbox_row[feature] for feature in features]
    group_actuals = group_df[features].mean().values
    
    player_top_percentiles = [player_row[feature + "_top_pct"] for feature in features]
    checkbox_top_percentiles = [checkbox_row[feature + "_top_pct"] for feature in features]

    # Axis labels
    axis_labels = [
        f"{feature}\nTop {int(round(tpct))}% ({actual:.2f})"
        for feature, tpct, actual in zip(features, player_top_percentiles, player_actuals)
    ]

    fig = go.Figure()

    # Player trace (simplified hover: just name)
    fig.add_trace(go.Scatterpolar(
        r=player_radar_values,
        theta=axis_labels,
        fill='toself',
        name=player_name,
        line=dict(color='skyblue'),
        fillcolor='rgba(135, 206, 235, 0.5)',  # skyblue with transparency
        hoverinfo='name'  # only show name when hovered
    ))
    
    # Checkbox trace (simplified hover: just name)
    if checkbox_player_df is not None and not checkbox_player_df.empty and checkbox_name is not None:
        fig.add_trace(go.Scatterpolar(
            r=checkbox_radar_values,
            theta=axis_labels,
            fill='toself',
            name=checkbox_name,
            line=dict(color='red'),
            fillcolor='rgba(255, 99, 132, 0.4)',
            text=[
                f"<b>{checkbox_name}</b><br>Top {int(round(tpct))}% ({actual:.2f})"
                for tpct, actual in zip(checkbox_top_percentiles, checkbox_actuals)
            ],
            hoverinfo='text'
        ))

    # Group trace (show group average values)
    fig.add_trace(go.Scatterpolar(
        r=group_radar_values,
        theta=axis_labels,
        fill='toself',
        name=comparison_group_name,
        line=dict(color='dodgerblue'),
        fillcolor='rgba(30, 144, 255, 0.5)',  # dodgerblue with transparency
        text=[
            f"<b>{feature}</b><br>Group Avg: {actual:.2f}"
            for feature, actual in zip(features, group_actuals)
        ],
        hoverinfo='text'
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 100])
        ),
        showlegend=True,
        title=f"Radar: {player_name} vs {comparison_group_name}",
        height=600
    )

    return fig

def mini_radar_chart(player_df, features, player_name, comparison_group_df=None, group_name="Group"):
    """
    Small radar chart for one player, optionally showing group average.
    Player is skyblue, group average is dodgerblue.
    Used for side-by-side display of multiple players.
    """
    from scipy.stats import rankdata

    # Combine data for percentile calculation
    if comparison_group_df is not None:
        combined_df = pd.concat([player_df, comparison_group_df], axis=0).reset_index(drop=True)
    else:
        combined_df = player_df.copy()

    def true_top_percentile(col):
        return (1 - rankdata(col, method="min") / len(col)) * 100

    scaled_df = combined_df[features].copy()
    for f in features:
        scaled_df[f + "_top_pct"] = true_top_percentile(scaled_df[f])

    player_row = scaled_df.iloc[0]
    player_top_pct = [player_row[f + "_top_pct"] for f in features]
    player_radar = [100 - p for p in player_top_pct]

    fig = go.Figure()

    # Player radar trace
    fig.add_trace(go.Scatterpolar(
        r=player_radar,
        theta=features,
        fill='toself',
        name=player_name,
        line=dict(color='skyblue'),
        hoverinfo='skip'
    ))

    if comparison_group_df is not None:
        group_rows = scaled_df.iloc[1:]
        group_top_pct = [group_rows[f + "_top_pct"].mean() for f in features]
        group_radar = [100 - p for p in group_top_pct]
        fig.add_trace(go.Scatterpolar(
            r=group_radar,
            theta=features,
            fill='toself',
            name=group_name,
            line=dict(color='dodgerblue'),
            hoverinfo='skip'
        ))

    fig.update_layout(
        polar=dict(radialaxis=dict(visible=False, range=[0, 100])),
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
        height=250,
        width=250
    )
    return fig








