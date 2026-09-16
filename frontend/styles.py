"""Minimal, intentionally conservative Streamlit styling."""

CSS = """
<style>
  .block-container { max-width: 980px; padding-top: 2rem; padding-bottom: 2rem; }
  [data-testid="stSidebar"] .block-container { padding-top: 1.25rem; }
  .app-subtitle { color: #8f9baa; margin-top: -0.65rem; margin-bottom: 1.5rem; }
  .health-ok, .health-bad, .health-warn {
    border-radius: 999px; display: inline-block; font-size: .78rem;
    padding: .18rem .55rem; margin-bottom: .75rem;
  }
  .health-ok { background: rgba(35, 134, 54, .18); color: #69d181; }
  .health-warn { background: rgba(187, 128, 9, .18); color: #e3b341; }
  .health-bad { background: rgba(218, 54, 51, .18); color: #ff7b72; }
  .thinking-preview, .thinking-full {
    color: #9ca6b3; font-size: .86rem; line-height: 1.45;
  }
  .thinking-preview {
    border-left: 2px solid #66707d; margin: .8rem 0 .35rem; padding: .4rem .75rem;
  }
  .source-card {
    border: 1px solid rgba(128, 128, 128, .32); border-radius: .6rem;
    margin: .55rem 0; padding: .75rem .85rem;
  }
  .source-title { font-weight: 650; margin-bottom: .15rem; }
  .source-meta, .source-chunk { color: #8f9baa; font-size: .76rem; }
  .source-preview { color: #b7c0ca; font-size: .86rem; margin: .45rem 0; }
  .welcome-card {
    border: 1px solid rgba(128, 128, 128, .25); border-radius: .8rem;
    margin: 2rem 0 1rem; padding: 1.1rem 1.25rem;
  }
  .disclaimer { color: #8f9baa; font-size: .78rem; margin-top: 1rem; }
</style>
"""
