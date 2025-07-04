#!/usr/bin/env python3
# webhook_listener.py

import Flask
from flask import request, jsonify
import logging
import subprocess
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(module)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Log to console
        # You might want to add logging.FileHandler("webhook_listener.log") in a real setup
    ]
)

app = Flask(__name__)

# Get the directory of the current script to find deployer.py
# This assumes deployer.py is in the same directory as webhook_listener.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEPLOYER_SCRIPT_PATH = os.path.join(BASE_DIR, 'deployer.py')
# Port for the applications deployed by deployer.py
# This should be managed more dynamically in a real system
# to avoid collisions if multiple apps are deployed.
# For now, we'll use a starting port and increment, or just a fixed one.
# Let's use a fixed one for simplicity in this iteration.
DEFAULT_DEPLOY_PORT = 5001


@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """
    Handles incoming webhook requests (e.g., from GitHub).
    """
    if request.method == 'POST':
        logging.info("Webhook received.")
        # Payload parsing and deployer triggering will be added in next steps.
        try:
            payload = request.get_json()
            if payload is None:
                logging.warning("No JSON payload received or content type not application/json.")
                return jsonify({"status": "error", "message": "Invalid JSON payload or content type"}), 400
            logging.info(f"Received payload: {payload}") # Log entire payload for now for debugging

            repo_url = None
            event_type = request.headers.get('X-GitHub-Event', 'unknown') # Get event type for GitHub
            logging.info(f"GitHub event type: {event_type}")

            if event_type == 'push':
                try:
                    repo_url = payload['repository']['clone_url']
                    pusher_name = payload.get('pusher', {}).get('name', 'unknown pusher')
                    branch_pushed_to = payload.get('ref', 'unknown ref').replace('refs/heads/', '')
                    logging.info(f"Push event detected for repository: {repo_url} by {pusher_name} to branch {branch_pushed_to}")

                    # For now, we'll only deploy if the push is to a common main/master branch.
                    # This can be made configurable.
                    # if branch_pushed_to not in ['main', 'master']:
                    #     logging.info(f"Push was to branch '{branch_pushed_to}', not 'main' or 'master'. No deployment triggered.")
                    #     return jsonify({"status": "ignored", "message": f"Push to branch {branch_pushed_to} ignored."}), 200

                except KeyError as e:
                    logging.warning(f"Could not extract repository URL or other details from push event payload. Missing key: {e}")
                    logging.debug(f"Payload structure: {payload}")
                    return jsonify({"status": "error", "message": f"Missing expected key in GitHub push payload: {e}"}), 400
            elif event_type == 'ping':
                # GitHub sends a 'ping' event when a webhook is first set up.
                repo_name = payload.get('repository', {}).get('full_name', 'N/A')
                zen_quote = payload.get('zen', 'No zen today.')
                logging.info(f"Received GitHub ping event for repository: {repo_name}. Zen: {zen_quote}")
                return jsonify({"status": "success", "message": "Ping event received successfully."}), 200
            else:
                logging.warning(f"Received unhandled event type: {event_type}. Only 'push' and 'ping' events are currently processed for GitHub.")
                # You might still want to extract a generic repo URL if available for other event types or providers
                # For example, payload.get('repository', {}).get('clone_url') or payload.get('repository', {}).get('html_url')
                # For now, we only act on 'push'.
                return jsonify({"status": "ignored", "message": f"Event type '{event_type}' not processed."}), 200

            if not repo_url:
                logging.warning("Repository URL could not be determined from the payload.")
                return jsonify({"status": "error", "message": "Could not determine repository URL from payload."}), 400

            # Placeholder for deployer.py triggering (next step)
            logging.info(f"Successfully extracted repository URL: {repo_url}. Ready to trigger deployment.")

            deployer_command = ['python3', DEPLOYER_SCRIPT_PATH, repo_url, '--port', str(DEFAULT_DEPLOY_PORT)]
            logging.info(f"Executing deployment command: {' '.join(deployer_command)}")

            try:
                # Using subprocess.run() will block until deployer.py completes.
                # For a more responsive webhook, Popen or a task queue would be better.
                process_result = subprocess.run(
                    deployer_command,
                    capture_output=True,
                    text=True,
                    check=False, # We'll check returncode manually to provide better logging
                    timeout=300 # Timeout of 5 minutes for the deployment script
                )

                if process_result.returncode == 0:
                    logging.info(f"deployer.py executed successfully for {repo_url}.")
                    logging.info(f"deployer.py stdout:\n{process_result.stdout}")
                    if process_result.stderr:
                         logging.warning(f"deployer.py stderr (though exited successfully):\n{process_result.stderr}")
                    return jsonify({"status": "success", "message": "Deployment triggered and completed.", "repository_url": repo_url, "deployer_stdout": process_result.stdout}), 200
                else:
                    logging.error(f"deployer.py failed for {repo_url} with exit code {process_result.returncode}.")
                    logging.error(f"deployer.py stdout:\n{process_result.stdout}")
                    logging.error(f"deployer.py stderr:\n{process_result.stderr}")
                    return jsonify({"status": "error", "message": "Deployment script failed.", "repository_url": repo_url, "deployer_stdout": process_result.stdout, "deployer_stderr": process_result.stderr}), 500

            except subprocess.TimeoutExpired:
                logging.error(f"deployer.py timed out for {repo_url}.")
                return jsonify({"status": "error", "message": "Deployment script timed out.", "repository_url": repo_url}), 500
            except FileNotFoundError:
                logging.error(f"deployer.py script not found at {DEPLOYER_SCRIPT_PATH}. Cannot trigger deployment.")
                return jsonify({"status": "error", "message": "Deployer script not found on server."}), 500
            except Exception as e:
                logging.error(f"An unexpected error occurred while trying to run deployer.py for {repo_url}: {e}", exc_info=True)
                return jsonify({"status": "error", "message": f"Internal error running deployment script: {e}"}), 500

        except Exception as e: # This outer exception is for errors in webhook parsing itself
            logging.error(f"Error processing webhook (before deployment trigger): {e}", exc_info=True)
            return jsonify({"status": "error", "message": "Internal server error during webhook processing"}), 500
    else:
        # Should not happen if methods=['POST'] is enforced by Flask, but as a fallback.
        logging.warning(f"Received non-POST request to /webhook: {request.method}")
        return jsonify({"status": "error", "message": "Method not allowed"}), 405

if __name__ == '__main__':
    listener_port = int(os.environ.get("LISTENER_PORT", 8000))
    logging.info(f"Starting webhook listener on port {listener_port}")
    # For development, Flask's dev server is fine.
    # For production, a proper WSGI server like Gunicorn or uWSGI should be used.
    app.run(host='0.0.0.0', port=listener_port, debug=False) # debug=False for now
