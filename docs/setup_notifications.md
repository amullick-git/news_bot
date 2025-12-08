# Setting up Discord Notifications

This guide walks you through setting up automated notifications for your News Podcast Generator.

## Part 1: Get the Discord Webhook URL

1.  **Open Discord** (App or Website).
2.  Navigate to the **Server** where you want notifications.
3.  **Right-click** the text channel (e.g., `#general`) where the bot should post.
4.  Select **Edit Channel** (the Gear icon ⚙️).
5.  In the left sidebar, click **Integrations**.
6.  Click **Webhooks**.
    *   If there are none, click **Create Webhook**.
    *   If existing ones are there, click **New Webhook**.
7.  **Customize the Webhook**:
    *   **Name**: `News Bot` (or whatever you prefer).
    *   **Channel**: Ensure the correct channel is selected.
    *   *(Optional)* Upload an icon.
8.  **Copy the URL**:
    *   Click the button **Copy Webhook URL**.
    *   *Keep this URL secret! Anyone with it can post to your channel.*

## Part 2: Add Secret to GitHub

1.  **Go to your GitHub Repository** in a web browser.
2.  Click on the **Settings** tab (usually the rightmost tab).
3.  In the left sidebar, scroll down to the **Security** section.
4.  Click **Secrets and variables**, then select **Actions**.
5.  Click the green button **New repository secret**.
6.  **Fill in the details**:
    *   **Name**: `NOTIFICATION_WEBHOOK_URL`
    *   **Secret**: *Paste the Discord Webhook URL you copied in Part 1.*
7.  Click **Add secret**.

## Verification

To test that it works without waiting for the scheduled run:
1.  Go to the **Actions** tab in your repo.
2.  Select **Daily Podcast Generation** on the left.
3.  Click **Run workflow** -> **Run workflow**.
4.  Wait for it to finish. You should see a message in your Discord channel!
