#!/usr/bin/env python3
"""
AI Systems Research Daily Digest Agent
=======================================
Collects 5 interesting papers/blogs on AI systems research,
generates TLDRs using Claude Code CLI, and emails them daily.

Requirements: Claude Code CLI installed (`npm install -g @anthropic-ai/claude-code`)

Topics covered:
- Fixed point arithmetic
- Quantization
- Pruning
- Linearization
- Algorithmic optimization
- AI compilers
- AI hardware accelerators
- LLM efficiency
"""

import os
import sys
import json
import random
import smtplib
import subprocess
import arxiv
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from pathlib import Path
import logging
from dotenv import load_dotenv

# Load .env from the same directory as this script
load_dotenv(Path(__file__).parent / ".env")

# Configure logging
LOG_DIR = Path(__file__).parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "digest.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# State file to track last run
STATE_FILE = Path(__file__).parent / ".last_run"
SEEN_PAPERS_FILE = Path(__file__).parent / ".seen_papers.json"


def load_seen_papers() -> set:
    """Load previously seen paper URLs."""
    if SEEN_PAPERS_FILE.exists():
        with open(SEEN_PAPERS_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen_papers(urls: set):
    """Persist seen paper URLs (keep last 500 to avoid unbounded growth)."""
    existing = load_seen_papers()
    combined = list(existing | urls)[-500:]
    with open(SEEN_PAPERS_FILE, "w") as f:
        json.dump(combined, f)


def already_ran_today() -> bool:
    """Check if the digest already ran today."""
    if not STATE_FILE.exists():
        return False
    
    try:
        last_run = STATE_FILE.read_text().strip()
        last_date = datetime.fromisoformat(last_run).date()
        return last_date == datetime.now().date()
    except (ValueError, OSError):
        return False


def mark_as_ran():
    """Mark that we ran today."""
    STATE_FILE.write_text(datetime.now().isoformat())

# Research topics to search
TOPICS_FILE = Path(__file__).parent / "topics.json"

def load_topics() -> tuple[list[str], list[str]]:
    """Load research topics and conferences from topics.json."""
    if TOPICS_FILE.exists():
        with open(TOPICS_FILE) as f:
            data = json.load(f)
        return data.get("topics", []), data.get("conferences", [])
    logger.warning("topics.json not found, using empty topic list")
    return [], []

RESEARCH_TOPICS, CONFERENCES = load_topics()


class AIResearchDigestAgent:
    def __init__(
        self,
        gmail_address: Optional[str] = None,
        gmail_app_password: Optional[str] = None,
        recipient_email: Optional[str] = None
    ):
        """Initialize the research digest agent."""
        self.gmail_address = gmail_address or os.getenv("GMAIL_ADDRESS")
        self.gmail_app_password = gmail_app_password or os.getenv("GMAIL_APP_PASSWORD")
        self.recipient_email = recipient_email or os.getenv("RECIPIENT_EMAIL", self.gmail_address)
        
        # Verify Claude Code is installed
        if not self._check_claude_code():
            raise RuntimeError("Claude Code CLI not found. Install with: npm install -g @anthropic-ai/claude-code")
        
        self.arxiv_client = arxiv.Client(page_size=10, delay_seconds=5, num_retries=2)
    
    def _check_claude_code(self) -> bool:
        """Check if Claude Code CLI is available."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return result.returncode == 0
        except (subprocess.SubprocessError, FileNotFoundError):
            return False
    
    def _call_claude(self, prompt: str) -> str:
        """Call Claude Code CLI with a prompt."""
        try:
            result = subprocess.run(
                ["claude", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=120  # 2 min timeout
            )
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.warning(f"Claude Code error: {result.stderr}")
                return ""
        except subprocess.TimeoutExpired:
            logger.warning("Claude Code timed out")
            return ""
        except Exception as e:
            logger.warning(f"Claude Code call failed: {e}")
            return ""
        
    def search_arxiv_papers(self, max_results: int = 10) -> list[dict]:
        """Search arXiv for recent AI systems research papers."""
        logger.info("Searching arXiv for recent papers...")
        
        # Randomly select topics to search
        selected_topics = random.sample(RESEARCH_TOPICS, min(7, len(RESEARCH_TOPICS)))
        all_papers = []
        previously_seen = load_seen_papers()

        # Category filter baked into the query — arXiv returns only these categories
        CAT_FILTER = (
            "cat:cs.LG OR cat:stat.ML OR cat:cs.CL OR cat:cs.AR OR "
            "cat:cs.PL OR cat:cs.DC OR cat:cs.NE OR cat:cs.ET"
        )

        for topic in selected_topics:
            try:
                conference = random.choice(CONFERENCES) if CONFERENCES else ""
                query = f"({topic} {conference}) AND ({CAT_FILTER})".strip()
                # Random offset so each run fetches a different page of results.
                # max_results must be > offset or the generator exits immediately.
                offset = random.randint(0, 40)
                search = arxiv.Search(
                    query=query,
                    max_results=offset + 5,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending
                )

                for result in self.arxiv_client.results(search, offset=offset):
                    # Skip already seen papers
                    if result.entry_id in previously_seen:
                        continue
                    # Only include papers from the last 60 days
                    if result.published.replace(tzinfo=None) > datetime.now() - timedelta(days=60):
                        paper = {
                            "title": result.title,
                            "authors": ", ".join([a.name for a in result.authors[:3]]),
                            "abstract": result.summary,
                            "url": result.entry_id,
                            "pdf_url": result.pdf_url,
                            "published": result.published.strftime("%Y-%m-%d"),
                            "categories": result.categories,
                            "source": "arXiv"
                        }
                        all_papers.append(paper)
                        
            except Exception as e:
                logger.warning(f"Error searching for '{topic}': {e}")
                continue
        
        # Remove duplicates by URL
        seen_urls = set()
        unique_papers = []
        for paper in all_papers:
            if paper["url"] not in seen_urls:
                seen_urls.add(paper["url"])
                unique_papers.append(paper)
        
        logger.info(f"Found {len(unique_papers)} unique papers")
        return unique_papers
    
    def rank_and_select_papers(self, papers: list[dict], num_papers: int = 5) -> list[dict]:
        """Use Claude to rank papers by relevance and interest."""
        if len(papers) <= num_papers:
            return papers
        
        logger.info(f"Ranking {len(papers)} papers to select top {num_papers}...")
        
        papers_text = "\n\n".join([
            f"Paper {i+1}:\nTitle: {p['title']}\nAuthors: {p['authors']}\nAbstract: {p['abstract'][:500]}..."
            for i, p in enumerate(papers)
        ])
        
        prompt = f"""You are an AI systems research expert selecting papers for a PhD student.
Pick the {num_papers} most relevant papers across these three pillars:

PILLAR 1 — AI Theory:
  neural network theory, generalization bounds, expressivity, approximation theory,
  loss landscapes, scaling laws, optimization theory, transformers theory, SSMs

PILLAR 2 — AI Compilers:
  ML compilers (MLIR, TVM, XLA, LLVM), operator fusion, kernel optimization,
  tiling, scheduling, code generation, polyhedral compilation, dataflow graphs

PILLAR 3 — AI Hardware & Algorithms:
  hardware accelerators (GPU, TPU, FPGA, ASIC, PIM, neuromorphic),
  quantization, pruning, sparsity, efficient attention, KV cache,
  speculative decoding, MoE efficiency, algorithm-hardware co-design

ACCEPT any paper that meaningfully advances one of these three pillars.
REJECT clearly unrelated papers: pure computer vision (not about efficiency),
video understanding, robotics, NLP applications, medical imaging, climate science,
statistical physics, spin glasses, phase transitions unrelated to ML training.

Rank by: relevance to pillars first, then novelty and impact.

Papers:
{papers_text}

Return ONLY a JSON array of paper numbers (1-indexed), best first.
If fewer than {num_papers} qualify, return only those that do.
Example: [3, 1, 5, 8, 2]
"""
        
        try:
            response_text = self._call_claude(prompt)
            
            # Parse the response - extract JSON array
            import re
            match = re.search(r'\[[\d,\s]+\]', response_text)
            if match:
                selected_indices = json.loads(match.group())
                selected_papers = [papers[i-1] for i in selected_indices[:num_papers] if i <= len(papers)]
                return selected_papers
                
        except Exception as e:
            logger.warning(f"Error ranking papers: {e}")
        
        # Fallback: return random selection
        return random.sample(papers, min(num_papers, len(papers)))
    
    def generate_tldr(self, paper: dict) -> str:
        """Generate a TLDR summary for a paper using Claude Code CLI."""
        prompt = f"""Generate a concise TLDR (3-4 sentences) for this AI systems research paper.
Focus on: the key contribution, methodology, and practical implications for LLM efficiency.

Title: {paper['title']}
Authors: {paper['authors']}
Abstract: {paper['abstract']}

Write the TLDR in a way that's useful for a PhD student working on efficient attention mechanisms.
Start directly with the summary, no preamble."""
        
        response = self._call_claude(prompt)
        if response:
            return response
        else:
            return f"[See abstract above for details]"
    
    def create_digest_email(self, papers: list[dict]) -> tuple[str, str]:
        """Create the email subject and HTML body."""
        date_str = datetime.now().strftime("%B %d, %Y")
        subject = f"⚛️ Atom — AI Research Digest · {date_str}"
        
        # Generate TLDRs for each paper
        papers_with_tldr = []
        for paper in papers:
            logger.info(f"Generating TLDR for: {paper['title'][:50]}...")
            tldr = self.generate_tldr(paper)
            paper["tldr"] = tldr
            papers_with_tldr.append(paper)
        
        # Create HTML email
        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               line-height: 1.6; color: #333; max-width: 700px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #7c3aed 0%, #4f46e5 100%);
                   color: white; padding: 30px; border-radius: 10px; margin-bottom: 30px; }}
        .header h1 {{ margin: 0; font-size: 26px; letter-spacing: -0.5px; }}
        .header p {{ margin: 10px 0 0 0; opacity: 0.85; font-size: 14px; }}
        .paper {{ background: #f8f9fa; border-radius: 8px; padding: 20px; margin-bottom: 20px;
                  border-left: 4px solid #7c3aed; }}
        .paper h2 {{ margin: 0 0 10px 0; font-size: 18px; color: #1a1a2e; }}
        .paper .meta {{ font-size: 13px; color: #666; margin-bottom: 12px; }}
        .paper .tldr {{ background: white; padding: 15px; border-radius: 6px;
                        font-size: 14px; margin-top: 12px; }}
        .paper .tldr-label {{ font-weight: 600; color: #7c3aed; margin-bottom: 5px; }}
        .paper a {{ color: #7c3aed; text-decoration: none; }}
        .paper a:hover {{ text-decoration: underline; }}
        .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 30px;
                   padding-top: 20px; border-top: 1px solid #eee; }}
        .topics {{ display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }}
        .topic {{ background: #ede9fe; color: #6d28d9; padding: 2px 8px;
                  border-radius: 12px; font-size: 11px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚛️ Atom &nbsp;·&nbsp; AI Research Digest</h1>
        <p>{date_str} &nbsp;·&nbsp; {len(papers)} papers curated for you</p>
    </div>
"""
        
        for i, paper in enumerate(papers_with_tldr, 1):
            categories = paper.get("categories", [])[:3]
            topics_html = "".join([f'<span class="topic">{cat}</span>' for cat in categories])
            
            html_body += f"""
    <div class="paper">
        <h2>{i}. {paper['title']}</h2>
        <div class="meta">
            <strong>Authors:</strong> {paper['authors']} • 
            <strong>Published:</strong> {paper['published']} • 
            <a href="{paper['url']}" target="_blank">arXiv</a> | 
            <a href="{paper['pdf_url']}" target="_blank">PDF</a>
        </div>
        <div class="topics">{topics_html}</div>
        <div class="tldr">
            <div class="tldr-label">📝 TLDR</div>
            {paper['tldr']}
        </div>
    </div>
"""
        
        html_body += """
    <div class="footer">
        <p>⚛️ <strong>Atom</strong> · AI Research Digest · Powered by Claude</p>
        <p>Theory · Compilers · Hardware · Algorithms</p>
    </div>
</body>
</html>
"""
        
        return subject, html_body
    
    def send_email(self, subject: str, html_body: str) -> bool:
        """Send the digest email via Gmail SMTP."""
        if not all([self.gmail_address, self.gmail_app_password, self.recipient_email]):
            logger.warning("Email credentials not configured. Saving digest locally instead.")
            return False
        
        logger.info(f"Sending email to {self.recipient_email}...")
        
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.gmail_address
            msg["To"] = self.recipient_email
            
            # Attach HTML body
            msg.attach(MIMEText(html_body, "html"))
            
            # Send via Gmail SMTP
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(self.gmail_address, self.gmail_app_password)
                server.sendmail(self.gmail_address, self.recipient_email, msg.as_string())
            
            logger.info("Email sent successfully!")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
    
    def save_digest_locally(self, subject: str, html_body: str):
        """Save digest to a local HTML file."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename = f"digest_{date_str}.html"
        
        with open(filename, "w") as f:
            f.write(html_body)
        
        logger.info(f"Digest saved to {filename}")
        return filename
    
    def run(self, num_papers: int = 5, send_email: bool = True):
        """Run the full digest pipeline."""
        logger.info("=" * 60)
        logger.info("Starting AI Research Digest Agent")
        logger.info("=" * 60)
        
        # Step 1: Collect papers
        papers = self.search_arxiv_papers(max_results=15)
        
        if not papers:
            logger.error("No papers found. Exiting.")
            return
        
        # Step 2: Rank and select top papers
        selected_papers = self.rank_and_select_papers(papers, num_papers)
        
        # Step 3: Generate digest email
        subject, html_body = self.create_digest_email(selected_papers)
        
        # Step 4: Send or save
        if send_email:
            success = self.send_email(subject, html_body)
            if not success:
                self.save_digest_locally(subject, html_body)
        else:
            self.save_digest_locally(subject, html_body)
        
        logger.info("=" * 60)
        logger.info("Digest complete!")
        logger.info("=" * 60)
        
        # Mark that we ran and persist seen papers (skip in test mode)
        if send_email:
            mark_as_ran()
            save_seen_papers({p["url"] for p in selected_papers})

        return selected_papers


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Research Digest Agent")
    parser.add_argument("--num-papers", type=int, default=5, help="Number of papers to include")
    parser.add_argument("--no-email", action="store_true", help="Save locally instead of emailing")
    parser.add_argument("--test", action="store_true", help="Run in test mode (no email)")
    parser.add_argument("--force", action="store_true", help="Force run even if already ran today")
    
    args = parser.parse_args()
    
    # Check if already ran today (unless forced or testing)
    if not args.force and not args.test and already_ran_today():
        logger.info("📬 Already sent today's digest. Use --force to run again.")
        sys.exit(0)
    
    agent = AIResearchDigestAgent()
    agent.run(
        num_papers=args.num_papers,
        send_email=not (args.no_email or args.test)
    )


if __name__ == "__main__":
    main()