"""
Content Generation (LLM)
========================

This module handles interactions with the Google Gemini API for content generation.
It includes functions for:
- Semantic filtering of articles to select the most relevant stories.
- Summarizing articles into a podcast script (dialogue format).
- Retry logic for API calls using `tenacity`.
"""
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
def filter_by_semantics(items: List[Dict[str, Any]], topics: List[str], model_name: str, limit: int = 10, audience: str = "general") -> List[Dict[str, Any]]:
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

    if audience == "kids":
        safety_instruction = "7. **Safety (Kids):** CRITICAL. Exclude stories involving murder, graphic violence, sexual content, disturbing crimes, or overly complex political intrigue. Prioritize science, space, nature, positive news, and understandable world events."
    else:
        safety_instruction = ""

    prompt = f"""
    You are a news editor. Your task is to select the top {limit} stories that are relevant to the following topics: {', '.join(topics)}.

    **CRITICAL SELECTION CRITERIA:**
    1. **Relevance:** Must match at least one of the topics.
    2. **Ordering:** Return the stories ordered strictly by the topics provided above. For example, if topics are "A, B", list all A stories first, then all B stories.
    3. **Importance:** Within each topic, prioritize critical/breaking news.
    4. **Diversity:** Ensure a good mix of different topics.
    5. **News vs Opinion:** STRICTLY EXCLUDE opinion pieces, editorials, commentaries, reviews, and "analysis" that is not grounded in new facts. Prioritize hard news.
    6. **Substance:** Exclude fluff, clickbait, or purely promotional content.
    {safety_instruction}

    Here are the candidate stories:
    {items_text}

    Return a JSON list of the indices (0-based) of the selected stories.
    Maximum count: {limit} stories (return fewer if not enough good matches).
    Example output: [0, 2, 5]
    Return ONLY the JSON list.
    """

    try:
        model = genai.GenerativeModel(model_name)
        # Force JSON response
        generation_config = {"response_mime_type": "application/json"}
        response = model.generate_content(prompt, generation_config=generation_config)
        
        text = response.text.strip()
        logger.debug(f"Gemini filtering response: {text}")

        # clean up potential markdown formatting (still good to have)
        if text.startswith("```"):
            # remove first line
            text = text.split("\n", 1)[1]
            # remove last line if it is backticks
            if text.strip().endswith("```"):
                text = text.rsplit("\n", 1)[0]
        
        if not text:
            logger.warning("Gemini returned empty text for filtering.")
            return []

        relevant_indices = json.loads(text)
        
        filtered_items = [items[i] for i in relevant_indices if isinstance(i, int) and 0 <= i < len(items)]
        # STRICTLY enforce the limit in code, regardless of what the LLM returns
        return filtered_items[:limit]

    except Exception as e:
        logger.error(f"Error in semantic filtering: {e}. Prompt preview: {prompt[:200]}...")
        if 'response' in locals() and hasattr(response, 'prompt_feedback'):
             logger.error(f"Prompt feedback: {response.prompt_feedback}")
        raise # Retry will catch this

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def summarize_with_gemini(articles: List[Dict[str, Any]], target_words: int, model_name: str, friendly_sources: str, audience: str = "general", show_name: str = "News Briefing", keywords: List[str] = None, greeting: str = "Hello") -> str:
    model = genai.GenerativeModel(model_name)

    articles_block = ""
    for idx, a in enumerate(articles, 1):
        articles_block += f"""
### Story {idx}
Title: {a.get('title')}
Summary: {a.get('summary')}
Source: {a.get('link')}
"""

    # Format keywords for the prompt
    keywords_str = ", ".join(keywords) if keywords else "today's topics"
    
    if audience == "kids":
       tone_instruction = "Tone: Energetic, simple, educational, fun, and engaging. Verify content is safe for legal minors (approx 10 years old). Explain complex terms simply. Break down complicated news into bite-sized, easy-to-understand concepts. Provide context where applicable"
       intro_instruction = f"HOST: High-energy intro! Start with '{greeting}!' and 'Welcome to {show_name}!' Start with an 'On This Day in History' fact relevant to these topics: {keywords_str}. Mention we are checking sources like {friendly_sources}."
    else:
       tone_instruction = "Tone: Conversational, engaging, energetic, bright, and yet professional. Professional news anchor style."
       intro_instruction = f"HOST: Intro. Start with '{greeting}!' and 'Welcome to {show_name}!' Start with an 'On This Day in History' fact relevant to these topics: {keywords_str}. Explicitly mention that we are covering news from {friendly_sources} and others."

    prompt = f"""
    You are writing a script for a professional news podcast featuring two speakers: a HOST and a REPORTER.

    **Format:**
    - Use "HOST:" for lines spoken by the host (Arjav).
    - Use "REPORTER:" for lines spoken by the reporter (Arohi).
    - {tone_instruction}
    - Don't keep repeating the name of the reporter or host in the conversation.
    - The HOST introduces the show, transitions between topics, and asks the REPORTER for details.
    - The REPORTER provides the in-depth news summaries and analysis.
    - End with the HOST signing off.

    **Constraints:**
    - Total length: STRICTLY ~{target_words} words. Do NOT exceed this.
    - Do NOT mention the word count or these instructions in the output.
    - Output ONLY the spoken dialogue script.
    - Be concise. Focus on the most important details.
    - Do NOT use markdown formatting (bold, italics) in the spoken text.
    - Do NOT include sound effects or music cues.
    - Ensure smooth transitions between stories.
    - Do NOT add any opinionated or editorialized language.

    **Source Material:**
    {articles_block}

    **Structure:**
    1. {intro_instruction}
    2. HOST & REPORTER: Dialogue covering the top stories. Group related stories together.
    3. HOST: Outro. Include a unique, surprising fun fact related to one of these topics: {keywords_str}. Vary the fact type each time (historical milestone, scientific discovery, cultural tidbit, technological breakthrough, etc.). Avoid generic or commonly known facts. Then sign off.
    """

    response = model.generate_content(prompt)
    return response.text

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def generate_themed_script(target_words: int, model_name: str, greeting: str, theme: str = "motivational", show_name: str = "Morning Spark") -> str:
    """
    Generates a script without news articles, focusing on a specific theme (e.g. motivation).
    """
    from datetime import datetime
    
    model = genai.GenerativeModel(model_name)
    
    # Theme-specific prompt additions
    theme_prompt = ""
    if theme == "motivational":
        theme_prompt = """
        **Theme: Daily Motivation & Positivity**
        - Concept: Provide a bright, uplifting, and energetic start to the day. 
        - Structure:
            1. Short, high-energy welcome.
            2. "Thought of the Day": A unique, powerful motivational quote or concept. Vary this daily (stoicism, modern psychology, gratitude, resilience, etc.).
            3. "Actionable Tip": A simple, practical thing the listener can do today to feel better or be more productive.
            4. "Good News Nugget": Briefly mention one generic positive thing about the world (e.g., "science is advancing," "spring is coming," "people are helping each other").
            5. Warm, encouraging sign-off.
        - Tone: Optimistic, not preachy, not religious. Like a helpful friend or life coach.
        """
    else:
        # Generic fallback
        theme_prompt = f"**Theme: {theme}**\nCreate an engaging podcast segment about {theme}."

    prompt = f"""
    You are writing a script for a short, single-host daily podcast.
    
    **Host Persona:** Warm, friends, encouraging, energetic. Name is "Arjav".
    
    **Format:**
    - Use "HOST:" for the spoken lines.
    - {tone_instruction if 'tone_instruction' in locals() else "Tone: Bright, clear, pacing is steady but energetic."}
    
    {theme_prompt}

    **Constraints:**
    - Total length: ~{target_words} words.
    - Output ONLY the spoken dialogue.
    - No sound effects or music cues.
    - No markdown formatting in speech.
    
    **Date Context:** Today is {datetime.now().strftime("%A, %B %d")}. Use this to make it feel fresh.
    """

    response = model.generate_content(prompt)
    return response.text
