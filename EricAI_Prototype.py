import io
import logging
import chess.pgn
import chess.engine
import ollama
import streamlit as st

# Configure logging for production auditing
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# --- PREMIUM STYLESHEET CONFIGURATION ---
st.set_page_config(page_title="EricAI Pro ♝ // Chess Intelligence Platform", layout="wide")

st.markdown("""
    <style>
    @import url('https://googleapis.com');
    * { font-family: 'Inter', sans-serif !important; }
    body, .stApp { background: radial-gradient(circle at 10% 10%, rgba(130, 90, 245, 0.18), transparent 30%), #0d0e11 !important; color: #f4f4f5 !important; }
    [data-testid="stSidebar"] { background: #12141c !important; border-right: 1px solid rgba(255,255,255,0.08); }
    .main h1, .main h2, .main h3, .main p, .main span { color: #ffffff !important; }
    .metric-card { background: linear-gradient(160deg, rgba(18, 22, 38, 0.95), rgba(28, 30, 50, 0.95)); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 26px; min-height: 150px; display: flex; flex-direction: column; justify-content: center; }
    .metric-value { font-size: 42px; font-weight: 800; color: #f59e0b; line-height: 1.02; margin-bottom: 8px; }
    .metric-label { font-size: 12px; color: #c5c5d1; letter-spacing: 1.4px; text-transform: uppercase; margin-bottom: 8px; display: block; }
    .hero-banner { background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 24px; padding: 28px; margin-bottom: 26px; }
    .hero-banner h2 { margin: 0 0 10px; font-size: 34px; line-height: 1.05; }
    .sidebar-note { background: rgba(245, 158, 11, 0.08); border: 1px solid rgba(245, 158, 11, 0.18); color: #f8e7c2; padding: 16px; border-radius: 16px; margin-top: 18px; }
    .stButton>button { background-color: #f59e0b !important; color: #0f172a !important; border: none !important; box-shadow: 0 10px 20px rgba(245,158,11,0.24) !important; width: 100%; }
    .stChatMessage { background: rgba(255,255,255,0.04) !important; border-radius: 18px !important; padding: 16px !important; }
    </style>
""", unsafe_allow_html=True)


class ChessOpeningBook:
    """Manages opening signature translations via historical FEN/EPD transposition arrays."""
    
    # Humanized design pattern: Moving massive structures to a localized class attribute
    OPENINGS = {
        "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq -": "King's Pawn Game",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Open Game (1...e5)",
        "rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": "King's Knight Opening",
        "rnbqkb1r/pppp1ppp/5n2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq -": "Petrov's Defense",
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Sicilian Defense",
        "rnbqkbnr/pp1ppppp/8/2p5/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq -": "Sicilian Defense: 2.Nf3",
        "rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "French Defense",
        "rnbqkbnr/pp1ppppp/2p5/8/4P3/8/PPPP1PPP/RNBQKBNR w KQkq -": "Caro-Kann Defense",
        "rnbqkbnr/pppppppp/8/8/3P4/8/PPPP1PPP/RNBQKBNR b KQkq -": "Queen's Pawn Game",
        "rnbqkbnr/ppp1pppp/8/3p4/2PP4/8/PP2PPPP/RNBQKBNR b KQkq -": "Queen's Gambit",
        "rnbqkb1r/pppppppp/5n2/8/3P4/8/PPP1PPPP/RNBQKBNR w KQkq -": "Indian Defense",
        "rnbqkbnr/pppppppp/8/8/2P5/8/PP1P1PPP/RNBQKBNR b KQkq -": "English Opening"
    }

    @classmethod
    def identify(cls, game_node: chess.pgn.Game) -> str:
        board = game_node.board()
        while board.move_stack:
            epd_signature = board.epd()
            if epd_signature in cls.OPENINGS:
                return cls.OPENINGS[epd_signature]
            board.pop()
            
        root_signature = chess.Board().epd()
        return cls.OPENINGS.get(root_signature, "Custom System Setup")


class StockfishAnalyzer:
    """Manages active communication tasks with the Stockfish UCI execution subsystem."""
    
    def __init__(self, target_user: str, max_games: int = 5):
        self.target_user = target_user.strip().lower()
        self.max_games = max_games

    def run_audit(self, file_wrapper: io.StringIO):
        try:
            engine = chess.engine.SimpleEngine.popen_uci("stockfish")
        except Exception as e:
            logging.error(f"Failed to start Stockfish binary subsystem: {str(e)}")
            st.error("❌ Stockfish execution failure. Ensure 'brew install stockfish' has been run locally.")
            return 0, 0, "Unknown Repertoire", []

        total_games = 0
        total_collapse_moves = 0
        openings_logged = []
        blunder_reports = []

        while total_games < self.max_games:
            game = chess.pgn.read_game(file_wrapper)
            if not game:
                break

            white = game.headers.get("White", "").strip().lower()
            black = game.headers.get("Black", "").strip().lower()
            
            if self.target_user == white:
                user_color = chess.WHITE
            elif self.target_user == black:
                user_color = chess.BLACK
            else:
                user_color = chess.WHITE

            total_games += 1
            board = game.board()
            opening_name = ChessOpeningBook.identify(game)
            openings_logged.append(opening_name)

            prev_eval = 0.0
            moves = list(game.mainline_moves())
            game_collapse_move = len(moves)

            for idx, move in enumerate(moves):
                is_user_move = (board.turn == user_color)
                board.push(move)

                info = engine.analyse(board, chess.engine.Limit(time=0.02))
                score = info["score"].white()
                current_eval = score.score(mate_score=1000) / 100.0 if score.score() is not None else 0.0

                eval_delta = prev_eval - current_eval
                if user_color == chess.BLACK:
                    eval_delta = -eval_delta

                if is_user_move and eval_delta >= 1.5:
                    game_collapse_move = idx + 1
                    blunder_reports.append({
                        "game_id": total_games,
                        "opening": opening_name,
                        "move_number": game_collapse_move,
                        "notation": str(move),
                        "loss_margin": round(eval_delta, 2)
                    })
                    break

                prev_eval = current_eval

            total_collapse_moves += game_collapse_move

        engine.quit()
        
        avg_collapse = int(total_collapse_moves / total_games) if total_games > 0 else 0
        primary_opening = max(set(openings_logged), key=openings_logged.count) if openings_logged else "Unknown"
        
        return total_games, avg_collapse, primary_opening, blunder_reports


def fetch_coach_review(total_games: int, avg_collapse: int, opening: str, blunders: list, history: list, message: str = None) -> str:
    summary = ""
    for log in blunders[:3]:
        summary += f"- Game {log['game_id']} ({log['opening']}): Blunder on Move {log['move_number']} ({log['notation']}), dropping {log['loss_margin']} points.\n"

    system_prompt = f"""You are EricAI, a professional chess Grandmaster reviewing structural user match files.
    
    FACTUAL INSIGHT MATRIX:
    - Total Profile Games: {total_games}
    - Average Tactical Focus Break: Move {avg_collapse}
    - Repertoire Preference Base: {opening}
    
    STOCKFISH CHRONICLE REQUISITION:
    {summary if summary else "- Matrix stable. Zero severe blunder deviations logged."}
    
    COMPLIANCE DIRECTION: Speak naturally. Do not dump dictionary titles like 'GAMES PROFILED' back to user outputs."""

    payload = [{"role": "system", "content": system_prompt}]
    for msg in history:
        payload.append({"role": msg["role"], "content": msg["content"]})
        
    payload.append({"role": "user", "content": message if message else "Provide a breakdown of my match performance records."})

    try:
        response = ollama.chat(
            model='llama3.2:3b',
            options={'temperature': 0.1, 'top_p': 0.1, 'num_gpu': 1},
            messages=payload
        )
        return response['message']['content']
    except Exception as e:
        return f"Model interaction variance caught: {str(e)}"


# --- APPLICATION DESKTOP WORKSPACE ---
st.markdown("<h1 style='font-weight: 700; letter-spacing: -1.5px;'>EricAI Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #71717a; font-size: 14px; margin-bottom: 0.25rem;'>HYBRID STOCKFISH REASONING & ANALYTICAL REVIEW PLATFORM</p>", unsafe_allow_html=True)
st.write("---")

st.markdown("""
    <div class='hero-banner'>
        <h2 style='color:#ffffff; margin:0 0 10px; font-size:28px;'>Performance Pipeline Engine</h2>
        <p>Isolate your exact performance signals. Upload PGN match histories below to map real-time blunder thresholds cleanly.</p>
    </div>
""", unsafe_allow_html=True)

if "stats" not in st.session_state: st.session_state.stats = None
if "messages" not in st.session_state: st.session_state.messages = []

# Sidebar Layout Design Configuration
st.sidebar.markdown("<h2 style='font-size: 18px;'>Data Control Panel</h2>", unsafe_allow_html=True)
username_input = st.sidebar.text_input("Active Chess Account Profile ID", value="", placeholder="e.g., MagnusCarlsen")
file_upload = st.sidebar.file_uploader("Upload Profile PGN Records", type=["pgn"])
trigger_audit = st.sidebar.button("Execute Deep Engine Audit")

if file_upload and trigger_audit:
    if not username_input:
        st.error("Please provide an account user signature key in the dashboard sidebar configuration block.")
    else:
        with st.spinner("Executing background data sweep parsing tracks..."):
            stream = io.StringIO(file_upload.getvalue().decode("utf-8"))
            analyzer = StockfishAnalyzer(target_user=username_input)
            games_count, collapse_move, opening_base, logs = analyzer.run_audit(stream)

            if games_count > 0:
                st.session_state.stats = {
                    "total": games_count,
                    "avg_moves": collapse_move,
                    "opening": opening_base,
                    "logs": logs
                }
                st.session_state.messages = []
                initial_text = fetch_coach_review(games_count, collapse_move, opening_base, logs, [])
                st.session_state.messages.append({"role": "assistant", "content": initial_text})

if st.session_state.stats:
    cached = st.session_state.stats
    st.markdown("### 📊 Engine Performance Intelligence")
    grid1, grid2, grid3 = st.columns(3)
    with grid1:
        st.markdown(f'Games Audited<br><strong>{cached["total"]}</strong>', unsafe_allow_html=True)
    with grid2:
        st.markdown(f'Avg Move Before Collapse<br><strong>{cached["avg_moves"]}</strong>', unsafe_allow_html=True)
    with grid3:
        truncated_title = (cached['opening'][:22] + '...') if len(cached['opening']) > 22 else cached['opening']
        st.markdown(f'Opening Profile Base<br><strong>{truncated_title}</strong>', unsafe_allow_html=True)

    st.markdown("### 💬 Chat Workflow Module")
    for chat in st.session_state.messages:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    if query := st.chat_input("Query profile performance insights..."):
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.messages.append({"role": "user", "content": query})

        with st.chat_message("assistant"):
            with st.spinner("Processing local matrix models..."):
                reply = fetch_coach_review(
                    cached['total'],
                    cached['avg_moves'],
                    cached['opening'],
                    cached['logs'],
                    st.session_state.messages[:-1],
                    query
                )
                st.markdown(reply)
                st.session_state.messages.append({"role": "assistant", "content": reply})
