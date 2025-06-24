# app.py
import pandas as pd
import streamlit as st
from urllib.parse import urlencode, quote
from scraper import get_fbref_stats, get_fbref_team_stats, build_all_leagues_df
from visuals import plot_radar_comparison
from sklearn.metrics.pairwise import cosine_similarity

# Set a page of this project
st.set_page_config(page_title="Football Stats App", layout="wide")

# Move the main title into the sidebar
with st.sidebar:
    st.markdown("## ⚽ Football Player Stats Explorer")
    page_choice = st.radio("Navigate to...", ["Explorer", "About"])

# Code for exploring the players' stats
if page_choice == "Explorer":
    # Sidebar inputs
    level_choice = st.sidebar.selectbox("Data Level", ["Player", "Team"])
    stat_choice = st.sidebar.selectbox("Statistic Type", [
        "Standard", "Shooting", "Passing", "Pass Types", 
        "Goal and Shot Creation", "Defensive Actions", 
        "Possession", "Playing Time", "Goalkeeping", "Goalkeeping Advanced"
    ])
    season_choice = st.sidebar.selectbox("Season", ["2024-2025", "2023-2024", "2022-2023", "2021-2022"])
    league_choice = st.sidebar.selectbox("League", [
        "Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1", 
        "Eredivisie", "Primeira Liga", "Belgian Pro League"
    ])

    stat_type_dict = {
        "Standard": "standard",
        "Shooting": "shooting",
        "Passing": "passing",
        "Pass Types": "passing_types",
        "Goal and Shot Creation": "gca",
        "Defensive Actions": "defense",
        "Possession": "possession",
        "Playing Time": "playingtime",
        "Goalkeeping": "keepers",
        "Goalkeeping Advanced": "keepersadv"
    }

    # Reverse dictionary for converting back lowercase stat_type → display label
    stat_type_reverse_dict = {v: k for k, v in stat_type_dict.items()}

    league_id_dict = {
        "Premier League": 9,
        "La Liga": 12,
        "Bundesliga": 20,
        "Serie A": 11,
        "Ligue 1": 13,
        "Eredivisie": 23,
        "Primeira Liga": 32,
        "Belgian Pro League": 37
    }

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_cached_stats(stat_type, season_str, league_name):
        stat_key = stat_type_dict.get(stat_type, None)
        if stat_key is None:
            return None, f"Statistic type '{stat_type}' not supported."
        return get_fbref_stats(stat_key, season_str, league_name)

    @st.cache_data(ttl=3600, show_spinner=False)
    def get_cached_team_stats(stat_type, season_str, league_name):
        stat_key = stat_type_dict.get(stat_type, None)
        if stat_key is None:
            return None, f"Statistic type '{stat_type}' not supported."
        return get_fbref_team_stats(stat_key, season_str, league_name)

    @st.cache_data(ttl=3600, show_spinner=False)
    def load_all_league_data(stat_type, season_str):
        all_leagues = list(league_id_dict.keys())
        stat_key = stat_type_dict.get(stat_type, None)
        if stat_key is None:
            return None, f"Statistic type '{stat_type}' not supported."
        return build_all_leagues_df(stat_key, season_str, all_leagues)

    def get_top_similar_players(selected_vec, candidate_df, radar_features, exclude_player, top_n=3):
        df = candidate_df[candidate_df["Player"] != exclude_player].dropna(subset=radar_features).reset_index(drop=True)
        if df.empty or selected_vec.size == 0:
            return None
        sim_scores = cosine_similarity(selected_vec, df[radar_features].values)[0]
        df = df.assign(similarity=sim_scores)
        return df.sort_values("similarity", ascending=False).head(top_n).reset_index(drop=True)

    # --- Similar player link generation ---
    def create_similar_player_link(player_name, squad, age, pos, similarity, league_group, stat_choice, season_choice, selected_player):
        query = {
            "player1": selected_player,
            "player2": player_name,
            "league_group": league_group,
            "stat_choice": stat_type_dict[stat_choice],  # store key in URL (e.g. 'gca')
            "season_choice": season_choice
        }
        #url_params = urlencode(query, quote_via=quote)  # support full names with spaces
        #return f"[{player_name} ({squad}, {age}, {similarity:.3f})](?{url_params})"
        return f"{player_name} ({squad}, {age}, {pos} / Similarity: {similarity:.3f})"

    # --- Read from query string ---
    query_params = st.query_params

    if season_choice and league_choice and stat_choice:

        # URL-based comparison mode
        if all(k in query_params for k in ("player1", "player2", "league_group", "stat_choice", "season_choice")):
            player1 = query_params["player1"][0]
            player2 = query_params["player2"][0]
            league_group = query_params["league_group"][0]

            # Convert lowercase stat_choice key back to display name
            stat_choice_q_lower = query_params["stat_choice"][0]
            stat_choice_q = stat_type_reverse_dict.get(stat_choice_q_lower, stat_choice_q_lower)
                
            # Season Choice
            season_choice_q = query_params["season_choice"][0]

            st.header(f"Comparison: {player1} vs {player2} in {league_group}")
            st.write(f"Statistic: {stat_choice_q} | Season: {season_choice_q}")

            df_all_leagues, error_all = load_all_league_data(stat_choice_q, season_choice_q)
            if error_all:
                st.error(error_all)
            elif df_all_leagues is not None:
                big5_leagues = ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]
                other3_leagues = ["Eredivisie", "Primeira Liga", "Belgian Pro League"]

                # Use selected group
                if league_group == league_choice:
                    group_df = df_all_leagues[df_all_leagues["League"] == league_choice]
                elif league_group == "Big 5 Leagues":
                    group_df = df_all_leagues[df_all_leagues["League"].isin(big5_leagues)]
                elif league_group == "Eredivisie/Primeira Liga/Belgian Pro League":
                    group_df = df_all_leagues[df_all_leagues["League"].isin(other3_leagues)]
                elif league_group == "All 8 Leagues":
                    group_df = df_all_leagues
                else:
                    group_df = df_all_leagues

                # Add selected players if not already in group
                player_rows = df_all_leagues[df_all_leagues["Player"].isin([player1, player2])]
                group_df = group_df.append(player_rows).drop_duplicates().reset_index(drop=True)

                player1_df = group_df[group_df["Player"] == player1]
                player2_df = group_df[group_df["Player"] == player2]

                if player1_df.empty:
                    st.error(f"No data for player {player1} in {league_group}")
                elif player2_df.empty:
                    st.error(f"No data for player {player2} in {league_group}")
                else:
                    numeric_cols = group_df.select_dtypes(include='number').columns.tolist()
                    radar_features = st.multiselect(
                        "Select features for radar chart", numeric_cols, default=numeric_cols[:5]
                    )

                    if radar_features:
                        fig = plot_radar_comparison(
                            player1_df, 
                            player2_df, 
                            player1, 
                            radar_features, 
                            comparison_group_name=league_group,
                            comparison_player2=player2_df
                        )
                        st.plotly_chart(fig, use_container_width=True)

            st.stop()

        with st.spinner("Fetching data..."):
            if level_choice == "Player":
                df, error = get_cached_stats(stat_choice, season_choice, league_choice)
            else:
                df, error = get_cached_team_stats(stat_choice, season_choice, league_choice)

        if error:
            st.error(error)

        elif df is not None:
            team_list = sorted(df["Squad"].unique())
            team_choice = st.sidebar.selectbox("Team", ["All Teams"] + team_list)

            if team_choice != "All Teams":
                df = df[df["Squad"] == team_choice].reset_index(drop=True)

            if level_choice == "Player":
                player_list = sorted(df["Player"].unique())
                player_choice = st.sidebar.selectbox("Player", ["All Players"] + player_list)

                if player_choice != "All Players":
                    df = df[df["Player"] == player_choice].reset_index(drop=True)

            st.success(f"{df.shape[0]} rows loaded.")
            st.subheader(f"{level_choice} Level Stats")
            st.dataframe(df)

        else:
            st.warning("No data loaded.")

        # Radar chart & similarity section
        if level_choice == "Player" and 'player_choice' in locals() and player_choice != "All Players":
            numeric_cols = df.select_dtypes(include='number').columns.tolist()
            radar_features = st.multiselect("Select features for radar chart", numeric_cols, default=numeric_cols[:5])

            big5_leagues = ["Premier League", "La Liga", "Bundesliga", "Serie A", "Ligue 1"]
            other3_leagues = ["Eredivisie", "Primeira Liga", "Belgian Pro League"]

            df_all_leagues, error_all = load_all_league_data(stat_choice, season_choice)

            if error_all:
                st.warning(error_all)
            elif df_all_leagues is not None and not df.empty:
                selected_row = df[df["Player"] == player_choice]

                league_groups = {
                    league_choice: [league_choice],
                    "Big 5 Leagues": big5_leagues,
                    "Eredivisie/Primeira Liga/Jupiler": other3_leagues,
                    "All 8 Leagues": list(league_id_dict.keys())
                }

                # Original code (""")
                for group_name, leagues in league_groups.items():
                    #st.text(f"Group: {group_name} / League: {leagues}")
                    #comp_group_df = df_all_leagues[df_all_leagues["League"].isin(leagues) & (df_all_leagues["Player"] != player_choice)]
                    comp_group_df = df_all_leagues[df_all_leagues["League"].isin(leagues)]
                    
                    sel_player_df = df_all_leagues[df_all_leagues["Player"] == player_choice]
                    
                    if sel_player_df.empty:
                        sel_player_df = df_all_leagues[df_all_leagues["Player"] == player_choice]
                        if sel_player_df.empty:
                            st.warning(f"No data for {player_choice} in {group_name}. Skipping...")
                            continue
                        
                    # Subheader
                    st.subheader(f"{player_choice} vs {group_name}")

                    # Selected vector
                    selected_vec = sel_player_df[radar_features].values
                    
                    #st.text(f"[DEBUG] Comparing {player_choice} against {group_name}")
                    #st.text(f"Player vector shape: {selected_vec.shape}")
                    #st.text(f"Comparison group shape: {comp_group_df.shape}")
                    
                    top_similar = get_top_similar_players(selected_vec, comp_group_df, radar_features, player_choice, top_n=3)

                    if top_similar is None or top_similar.empty:
                        st.write("No similar players found for this group.")
                        continue
                    
                    st.markdown(f"**Top 3 Similar Players in {group_name}:**")
                    
                    # Create display labels using the same link logic
                    player_radio_labels = []
                    player_radio_mapping = {}
                    
                    for i, row in top_similar.iterrows():
                        link_md = create_similar_player_link(
                            player_name=row["Player"],
                            squad=row["Squad"],
                            age=row.get("Age", "N/A"),
                            pos=row["Pos"],
                            similarity=row["similarity"],
                            league_group=group_name,
                            stat_choice=stat_choice,
                            season_choice=season_choice,
                            selected_player=player_choice
                        )
                        
                        player_radio_labels.append(link_md)
                        player_radio_mapping[link_md] = row["Player"]
                        
                    # Streamlit radio button to select one player
                    selected_radio_label = st.radio(f"Comparison with Similar Player:",
                        options=player_radio_labels + ["None"],
                        key=f"radio_{group_name}")
                    
                    # Retrieve selected player name
                    if selected_radio_label != "None":
                        selected_similar_player = player_radio_mapping[selected_radio_label]
                        checkbox_df = df_all_leagues[df_all_leagues["Player"] == selected_similar_player]
                    else:
                        selected_similar_player = None
                        checkbox_df = None

                    # Update data for radar chart
                    radar_fig = plot_radar_comparison(
                        selected_player_df=sel_player_df,
                        comparison_df=comp_group_df,
                        player_name=player_choice,
                        features=radar_features,
                        comparison_group_name=group_name,
                        checkbox_player_df=checkbox_df,
                        checkbox_name=selected_similar_player
                    )
                    
                    st.plotly_chart(radar_fig, use_container_width=True)

    else:
        st.warning("Please select all required inputs.")

# Code for "About" page
elif page_choice == "About":
    st.header("📘 About This App")
    st.markdown("""
    Welcome to the **Football Player Stats Explorer**!  
    This app helps users explore football player performance across major European leagues
    using interactive visualizations like radar charts and similarity comparisons using the data from Fbref.
    
    (This app is currently under development.)

    ### 👨‍💻 About Me
    My name is Junseok Yang, and I built this app as part of my football analytics portfolio.
    I’m passionate about data science and football, and I enjoy combining the two
    to create insightful tools for analysts, coaches, and fans. You can find more information
    about me in [my personal webpage](https://jsyang354.github.io).

    ### 🛠️ Tools Used
    - **Python & Streamlit** for App Development  
    - **Pandas & NumPy** for Data Manipulation  
    - **Plotly** for Interactive Charts  
    - **Scikit-learn & Scipy** for Player Comparisons (Cosine Similarity)

    If you find this useful or have suggestions, feel free to reach out!
    """)