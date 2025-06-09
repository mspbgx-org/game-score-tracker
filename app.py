from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///games.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Models
class Game(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    mode = db.Column(db.String(50), nullable=False, default='sum_high')  # sum_high, sum_low, placement
    matches = db.relationship('Match', backref='game', lazy=True)

class Match(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('game.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    rounds = db.relationship('Round', backref='match', lazy=True)
    players = db.relationship('Player', backref='match', lazy=True)

class Round(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    number = db.Column(db.Integer, nullable=False)
    results = db.relationship('Result', backref='round', lazy=True)

class Player(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('match.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    results = db.relationship('Result', backref='player', lazy=True)

class Result(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    round_id = db.Column(db.Integer, db.ForeignKey('round.id'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('player.id'), nullable=False)
    score = db.Column(db.Integer, nullable=False)

# Helpers
def calculate_totals(match):
    totals = {}
    if match.game.mode.startswith("sum"):
        for player in match.players:
            totals[player.id] = sum(r.score for r in player.results)
    elif match.game.mode == "placement":
        round_count = {}
        placement_sum = {}
        for round in match.rounds:
            scores = sorted(round.results, key=lambda r: r.score)
            for i, result in enumerate(scores):
                placement_sum[result.player_id] = placement_sum.get(result.player_id, 0) + i + 1
                round_count[result.player_id] = round_count.get(result.player_id, 0) + 1
        for pid in placement_sum:
            totals[pid] = placement_sum[pid] / round_count[pid]
    return totals

@app.route('/')
def index():
    games = Game.query.all()
    return render_template('index.html', games=games)

@app.route('/game/<int:game_id>')
def view_game(game_id):
    game = Game.query.get_or_404(game_id)
    return render_template('game.html', game=game, calculate_totals=calculate_totals)

@app.route('/add_game', methods=['POST'])
def add_game():
    name = request.form.get('name')
    mode = request.form.get('mode')
    if name and mode:
        db.session.add(Game(name=name, mode=mode))
        db.session.commit()
    return redirect(url_for('index'))

@app.route('/add_match/<int:game_id>', methods=['POST'])
def add_match(game_id):
    match = Match(game_id=game_id)
    db.session.add(match)
    db.session.commit()
    return redirect(url_for('view_game', game_id=game_id))

@app.route('/add_player/<int:match_id>', methods=['POST'])
def add_player(match_id):
    name = request.form.get('name')
    if name:
        db.session.add(Player(match_id=match_id, name=name))
        db.session.commit()
    match = Match.query.get(match_id)
    return redirect(url_for('view_game', game_id=match.game_id))

@app.route('/add_round/<int:match_id>', methods=['POST'])
def add_round(match_id):
    match = Match.query.get(match_id)
    next_number = max([r.number for r in match.rounds], default=0) + 1
    new_round = Round(match_id=match_id, number=next_number)
    db.session.add(new_round)
    db.session.commit()
    for player in match.players:
        score = request.form.get(f'score_{player.id}')
        if score:
            db.session.add(Result(round_id=new_round.id, player_id=player.id, score=int(score)))
    db.session.commit()
    return redirect(url_for('view_game', game_id=match.game_id))

if __name__ == '__main__':
    os.makedirs("templates", exist_ok=True)
    with open("templates/index.html", "w") as f:
        f.write("""
<!doctype html>
<html>
<head><title>Games</title></head>
<body>
<h1>Games</h1>
<ul>
{% for game in games %}
  <li><a href="/game/{{ game.id }}">{{ game.name }}</a> ({{ game.mode }})</li>
{% endfor %}
</ul>
<form action="/add_game" method="post">
    <input name="name" placeholder="New game name">
    <select name="mode">
        <option value="sum_high">Sum (highest wins)</option>
        <option value="sum_low">Sum (lowest wins)</option>
        <option value="placement">Placement</option>
    </select>
    <button type="submit">Add Game</button>
</form>
</body>
</html>
""")

    with open("templates/game.html", "w") as f:
        f.write("""
<!doctype html>
<html>
<head><title>{{ game.name }}</title>
<style>
.green { background-color: lightgreen; font-weight: bold; }
</style>
</head>
<body>
<h1>{{ game.name }} <small>({{ game.mode }})</small></h1>
<h2>Matches</h2>
<ul>
{% for match in game.matches %}
    <li>
        <strong>Match {{ loop.index }} ({{ match.created_at }})</strong>
        <form action="/add_player/{{ match.id }}" method="post">
            <input name="name" placeholder="Player name">
            <button type="submit">Add Player</button>
        </form>
        <table border="1">
            <thead>
                <tr>
                    <th>Round</th>
                    {% for player in match.players %}
                        <th>{{ player.name }}</th>
                    {% endfor %}
                </tr>
            </thead>
            <tbody>
                {% for round in match.rounds %}
                    <tr>
                        <td>{{ round.number }}</td>
                        {% for player in match.players %}
                            <td>
                            {% for result in round.results %}
                                {% if result.player_id == player.id %}
                                    {{ result.score }}
                                {% endif %}
                            {% endfor %}
                            </td>
                        {% endfor %}
                    </tr>
                {% endfor %}
                <tr>
                    <td><strong>Total</strong></td>
                    {% set totals = calculate_totals(match) %}
                    {% if totals %}
                        {% if game.mode == 'sum_high' %}
                            {% set best = totals.values() | max %}
                        {% elif game.mode == 'sum_low' or game.mode == 'placement' %}
                            {% set best = totals.values() | min %}
                        {% else %}
                            {% set best = None %}
                        {% endif %}
                    {% else %}
                        {% set best = None %}
                    {% endif %}
                    {% for player in match.players %}
                        {% set value = totals.get(player.id, '-') %}
                        <td class="{{ 'green' if best is not none and value == best else '' }}">
                            {% if game.mode == 'placement' and value != '-' %}
                                {{ value|round(2) }}
                            {% else %}
                                {{ value }}
                            {% endif %}
                        </td>
                    {% endfor %}
                </tr>
            </tbody>
        </table>
        <form action="/add_round/{{ match.id }}" method="post">
            {% for player in match.players %}
                <input name="score_{{ player.id }}" placeholder="{{ player.name }}'s score">
            {% endfor %}
            <button type="submit">Add Round</button>
        </form>
    </li>
{% endfor %}
</ul>
<form action="/add_match/{{ game.id }}" method="post">
    <button type="submit">Add Match</button>
</form>
<a href="/">Back</a>
</body>
</html>
""")

    with app.app_context():
        db.create_all()
    app.run(debug=True)
