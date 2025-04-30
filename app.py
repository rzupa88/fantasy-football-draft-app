from flask import Flask, request, redirect, url_for
import pandas as pd
import os

app = Flask(__name__)

def generate_draft_order(teams):
    """Generate snake draft order for 12 teams."""
    draft_order = []
    for round_num in range(1, 19):
        if round_num % 2 == 1:
            for i, team in enumerate(teams, 1):
                draft_order.append({'team': team, 'round': round_num, 'pick': (round_num - 1) * 12 + i})
        else:
            for i, team in enumerate(reversed(teams), 1):
                draft_order.append({'team': team, 'round': round_num, 'pick': (round_num - 1) * 12 + i})
    return pd.DataFrame(draft_order)

@app.route('/', methods=['GET'])
def index():
    """Redirect to home page."""
    return redirect(url_for('home'))

@app.route('/home', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        teams = [request.form.get(f'team{i}') for i in range(1, 13)]
        user_team = request.form.get('user_team')
        if all(teams) and len(set(teams)) == 12 and user_team in teams:
            pd.DataFrame(teams, columns=['team']).to_csv('teams.csv', index=False)
            pd.DataFrame([user_team], columns=['user_team']).to_csv('user_team.csv', index=False)
            return redirect(url_for('draft'))
        else:
            error = "Please enter 12 unique team names and select your team."
    else:
        error = None
    
    teams = ['Team ' + str(i) for i in range(1, 13)]
    user_team = teams[0]
    if pd.io.common.file_exists('teams.csv'):
        teams_df = pd.read_csv('teams.csv')
        teams = teams_df['team'].tolist()[:12]
        if pd.io.common.file_exists('user_team.csv'):
            user_team = pd.read_csv('user_team.csv')['user_team'].iloc[0]
    
    team_inputs = ''.join(
        f'<label>Team {i}:</label><input type="text" name="team{i}" value="{teams[i-1]}" required><br>'
        for i in range(1, 13)
    )
    team_options = ''.join(
        f'<option value="{team}" {"selected" if team == user_team else ""}>{team}</option>'
        for team in teams
    )
    
    return f"""
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }}
        h1 {{ color: #333; text-align: center; }}
        .form-container {{ max-width: 600px; margin: auto; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        input, select {{ width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ccc; border-radius: 4px; }}
        input[type="submit"] {{ background: #28a745; color: white; cursor: pointer; }}
        input[type="submit"]:hover {{ background: #218838; }}
        .error {{ color: red; text-align: center; }}
    </style>
    <h1>Fantasy Football Draft Setup</h1>
    <div class="form-container">
        <h2>Enter Team Names (Draft Order)</h2>
        <p class="error">{error if error else ''}</p>
        <form method="post">
            {team_inputs}
            <label>Your Team:</label>
            <select name="user_team" required>
                {team_options}
            </select><br>
            <input type="submit" value="Save and Start Draft">
        </form>
    </div>
    """

@app.route('/draft', methods=['GET', 'POST'])
def draft():
    if not pd.io.common.file_exists('teams.csv') or not pd.io.common.file_exists('user_team.csv'):
        return redirect(url_for('home'))
    teams_df = pd.read_csv('teams.csv')
    teams = teams_df['team'].tolist()
    if len(teams) != 12:
        return redirect(url_for('home'))
    user_team = pd.read_csv('user_team.csv')['user_team'].iloc[0]
    
    draft_order = generate_draft_order(teams)
    
    stats = pd.read_csv('players.csv')
    stats = stats.fillna(0)
    stats['fantasy_points_ppr'] = (
        stats['Rush Yds'] * 0.1 + stats['Rush TD'] * 6 +
        stats['Rec Recept'] * 1 + stats['Rec Yds'] * 0.1 + stats['Rec TD'] * 6 +
        stats['Pass Yds'] * 0.04 + stats['Pass TD'] * 4 - stats['Pass Int'] * 2 -
        stats['FmbL'] * 2 + (stats['2PM'] + stats['2PP']) * 2
    )
    stats['Player'] = stats['Player'].str.replace(r'[\*\+]', '', regex=True)
    
    your_draft = pd.read_csv('draft.csv') if pd.io.common.file_exists('draft.csv') else pd.DataFrame(columns=['round', 'pick', 'player_name', 'position'])
    other_draft = pd.read_csv('other_teams_draft.csv') if pd.io.common.file_exists('other_teams_draft.csv') else pd.DataFrame(columns=['team', 'round', 'pick', 'player_name', 'position'])
    
    if request.method == 'POST' and 'your_draft' in request.form:
        pick_id = int(request.form['pick_id'])
        player_info = request.form['player'].split('|')
        player_name = player_info[0]
        position = player_info[1]
        pick_info = draft_order.iloc[pick_id]
        new_pick = pd.DataFrame([[pick_info['round'], pick_info['pick'], player_name, position]], columns=['round', 'pick', 'player_name', 'position'])
        your_draft = pd.concat([your_draft, new_pick], ignore_index=True)
        your_draft.to_csv('draft.csv', index=False)
    
    if request.method == 'POST' and 'other_draft' in request.form:
        pick_id = int(request.form['other_pick_id'])
        player_info = request.form['other_player'].split('|')
        player_name = player_info[0]
        position = player_info[1]
        pick_info = draft_order.iloc[pick_id]
        new_pick = pd.DataFrame([[pick_info['team'], pick_info['round'], pick_info['pick'], player_name, position]], columns=['team', 'round', 'pick', 'player_name', 'position'])
        other_draft = pd.concat([other_draft, new_pick], ignore_index=True)
        other_draft.to_csv('other_teams_draft.csv', index=False)
    
    position_filter = request.form.get('position_filter', 'All') if request.method == 'POST' and 'filter' in request.form else 'All'
    all_drafted = pd.concat([your_draft[['player_name']], other_draft[['player_name']]], ignore_index=True)
    available = stats[~stats['Player'].isin(all_drafted['player_name'])] if not all_drafted.empty else stats
    
    all_picks = pd.concat([your_draft[['round', 'pick']], other_draft[['round', 'pick']]], ignore_index=True)
    last_pick = all_picks['pick'].max() if not all_picks.empty else 0
    current_pick_id = draft_order[draft_order['pick'] > last_pick]['pick'].idxmin() if last_pick < draft_order['pick'].max() else 0
    current_pick = draft_order.iloc[current_pick_id]
    current_pick_text = f"Current Pick: {current_pick['team']} (Round {current_pick['round']}, Pick {current_pick['pick']})"
    
    best_available = available.nlargest(1, 'fantasy_points_ppr')[['Player', 'FantPos', 'fantasy_points_ppr']]
    best_available_text = (
        f"Best Available: {best_available.iloc[0]['Player']} ({best_available.iloc[0]['FantPos']}, "
        f"{best_available.iloc[0]['fantasy_points_ppr']:.1f} projected points)"
    ) if not best_available.empty else "No players left."
    
    roster = your_draft.groupby('position').size().to_dict()
    required = {'QB': 1, 'RB': 2, 'WR': 2, 'TE': 1, 'FLEX': 1, 'DST': 1, 'K': 1}
    needs = [pos for pos, count in required.items() if roster.get(pos, 0) < count and pos not in ['DST', 'K']]
    needs_text = f"Position Needs: {', '.join(needs) if needs else 'None'}"
    
    top_threshold = available['fantasy_points_ppr'].quantile(0.8)
    scarcity = available[available['fantasy_points_ppr'] >= top_threshold].groupby('FantPos').size().to_dict()
    scarcity_text = "Scarcity (Top Players Left): " + ', '.join(f"{pos}: {count}" for pos, count in scarcity.items()) if scarcity else "No elite players left."
    
    dropdown_options = [
        f"<option value='{row['Player']}|{row['FantPos']}'>{row['Player']} ({row['FantPos']}, {row['fantasy_points_ppr']:.1f} points)</option>"
        for _, row in available.iterrows()
    ]
    dropdown_html = f"<select name='player' required>{''.join(dropdown_options)}</select>" if dropdown_options else "<p>No players available.</p>"
    other_dropdown_html = f"<select name='other_player' required>{''.join(dropdown_options)}</select>" if dropdown_options else "<p>No players available.</p>"
    
    position_options = ['All', 'QB', 'RB', 'WR', 'TE', 'DST', 'K']
    filter_options = ''.join(
        f'<option value="{pos}" {"selected" if pos == position_filter else ""}>{pos}</option>'
        for pos in position_options
    )
    top_players = available if position_filter == 'All' else available[available['FantPos'] == position_filter]
    top_players = top_players[['Player', 'FantPos', 'fantasy_points_ppr']].nlargest(10, 'fantasy_points_ppr')
    table = top_players.to_html(index=False, classes='player-table')
    your_draft_table = your_draft.to_html(index=False, classes='draft-table') if not your_draft.empty else "<p>No picks yet.</p>"
    other_draft_table = other_draft.to_html(index=False, classes='draft-table') if not other_draft.empty else "<p>No other team picks yet.</p>"
    
    reset_js = """
    <script>
        function confirmReset() {
            const a = Math.floor(Math.random() * 9) + 1;
            const b = Math.floor(Math.random() * 9) + 1;
            const answer = a + b;
            const userAnswer = prompt(`Are you sure you want to reset the draft? This will clear all picks.\\nSolve: ${a} + ${b} = ?`);
            if (userAnswer == null) {
                return;
            }
            if (parseInt(userAnswer) === answer) {
                window.location.href = '/reset';
            } else {
                alert('Incorrect answer. Draft not reset.');
            }
        }
    </script>
    """
    
    return f"""
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; }}
        h1, h2 {{ color: #333; }}
        .container {{ max-width: 800px; margin: auto; padding: 20px; background: white; border-radius: 8px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        .form-container, .insights {{ margin-bottom: 20px; }}
        input, select {{ width: 100%; padding: 8px; margin: 5px 0; border: 1px solid #ccc; border-radius: 4px; }}
        input[type="submit"], .reset-button {{ background: #28a745; color: white; cursor: pointer; width: auto; padding: 10px 20px; border: none; border-radius: 4px; }}
        input[type="submit"]:hover, .reset-button:hover {{ background: #218838; }}
        .reset-button {{ background: #dc3545; }}
        .reset-button:hover {{ background: #c82333; }}
        .player-table, .draft-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; }}
        .player-table th, .draft-table th {{ background: #007bff; color: white; padding: 10px; }}
        .player-table td, .draft-table td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
        .current-pick {{ font-weight: bold; color: #d32f2f; }}
        .nav-link {{ margin: 10px 0; display: inline-block; }}
        .user-team {{ font-weight: bold; color: #28a745; }}
        @media (max-width: 600px) {{ .container {{ padding: 10px; }} input, select {{ font-size: 14px; }} }}
    </style>
    {reset_js}
    <h1>My Fantasy Football Draft</h1>
    <div class="container">
        <p class="user-team">Your Team: {user_team}</p>
        <p class="current-pick">{current_pick_text}</p>
        <a href="/home" class="nav-link">Return to Team Setup</a>
        <button class="reset-button" onclick="confirmReset()">Reset Draft</button>
        <div class="insights">
            <h2>AI Draft Insights</h2>
            <p>{best_available_text}</p>
            <p>{needs_text}</p>
            <p>{scarcity_text}</p>
        </div>
        <div class="form-container">
            <h2>Draft Your Player</h2>
            <form method="post">
                <input type="hidden" name="your_draft" value="true">
                <input type="hidden" name="pick_id" value="{current_pick_id}">
                <label>Player:</label>{dropdown_html}<br>
                <input type="submit" value="Draft Player">
            </form>
        </div>
        <div class="form-container">
            <h2>Draft Other Team's Player</h2>
            <form method="post">
                <input type="hidden" name="other_draft" value="true">
                <input type="hidden" name="other_pick_id" value="{current_pick_id}">
                <label>Player:</label>{other_dropdown_html}<br>
                <input type="submit" value="Add Other Team Pick">
            </form>
        </div>
        <div class="form-container">
            <h2>Filter Top 10 Available Players</h2>
            <form method="post">
                <input type="hidden" name="filter" value="true">
                <label>Position:</label>
                <select name="position_filter">
                    {filter_options}
                </select><br>
                <input type="submit" value="Apply Filter">
            </form>
        </div>
        <h2>Top 10 Available Players (Projected Points)</h2>
        {table}
        <h2>Your Draft Picks</h2>
        {your_draft_table}
        <h2>Other Teams' Draft Picks</h2>
        {other_draft_table}
    </div>
    """

@app.route('/reset', methods=['POST', 'GET'])
def reset():
    if pd.io.common.file_exists('draft.csv'):
        os.remove('draft.csv')
    if pd.io.common.file_exists('other_teams_draft.csv'):
        os.remove('other_teams_draft.csv')
    return redirect(url_for('draft'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)