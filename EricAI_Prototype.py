import subprocess
import sys
import io
import os
import re

# 1. Force-install all required libraries directly through the active code runtime
for package in ["python-chess", "ollama"]:
    try:
        __import__(package.replace("-", ""))
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])

import streamlit as st
import chess.pgn
import chess.engine
import ollama

# 2. Initialize luxury dark theme layout
st.set_page_config(page_title="EricAI Pro ♝ // GM Analytics Engine", layout="wide")

# 3. Inject CSS for custom glass card styling, dark background, and amber branding
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    * { font-family: 'Inter', sans-serif !important; }
    body, .stApp { background: radial-gradient(circle at 10% 10%, rgba(130, 90, 245, 0.18), transparent 30%), #0d0e11 !important; color: #f4f4f5 !important; }
    [data-testid="stSidebar"] { background: #12141c !important; border-right: 1px solid rgba(255,255,255,0.08); }
    .main h1, .main h2, .main h3, .main p, .main span { color: #ffffff !important; }
    .premium-card { background: rgba(20, 24, 40, 0.92); border: 1px solid rgba(255,255,255,0.08); box-shadow: 0 25px 60px rgba(0,0,0,0.24); padding: 26px; border-radius: 22px; margin-bottom: 26px; }
    .metric-card { background: linear-gradient(160deg, rgba(18, 22, 38, 0.95), rgba(28, 30, 50, 0.95)); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 26px; min-height: 150px; display: flex; flex-direction: column; justify-content: center; }
    .metric-value { font-size: 42px; font-weight: 800; color: #f59e0b; line-height: 1.02; margin-bottom: 8px; }
    .metric-label { font-size: 12px; color: #c5c5d1; letter-spacing: 1.4px; text-transform: uppercase; margin-bottom: 8px; display: block; }
    .hero-banner { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 24px; padding: 28px; margin-bottom: 26px; }
    .hero-banner h2 { margin: 0 0 10px; font-size: 34px; line-height: 1.05; }
    .hero-banner p { margin: 0; color: #d4d4d8; font-size: 15px; line-height: 1.75; }
    .sidebar-note { background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.18); color: #f8e7c2; padding: 16px; border-radius: 16px; margin-top: 18px; }
    .stButton>button { background-color: #f59e0b !important; color: #0f172a !important; border: none !important; box-shadow: 0 10px 20px rgba(245,158,11,0.24) !important; }
    .stButton>button:hover { background-color: #fbbf24 !important; }
    .stChatMessage { background: rgba(255,255,255,0.04) !important; border-radius: 18px !important; padding: 16px !important; }
    </style>
""", unsafe_allow_html=True)

st.markdown("<h1 style='font-weight: 700; letter-spacing: -1.5px;'>EricAI Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #71717a; font-size: 14px; margin-bottom: 0.25rem;'>HYBRID STOCKFISH REASONING & ANALYTICAL REVIEW PLATFORM</p>", unsafe_allow_html=True)
st.write("---")
st.markdown("""
    <div class='hero-banner'>
        <h2>Chess analysis that feels premium.</h2>
        <p>Upload your PGN file and let EricAI Pro surface opening leverage, collapse points, and precise tactical coaching in a polished dark interface.</p>
    </div>
""", unsafe_allow_html=True)

# Initialize persistent session state properties
if "stats" not in st.session_state: st.session_state.stats = None
if "messages" not in st.session_state: st.session_state.messages = []

# Create Interactive Inputs inside the Sidebar
st.sidebar.markdown("<h2 style='font-size: 18px;'>Data Intake</h2>", unsafe_allow_html=True)
uploaded_file = st.sidebar.file_uploader("Upload historic .pgn data matches", type=["pgn"])
analyze_button = st.sidebar.button("Execute Deep Engine Audit")
st.sidebar.markdown("<div class='sidebar-note'><strong>Pro tip:</strong> Use recent clean PGN exports for the most accurate opening and blunder signals.</div>", unsafe_allow_html=True)
st.sidebar.markdown("---")
st.sidebar.markdown("### Quick Start")
st.sidebar.write("- Upload a PGN file")
st.sidebar.write("- Execute the deep audit")
st.sidebar.write("- Chat with Coach EricAI Pro")
# Create Interactive Inputs inside the Sidebar
st.sidebar.markdown("<h2 style='font-size: 18px;'>Data Intake</h2>", unsafe_allow_html=True)

# 👈 ADD THIS EXACT LINE HERE
target_user = st.sidebar.text_input("User Chess Username", value="", placeholder="e.g., GothamChess")


# --- 4. COMPREHENSIVE TRANSPOSITION OPENING BOOK (100+ OPENINGS) ---
def identify_opening_by_moves(game_node):
    opening_book = {
        # --- e4 e5 OPEN GAMES & DERIVATIVES ---
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": "King's Pawn Game",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Open Game (1...e5)",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": "King's Knight Opening",
        "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": "Petrov's Defense",
        "rnbqkbnr/pp1p1ppp/8/2p1p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": "Elephant Gambit",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/2N5/PPPP1PPP/R1BQKBNR b KQkq -": "Vienna Game",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5P2/PPPP1PPP/RNBQKBNR b KQkq -": "Barnes Opening",
        "rnbqkbnr/pppp1ppp/8/4p3/2P1P3/8/PP1P1PPP/RNBQKBNR b KQkq -": "King's Pawn: Whale Variation",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq d6 0 2": "King's Pawn: Damiano Defense",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5Q2/PPPP1PPP/RNBQKBNR b KQkq -": "Napoleon Opening",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/2P5/PP1P1PPP/RNBQKBNR b KQkq -": "Lopez Opening",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq f5 0 2": "King's Gambit",
        "rnbqkbnr/pppp1ppp/8/4p3/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": "Center Game",
        "rnbqkbnr/pp1p1ppp/8/2p5/4P3/5N2/PPP2PPP/RNBQKB1R b KQkq -": "Open Sicilian Setup",
        
        # --- ITALIAN / RUY LOPEZ / SCOTCH / FOUR KNIGHTS ---
        "rnbqkb1r/pppp1ppp/5n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -": "Italian Game: Two Knights Defense",
        "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -": "Italian Game",
        "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 1 3": "Italian Game: Mainline",
        "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 2 3": "Italian: Giuoco Piano",
        "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 3 3": "Italian: Evans Gambit",
        "r1bqkbnr/pppp1ppp/2n5/4p3/1B2P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": "Ruy Lopez (Spanish Opening)",
        "r1bqkbnr/pppp1ppp/2n5/4p3/1B2P3/5N2/PPPP1PPP/RNBQKB1R a6 0 3": "Ruy Lopez: Morphy Defense",
        "r1bqkbnr/pppp1ppp/2n5/4p3/1B2P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 3": "Ruy Lopez: Berlin Defense",
        "r1bqkbnr/pppp1ppp/2n5/4p3/1B2P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 2 3": "Ruy Lopez: Schliemann Defense",
        "r1bqkbnr/pppp1ppp/2n5/4p3/1B2P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 3 3": "Ruy Lopez: Steinitz Defense",
        "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq -": "Scotch Game",
        "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 1 3": "Scotch Gambit",
        "r1bqkbnr/pppp1ppp/2n5/4p3/3PP3/5N2/PPP2PPP/RNBQKB1R b KQkq - 2 3": "Scotch: Mieses Variation",
        "r1bqkbnr/pp1p1ppp/2n5/2p1p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq -": "Italian: Anti-Fried Liver",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/4P3/2N2N2/PPPP1PPP/R1BQKB1R w KQkq -": "Four Knights Game",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/2N2N2/PPPP1PPP/R1BQK2R b KQkq -": "Four Knights: Italian Variation",
        "r1bqkb1r/pppp1ppp/2n2n2/4p3/1B2P3/2N2N2/PPPP1PPP/R1BQKB1R b KQkq -": "Four Knights: Spanish Variation",
        "r1bqkbnr/pppp1ppp/2n5/4p3/4P3/2P5/PP1P1PPP/RNBQKBNR b KQkq -": "Ponziani Opening",

        # --- e4 SEMI-OPEN GAMES (SICILIAN, FRENCH, CARO-KANN) ---
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Sicilian Defense",
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": "Sicilian Defense: 2.Nf3",
        "rnbqkbnr/pp2pppp/3p4/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": "Sicilian: Traditional Variations",
        "r1bqkbnr/pp1ppppp/2n5/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": "Sicilian: Old / Closed Lines",
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/2C5/PPPP1PPP/R1BQKBNR b KQkq -": "Closed Sicilian",
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/2P5/PP1P1PPP/RNBQKBNR b KQkq -": "Sicilian: Alapin Variation",
        "rnbqkbnr/pp1ppppp/8/2p5/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": "Sicilian: Smith-Morra Gambit",
        "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "French Defense",
        "rnbqkbnr/pppp1ppp/4p3/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": "French Defense: Normal",
        "rnbqkbnr/pppp1ppp/4p3/4P3/8/8/PPPP1PPP/RNBQKBNR b KQkq -": "French Defense: Advance Variation",
        "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Caro-Kann Defense",
        "rnbqkbnr/pp1ppppp/2p5/8/3PP3/8/PPP2PPP/RNBQKBNR b KQkq -": "Caro-Kann Defense: Mainline",
        "rnbqkbnr/pp2pppp/8/3p5/3P5/8/PPP2PPP/RNBQKBNR w KQkq -": "Caro-Kann: Exchange Variation",
        "rnbqkbnr/pp2pppp/8/3pP3/8/8/PPPP1PPP/RNBQKBNR w KQkq -": "Caro-Kann: Advance Variation",
        "rnbqkbnr/pppppp1p/6p1/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Modern Defense / Robatsch",
        "rnbqkb1r/pppppp1p/5np1/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Pirc Defense",
        "rnbqkbnr/pp2pppp/2pp4/8/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": "Caro-Kann: Breyer Setup",
        "rnbqkbnr/ppp1pppp/3p4/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Pirc: Early Line",

        # --- d4 CLOSED GAMES (QUEEN'S GAMBIT, SLAV, INDIAN) ---
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPPP1PPP/RNBQKBNR b KQkq -": "Queen's Pawn Game",
        "rnbqkbnr/pppp1ppp/8/4p3/3P4/8/PPPP1PPP/RNBQKBNR w KQkq -": "Englund Gambit",
        "rnbqkbnr/ppp1pppp/8/3p4/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -": "Queen's Pawn Game: 2.d5",
        "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq -": "Queen's Gambit",
        "rnbqkbnr/ppp2ppp/4p3/3p4/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": "Queen's Gambit Declined",
        "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq - 1 2": "Queen's Gambit Accepted",
        "rnbqkbnr/pp1ppppp/8/2p5/2PP4/8/PP2PPPP/RNBQKBNR b KQkq -": "Slav Defense",
        "rnbqkbnr/pp1ppppp/2p5/3p4/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": "Slav Defense: Traditional",
        "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -": "Indian Defense",
        "rnbqkb1r/pppppppp/5n2/8/2PP4/8/PP2PPPP/RNBQKBNR b KQkq -": "Indian Defense: Normal",
        "rnbqkb1r/pppp1ppp/4pn2/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": "Nimzo-Indian / Bogo-Indian Setup",
        "rnbqkb1r/pppppp1p/5np1/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": "King's Indian / Grünfeld Setup",
        "rnbqkb1r/pp1ppp1p/2p2np1/8/2PP4/8/PP2PPPP/RNBQKBNR w KQkq -": "King's Indian: Slav Setup",
        "rnbqkbnr/ppp1pppp/8/3p4/3P4/5N2/PPP1PPPP/RNBQKB1R b KQkq -": "Queen's Pawn: 2.Nf3",
        "rnbqkbnr/pp1ppppp/8/2p5/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -": "Benoni: Old Line",
        "rnbqkbnr/pp1ppppp/8/2p5/3P4/5N2/PPP1PPPP/RNBQKB1R b KQkq -": "Benoni Defense: 2.Nf3",
        "rnbqkbnr/ppppp1pp/8/5p2/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -": "Dutch Defense",

        # --- FLANK OPENINGS & IRREGULAR LINES ---
        "rnbqkbnr/pppppppp/8/8/2P5/8/PP1P1PPP/RNBQKBNR b KQkq -": "English Opening",
        "rnbqkbnr/pppp1ppp/8/4p3/2P5/8/PP1P1PPP/RNBQKBNR w KQkq -": "English Opening: King's English",
        "rnbqkb1r/pppppppp/5n2/8/2P5/8/PP1P1PPP/RNBQKBNR w KQkq -": "English Opening: Anglo-Indian",
        "rnbqkbnr/pp1ppppp/8/2p5/2P5/8/PP1P1PPP/RNBQKBNR w KQkq -": "English Opening: Symmetrical",
        "rnbqkbnr/pppppppp/8/8/8/2N5/PPPPPPPP/R1BQKBNR b KQkq -": "Nimzowitsch Opening / Dunst",
        "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 1 1": "Standard Start Position",
        "rnbqkbnr/pppppppp/8/8/8/7P/PPPPPPP1/RNBQKBNR b KQkq -": "Grob Opening",
        "rnbqkbnr/pppppppp/8/8/1P6/8/P1PPPPPP/RNBQKBNR b KQkq -": "Sokolsky / Polish Opening",
        "rnbqkbnr/pppppppp/8/8/1P6/8/P1PPPPPP/RNBQKBNR b KQkq - 1 1": "Polish Opening",
"rnbqkbnr/pppppppp/8/8/3F4/8/PPPP1PPP/RNBQKBNR b KQkq -": "Bird's Opening","rnbqkbnr/pppppppp/8/8/8/6P1/PPPPPP1P/RNBQKBNR b KQkq -": "Benko Opening / King's Fianchetto","rnbqkbnr/pppppppp/8/8/8/5N2/PPPPPPPP/RNBQKB1R b KQkq - 1 1": "Reti System"
    }
    board = game_node.board()
    # Trace steps backward through actual node stack history to handle transpositions safely
    while board.move_stack:
        current_epd = board.epd()
        if current_epd in opening_book:
            return opening_book[current_epd]
        board.pop()
    root_epd = chess.Board().epd()
    if root_epd in opening_book:
        return opening_book[root_epd]
    return "Custom System Setup"

# --- 5. DEEP BACKEND STOCKFISH PROCESSING LOOP ---
# --- 5. DEEP USER-SPECIFIC STOCKFISH PROCESSING LOOP ---
def process_match_history_with_stockfish(file_wrapper, target_user, max_games=5):
    try:
        engine = chess.engine.SimpleEngine.popen_uci("stockfish")
    except Exception:
        st.error("❌ Stockfish is not globally active on your system path. Please open your Mac terminal and run: brew install stockfish")
        return 0, 0, "Unknown System", []

    total_games_counted = 0
    total_moves_before_blunder = 0
    openings_played_list = []
    engine_blunder_reports = []

    while total_games_counted < max_games:
        parsed_game = chess.pgn.read_game(file_wrapper)
        if parsed_game is None:
            break

        # Extract Profile Usernames from PGN Meta Tags
        white_player = parsed_game.headers.get("White", "").strip()
        black_player = parsed_game.headers.get("Black", "").strip()
        
        # Match user role to dynamic color assignment
        if target_user.lower() == white_player.lower():
            user_color = chess.WHITE
        elif target_user.lower() == black_player.lower():
            user_color = chess.BLACK
        else:
            user_color = chess.WHITE  # Fallback baseline
            
        total_games_counted += 1
        board = parsed_game.board()
        opening_label = identify_opening_by_moves(parsed_game)
        openings_played_list.append(opening_label)

        previous_evaluation = 0.0
        game_moves = list(parsed_game.mainline_moves())
        collapse_move_for_this_game = len(game_moves)

        for move_idx, move in enumerate(game_moves):
            # Track whose turn it is BEFORE pushing the move mutation
            is_user_turn = (board.turn == user_color)
            board.push(move)
            
            analysis_info = engine.analyse(board, chess.engine.Limit(time=0.02))
            score_object = analysis_info["score"].white()
            current_evaluation = score_object.score(mate_score=1000) / 100.0 if score_object.score() is not None else 0.0

            # Calculate evaluation drop dynamically relative to color side
            evaluation_drop = previous_evaluation - current_evaluation
            if user_color == chess.BLACK:
                evaluation_drop = -evaluation_drop

            # Only log a collapse if it happened strictly on the user's turn
            if is_user_turn and evaluation_drop >= 1.5:
                collapse_move_for_this_game = move_idx + 1
                engine_blunder_reports.append({
                    "game_id": total_games_counted,
                    "opening": opening_label,
                    "move_number": collapse_move_for_this_game,
                    "notation": str(move),
                    "loss_margin": round(evaluation_drop, 2),
                })
                break

            previous_evaluation = current_evaluation

        total_moves_before_blunder += collapse_move_for_this_game

    engine.quit()

    avg_collapse_move = int(total_moves_before_blunder / total_games_counted) if total_games_counted > 0 else 0
    favorite_system = max(set(openings_played_list), key=openings_played_list.count) if openings_played_list else "Unknown System"
    return total_games_counted, avg_collapse_move, favorite_system, engine_blunder_reports

# --- 6. OPTIMIZED AI PERSONA STRUCTURING ---
def generate_eric_ai_response(total_games, avg_collapse, favorite_opening, blunder_logs, chat_history, current_user_message=None):
    blunder_data_summary = ""
    for log in blunder_logs[:3]:
        blunder_data_summary += f"- Game {log['game_id']} ({log['opening']}): Blunder on Move {log['move_number']} ({log['notation']}), dropping evaluation by {log['loss_margin']} points.\n"

    system_prompt = f"""You are EricAI, a high-level Grandmaster chess analyst. Your answers are direct and completely factual.
You are interpreting mathematical output from a Stockfish backend analysis of the user's specific moves.
STOCKFISH SCIENTIFIC ENGINE INSIGHTS:
- Games Profiled: {total_games}
- Average Move Where User Positional Collapse/Blunder Occurs: Move {avg_collapse}
- Repertoire Base: {favorite_opening}
EXACT USER BLUNDER EVENT LOGS:
{blunder_data_summary if blunder_data_summary else "- No extreme evaluation drops detected on user turns."}
STRICT CHAT DIRECTIONS:
1. Speak like a real human Grandmaster coach. Never use plain text data tags like "GAMES PROFILED:" in your chat text output.
2. Give technical tactical insights based on the move numbers. If they blunder near move {avg_collapse}, tell them how to fix it.
3. Do not invent details or guess timelines. Stick entirely to the provided data."""

    messages_payload = [{'role': 'system', 'content': system_prompt}]
    for msg in chat_history:
        messages_payload.append({'role': msg['role'], 'content': msg['content']})

    if current_user_message:
        messages_payload.append({'role': 'user', 'content': current_user_message})
    else:
        messages_payload.append({'role': 'user', 'content': "Give me an expert grandmaster analysis of my performance engine logs."})

    try:
        ai_response = ollama.chat(
            model='llama3.2:3b',
            options={
                'temperature': 0.1,
                'top_p': 0.1,
                'num_gpu': 1,
            },
            messages=messages_payload
        )
        return ai_response['message']['content']
    except Exception as e:
        return f"Local generation engine error: {str(e)}"

# --- 7. CHAT & INTERFACE LOGIC COMPONENT ---
if uploaded_file is not None and analyze_button:
    if not target_user:
        st.error("Please enter your chess username in the sidebar input field before executing the audit configuration.")
    else:
        with st.spinner("Stockfish is filtering your profile moves..."):
            file_content = uploaded_file.getvalue().decode("utf-8")
            text_stream = io.StringIO(file_content)
            # Added target_user parameter mapping to pass user configuration details to function
            total, avg_collapse_val, favorite_system, blunder_logs = process_match_history_with_stockfish(text_stream, target_user)

        if total > 0:
            st.session_state.stats = {"total": total,"avg_moves": avg_collapse_val,"opening": favorite_system,"logs": blunder_logs}
            st.session_state.messages = []
            initial_reply = generate_eric_ai_response(total, avg_collapse_val, favorite_system, blunder_logs, [])
            st.session_state.messages.append({"role": "assistant", "content": initial_reply})

if st.session_state.stats:
    stats = st.session_state.stats
    st.markdown("### 📊 Engine Performance Intelligence")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"""
            <div class="metric-card">
                <span class="metric-label">Games Audited</span>
                <span class="metric-value">{stats["total"]}</span>
            </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
            <div class="metric-card">
                <span class="metric-label">Avg Move Before Collapse</span>
                <span class="metric-value">{stats["avg_moves"]}</span>
            </div>
        """, unsafe_allow_html=True)
    with col3:
        clean_opening = (stats['opening'][:22] + '...') if len(stats['opening']) > 22 else stats['opening']
        st.markdown(f"""
            <div class="metric-card">
                <span class="metric-label">Opening Profile Base</span>
                <span class="metric-value" style="font-size: 26px; font-weight: 700;">{clean_opening}</span>
            </div>
        """, unsafe_allow_html=True)

    st.markdown("### 💬 Chat with Coach EricAI Pro")
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if user_query := st.chat_input("Ask about specific move variations..."):
        with st.chat_message("user"):
            st.markdown(user_query)
        st.session_state.messages.append({"role": "user", "content": user_query})
        with st.chat_message("assistant"):
            with st.spinner("Reviewing centipawn data structures..."):
                coach_reply = generate_eric_ai_response(stats['total'], stats['avg_moves'], stats['opening'], stats['logs'], st.session_state.messages[:-1], user_query)
            st.markdown(coach_reply)
            st.session_state.messages.append({"role": "assistant", "content": coach_reply})

