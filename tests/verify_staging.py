import os
import sys
import subprocess
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

# Add root to path if needed (usually cwd is in path)
sys.path.append(os.getcwd())
try:
    from src import main as bot_main
except ImportError:
    # If specific imports fail unrelated to logic (e.g. missing keys during import time)
    pass

def verify_staging():
    print("=== Verifying Artifact Staging Logic ===")
    
    try:
        # 1. Mock External APIs to avoid keys and costs
        with patch("src.content.genai") as mock_genai, \
             patch("src.main.generate_rss_feed") as mock_rss, \
             patch("src.audio.texttospeech") as mock_tts, \
             patch("src.fetcher.feedparser.parse") as mock_feed:
             
            # Setup Gemini Mocks
            mock_model = MagicMock()
            mock_genai.GenerativeModel.return_value = mock_model
            
            # Prepare responses for Sequence: 
            # 1. Semantic Filter (JSON list of indices)
            # 2. Script Generation (Text)
            mock_filter_resp = MagicMock()
            mock_filter_resp.text = "[0, 1]"
            
            mock_script_resp = MagicMock()
            mock_script_resp.text = "HOST: MOCKED SCRIPT.\nREPORTER: END."
            
            # side_effect ensures sequential returns
            mock_model.generate_content.side_effect = [mock_filter_resp, mock_script_resp]
            
            # Mock TTS response
            mock_client = MagicMock()
            mock_tts.TextToSpeechClient.return_value = mock_client
            mock_client.synthesize_speech.return_value.audio_content = b"fake_audio"
            
            # Mock Feed Metadata
            mock_feed.return_value.feed = {"title": "Test News Source"}
            now_str = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
            mock_feed.return_value.entries = [
                {"title": "Test News 1", "link": "http://test.com/1", "summary": "Summary 1", "published": now_str},
                {"title": "Test News 2", "link": "http://test.com/2", "summary": "Summary 2", "published": now_str}
            ]
            
            # 2. Run the bot (Dry run / Test mode logic but in current dir)
            print("Running bot with mocks...")
            # Patch sys.argv to simulate command line args with unique type `verification_test`
            # This ensures generated files have distinct names we can clean up safely.
            with patch.object(sys, 'argv', ["main.py", "--duration", "1", "--type", "verification_test"]):
                try:
                    bot_main.main()
                except SystemExit:
                    pass
                except Exception as e:
                    print(f"Bot failed: {e}")
                    sys.exit(1)
            
            # 3. Check for modified files (sanity check)
            print("\nChecking git status prior to staging script...")
            # We expect files to be modified/untracked.
            status_output = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8")
            # print(f"Git status before staging:\n{status_output}") 
            
            if not status_output.strip():
                print("WARNING: No files were modified by the bot. Verification might be invalid.")
            
            # 3.1 NEW: Strict check for ignored files
            # Check if *production-like* filenames would be ignored.
            # We cannot check the actual generated verification_test files because they ARE ignored by design (*verification_test*)
            print("\nVerifying production artifacts are not git-ignored...")
            
            # Simulated files that should be tracked
            test_filenames = [
                "docs/episodes/episode_daily_2025-01-01_12.mp3",
                "docs/episodes/episode_script_daily_2025-01-01_12.txt",
                "docs/episodes/episode_metadata_daily_2025-01-01_12.json",
                "docs/episodes/links_daily_2025-01-01_12.html",
                "docs/episodes/episode_sources_daily_2025-01-01_12.md"
            ]
            
            for f in test_filenames:
                try:
                    # git check-ignore returns 0 if ignored (FAILURE for us), 1 if NOT ignored (SUCCESS)
                    subprocess.check_call(["git", "check-ignore", "-q", f])
                    print(f"FAILURE: Production file would be git-ignored: {f}")
                    sys.exit(1)
                except subprocess.CalledProcessError:
                    # Exit code 1 means NOT ignored. This is good.
                    pass
            print("SUCCESS: Production artifacts are properly tracked.")
            

            # 4. Run the staging script
            print("\nRunning scripts/stage_artifacts.sh...")
            subprocess.check_call(["./scripts/stage_artifacts.sh"])
            
            # 5. Verify that NO unstaged changes remain (for the files we care about)
            print("\nVerifying staging...")
            final_status = subprocess.check_output(["git", "status", "--porcelain"]).decode("utf-8")
            print(f"Git status after staging:\n{final_status}")
            
            lines = final_status.splitlines()
            unstaged_files = []
            for line in lines:
                if not line.strip(): continue
                code = line[:2]
                path = line[3:]
                
                # Ignored files
                if path == "feed.xml": continue 
                if path == "docs/feed.xml": continue
                if path.endswith(".py"): continue # Ignore source code changes
                if path.startswith("tests/"): continue
                
                # Check for unstaged modifications
                if "M" in code[1]: # Modified and unstaged (second column)
                    unstaged_files.append(path)
                elif code.startswith("??") and path.startswith("docs/episodes/"): 
                    # Untracked episode file means it wasn't staged!
                    unstaged_files.append(path)
                elif code == " M" and path == "docs/index.html": 
                     unstaged_files.append(path)
                     
            if unstaged_files:
                print("FAILURE: The following artifacts were modified/created but NOT staged by the script:")
                for f in unstaged_files:
                    print(f" - {f}")
                sys.exit(1)
            else:
                print("SUCCESS: All generated artifacts were correctly staged.")

    except Exception as e:
        print(f"Verification Failed with Exception: {e}")
        sys.exit(1)

    finally:
        # Cleanup: Undo changes to keep the working repository clean
        print("\nCleaning up verification artifacts...")
        try:
            # Restore staged/modified files (index.html, metrics)
            # Use --staged first to unstage, then restore to revert content
            subprocess.call(["git", "restore", "--staged", "docs/index.html", "metrics/metrics_prod.md", "metrics/metrics_stats.json"])
            subprocess.call(["git", "restore", "docs/index.html", "metrics/metrics_prod.md", "metrics/metrics_stats.json"])
            
            # Clean up test output directory if it exists
            if os.path.exists("test_output"):
                 import shutil
                 shutil.rmtree("test_output")
                 
            # Remove verification artifacts (using unique type identifier)
            # This targets ONLY the files created by --type verification_test
            subprocess.call("rm docs/episodes/episode_*verification_test*.mp3", shell=True)
            subprocess.call("rm docs/episodes/episode_*verification_test*.json", shell=True)
            subprocess.call("rm docs/episodes/episode_*verification_test*.md", shell=True)
            subprocess.call("rm docs/episodes/links_*verification_test*.html", shell=True)
            
        except Exception as e:
            print(f"Warning: Cleanup failed: {e}")

if __name__ == "__main__":
    verify_staging()
