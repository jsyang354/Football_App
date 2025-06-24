# Package for scraping
from urllib.request import Request, urlopen
from bs4 import BeautifulSoup, Comment
import pandas as pd
from io import StringIO

# Dictionary for statistic types and League ID
stat_type_dict = {
    # Fieldplayer stats
    "Standard": "standard",
    "Shooting": "shooting",
    "Passing": "passing",
    "Pass Types": "passing_types",
    "Goal and Shot Creation": "gca",
    "Defensive Action": "defense",
    "Possession": "possession",
    "Playing Time": "playingtime",
    
    # Goalkeeper stats
    "Goalkeeping": "keepers",
    "Goalkeeping Advanced": "keepersadv"
}

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

# Function to extract feature statistics
def get_fbref_stats(stat_type, season_str, league_name):
    league_id = league_id_dict[league_name]
    league_name_url = league_name.replace(" ", "-")
    
    # URL part for stat_type
    # Modified stat_type == "standard" (lowercase) for fixing error (Jun 16)
    url_stat_type = "stats" if stat_type == "standard" else stat_type_dict[stat_type]
    url = f"https://fbref.com/en/comps/{league_id}/{season_str}/{url_stat_type}/{season_str}-{league_name_url}-Stats"

    headers = {'User-Agent': 'Mozilla/5.0'}
    req = Request(url, headers=headers)

    try:
        html = urlopen(req)
        print(f"Requesting URL: {url}")
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        return None, f"Error loading page: {e}"
    
    # Fix table_id mapping for these cases
    table_id = {
        "Playing Time": "stats_playing_time",
        "Goalkeeping": "stats_keeper",
        "Goalkeeping Advanced": "stats_keeper_adv"
    }.get(stat_type, "stats_standard" if stat_type == "standard" else f"stats_{stat_type_dict[stat_type]}")
    
    def find_table_in_comments(soup, table_id):
    # Try to find table normally
        table = soup.find("table", {"id": table_id})
        if table:
            return table
    
    # If not found, search inside comments
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

    # Remove repeated header rows
    df = df[df[df.columns[0]] != df.columns[0]]
    df.reset_index(drop=True, inplace=True)

    # Flatten multi-index columns and clean 'Unnamed' prefixes
    df.columns = [
        col[1] if col[0].startswith('Unnamed') or col[0] == col[1]
        else f"{col[0]}_{col[1]}"
        for col in df.columns
    ]

    # Drop unwanted columns if they exist
    df.drop(columns=[c for c in df.columns if c.lower() in ['rk', 'matches']], inplace=True, errors='ignore')

    # Convert numeric columns except known non-numeric
    non_numeric_cols = {"Player", "Nation", "Pos", "Squad", "Age", "Born"}
    for col in df.columns:
        if col not in non_numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
    # Fill NaN values with 0
    df.fillna(0, inplace=True)
    
    # For non-standard stat types, fetch appropriate standard table for filtering
    if stat_type != "Standard":
        # Decide source for filtering: Standard for most, Goalkeeping for Advanced
        if stat_type == "Goalkeeping Advanced":
            std_url = f"https://fbref.com/en/comps/{league_id}/{season_str}/keepers/{season_str}-{league_name_url}-Stats"
            std_table_id = "stats_keeper"
        elif stat_type == "Goalkeeping":
            std_url = url  # Already have the Goalkeeping data in `df`, no need to refetch
            std_table_id = "stats_keeper"
        else:
            std_url = f"https://fbref.com/en/comps/{league_id}/{season_str}/stats/{season_str}-{league_name_url}-Stats"
            std_table_id = "stats_standard"

        # Only fetch if we didn't already get the standard data (i.e., not Goalkeeping)
        if stat_type != "Goalkeeping":
            req_std = Request(std_url, headers=headers)
            try:
                html_std = urlopen(req_std)
                soup_std = BeautifulSoup(html_std, 'html.parser')
            except Exception as e:
                return None, f"Error loading standard stats page: {e}"

            comment_blocks_std = soup_std.find_all(string=lambda text: isinstance(text, Comment))
            std_table_html = None
            for comment in comment_blocks_std:
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
            # If stat_type is Goalkeeping, apply filter directly
            df = df[(df["Playing Time_MP"] >= 5) & (df["Playing Time_Min"] >= 150)].reset_index(drop=True)
    
    else:
        df = df[(df["Playing Time_MP"] >= 5) & (df["Playing Time_Min"] >= 150)].reset_index(drop=True)

    return df, None

# Team-level scraping function
def get_fbref_team_stats(stat_type, season_str, league_name):
    # URL construction
    league_id = league_id_dict[league_name]
    league_name_url = league_name.replace(" ", "-")
    stat_suffix = stat_type_dict[stat_type]
    url = f"https://fbref.com/en/comps/{league_id}/{season_str}/{stat_suffix}/{season_str}-{league_name_url}-Stats"

    headers = {'User-Agent': 'Mozilla/5.0'}
    req = Request(url, headers=headers)

    # Try to load page
    try:
        html = urlopen(req)
        print(f"Requesting team URL: {url}")
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        return None, f"Error loading team stats page: {e}"

    # --- Helper: find table by caption ---
    def find_table_by_caption(soup, caption_startswith="Squad"):
        # First check visible tables
        for table in soup.find_all("table"):
            caption = table.find("caption")
            if caption and caption.text.strip().startswith(caption_startswith):
                return table
        # Then check within HTML comments
        comments = soup.find_all(string=lambda text: isinstance(text, Comment))
        for comment in comments:
            comment_soup = BeautifulSoup(comment, "html.parser")
            for table in comment_soup.find_all("table"):
                caption = table.find("caption")
                if caption and caption.text.strip().startswith(caption_startswith):
                    return table
        return None

    table_html = find_table_by_caption(soup, caption_startswith="Squad")

    if table_html is None:
        return None, f"No team-level table found for stat type '{stat_type}'"

    # Parse table into DataFrame
    try:
        df = pd.read_html(StringIO(str(table_html)), flavor='lxml')[0]
    except Exception as e:
        return None, f"Error parsing table HTML: {e}"

    # Clean table
    df = df[df[df.columns[0]] != df.columns[0]]
    df.reset_index(drop=True, inplace=True)

    # Flatten column names
    df.columns = [
        col[1] if col[0].startswith('Unnamed') or col[0] == col[1]
        else f"{col[0]}_{col[1]}"
        for col in df.columns
    ]

    # Convert numeric columns
    non_numeric_cols = {"Squad", "Country"}
    for col in df.columns:
        if col not in non_numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    df.fillna(0, inplace=True)

    return df, None

# Collecting all 8 leagues data
def build_all_leagues_df(stat_type, season_str, league_list):
    all_dfs = []

    for league in league_list:
        df, error = get_fbref_stats(stat_type=stat_type, season_str=season_str, league_name=league)
        if df is not None:
            df["League"] = league  # Tag the league name
            all_dfs.append(df)
        else:
            print(f"Skipped {league} due to error: {error}")

    if not all_dfs:
        return None, "No data could be loaded for any league."

    df_all = pd.concat(all_dfs, ignore_index=True)
    return df_all, None