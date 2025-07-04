# Webhook Listener & Deployer: Installation, Deployment, and Testing Manual

This document provides instructions on how to set up, run, and test the webhook listener and the associated `deployer.py` script. This system allows for automatic deployment of simple Flask applications from GitHub repositories when a `push` event occurs.

## 1. Prerequisites

Before you begin, ensure you have the following installed on your system:

*   **Python 3** (version 3.7 or higher recommended)
*   **pip** (Python package installer, usually comes with Python 3)
*   **Git** (version control system)

You can check their installations by running:
```bash
python3 --version
pip3 --version
git --version
```

## 2. Installation

1.  **Get the Code:**
    *   Ensure you have the following Python scripts in the same directory:
        *   `webhook_listener.py`
        *   `deployer.py`

2.  **Install Python Dependencies:**
    *   The webhook listener requires the `Flask` library. Install it using pip:
        ```bash
        pip3 install Flask
        ```
    *   The `deployer.py` script itself does not have external library dependencies other than standard Python modules, but the Flask applications it deploys will have their own (specified in their `requirements.txt`).

## 3. Running the Webhook Listener

1.  **Navigate to the Directory:**
    Open your terminal and change to the directory where `webhook_listener.py` and `deployer.py` are located.

2.  **Start the Listener:**
    Run the following command:
    ```bash
    python3 webhook_listener.py
    ```
    *   By default, the listener will start on port `8000`. You can change this by setting the `LISTENER_PORT` environment variable:
        ```bash
        LISTENER_PORT=8081 python3 webhook_listener.py
        ```
    *   You should see log output indicating the listener has started, e.g.:
        `INFO - Starting webhook listener on port 8000`

3.  **Keep the Listener Running:**
    The listener needs to be running continuously to receive webhooks. If you close the terminal, the listener will stop. For persistent operation in a production environment, consider using a process manager like `systemd`, `supervisor`, or running it within a Docker container with a proper WSGI server (like Gunicorn).

## 4. Configuring Webhook on GitHub

To make GitHub send events to your listener, you need to configure a webhook in your target GitHub repository (the one you want to automatically deploy).

1.  **Expose Your Listener to the Internet:**
    *   GitHub needs to be able to send HTTP POST requests to your listener. If your listener is running on your local machine, it's likely not directly accessible from the internet.
    *   **For local testing, `ngrok` is highly recommended.** `ngrok` creates a secure tunnel to your local machine and gives you a public URL.
        *   Download and install ngrok from [https://ngrok.com/](https://ngrok.com/).
        *   If your listener is running on port `8000`, run: `ngrok http 8000`
        *   `ngrok` will display a public "Forwarding" URL (e.g., `https://<random_string>.ngrok.io`). Use this URL as your Payload URL.
    *   If deploying on a server with a public IP, use `http://<your_server_public_ip>:<listener_port>/webhook`.

2.  **Add Webhook in GitHub Repository:**
    *   Go to your GitHub repository.
    *   Click on **Settings**.
    *   In the left sidebar, click on **Webhooks**.
    *   Click the **Add webhook** button.
    *   **Payload URL:** Enter the public URL of your listener (e.g., your ngrok URL or public server URL followed by `/webhook`). Example: `https://<random_string>.ngrok.io/webhook`
    *   **Content type:** Select `application/json`.
    *   **Secret:**
        *   For this version of the listener, webhook signature verification is **not implemented**. You can leave this field blank for now.
        *   **Important Security Note:** In a production environment, you should **always** set a secret and implement signature verification in your listener to ensure requests are genuinely from GitHub.
    *   **Which events would you like to trigger this webhook?**
        *   Select "Just the `push` event." (This is usually sufficient for CI/CD on code changes).
    *   **Active:** Ensure this checkbox is checked.
    *   Click **Add webhook**.

3.  **Initial Ping Event:**
    *   GitHub will immediately send a "ping" event to your Payload URL.
    *   Check the console output of your `webhook_listener.py`. You should see logs indicating a "ping" event was received, e.g.:
        `INFO - Received GitHub ping event for repository: <your_username>/<your_repo_name>. Zen: <some_quote>`
    *   In GitHub's webhook settings, you should see a green checkmark next to the ping event in "Recent Deliveries" if it was successful.

## 5. Testing the Full CI/CD Flow

1.  **Prepare a Test Flask Application Repository:**
    *   Ensure you have a simple Flask application in a GitHub repository.
    *   This application **must** have a `requirements.txt` file at its root.
    *   It should be runnable by `flask run`, `python app.py`, or `python main.py`.
    *   Example: A simple `app.py`:
        ```python
        from flask import Flask
        app = Flask(__name__)
        @app.route('/')
        def hello_world():
            return 'Hello from Auto-Deployed App!'
        if __name__ == '__main__':
            app.run(host='0.0.0.0', port=5000) # Port will be overridden by deployer.py
        ```
    *   And a `requirements.txt`:
        ```
        Flask
        ```
    *   Commit and push this to your GitHub repository for which you configured the webhook.

2.  **Trigger the Webhook:**
    *   Make a change to your test Flask application repository (e.g., modify a file, add a new one).
    *   Commit and `git push` the changes to GitHub (to the branch your webhook is watching, typically `main` or `master`).

3.  **Observe Logs:**
    *   **`webhook_listener.py` logs:**
        *   You should see a "Webhook received" message.
        *   Followed by "Push event detected for repository: <your_repo_url>..."
        *   Then "Executing deployment command: python3 ./deployer.py <your_repo_url> --port 5001" (or the configured deploy port).
        *   Finally, logs indicating success or failure of `deployer.py`, including its stdout/stderr.
    *   **`deployer.py` logs (as captured by the listener):**
        *   Cloning messages, venv creation, dependency installation, and Flask application startup messages.

4.  **Verify Deployed Application:**
    *   If `deployer.py` successfully started the Flask application, it should be accessible on the port specified by `DEFAULT_DEPLOY_PORT` in `webhook_listener.py` (default is `5001`).
    *   Open your browser and go to `http://localhost:5001` (if running the listener locally) or `http://<your_server_ip>:5001`.
    *   You should see your Flask application running.

5.  **Stopping the Deployed Application:**
    *   The `deployer.py` script runs the Flask app and waits for Ctrl+C to stop *that specific deployment*.
    *   When triggered by the webhook listener, `deployer.py` runs as a subprocess. The listener currently uses `subprocess.run()` which waits for it to complete.
    *   **Important:** The current setup does not manage multiple deployments or stop old ones when a new one starts. Each trigger will attempt to run `deployer.py`, which will then try to use the `DEFAULT_DEPLOY_PORT`. If an old app is still running on that port, `deployer.py` might fail to start the new one. True process management is an advanced topic.

## 6. Manual Testing with `curl` (Alternative to GitHub Webhook)

If you want to test the listener without setting up a full GitHub webhook, or to debug payload issues, you can use `curl` to simulate a GitHub POST request.

1.  **Sample GitHub Push Payload (`payload.json`):**
    Create a file named `payload.json` with a minimal structure like this (replace with your actual repository details):
    ```json
    {
      "ref": "refs/heads/main",
      "repository": {
        "name": "my-test-flask-app",
        "full_name": "your_username/my-test-flask-app",
        "clone_url": "https://github.com/your_username/my-test-flask-app.git",
        "html_url": "https://github.com/your_username/my-test-flask-app"
      },
      "pusher": {
        "name": "your_username",
        "email": "your_email@example.com"
      }
    }
    ```
    *(Ensure the `clone_url` points to a repository `deployer.py` can actually clone and run.)*

2.  **Send the Request with `curl`:**
    Open your terminal and run (ensure `webhook_listener.py` is running):
    ```bash
    curl -X POST \
         -H "Content-Type: application/json" \
         -H "X-GitHub-Event: push" \
         -d @payload.json \
         http://localhost:8000/webhook
    ```
    *   `-H "X-GitHub-Event: push"` simulates a push event header.
    *   `-d @payload.json` sends the content of `payload.json` as the request body.

3.  **Check Listener Logs:**
    Observe the `webhook_listener.py` console output for processing details.

## 7. Troubleshooting

*   **"No JSON payload received" or "Invalid JSON payload" in listener logs:**
    *   Ensure your webhook in GitHub is set to "Content type: `application/json`".
    *   If using `curl`, ensure you have `-H "Content-Type: application/json"` and a valid JSON body.
*   **`deployer.py` script not found:**
    *   Verify `deployer.py` is in the same directory as `webhook_listener.py` or that `DEPLOYER_SCRIPT_PATH` in `webhook_listener.py` is correct.
*   **`deployer.py` fails:**
    *   Check the stdout/stderr from `deployer.py` printed in the listener's logs. This will usually indicate issues like:
        *   Git cloning problems (repository not found, permissions).
        *   Python/venv setup issues.
        *   Missing `requirements.txt` in the target repository.
        *   Errors within the target Flask application itself.
*   **Port conflicts:**
    *   Ensure the listener port (e.g., 8000) is free.
    *   Ensure the `DEFAULT_DEPLOY_PORT` (e.g., 5001) used by `deployer.py` is free before a new deployment. The current system doesn't handle stopping old deployments.

This manual should provide a good starting point for testing the system. Remember that this is a simplified setup and production deployments would require more robust error handling, security, and process management.
