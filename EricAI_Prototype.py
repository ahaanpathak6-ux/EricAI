import io
import logging
import chess.pgn
import chess.engine
import ollama
import streamlit as st

# Set up logging to track what's happening behind the scenes
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ============================================================================
#  THEME & UI CONFIGURATION
# ============================================================================
# Dark theme with amber accents—designed to feel premium and focused

st.set_page_config(
    page_title="EricAI Pro ♝ // Chess Intelligence Platform",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    @import url('https://googleapis.com');
    * { font-family: 'Inter', sans-serif !important; }
    body, .stApp { 
        background: radial-gradient(circle at 10% 10%, rgba(130, 90, 245, 0.18), transparent 30%), #0d0e11 !important; 
        color: #f4f4f5 !important; 
    }
    [data-testid="stSidebar"] { 
        background: #12141c !important; 
        border-right: 1px solid rgba(255,255,255,0.08); 
    }
    .main h1, .main h2, .main h3, .main p, .main span { color: #ffffff !important; }
    .metric-card { 
        background: linear-gradient(160deg, rgba(18, 22, 38, 0.95), rgba(28, 30, 50, 0.95)); 
        border: 1px solid rgba(255,255,255,0.08); 
        border-radius: 18px; 
        padding: 26px; 
        min-height: 150px;
    }
    .metric-value { 
        font-size: 42px; 
        font-weight: 800; 
        color: #f59e0b; 
        line-height: 1.02; 
        margin-bottom: 8px; 
    }
    .metric-label { 
        font-size: 12px; 
        color: #c5c5d1; 
        letter-spacing: 1.4px; 
        text-transform: uppercase; 
        margin-bottom: 8px; 
        display: block; 
    }
    .hero-banner { 
        background: rgba(255,255,255,0.04); 
        border: 1px solid rgba(255,255,255,0.08); 
        border-radius: 24px; 
        padding: 28px; 
        margin-bottom: 26px; 
    }
    .hero-banner h2 { 
        margin: 0 0 10px; 
        font-size: 34px; 
        line-height: 1.05; 
    }
    .sidebar-note { 
        background: rgba(245, 158, 11, 0.08); 
        border: 1px solid rgba(245, 158, 11, 0.18); 
        color: #f8e7c2; 
        padding: 16px; 
        border-radius: 16px; 
        margin-top: 18px; 
    }
    .stButton>button { 
        background-color: #f59e0b !important; 
        color: #0f172a !important; 
        border: none !important; 
        box-shadow: 0 10px 20px rgba(245,158,11,0.24) !important; 
        width: 100%; 
    }
    .stButton>button:hover { background-color: #fbbf24 !important; }
    .stChatMessage { 
        background: rgba(255,255,255,0.04) !important; 
        border-radius: 18px !important; 
        padding: 16px !important; 
    }
    </style>
""", unsafe_allow_html=True)


# ============================================================================
#  CHESS OPENING RECOGNITION
# ============================================================================

class ChessOpeningBook:
    """
    Identifies chess openings by comparing board positions against a reference library.
    
    Think of this as a lookup table—we take the board position and trace backward through
    move history to find the earliest matching opening in our dictionary.
    """
    
    # Library of opening positions (FEN signatures mapped to opening names)
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
    def identify(cls, game: chess.pgn.Game) -> str:
        """
        Figures out which opening is being played by looking at board states.
        
        Moves backward through the game until we find a position that matches
        something in our opening library. If nothing matches, returns "Custom System Setup".
        """
        board = game.board()
        
        # Walk backward through moves to find a recognized position
        while board.move_stack:
            position = board.epd()
            if position in cls.OPENINGS:
                return cls.OPENINGS[position]
            board.pop()
        
        # If we reach the start position, check that
        starting_position = chess.Board().epd()
        return cls.OPENINGS.get(starting_position, "Custom Setup")


# ============================================================================
#  STOCKFISH ANALYSIS ENGINE
# ============================================================================

class StockfishAnalyzer:
    """
    Analyzes your chess games using Stockfish to find blunders and tactical errors.
    
    This class:
    - Reads PGN files from your computer
    - Identifies which games are yours (by username)
    - Uses Stockfish to evaluate each position
    - Tracks where you made costly mistakes
    
    Note: Requires Stockfish to be installed locally.
    """
    
    def __init__(self, username: str, max_games: int = 5):
        """
        Set up the analyzer with your chess username.
        
        Args:
            username: Your chess.com or lichess username
            max_games: How many games to analyze (default: 5)
        """
        self.username = username.strip().lower()
        self.max_games = max_games

    def analyze_games(self, pgn_file: io.StringIO):
        """
        Analyzes games from a PGN file and returns performance stats.
        
        Returns:
            Tuple of (num_games, avg_move_of_first_blunder, most_played_opening, list_of_blunders)
        
        Raises:
            Returns empty data if Stockfish isn't available.
        """
        try:
            engine = chess.engine.SimpleEngine.popen_uci("stockfish")
        except Exception as e:
            logging.error(f"Couldn't start Stockfish: {str(e)}")
            st.error(
                "⚠️ Stockfish not installed. Get it here:\n"
                "• **Mac**: Run `brew install stockfish` in Terminal\n"
                "• **Windows/Linux**: Download from stockfishchess.org"
            )
            return 0, 0, "No Data", []

        num_games = 0
        total_moves_to_first_blunder = 0
        openings_played = []
        all_blunders = []

        # Process each game in the file
        while num_games < self.max_games:
            game = chess.pgn.read_game(pgn_file)
            if not game:
                break  # No more games in the file

            # Extract player names from the PGN headers
            white_player = game.headers.get("White", "").strip().lower()
            black_player = game.headers.get("Black", "").strip().lower()
            
            # Figure out which side you played
            if self.username == white_player:
                your_color = chess.WHITE
            elif self.username == black_player:
                your_color = chess.BLACK
            else:
                # If your username isn't found, skip this game or assume White
                continue

            num_games += 1
            board = game.board()
            opening_name = ChessOpeningBook.identify(game)
            openings_played.append(opening_name)

            previous_eval = 0.0
            all_moves = list(game.mainline_moves())
            move_of_first_blunder = len(all_moves)  # Default: game completed fine

            # Step through each move
            for move_index, move in enumerate(all_moves):
                # Check whose turn it is BEFORE the move
                is_your_move = (board.turn == your_color)
                board.push(move)

                # Ask Stockfish to evaluate this position
                analysis = engine.analyse(board, chess.engine.Limit(time=0.02))
                eval_score = analysis["score"].white()
                current_eval = eval_score.score(mate_score=1000) / 100.0 if eval_score.score() is not None else 0.0

                # See how much the position changed (higher = worse for you)
                eval_change = previous_eval - current_eval
                if your_color == chess.BLACK:
                    eval_change = -eval_change  # Flip perspective for Black

                # If YOUR move made things significantly worse, log it as a blunder
                if is_your_move and eval_change >= 1.5:  # 1.5 centipawns
                    move_of_first_blunder = move_index + 1
                    all_blunders.append({
                        "game_num": num_games,
                        "opening": opening_name,
                        "move_number": move_of_first_blunder,
                        "move_notation": str(move),
                        "points_lost": round(eval_change, 2)
                    })
                    break  # Stop analyzing this game after the first big mistake

                previous_eval = current_eval

            total_moves_to_first_blunder += move_of_first_blunder

        engine.quit()
        
        # Calculate summary stats
        avg_move_to_blunder = int(total_moves_to_first_blunder / num_games) if num_games > 0 else 0
        favorite_opening = max(set(openings_played), key=openings_played.count) if openings_played else "Unknown"
        
        return num_games, avg_move_to_blunder, favorite_opening, all_blunders


# ============================================================================
#  AI COACHING RESPONSE GENERATOR
# ============================================================================

def get_ai_coaching(
    games_analyzed: int,
    avg_blunder_move: int,
    main_opening: str,
    blunder_list: list,
    chat_history: list,
    user_question: str = None
) -> str:
    """
    Uses Ollama's local LLM to generate coaching feedback based on your game analysis.
    
    Tells the AI about your performance data, then asks it to give advice
    in a human, conversational tone (not robotic).
    
    Note: Requires Ollama running locally with llama3.2:3b model.
    """
    
    # Summarize your biggest mistakes for the AI
    blunder_summary = ""
    for blunder in blunder_list[:3]:
        blunder_summary += (
            f"• Game {blunder['game_num']} ({blunder['opening']}): "
            f"Blunder on move {blunder['move_number']} ({blunder['move_notation']}), "
            f"lost {blunder['points_lost']} points\n"
        )

    # Craft a system prompt that tells the AI how to act
    coaching_prompt = f"""You are Coach EricAI, a friendly but knowledgeable chess coach.

YOUR PLAYER'S STATS:
• Games Reviewed: {games_analyzed}
• First Big Mistake Usually Happens: Around Move {avg_blunder_move}
• Favorite Opening: {main_opening}

THEIR BLUNDERS THIS SESSION:
{blunder_summary if blunder_summary else "• No major blunders detected—nice work!"}

HOW TO RESPOND:
1. Be encouraging but honest about problem areas
2. Sound like a real coach talking to a student, not a robot reading data
3. Only discuss their actual blunders—don't make up scenarios
4. Give practical tips they can use next time"""

    # Build the message list
    messages = [{"role": "system", "content": coaching_prompt}]
    
    # Add previous messages for context
    for msg in chat_history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    
    # Add the current question
    default_question = "Tell me about the blunders in my games today and how I can improve."
    messages.append({"role": "user", "content": user_question or default_question})

    try:
        response = ollama.chat(
            model="llama3.2:3b",
            options={"temperature": 0.1, "top_p": 0.1, "num_gpu": 1},
            messages=messages
        )
        return response["message"]["content"]
    except Exception as e:
        return (
            "❌ **Coach is not available right now.**\n\n"
            f"Make sure Ollama is running and llama3.2:3b is installed.\n"
            f"Error: {str(e)}"
        )


# ============================================================================
#  STREAMLIT APP INTERFACE
# ============================================================================

# Header
st.markdown("<h1 style='font-weight: 700; letter-spacing: -1.5px;'>♟️ EricAI Pro</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='color: #71717a; font-size: 14px;'>"
    "Your personal chess coach powered by Stockfish analysis"
    "</p>",
    unsafe_allow_html=True
)
st.write("---")

# Hero section
st.markdown("""
    <div class='hero-banner'>
        <h2 style='color:#ffffff; margin:0 0 10px;'>Get Smarter About Your Chess</h2>
        <p>Upload your games and let EricAI find your blunders, spot patterns, and coach you to improvement.</p>
    </div>
""", unsafe_allow_html=True)

# Initialize session state
if "stats" not in st.session_state: 
    st.session_state.stats = None
if "messages" not in st.session_state: 
    st.session_state.messages = []


# ============================================================================
#  SIDEBAR: USER INPUTS
# ============================================================================

st.sidebar.markdown("<h3>📋 Set Up Your Analysis</h3>", unsafe_allow_html=True)

with st.sidebar:
    username = st.text_input(
        "Your Chess Username",
        value="",
        placeholder="e.g., GothamChess",
        help="Used to identify which games are yours in the PGN file"
    )
    
    pgn_file = st.file_uploader(
        "Upload Your PGN File",
        type=["pgn"],
        help="Export your games from chess.com or lichess and upload here"
    )
    
    analyze_button = st.button(
        "🔍 Analyze My Games",
        use_container_width=True,
        help="Process your games with Stockfish to find blunders"
    )
    
    st.markdown(
        "<div class='sidebar-note'>"
        "<strong>💡 Pro Tip:</strong> PGN files with 5-10 recent games work best. "
        "Make sure your username matches exactly."
        "</div>",
        unsafe_allow_html=True
    )


# ============================================================================
#  MAIN FLOW: ANALYSIS
# ============================================================================

if pgn_file and analyze_button:
    if not username:
        st.error("⚠️ **Please enter your chess username** so we can identify your games.")
    else:
        with st.spinner("🔄 Stockfish is analyzing your games... (this may take a minute)"):
            # Convert file to StringIO
            file_stream = io.StringIO(pgn_file.getvalue().decode("utf-8"))
            
            # Run analysis
            analyzer = StockfishAnalyzer(username=username)
            (
                games_found,
                avg_blunder_move,
                favorite_opening,
                blunders_found
            ) = analyzer.analyze_games(file_stream)

            if games_found > 0:
                # Save results to session
                st.session_state.stats = {
                    "total": games_found,
                    "avg_moves": avg_blunder_move,
                    "opening": favorite_opening,
                    "logs": blunders_found
                }
                st.session_state.messages = []
                
                # Generate first AI response
                coach_response = get_ai_coaching(
                    games_found,
                    avg_blunder_move,
                    favorite_opening,
                    blunders_found,
                    []
                )
                st.session_state.messages.append({"role": "assistant", "content": coach_response})
                
                st.success("✅ Analysis complete! Check out your results below.")


# ============================================================================
#  RESULTS DISPLAY & COACHING CHAT
# ============================================================================

if st.session_state.stats:
    stats = st.session_state.stats
    
    # Performance cards
    st.markdown("### 📊 Your Performance Summary")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(label="Games Analyzed", value=stats["total"])
    
    with col2:
        st.metric(label="Move of First Blunder", value=f"~{stats['avg_moves']}")
    
    with col3:
        opening_display = (
            stats['opening'][:20] + "..." 
            if len(stats['opening']) > 20 
            else stats['opening']
        )
        st.metric(label="Main Opening", value=opening_display)
    
    # Chat section
    st.markdown("### 💬 Chat with Your Coach")
    st.caption("Ask EricAI about your games, tactics, or how to improve")
    
    # Display previous messages
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"], avatar="🧑‍🏫" if msg["role"] == "assistant" else "👤"):
            st.markdown(msg["content"])
    
    # Chat input
    user_input = st.chat_input("Ask me anything about your performance...")
    
    if user_input:
        # Show user message
        with st.chat_message("user", avatar="👤"):
            st.markdown(user_input)
        st.session_state.messages.append({"role": "user", "content": user_input})
        
        # Get AI response
        with st.chat_message("assistant", avatar="🧑‍🏫"):
            with st.spinner("Coach is thinking..."):
                coach_reply = get_ai_coaching(
                    stats['total'],
                    stats['avg_moves'],
                    stats['opening'],
                    stats['logs'],
                    st.session_state.messages[:-1],  # Exclude the message we just added
                    user_input
                )
                st.markdown(coach_reply)
                st.session_state.messages.append({"role": "assistant", "content": coach_reply})
