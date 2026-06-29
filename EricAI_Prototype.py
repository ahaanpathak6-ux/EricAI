import io
import logging
import chess.pgn
import chess.engine
import ollama
import streamlit as st

# Configure logging to track analysis events and errors
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# === PREMIUM STYLESHEET CONFIGURATION ===
# Custom dark theme with amber accents for the Streamlit UI
st.set_page_config(page_title="EricAI Pro ♝ // Chess Intelligence Platform", layout="wide")

st.markdown("""
    <style>
    @import url('https://googleapis.com');
    * { font-family: 'Inter', sans-serif !important; }
    body, .stApp { background: radial-gradient(circle at 10% 10%, rgba(130, 90, 245, 0.18), transparent 30%), #0d0e11 !important; color: #f4f4f5 !important; }
    [data-testid="stSidebar"] { background: #12141c !important; border-right: 1px solid rgba(255,255,255,0.08); }
    .main h1, .main h2, .main h3, .main p, .main span { color: #ffffff !important; }
    .metric-card { background: linear-gradient(160deg, rgba(18, 22, 38, 0.95), rgba(28, 30, 50, 0.95)); border: 1px solid rgba(255,255,255,0.08); border-radius: 18px; padding: 26px; min-height: 15[...]
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
    """
    Manages chess opening identification by matching FEN/EPD board signatures.
    Supports 12+ common openings with transposition handling.
    """
    
    # Dictionary mapping EPD signatures to opening names
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
        """
        Identifies the opening by tracing game moves backward through board states.
        Returns the opening name if found, otherwise defaults to "Custom System Setup".
        """
        board = game_node.board()
        # Walk backward through move stack to find matching EPD signature
        while board.move_stack:
            epd_signature = board.epd()
            if epd_signature in cls.OPENINGS:
                return cls.OPENINGS[epd_signature]
            board.pop()
            
        root_signature = chess.Board().epd()
        return cls.OPENINGS.get(root_signature, "Custom System Setup")


class StockfishAnalyzer:
    """
    Analyzes chess games using Stockfish engine to identify blunders and tactical mistakes.
    Requires Stockfish to be installed locally.
    """
    
    def __init__(self, target_user: str, max_games: int = 5):
        """
        Initialize analyzer with target username and maximum games to process.
        
        Args:
            target_user: Chess username to identify in PGN headers
            max_games: Maximum number of games to analyze (default: 5)
        """
        self.target_user = target_user.strip().lower()
        self.max_games = max_games

    def run_audit(self, file_wrapper: io.StringIO):
        """
        Runs Stockfish analysis on uploaded PGN file.
        
        Returns:
            Tuple of (total_games, avg_collapse_move, primary_opening, blunder_reports)
        """
        try:
            engine = chess.engine.SimpleEngine.popen_uci("stockfish")
        except Exception as e:
            logging.error(f"Stockfish engine failed to start: {str(e)}")
            st.error("❌ Stockfish not found. Install via: brew install stockfish (Mac) or download from stockfishchess.org")
            return 0, 0, "Unknown Repertoire", []

        total_games = 0
        total_collapse_moves = 0
        openings_logged = []
        blunder_reports = []

        while total_games < self.max_games:
            game = chess.pgn.read_game(file_wrapper)
            if not game:
                break

            # Extract player names from PGN headers
            white = game.headers.get("White", "").strip().lower()
            black = game.headers.get("Black", "").strip().lower()
            
            # Determine which color the target user was playing
            if self.target_user == white:
                user_color = chess.WHITE
            elif self.target_user == black:
                user_color = chess.BLACK
            else:
                # Default to WHITE if username not found (fallback behavior)
                user_color = chess.WHITE

            total_games += 1
            board = game.board()
            opening_name = ChessOpeningBook.identify(game)
            openings_logged.append(opening_name)

            prev_eval = 0.0
            moves = list(game.mainline_moves())
            game_collapse_move = len(moves)  # Default: game completed without major blunder

            for idx, move in enumerate(moves):
                # Check if it's the user's turn BEFORE applying the move
                is_user_move = (board.turn == user_color)
                board.push(move)

                # Evaluate position after move (low time limit for speed)
                info = engine.analyse(board, chess.engine.Limit(time=0.02))
                score = info["score"].white()
                current_eval = score.score(mate_score=1000) / 100.0 if score.score() is not None else 0.0

                # Calculate evaluation change (positive = position got worse for user)
                eval_delta = prev_eval - current_eval
                # Flip sign if user is playing Black (inverse perspective)
                if user_color == chess.BLACK:
                    eval_delta = -eval_delta

                # Log blunder if user's move caused evaluation drop >= 1.5 centipawns
                if is_user_move and eval_delta >= 1.5:
                    game_collapse_move = idx + 1
                    blunder_reports.append({
                        "game_id": total_games,
                        "opening": opening_name,
                        "move_number": game_collapse_move,
                        "notation": str(move),
                        "loss_margin": round(eval_delta, 2)
                    })
                    break  # Stop analyzing this game after first major blunder

                prev_eval = current_eval

            total_collapse_moves += game_collapse_move

        engine.quit()
        
        # Calculate statistics
        avg_collapse = int(total_collapse_moves / total_games) if total_games > 0 else 0
        primary_opening = max(set(openings_logged), key=openings_logged.count) if openings_logged else "Unknown"
        
        return total_games, avg_collapse, primary_opening, blunder_reports


def fetch_coach_review(total_games: int, avg_collapse: int, opening: str, blunders: list, history: list, message: str = None) -> str:
    """
    Generates AI coaching feedback using Ollama (llama3.2:3b model).
    Requires Ollama to be running locally with the model pulled.
    
    Args:
        total_games: Number of games analyzed
        avg_collapse: Average move number where blunders occur
        opening: Most frequently played opening
        blunders: List of blunder events with details
        history: Chat history for context
        message: User's current question (if any)
    
    Returns:
        AI-generated coaching response as string
    """
    # Summarize first 3 blunders for the AI
    summary = ""
    for log in blunders[:3]:
        summary += f"- Game {log['game_id']} ({log['opening']}): Blunder on Move {log['move_number']} ({log['notation']}), dropped {log['loss_margin']} centipawns.\n"

    system_prompt = f"""You are EricAI, a professional chess coach analyzing player performance data.

PLAYER PROFILE:
- Games Analyzed: {total_games}
- Average Move When Blunders Occur: Move {avg_collapse}
- Primary Opening Played: {opening}

DETECTED BLUNDERS:
{summary if summary else "- No significant blunders detected in analyzed games."}

INSTRUCTIONS:
1. Provide natural, conversational coaching advice based on the data above.
2. Avoid repeating raw data labels - speak like a human coach, not a machine.
3. Only reference blunders and statistics that are provided above."""

    payload = [{"role": "system", "content": system_prompt}]
    # Add chat history for context
    for msg in history:
        payload.append({"role": msg["role"], "content": msg["content"]})
        
    payload.append({"role": "user", "content": message if message else "Give me a coaching breakdown of my chess performance."})

    try:
        response = ollama.chat(
            model='llama3.2:3b',
            options={'temperature': 0.1, 'top_p': 0.1, 'num_gpu': 1},
            messages=payload
        )
        return response['message']['content']
    except Exception as e:
        return f"Error: Ollama model unavailable. Ensure Ollama is running locally and llama3.2:3b is installed. {str(e)}"


# === STREAMLIT UI LAYOUT ===
st.markdown("<h1 style='font-weight: 700; letter-spacing: -1.5px;'>EricAI Pro</h1>", unsafe_allow_html=True)
st.markdown("<p style='color: #71717a; font-size: 14px; margin-bottom: 0.25rem;'>HYBRID STOCKFISH REASONING & ANALYTICAL REVIEW PLATFORM</p>", unsafe_allow_html=True)
st.write("---")

st.markdown("""
    <div class='hero-banner'>
        <h2 style='color:#ffffff; margin:0 0 10px; font-size:28px;'>Performance Analysis Engine</h2>
        <p>Upload your PGN file to analyze blunders, identify tactical weaknesses, and get personalized coaching from EricAI.</p>
    </div>
""", unsafe_allow_html=True)

# Initialize session state for persistent data
if "stats" not in st.session_state: 
    st.session_state.stats = None
if "messages" not in st.session_state: 
    st.session_state.messages = []

# === SIDEBAR INPUT CONTROLS ===
st.sidebar.markdown("<h2 style='font-size: 18px;'>Analysis Setup</h2>", unsafe_allow_html=True)
username_input = st.sidebar.text_input("Chess Username", value="", placeholder="e.g., GothamChess")
file_upload = st.sidebar.file_uploader("Upload PGN File", type=["pgn"])
trigger_audit = st.sidebar.button("Analyze Games")

# === MAIN ANALYSIS FLOW ===
if file_upload and trigger_audit:
    if not username_input:
        st.error("⚠️ Please enter your chess username to identify your games.")
    else:
        with st.spinner("Analyzing games with Stockfish..."):
            stream = io.StringIO(file_upload.getvalue().decode("utf-8"))
            analyzer = StockfishAnalyzer(target_user=username_input)
            games_count, collapse_move, opening_base, logs = analyzer.run_audit(stream)

            if games_count > 0:
                # Store results in session state
                st.session_state.stats = {
                    "total": games_count,
                    "avg_moves": collapse_move,
                    "opening": opening_base,
                    "logs": logs
                }
                st.session_state.messages = []
                # Generate initial AI response
                initial_text = fetch_coach_review(games_count, collapse_move, opening_base, logs, [])
                st.session_state.messages.append({"role": "assistant", "content": initial_text})

# === DISPLAY ANALYSIS RESULTS ===
if st.session_state.stats:
    cached = st.session_state.stats
    st.markdown("### 📊 Analysis Summary")
    grid1, grid2, grid3 = st.columns(3)
    with grid1:
        st.markdown(f'**Games Audited**<br>{cached["total"]}', unsafe_allow_html=True)
    with grid2:
        st.markdown(f'**Avg Move Before Blunder**<br>{cached["avg_moves"]}', unsafe_allow_html=True)
    with grid3:
        truncated_title = (cached['opening'][:22] + '...') if len(cached['opening']) > 22 else cached['opening']
        st.markdown(f'**Primary Opening**<br>{truncated_title}', unsafe_allow_html=True)

    st.markdown("### 💬 Chat with Coach EricAI")
    # Display chat history
    for chat in st.session_state.messages:
        with st.chat_message(chat["role"]):
            st.markdown(chat["content"])

    # Handle new user messages
    if query := st.chat_input("Ask about your performance..."):
        with st.chat_message("user"):
            st.markdown(query)
        st.session_state.messages.append({"role": "user", "content": query})

        with st.chat_message("assistant"):
            with st.spinner("Coach is reviewing your data..."):
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
