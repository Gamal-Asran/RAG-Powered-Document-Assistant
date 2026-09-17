"""Design tokens and localized Streamlit styling for the assistant UI."""

CSS = """
<style>
  :root {
    --page: #0B0F14; --sidebar: #11161D; --surface: #151B23;
    --surface-hover: #1B2430; --text: #F3F6FA; --text-secondary: #9AA7B5;
    --text-muted: #6F7C89; --border: #26313D; --accent: #4F8FF7;
    --accent-hover: #6AA3FF; --success: #45C486; --error: #F06A6A;
    --thinking: #10151B; --radius-sm: 8px; --radius-md: 12px; --radius-lg: 16px;
  }

  html, body, [data-testid="stAppViewContainer"], .stApp { background: var(--page); color: var(--text); }
  html, body { overflow-x: hidden; }
  [data-testid="stAppViewContainer"] > .main { min-height: 100vh; }
  .block-container {
    box-sizing: border-box; max-width: 880px; min-height: 100vh;
    padding: 1.35rem 1.5rem 1.25rem;
  }

  /* Compact application header */
  .st-key-app_header { margin-bottom: .35rem; }
  .app-header { align-items: center; display: flex; gap: .85rem; min-height: 64px; }
  .shield-mark {
    align-items: center; background: var(--accent);
    clip-path: polygon(50% 0, 92% 16%, 84% 72%, 50% 100%, 16% 72%, 8% 16%);
    display: flex; flex: 0 0 auto; height: 36px; justify-content: center; width: 32px;
  }
  .shield-mark::after { background: var(--page); clip-path: inherit; content: ""; height: 28px; width: 24px; }
  .app-title-row { align-items: center; display: flex; flex-wrap: wrap; gap: .55rem; }
  .app-title {
    color: var(--text); font-size: clamp(1.7rem, 2.3vw, 2rem); font-weight: 650;
    letter-spacing: -.035em; line-height: 1.08;
  }
  .app-subtitle { color: var(--text-secondary); font-size: .875rem; line-height: 1.4; margin-top: .28rem; }
  .local-badge {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-sm);
    color: var(--text-secondary); font-size: .68rem; font-weight: 600; letter-spacing: .04em;
    padding: .16rem .4rem; text-transform: uppercase;
  }

  /* Vertically balanced empty state and responsive suggestions */
  .st-key-empty_state {
    display: flex; flex-direction: column; justify-content: center;
    min-height: clamp(310px, calc(100vh - 260px), 500px);
  }
  .empty-copy { margin: 0 auto 1.25rem; max-width: 620px; text-align: center; }
  .empty-title {
    color: var(--text); font-size: clamp(1.55rem, 3vw, 2.05rem); font-weight: 620;
    letter-spacing: -.025em; line-height: 1.2; margin-bottom: .5rem;
  }
  .empty-description {
    color: var(--text-secondary); font-size: .95rem; line-height: 1.55;
    margin: 0 auto; max-width: 580px;
  }
  .st-key-suggestion_grid [data-testid="stHorizontalBlock"] { gap: .75rem; }
  .st-key-suggestion_grid .stButton button {
    align-items: flex-start; background: transparent; border: 1px solid var(--border);
    border-radius: var(--radius-md); color: var(--text); display: flex; height: 88px;
    justify-content: flex-start; padding: .8rem .9rem; text-align: left;
    transition: background-color .15s ease, border-color .15s ease; white-space: normal;
  }
  .st-key-suggestion_grid .stButton button:hover {
    background: var(--surface-hover); border-color: #34465a; color: var(--text);
  }
  .st-key-suggestion_grid .stButton button p::first-line {
    color: var(--text-secondary); font-size: .72rem; font-weight: 650; letter-spacing: .02em;
  }
  .st-key-suggestion_grid .stButton button p { line-height: 1.35; overflow: visible; white-space: pre-line; }
  .empty-disclaimer { color: var(--text-muted); font-size: .75rem; margin-top: .8rem; text-align: center; }

  /* Conversation flow */
  .st-key-conversation_messages { padding-bottom: 1.2rem; }
  .st-key-conversation_messages [data-testid="stChatMessage"],
  .st-key-pending_turn [data-testid="stChatMessage"] {
    background: transparent; border: 0; gap: .65rem; margin: .35rem 0 1.35rem;
    padding: .35rem 0; width: 100%;
  }
  .st-key-conversation_messages [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]),
  .st-key-pending_turn [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
    background: #14233a; border-radius: var(--radius-md); margin-left: auto;
    max-width: min(78%, 650px); padding: .7rem .9rem; width: fit-content;
  }
  .st-key-conversation_messages [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageAvatarUser"] { display: none; }
  .st-key-conversation_messages [data-testid="stChatMessage"] p,
  .st-key-conversation_messages [data-testid="stMarkdownContainer"] { overflow-wrap: anywhere; }
  .st-key-conversation_messages pre { overflow-x: auto; }
  .st-key-conversation_messages table { display: block; max-width: 100%; overflow-x: auto; }
  .assistant-label {
    color: var(--text-secondary); font-size: .72rem; font-weight: 650; letter-spacing: .035em;
    margin-bottom: .45rem; text-transform: uppercase;
  }
  .assistant-label span { color: var(--accent); font-size: .62rem; }

  /* Thinking and source disclosures */
  .thinking-preview {
    background: var(--thinking); border-radius: var(--radius-sm); margin: .9rem 0 .35rem;
    padding: .65rem .75rem;
  }
  .thinking-label { color: var(--text-secondary); font-size: .78rem; font-weight: 600; margin-bottom: .28rem; }
  .thinking-copy, .thinking-full, .thinking-unavailable {
    color: var(--text-muted); font-size: .78rem; line-height: 1.5;
  }
  .thinking-unavailable { margin: .75rem 0; }
  [data-testid="stExpander"] {
    background: transparent; border-color: var(--border); border-radius: var(--radius-sm); margin-top: .4rem;
  }
  [data-testid="stExpander"] summary { color: var(--text-secondary); font-size: .82rem; }
  .source-card { border-bottom: 1px solid var(--border); padding: .8rem .1rem; }
  .source-card:last-child { border-bottom: 0; }
  .source-title { color: var(--text); font-size: .88rem; font-weight: 620; line-height: 1.35; }
  .source-meta { color: var(--text-secondary); font-size: .74rem; margin-top: .16rem; }
  .source-preview {
    color: var(--text-secondary); display: -webkit-box; font-size: .8rem;
    -webkit-line-clamp: 3; -webkit-box-orient: vertical; line-height: 1.45;
    margin: .48rem 0; overflow: hidden;
  }
  .source-footer {
    align-items: center; display: flex; flex-wrap: wrap; gap: .45rem 1rem; justify-content: space-between;
  }
  .source-footer a { color: var(--accent-hover); font-size: .76rem; text-decoration: none; }
  .source-chunk {
    color: var(--text-muted); font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: .68rem; overflow-wrap: anywhere;
  }

  /* Integrated composer */
  .st-key-composer_shell {
    background: var(--surface); border: 1px solid var(--border); border-radius: var(--radius-lg);
    bottom: .5rem; margin-top: auto; padding: .55rem .65rem .42rem;
    position: sticky; z-index: 20;
  }
  .st-key-composer_shell [data-testid="stHorizontalBlock"] { align-items: center; gap: .45rem; }
  .st-key-composer_shell [data-testid="stChatInput"] {
    background: transparent; border-color: transparent; box-shadow: none;
  }
  .st-key-composer_shell [data-testid="stChatInput"]:focus-within { box-shadow: none; }
  .st-key-composer_shell textarea { color: var(--text); font-size: .94rem; }
  .st-key-composer_shell textarea::placeholder { color: var(--text-muted); }
  .st-key-composer_shell [data-testid="stChatInputSubmitButton"] {
    background: var(--accent); border: 0; border-radius: var(--radius-sm); color: white; min-height: 38px;
  }
  .st-key-composer_shell [data-testid="stChatInputSubmitButton"]:hover:not(:disabled) {
    background: var(--accent-hover); color: white;
  }
  .st-key-composer_shell [data-testid="stToggle"] label { color: var(--text-secondary); font-size: .82rem; }
  .composer-note { color: var(--text-muted); font-size: .68rem; margin: .38rem .25rem 0; }

  /* Compact working state */
  .st-key-working_state { margin: .2rem 0 1rem 2.8rem; }
  .working-title { color: var(--text-secondary); font-size: .84rem; font-weight: 600; }
  .working-dot {
    animation: local-pulse 1.4s ease-in-out infinite; color: var(--accent);
    background: currentColor; border-radius: 50%; display: inline-block; height: .48rem;
    margin-right: .5rem; width: .48rem;
  }
  .working-elapsed { color: var(--text-muted); font-variant-numeric: tabular-nums; font-weight: 500; }
  @keyframes local-pulse { 0%, 100% { opacity: .35; } 50% { opacity: 1; } }

  /* Sidebar */
  [data-testid="stSidebar"] { background: var(--sidebar); min-width: 260px !important; width: 260px !important; }
  [data-testid="stSidebar"] > div:first-child { width: 260px !important; }
  [data-testid="stSidebar"] .block-container { min-height: 100vh; padding: 1.15rem .8rem 1rem; }
  .sidebar-brand { margin: 0 .25rem 1rem; }
  .sidebar-title { color: var(--text); font-size: 1rem; font-weight: 650; }
  .sidebar-subtitle { color: var(--text-muted); font-size: .72rem; margin-top: .12rem; }
  .st-key-new_chat_action button {
    background: var(--accent); border: 0; border-radius: var(--radius-sm); color: white; min-height: 40px;
  }
  .st-key-new_chat_action button:hover { background: var(--accent-hover); color: white; }
  .conversation-heading {
    color: var(--text-muted); font-size: .68rem; font-weight: 650; letter-spacing: .07em;
    margin: 1rem .3rem .4rem; text-transform: uppercase;
  }
  .conversation-empty { color: var(--text-muted); font-size: .78rem; padding: .7rem .3rem; }
  .st-key-conversation_list { padding-bottom: 6rem; }
  .st-key-conversation_list [data-testid="stHorizontalBlock"] { gap: .2rem; }
  .st-key-conversation_list .stButton button {
    background: transparent; border: 0; border-radius: var(--radius-sm); color: var(--text-secondary);
    min-height: 42px; padding: .42rem .5rem; text-align: left;
  }
  .st-key-conversation_list .stButton button:hover { background: var(--surface-hover); color: var(--text); }
  .st-key-conversation_list [data-testid="column"]:last-child .stButton button p { display: none; }
  .st-key-conversation_list .stButton button p {
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
    line-height: 1.25; overflow: hidden; white-space: normal;
  }
  .st-key-active_conversation_row { background: rgba(79, 143, 247, .12); border-radius: var(--radius-sm); }
  .st-key-active_conversation_row .stButton button { color: var(--text); }
  .st-key-sidebar_footer {
    background: var(--sidebar); bottom: .85rem; padding: .65rem .25rem .15rem;
    position: fixed; width: 232px; z-index: 5;
  }
  .health-line { color: var(--text-secondary); font-size: .76rem; }
  .health-dot { color: var(--success); margin-right: .35rem; }
  .health-dot.offline { color: var(--error); }
  .health-dot.degraded { color: #E3B341; }
  .memory-note { color: var(--text-muted); font-size: .68rem; margin-top: .2rem; }

  button:focus-visible, a:focus-visible, input:focus-visible {
    outline: 2px solid var(--accent-hover) !important; outline-offset: 2px;
  }

  @media (max-width: 900px) {
    [data-testid="stSidebar"] { min-width: 0 !important; width: 0 !important; }
    [data-testid="stSidebar"] > div:first-child { width: 260px !important; }
    .block-container { padding: 3.3rem .9rem .75rem; }
    .app-title { font-size: 1.65rem; }
    .app-header { min-height: 58px; }
    .st-key-empty_state { min-height: clamp(300px, calc(100vh - 240px), 450px); }
    .st-key-suggestion_grid [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
    .st-key-suggestion_grid [data-testid="stColumn"] { flex: 1 1 100%; min-width: 100%; width: 100%; }
    .st-key-suggestion_grid .stButton button { height: auto; min-height: 70px; }
    .st-key-conversation_messages [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) { max-width: 90%; }
    .st-key-composer_shell [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
    .st-key-composer_shell [data-testid="stColumn"]:first-child { flex: 1 1 100%; min-width: 100%; }
    .st-key-composer_shell [data-testid="stColumn"]:not(:first-child) { flex: 1 1 auto; width: auto; }
    .source-footer { align-items: flex-start; flex-direction: column; }
  }

  @media (max-height: 780px) and (min-width: 901px) {
    .block-container { padding-top: .85rem; }
    .st-key-empty_state { min-height: calc(100vh - 215px); }
    .empty-copy { margin-bottom: .85rem; }
    .st-key-suggestion_grid .stButton button { height: 84px; padding: .65rem .8rem; }
  }
</style>
"""
