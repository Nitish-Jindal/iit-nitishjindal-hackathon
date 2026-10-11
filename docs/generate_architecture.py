"""
Generate architecture diagram for the submission.
Requires: pip install matplotlib
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

fig, ax = plt.subplots(1, 1, figsize=(18, 12))
ax.set_xlim(0, 18)
ax.set_ylim(0, 12)
ax.axis('off')
fig.patch.set_facecolor('#0d1117')
ax.set_facecolor('#0d1117')

def rounded_box(ax, x, y, w, h, color, text, fontsize=9, text_color='white', alpha=0.9, border_color=None):
    box = FancyBboxPatch((x, y), w, h,
                          boxstyle="round,pad=0.1",
                          facecolor=color, alpha=alpha,
                          edgecolor=border_color or color,
                          linewidth=1.5)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, ha='center', va='center',
            fontsize=fontsize, color=text_color, fontweight='bold',
            wrap=True, multialignment='center')

def arrow(ax, x1, y1, x2, y2, color='#58a6ff'):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=2))

# Title
ax.text(9, 11.5, 'FinSight AI — System Architecture',
        ha='center', va='center', fontsize=16, color='white', fontweight='bold')

# ── DATA SOURCES ───────────────────────────────────────────────────────────
rounded_box(ax, 0.5, 9.5, 3.5, 1.2, '#1f6feb', 'Source 1\nRSS Feeds\n(Reuters, Yahoo,\nCNBC, MarketWatch)', fontsize=8)
rounded_box(ax, 4.5, 9.5, 3.5, 1.2, '#1f6feb', 'Source 2\nSocial Media\n(Synthetic Twitter/X\nfinancial posts)', fontsize=8)

# INGESTION
rounded_box(ax, 0.5, 7.8, 7.5, 1.2, '#388bfd', 'INGESTION LAYER\nfeedparser • ticker detection • MD5 deduplication\nsrc/engine/ingestion.py', fontsize=8, border_color='#58a6ff')
arrow(ax, 2.25, 9.5, 2.25, 9.0)
arrow(ax, 6.25, 9.5, 6.25, 9.0)

# NLP ENGINE CORE
rounded_box(ax, 0.5, 5.5, 7.5, 1.8, '#238636', 'AI/NLP RISK ENGINE (CORE)\nsrc/engine/nlp_analyzer.py', fontsize=9, border_color='#3fb950')
# Sub-boxes inside NLP engine
rounded_box(ax, 0.7, 5.7, 2.2, 1.1, '#2ea043', 'Sentiment\nFinBERT\n[-1.0 → +1.0]', fontsize=7.5, border_color='#56d364')
rounded_box(ax, 3.1, 5.7, 2.2, 1.1, '#2ea043', 'Event Type\nBART-MNLI\nZero-Shot (10 labels)', fontsize=7.5, border_color='#56d364')
rounded_box(ax, 5.6, 5.7, 2.2, 1.1, '#2ea043', 'Impact Score\nWeighted Formula\n[1.0 → 10.0]', fontsize=7.5, border_color='#56d364')
arrow(ax, 4.25, 7.8, 4.25, 7.3)

# RISK SIGNAL OUTPUT
rounded_box(ax, 1.5, 4.0, 5.5, 1.1, '#6e40c9', 'RISK SIGNAL OUTPUT\nticker | sentiment_score | event_type | impact_score | confidence | timestamp', fontsize=7.5, border_color='#a371f7')
arrow(ax, 4.25, 5.5, 4.25, 5.1)

# SQLite
rounded_box(ax, 9.5, 5.5, 2.5, 1.0, '#b08800', 'SQLITE DB\nWAL Mode\ndatabase.py', fontsize=8, border_color='#e3b341')
arrow(ax, 7.5, 4.5, 9.0, 5.8, color='#e3b341')

# MODULE A
rounded_box(ax, 0.5, 1.8, 3.5, 2.0, '#c0392b', 'MODULE A\nTactical Index Rebalancer\n• 20-stock mock index\n• Sentiment-driven weights\n• Min/max bounds [1%, 20%]\n• Sector aggregation', fontsize=7.5, border_color='#e74c3c')
arrow(ax, 2.25, 4.0, 2.25, 3.8)

# MODULE B
rounded_box(ax, 4.5, 1.8, 3.5, 2.0, '#d35400', 'MODULE B\nPortfolio Stress Testing\n• 19-asset portfolio\n• Loans/bonds/swaps/CDS\n• Auto-trigger @ impact>7\n• Basel III-style shocks', fontsize=7.5, border_color='#e67e22')
arrow(ax, 6.25, 4.0, 6.25, 3.8)

# FastAPI
rounded_box(ax, 9.5, 3.5, 2.5, 1.0, '#1f4b8e', 'FastAPI\nREST API\n:8000\n/signals /analyze', fontsize=7.5, border_color='#58a6ff')
arrow(ax, 7.5, 4.3, 9.0, 4.0, color='#58a6ff')

# Streamlit Dashboard
rounded_box(ax, 9.5, 1.8, 2.5, 1.5, '#6200ea', 'Streamlit\nDashboard\n:8501\n5-page UI', fontsize=8, border_color='#a371f7')
arrow(ax, 4.25, 1.8, 9.0, 2.5, color='#a371f7')

# Arrows from modules to dashboard
arrow(ax, 2.25, 1.8, 9.0, 2.3, color='#a371f7')
arrow(ax, 6.25, 1.8, 9.2, 2.2, color='#a371f7')

# FastAPI <-> Dashboard
arrow(ax, 10.5, 3.5, 10.5, 3.3, color='#58a6ff')

# Legend
legend_items = [
    mpatches.Patch(color='#1f6feb', label='Data Sources'),
    mpatches.Patch(color='#388bfd', label='Ingestion Layer'),
    mpatches.Patch(color='#238636', label='NLP Engine'),
    mpatches.Patch(color='#6e40c9', label='Risk Signal'),
    mpatches.Patch(color='#c0392b', label='Module A'),
    mpatches.Patch(color='#d35400', label='Module B'),
    mpatches.Patch(color='#1f4b8e', label='FastAPI'),
    mpatches.Patch(color='#6200ea', label='Dashboard'),
]
ax.legend(handles=legend_items, loc='lower right', facecolor='#161b22',
          labelcolor='white', fontsize=8, framealpha=0.8)

# Model labels
ax.text(12.5, 6.8, 'NLP Models:', color='#8b949e', fontsize=8, fontweight='bold')
ax.text(12.5, 6.4, '• ProsusAI/finbert', color='#3fb950', fontsize=7.5)
ax.text(12.5, 6.0, '• facebook/bart-large-mnli', color='#3fb950', fontsize=7.5)
ax.text(12.5, 5.5, 'Fallbacks:', color='#8b949e', fontsize=8, fontweight='bold')
ax.text(12.5, 5.1, '• Lexicon-based sentiment', color='#e3b341', fontsize=7.5)
ax.text(12.5, 4.7, '• Keyword event classifier', color='#e3b341', fontsize=7.5)

ax.text(12.5, 4.0, 'Stress Scenarios:', color='#8b949e', fontsize=8, fontweight='bold')
for i, s in enumerate(['Geopolitical', 'Macroeconomic', 'Credit Event',
                        'M&A', 'Regulatory', 'Severe Stress']):
    ax.text(12.5, 3.6 - i * 0.35, f'• {s}', color='#f0883e', fontsize=7.5)

plt.tight_layout()
out = Path(__file__).parent.parent / 'docs' / 'architecture.png'
out.parent.mkdir(exist_ok=True)
plt.savefig(str(out), dpi=180, bbox_inches='tight', facecolor='#0d1117')
print(f'Architecture diagram saved to {out}')
