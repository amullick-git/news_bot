import pytest
from unittest.mock import patch, MagicMock
from src.audio import text_to_speech
from google.cloud import texttospeech

@pytest.fixture
def mock_tts_client():
    with patch('src.audio.texttospeech.TextToSpeechClient') as mock:
        client_instance = mock.return_value
        # Configure the response to have bytes content
        response = MagicMock()
        response.audio_content = b"fake_audio_bytes"
        client_instance.synthesize_speech.return_value = response
        yield mock

def test_voice_selection_wavenet_default(mock_tts_client):
    """Test that default voice type is WaveNet"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3") # Default
    
    # Check calls to synthesize_speech
    assert mock_instance.synthesize_speech.called
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Wavenet" in voice_params.name
    assert "Studio" in voice_params.name

def test_voice_selection_neural(mock_tts_client):
    """Test that voice_type='neural' selects Neural2 voices"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="neural")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Neural2" in voice_params.name

def test_voice_selection_studio(mock_tts_client):
    """Test that voice_type='studio' selects Studio voices"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="studio")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Studio" in voice_params.name

def test_voice_selection_chirp3_hd(mock_tts_client):
    """Test that voice_type='chirp3-hd' selects Chirp3 HD voices"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="chirp3-hd")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Chirp3-HD" in voice_params.name

def test_voice_selection_explicit_wavenet(mock_tts_client):
    """Test explicit 'wavenet' selection"""
    mock_instance = mock_tts_client.return_value
    
    text_to_speech("HOST: Hello.", "out.mp3", voice_type="wavenet")
    
    call_args = mock_instance.synthesize_speech.call_args
    voice_params = call_args.kwargs['voice']
    
    assert "Wavenet" in voice_params.name
