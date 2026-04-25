import re
import urllib.parse
import feedparser
import requests
from datetime import datetime
from typing import Optional


DEFAULT_NITTER_URL = "https://nitter.net"


class NitterFeed:
    def __init__(self, username: str, base_url: str = DEFAULT_NITTER_URL):
        self.base_url = base_url.rstrip("/")
        self.username = username.lower().strip().replace("@", "")
        self.url = f"{self.base_url}/{self.username}/rss"

    def fetch(self) -> dict:
        try:
            response = requests.get(
                self.url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15
            )
            response.raise_for_status()
            return self._parse(response.text)
        except requests.RequestException as e:
            return {"error": str(e), "items": []}

    def _parse(self, xml_content: str) -> dict:
        feed = feedparser.parse(xml_content)
        if feed.bozo and not feed.entries:
            return {"error": "Failed to parse feed", "items": []}

        items = []
        for entry in feed.entries:
            item = self._parse_entry(entry)
            items.append(item)

        # Extract profile image from <image><url>
        profile_image = ""
        if hasattr(feed, 'feed') and feed.feed.get('image'):
            url = feed.feed.image.get('url', '')
            if url:
                decoded = urllib.parse.unquote(url)
                if '/profile_images/' in decoded:
                    profile_image = decoded
                elif decoded.startswith('https://nitter.net/pic/'):
                    profile_image = 'https://pbs.twimg.com' + decoded[len('https://nitter.net/pic'):]

        return {
            "title": feed.feed.get("title", f"@{self.username}"),
            "link": feed.feed.get("link", f"{self.base_url}/{self.username}"),
            "items": items,
            "profile_image": profile_image,
        }

    def _parse_entry(self, entry) -> dict:
        # Extract plain text from title
        title = self._strip_html(entry.get("title", ""))
        
        # Parse description (contains HTML with images)
        description = entry.get("description", "")
        
        # Extract image URLs from description
        images = self._extract_images(description)
        
        # Determine if has video
        has_video = "Video" in description or "ext_tw_video_thumb" in description
        
        # Extract link - feedparser exposes .link as attribute; strip #m fragment
        raw_link = getattr(entry, "link", None) or entry.get("link", "")
        link = raw_link.split("#")[0] if raw_link else ""
        
        # Parse date
        pub_date = entry.get("published", "")
        parsed_date = self._parse_date(pub_date)
        
        return {
            "id": entry.get("id", ""),
            "title": title,
            "description": description,
            "link": link,
            "pub_date": pub_date,
            "parsed_date": parsed_date,
            "images": images,
            "has_video": has_video,
            "author": entry.get("dc_creator", ""),
        }

    def _strip_html(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')
        return text.strip()

    def _extract_images(self, html: str) -> list:
        """
        Extract images and resolve nitter /pic/* proxy URLs to direct pbs.twimg.com URLs.

        Nitter encodes all Twitter images under its own /pic/ path.
        After URL-decoding the src, the three forms are:

          /pic/media/<hash>[?…]              → pbs.twimg.com/media/<hash>[?…]
          /pic/ext_tw_video_thumb/<rest>     → pbs.twimg.com/ext_tw_video_thumb/<rest>
          /pic/card_img/<id>/<key>[?…]       → pbs.twimg.com/card_img/<id>/<key>[?…]

        All three map by simply stripping the leading /pic/ prefix.
        """
        images = []
        seen = set()

        pattern = re.compile(
            r'<img\s[^>]*src="(' + re.escape(self.base_url) + r'/pic/[^"]+)"',
            re.IGNORECASE,
        )

        for match in pattern.finditer(html):
            raw_src = match.group(1)
            decoded = urllib.parse.unquote(raw_src)
            path = decoded[len(self.base_url):]  # e.g. /pic/media/ABC or /pic/card_img/…

            if path.startswith("/pic/media/"):
                img_type = "image"
            elif path.startswith("/pic/ext_tw_video_thumb/"):
                img_type = "video"
            elif path.startswith("/pic/card_img/"):
                img_type = "card"
            else:
                continue

            url = "https://pbs.twimg.com" + path[len("/pic"):]

            if url not in seen:
                seen.add(url)
                images.append({"url": url, "type": img_type})

        return images

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        if not date_str:
            return None
        try:
            # RFC 822 format
            from email.utils import parsedate_to_datetime
            return parsedate_to_datetime(date_str)
        except Exception:
            try:
                return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %Z")
            except Exception:
                return None


def fetch_account(username: str, base_url: str = DEFAULT_NITTER_URL) -> dict:
    feed = NitterFeed(username, base_url)
    return feed.fetch()


if __name__ == "__main__":
    import json
    result = fetch_account("le360fr")
    print(json.dumps(result, indent=2, default=str))
