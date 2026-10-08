"""HTML → plain text conversion for email fallbacks."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup


def html_to_plain_text(html: str) -> str:
    if not html or not html.strip():
        return ""

    soup = BeautifulSoup(html, "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    for tag in soup.find_all(["p", "div", "h1", "h2", "h3", "tr", "li", "blockquote"]):
        tag.append("\n")
    for a in soup.find_all("a"):
        href = a.get("href")
        text = a.get_text(" ", strip=True)
        if href and text:
            a.replace_with(f"{text} ({href})")
        elif href:
            a.replace_with(href)
    for li in soup.find_all("li"):
        text = li.get_text(" ", strip=True)
        li.clear()
        li.append(f"• {text}")

    text = soup.get_text("\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
