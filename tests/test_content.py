import pytest
from unittest.mock import MagicMock, patch
from src.content import filter_by_semantics

def test_filter_by_semantics():
    items = [{"title": "A"}, {"title": "B"}, {"title": "C"}]
    
    with patch("src.content.genai") as mock_genai:
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value.text = "[0, 2]"
        
        filtered = filter_by_semantics(items, ["topic"], "model")
        
        assert len(filtered) == 2
        assert filtered[0]["title"] == "A"
        assert filtered[1]["title"] == "C"

def test_summarize_with_gemini_kids_prompt():
    from src.content import summarize_with_gemini
    
    with patch("src.content.genai") as mock_genai:
        mock_model = MagicMock()
        mock_genai.GenerativeModel.return_value = mock_model
        mock_model.generate_content.return_value.text = "Script"
        
        articles = [{"title": "T", "summary": "S", "link": "L"}]
        
        summarize_with_gemini(articles, 100, "model", "sources", audience="kids")
        
        # Verify prompt contains kids instruction
        call_args = mock_model.generate_content.call_args
        prompt = call_args[0][0]
        assert "Break down complicated news" in prompt
        assert "Provide context where applicable" in prompt
        assert "minors (approx 12 years old)" in prompt
