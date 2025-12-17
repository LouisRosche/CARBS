"""
Research Ingester

Ingests research papers and market analysis for insights.
"""

import logging
import re
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class ResearchIngester:
    """
    Ingests research papers and market analysis

    Sources:
    - ArXiv preprints
    - CoinDesk research
    - Messari reports
    - Trading journals
    """

    def __init__(self, data_dir: Path = None):
        self.data_dir = data_dir or Path("data/research")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._research_cache: deque = deque(maxlen=200)  # Limit cached papers
        self._insights: deque = deque(maxlen=500)  # Limit stored insights

    async def fetch_arxiv_papers(
        self,
        query: str = "cryptocurrency trading",
        max_results: int = 10
    ) -> List[Dict]:
        """Fetch relevant papers from ArXiv"""
        import aiohttp

        papers = []
        base_url = "http://export.arxiv.org/api/query"

        try:
            async with aiohttp.ClientSession() as session:
                params = {
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": max_results,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending"
                }

                async with session.get(base_url, params=params) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        papers = self._parse_arxiv_response(text)

        except Exception as e:
            logger.error(f"Failed to fetch ArXiv papers: {e}")

        return papers

    def _parse_arxiv_response(self, xml_text: str) -> List[Dict]:
        """Parse ArXiv API response"""
        papers = []

        # Simple regex parsing (would use proper XML parser in production)
        entries = re.findall(r'<entry>(.*?)</entry>', xml_text, re.DOTALL)

        for entry in entries:
            title_match = re.search(r'<title>(.*?)</title>', entry, re.DOTALL)
            summary_match = re.search(r'<summary>(.*?)</summary>', entry, re.DOTALL)
            published_match = re.search(r'<published>(.*?)</published>', entry)
            id_match = re.search(r'<id>(.*?)</id>', entry)

            if title_match and summary_match:
                papers.append({
                    "title": title_match.group(1).strip(),
                    "summary": summary_match.group(1).strip()[:500],
                    "published": published_match.group(1) if published_match else "",
                    "url": id_match.group(1) if id_match else "",
                    "source": "arxiv"
                })

        return papers

    async def extract_insights(self, papers: List[Dict]) -> List[Dict]:
        """Extract actionable insights from papers"""
        insights = []

        # Keywords that indicate actionable findings
        action_keywords = [
            "outperform", "significant", "profitable", "alpha",
            "predict", "forecast", "correlation", "strategy"
        ]

        for paper in papers:
            summary_lower = paper.get("summary", "").lower()

            # Check for actionable content
            relevance_score = sum(1 for k in action_keywords if k in summary_lower)

            if relevance_score >= 2:
                insights.append({
                    "source": paper.get("url", ""),
                    "title": paper.get("title", ""),
                    "relevance_score": relevance_score,
                    "summary": paper.get("summary", "")[:300],
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })

        self._insights.extend(insights)
        return insights

    def get_strategy_recommendations(self) -> List[str]:
        """Get strategy recommendations from research"""
        # Analyze accumulated insights for recommendations
        recommendations = []

        # Example logic - would be more sophisticated in production
        keywords_to_recommendations = {
            "momentum": "Consider momentum-based strategies for trending markets",
            "mean reversion": "Mean reversion strategies may work in ranging markets",
            "sentiment": "Sentiment signals show predictive power for short-term moves",
            "volume": "Volume analysis can confirm breakout strength",
            "machine learning": "ML models outperform in pattern recognition tasks"
        }

        for insight in self._insights[-50:]:  # Recent insights
            summary = insight.get("summary", "").lower()
            for keyword, recommendation in keywords_to_recommendations.items():
                if keyword in summary and recommendation not in recommendations:
                    recommendations.append(recommendation)

        return recommendations
