from urllib.request import Request, urlopen
from bs4 import BeautifulSoup, Comment
import pandas as pd
from io import StringIO

# Mapping only for League IDs (this is still needed)
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

# Function to extract player stats
def get_fbref_stats(stat_type, season_str, league_name):
    league_id = league_id_dict[league_name]
    league_name_url = league_name.replace(" ", "-")

    url_stat_type = "stats" if stat_type == "standard" else stat_type
    url = f"https://fbref.com/en/comps/{league_id}/{season_str}/{url_stat_type}/{season_str}-{league_name_url}-Stats"

    headers = {'User-Agent': 'Mozilla/5.0'}
    req = Request(url, headers=headers)

    try:
        html = urlopen(req)
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        return None, f"Error loading page: {e}"

    # Determine table ID based on stat_type
    table_id = {
        "playingtime": "stats_playing_time",
        "keepers": "stats_keeper",
        "keepersadv": "stats_keeper_adv"
    }.get(stat_type, "stats_standard" if stat_type == "standard" else f"stats_{stat_type}")

    def find_table_in_comments(soup, table_id):
        table = soup.find("table", {"id": table_id})
        if table:
            return table
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment_soup = BeautifulSoup(comment, "html.parser")
            table = comment_soup.find("table", {"id": table_id})
            if table:
                return table
        return None

    table_html = find_table_in_comments(soup, table_id)

    try:
        df = pd.read_html(StringIO(str(table_html)), flavor='lxml')[0]
    except Exception as e:
        return None, f"Error parsing table HTML: {e}"

    df = df[df[df.columns[0]] != df.columns[0]]
    df.reset_index(drop=True, inplace=True)
    df.columns = [
        col[1] if col[0].startswith('Unnamed') or col[0] == col[1]
        else f"{col[0]}_{col[1]}"
        for col in df.columns
    ]

    df.drop(columns=[c for c in df.columns if c.lower() in ['rk', 'matches']], inplace=True, errors='ignore')

    non_numeric_cols = {"Player", "Nation", "Pos", "Squad", "Age", "Born"}
    for col in df.columns:
        if col not in non_numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df.fillna(0, inplace=True)

    # Apply filter using standard stats (if not already standard)
    if stat_type != "standard":
        if stat_type == "keepersadv":
            std_url = f"https://fbref.com/en/comps/{league_id}/{season_str}/keepers/{season_str}-{league_name_url}-Stats"
            std_table_id = "stats_keeper"
        elif stat_type == "keepers":
            std_url = url  # already loaded
            std_table_id = "stats_keeper"
        else:
            std_url = f"https://fbref.com/en/comps/{league_id}/{season_str}/stats/{season_str}-{league_name_url}-Stats"
            std_table_id = "stats_standard"

        if stat_type != "keepers":
            req_std = Request(std_url, headers=headers)
            try:
                html_std = urlopen(req_std)
                soup_std = BeautifulSoup(html_std, 'html.parser')
            except Exception as e:
                return None, f"Error loading standard stats page: {e}"

            std_table_html = None
            for comment in soup_std.find_all(string=lambda text: isinstance(text, Comment)):
                if std_table_id in comment:
                    comment_soup = BeautifulSoup(comment, 'html.parser')
                    std_table_html = comment_soup.find("table", {"id": std_table_id})
                    if std_table_html:
                        break

            if std_table_html is None:
                return None, f"Standard stats table not found at {std_url}"

            try:
                std_df = pd.read_html(StringIO(str(std_table_html)), flavor='lxml')[0]
            except Exception as e:
                return None, f"Error parsing standard stats table: {e}"

            std_df = std_df[std_df[std_df.columns[0]] != std_df.columns[0]]
            std_df.reset_index(drop=True, inplace=True)
            std_df.columns = [
                col[1] if col[0].startswith('Unnamed') or col[0] == col[1]
                else f"{col[0]}_{col[1]}"
                for col in std_df.columns
            ]
            for col in std_df.columns:
                if col not in non_numeric_cols:
                    std_df[col] = pd.to_numeric(std_df[col], errors='coerce').fillna(0)

            valid_players = std_df[(std_df["Playing Time_MP"] >= 5) &
                                   (std_df["Playing Time_Min"] >= 150)]["Player"]
            df = df[df["Player"].isin(valid_players)].reset_index(drop=True)
        else:
            df = df[(df["Playing Time_MP"] >= 5) & (df["Playing Time_Min"] >= 150)].reset_index(drop=True)
    else:
        df = df[(df["Playing Time_MP"] >= 5) & (df["Playing Time_Min"] >= 150)].reset_index(drop=True)

    return df, None

# Team-level scraping
def get_fbref_team_stats(stat_type, season_str, league_name):
    league_id = league_id_dict[league_name]
    league_name_url = league_name.replace(" ", "-")
    stat_suffix = stat_type
    url = f"https://fbref.com/en/comps/{league_id}/{season_str}/{stat_suffix}/{season_str}-{league_name_url}-Stats"

    headers = {'User-Agent': 'Mozilla/5.0'}
    req = Request(url, headers=headers)

    try:
        html = urlopen(req)
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        return None, f"Error loading team stats page: {e}"

    def find_table_by_caption(soup, caption_startswith="Squad"):
        for table in soup.find_all("table"):
            caption = table.find("caption")
            if caption and caption.text.strip().startswith(caption_startswith):
                return table
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment_soup = BeautifulSoup(comment, "html.parser")
            for table in comment_soup.find_all("table"):
                caption = table.find("caption")
                if caption and caption.text.strip().startswith(caption_startswith):
                    return table
        return None

    table_html = find_table_by_caption(soup)

    if table_html is None:
        return None, f"No team-level table found for stat type '{stat_type}'"

    try:
        df = pd.read_html(StringIO(str(table_html)), flavor='lxml')[0]
    except Exception as e:
        return None, f"Error parsing table HTML: {e}"

    df = df[df[df.columns[0]] != df.columns[0]]
    df.reset_index(drop=True, inplace=True)
    df.columns = [
        col[1] if col[0].startswith('Unnamed') or col[0] == col[1]
        else f"{col[0]}_{col[1]}"
        for col in df.columns
    ]

    non_numeric_cols = {"Squad", "Country"}
    for col in df.columns:
        if col not in non_numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df.fillna(0, inplace=True)

    return df, None

# Combine all leagues
def build_all_leagues_df(stat_type, season_str, league_list):
    all_dfs = []

    for league in league_list:
        df, error = get_fbref_stats(stat_type=stat_type, season_str=season_str, league_name=league)
        if df is not None:
            df["League"] = league
            all_dfs.append(df)
        else:
            print(f"Skipped {league} due to error: {error}")

    if not all_dfs:
        return None, "No data could be loaded for any league."

    df_all = pd.concat(all_dfs, ignore_index=True)
    return df_all, None
