import google.generativeai as genai
import json
import os
from typing import List, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential
from .utils import get_logger

logger = get_logger(__name__)

def configure_gemini(api_key: str):
    genai.configure(api_key=api_key)

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def filter_by_semantics(items: List[Dict[str, Any]], topics: List[str], model_name: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Use Gemini to filter news items based on semantic relevance to topics.
    """
    if not items or not topics:
        return items

    logger.info(f"Sending {len(items)} items to Gemini for semantic filtering...")

    # Prepare the list of items for the prompt
    items_text = ""
    for i, item in enumerate(items):
        # limit summary length to save tokens/noise
        summary = (item.get('summary') or "")[:300]
        items_text += f"Item {i}:\nTitle: {item.get('title')}\nSummary: {summary}\n\n"

    prompt = f"""
    You are a news editor. Your task is to select the top {limit} stories that are relevant to the following topics: {', '.join(topics)}.

    **CRITICAL SELECTION CRITERIA:**
    1. **Relevance:** Must match at least one of the topics.
    2. **Ordering:** Return the stories ordered strictly by the topics provided above. For example, if topics are "A, B", list all A stories first, then all B stories.
    3. **Importance:** Within each topic, prioritize critical/breaking news.
    4. **Diversity:** Ensure a good mix of different topics.
    5. **News vs Opinion:** STRICTLY EXCLUDE opinion pieces, editorials, commentaries, reviews, and "analysis" that is not grounded in new facts. Prioritize hard news.
    6. **Substance:** Exclude fluff, clickbait, or purely promotional content.

    Here are the candidate stories:
    {items_text}

    Return a JSON list of the indices (0-based) of the selected stories.
    Target count: ~{limit} stories (return fewer if not enough good matches).
    Example output: [0, 2, 5]
    Return ONLY the JSON list.
    """

    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content(prompt)
        
        text = response.text.strip()
        # clean up potential markdown formatting
        if text.startswith("```"):
            # remove first line
            text = text.split("\n", 1)[1]
            # remove last line if it is backticks
            if text.strip().endswith("```"):
                text = text.rsplit("\n", 1)[0]
        
        relevant_indices = json.loads(text)
        
        filtered_items = [items[i] for i in relevant_indices if isinstance(i, int) and 0 <= i < len(items)]
        return filtered_items

    except Exception as e:
        logger.error(f"Error in semantic filtering: {e}")
        raise # Retry will catch this

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def summarize_with_gemini(articles: List[Dict[str, Any]], target_words: int, model_name: str, friendly_sources: str) -> str:
    model = genai.GenerativeModel(model_name)

    articles_block = ""
    for idx, a in enumerate(articles, 1):
        articles_block += f"""
### Story {idx}
Title: {a.get('title')}
Summary: {a.get('summary')}
Source: {a.get('link')}
"""

    prompt = f"""
    You are writing a script for a professional news podcast featuring two speakers: a HOST and a REPORTER.

    **Format:**
    - Use "HOST:" for lines spoken by the host (Arjav).
    - Use "REPORTER:" for lines spoken by the reporter (Arohi).
    - Write in a conversational, engaging, yet professional tone.
    - Don't keep repeating the name of the reporter or host in the conversation.
    - The HOST introduces the show, transitions between topics, and asks the REPORTER for details.
    - The REPORTER provides the in-depth news summaries and analysis.
    - End with the HOST signing off.

    **Constraints:**
    - Total length: ~{target_words} words.
    - Do NOT use markdown formatting (bold, italics) in the spoken text.
    - Do NOT include sound effects or music cues.
    - Ensure smooth transitions between stories.
    - Do NOT add any opinionated or editorialized language.

    **Source Material:**
    {articles_block}

    **Structure:**
    1. HOST: Intro (Welcome to Arjav's Daily News Briefing...). Start with a short, interesting fact to grab attention. IMPORTANT: In the intro, explicitly mention that we are covering news from {friendly_sources} and others.
    2. HOST & REPORTER: Dialogue covering the top stories. Group related stories together.
    3. HOST: Outro. Include a short, interesting "fun fact of the day" (related to tech, science, or history) before signing off.
    """

    response = model.generate_content(prompt)
    return response.text
