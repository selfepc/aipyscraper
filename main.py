"""
Twitter Scraper with Scroll Handling for Dynamic Content
Option usage :# With JSON output
python3 main.py "show twitter profile randomworldke first 5 posts" --format json
# Basic website scan
python3 main.py "go to https://example.com and extract page info"
# With specific target
python3 main.py "analyze https://github.com/torvalds and get repositories" --format json
"""

import os
import re
import json
import logging
import argparse
from typing import Dict, List, Optional
from datetime import datetime
from playwright.sync_api import sync_playwright, Page, TimeoutError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TwitterScraper:
    """Advanced Twitter scraper with scroll functionality"""
    
    def __init__(self):
        self.config = {
            'scroll_attempts': 5,
            'scroll_delay': 2000,  # milliseconds
            'selectors': {
                'posts': 'article[data-testid="tweet"]',
                'content': 'div[data-testid="tweetText"]',
                'metrics': {
                    'reply': '[data-testid="reply"] span',
                    'retweet': '[data-testid="retweet"] span',
                    'like': '[data-testid="like"] span'
                },
                'errors': 'text=/doesn’t exist|account suspended/i'
            },
            'timeouts': {
                'navigation': 60000,
                'content_load': 45000,
                'element': 30000
            }
        }

    def scrape_profile(self, username: str, post_count: int) -> Dict:
        """Main scraping method with scroll handling"""
        result = {
            "username": username,
            "requested_posts": post_count,
            "scraped_posts": 0,
            "posts": [],
            "errors": []
        }

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            try:
                # Navigate to profile
                nav_error = self._navigate_to_profile(page, username)
                if nav_error:
                    result["errors"].append(nav_error)
                    return result

                # Scroll to load more posts
                self._auto_scroll(page, post_count)

                # Find and process posts
                posts = page.query_selector_all(self.config['selectors']['posts'])
                posts = posts[:post_count]
                
                result["scraped_posts"] = len(posts)
                for idx, post in enumerate(posts, 1):
                    post_data = self._process_post(post, idx)
                    if post_data:
                        result["posts"].append(post_data)
                    else:
                        result["errors"].append(f"Failed to process post {idx}")

                return result

            except Exception as e:
                logger.error(f"Scraping failed: {str(e)}")
                result["errors"].append(f"Runtime error: {str(e)}")
                return result
            finally:
                browser.close()

    def _auto_scroll(self, page: Page, target_count: int) -> None:
        """Auto-scroll to load more tweets"""
        last_height = 0
        current_count = 0
        scroll_attempt = 0

        while scroll_attempt < self.config['scroll_attempts']:
            # Get current number of posts
            posts = page.query_selector_all(self.config['selectors']['posts'])
            current_count = len(posts)
            
            if current_count >= target_count:
                break

            # Scroll to bottom
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(self.config['scroll_delay'])
            
            # Check if scroll succeeded
            new_height = page.evaluate("document.body.scrollHeight")
            if new_height == last_height:
                break
                
            last_height = new_height
            scroll_attempt += 1

        logger.info(f"Loaded {current_count} posts after {scroll_attempt} scrolls")

    def _navigate_to_profile(self, page: Page, username: str) -> Optional[str]:
        """Navigate to Twitter profile with error handling"""
        try:
            page.goto(
                f"https://twitter.com/{username}",
                timeout=self.config['timeouts']['navigation']
            )
            
            # Check for errors
            error_element = page.query_selector(self.config['selectors']['errors'])
            if error_element:
                return f"Profile error: {error_element.inner_text()[:200]}"

            # Wait for initial content
            page.wait_for_selector(
                self.config['selectors']['posts'],
                timeout=self.config['timeouts']['content_load']
            )
            return None

        except TimeoutError:
            return "Timeout waiting for profile to load"
        except Exception as e:
            return f"Navigation error: {str(e)}"

    def _process_post(self, post_element, position: int) -> Optional[Dict]:
        """Process individual tweet with error handling"""
        try:
            return {
                "position": position,
                "content": self._get_element_text(post_element, 'content'),
                "likes": self._get_metric(post_element, 'like'),
                "retweets": self._get_metric(post_element, 'retweet'),
                "replies": self._get_metric(post_element, 'reply'),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Post processing error: {str(e)}")
            return None

    def _get_element_text(self, parent, element_type: str) -> str:
        """Safe element text extraction"""
        try:
            element = parent.wait_for_selector(
                self.config['selectors'][element_type],
                timeout=self.config['timeouts']['element']
            )
            return element.inner_text().strip()
        except:
            return 'Content unavailable'

    def _get_metric(self, parent, metric_type: str) -> str:
        """Metric extraction with validation"""
        try:
            element = parent.wait_for_selector(
                self.config['selectors']['metrics'][metric_type],
                timeout=self.config['timeouts']['element']
            )
            return element.inner_text().strip() or '0'
        except:
            return 'N/A'

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Twitter Profile Scraper')
    parser.add_argument('command', type=str)
    parser.add_argument('--format', type=str, default='json', choices=['json'])
    
    args = parser.parse_args()
    
    # Parse command
    match = re.match(r"analyze twitter account (\w+) get (\d+) posts?", args.command)
    if not match:
        print(json.dumps({"error": "Invalid command format"}))
        exit(1)
        
    username = match.group(1)
    post_count = int(match.group(2))
    
    scraper = TwitterScraper()
    result = scraper.scrape_profile(username, post_count)
    print(json.dumps(result, indent=2, ensure_ascii=False))