#!/usr/bin/env python3
# deployer.py

import subprocess
import logging
import shutil
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def clone_repo(repo_url, clone_dir):
    """
    Clones a Git repository from repo_url into clone_dir.
    """
    if os.path.exists(clone_dir):
        logging.info(f"Directory {clone_dir} already exists. Removing it.")
        shutil.rmtree(clone_dir) # Remove existing directory to ensure a fresh clone
    os.makedirs(clone_dir) # Create the directory after ensuring it's empty

    logging.info(f"Cloning repository from {repo_url} into {clone_dir}...")
    try:
        process = subprocess.run(
            ['git', 'clone', repo_url, clone_dir],
            capture_output=True,
            text=True,
            check=True
        )
        logging.info(f"Repository cloned successfully. Output:\n{process.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Failed to clone repository. Error:\n{e.stderr}")
        return False
    except FileNotFoundError:
        logging.error("Git command not found. Please ensure Git is installed and in your PATH.")
        return False

import argparse
import tempfile

def main():
    """
    Main function to orchestrate the deployment process.
    """
    parser = argparse.ArgumentParser(description="Clone a Git repository and run a Flask application.")
    parser.add_argument("repo_url", help="The URL of the Git repository to clone.")
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="The port number to run the Flask application on (default: 5000)."
    )
    args = parser.parse_args()

import signal
import time

def main():
    """
    Main function to orchestrate the deployment process.
    """
    parser = argparse.ArgumentParser(description="Clone a Git repository and run a Flask application.")
    parser.add_argument("repo_url", help="The URL of the Git repository to clone.")
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="The port number to run the Flask application on (default: 5000)."
    )
    args = parser.parse_args()

    logging.info(f"Attempting to deploy: {args.repo_url} on port {args.port}")

    app_process = None
    # Create a temporary directory for cloning the repository
    # temp_dir = tempfile.mkdtemp() # This creates a directory like /tmp/tmpXXXXXX
    # For easier inspection during development, let's use a fixed name for now,
    # but tempfile.mkdtemp() is better for production.
    temp_dir_name = "cloned_flask_app_temp"
    # Ensure the path is absolute for clarity and to avoid issues with os.chdir
    temp_clone_dir = os.path.abspath(temp_dir_name)

    logging.info(f"Temporary clone directory: {temp_clone_dir}")

    original_sigint_handler = signal.getsignal(signal.SIGINT)

    def signal_handler(sig, frame):
        logging.info("SIGINT received, shutting down...")
        if app_process and app_process.poll() is None: # Check if process exists and is running
            logging.info(f"Terminating Flask app process {app_process.pid}...")
            app_process.terminate() # Send SIGTERM
            try:
                app_process.wait(timeout=10) # Wait for up to 10 seconds
            except subprocess.TimeoutExpired:
                logging.warning(f"Flask app process {app_process.pid} did not terminate in time, killing.")
                app_process.kill() # Send SIGKILL if it doesn't terminate
            logging.info("Flask app process terminated.")

        # Restore original SIGINT handler to allow Python to exit cleanly
        # if it needs to handle a second Ctrl+C (e.g. if cleanup hangs)
        signal.signal(signal.SIGINT, original_sigint_handler)
        # The finally block will handle cleanup
        # Raising KeyboardInterrupt to stop the main loop if it's in one
        raise KeyboardInterrupt

    signal.signal(signal.SIGINT, signal_handler)

    try:
        if clone_repo(args.repo_url, temp_clone_dir):
            logging.info(f"Repository cloned successfully to {temp_clone_dir}")
            app_process = run_flask_app(temp_clone_dir, args.port)

            if app_process:
                logging.info(f"Flask application started. PID: {app_process.pid}. Access it at http://0.0.0.0:{args.port}")
                logging.info("Press Ctrl+C to stop the application and clean up.")

                # Keep the script alive while the app is running
                # and periodically print output if any
                while app_process.poll() is None:
                    try:
                        # Non-blocking read of stdout/stderr
                        stdout_line = app_process.stdout.readline()
                        stderr_line = app_process.stderr.readline()
                        if stdout_line:
                            logging.info(f"[App STDOUT]: {stdout_line.strip()}")
                        if stderr_line:
                            logging.warning(f"[App STDERR]: {stderr_line.strip()}")
                        time.sleep(0.1) # Prevent busy-waiting
                    except Exception as e: # Handle cases where readline might fail if process closes stream
                        logging.debug(f"Exception while reading app output: {e}")
                        break

                # After loop, check exit code
                exit_code = app_process.returncode
                logging.info(f"Flask application process exited with code {exit_code}.")

            else:
                logging.error("Failed to start the Flask application.")
        else:
            logging.error(f"Failed to clone repository: {args.repo_url}")

    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Exiting.")
    except Exception as e:
        logging.error(f"An unexpected error occurred in main: {e}", exc_info=True)
    finally:
        logging.info(f"Cleaning up temporary directory: {temp_clone_dir}")
        if os.path.exists(temp_clone_dir):
            shutil.rmtree(temp_clone_dir)
            logging.info(f"Temporary directory {temp_clone_dir} removed.")
        else:
            logging.info(f"Temporary directory {temp_clone_dir} not found, no cleanup needed or already cleaned.")

        # Ensure the original SIGINT handler is restored if we exited abnormally
        # before the signal_handler function itself restored it.
        current_handler = signal.getsignal(signal.SIGINT)
        if current_handler is signal_handler: # Check if our handler is still installed
             signal.signal(signal.SIGINT, original_sigint_handler)
        logging.info("Script finished.")


def run_flask_app(app_dir, port):
    """
    Sets up a virtual environment, installs dependencies,
    and runs a Flask application.
    """
    logging.info(f"Attempting to run Flask app in {app_dir} on port {port}")
    original_cwd = os.getcwd()

    try:
        os.chdir(app_dir)
        logging.info(f"Changed directory to {os.getcwd()}")

        # 1. Create virtual environment
        venv_dir = os.path.join(os.getcwd(), "venv")
        logging.info(f"Creating virtual environment in {venv_dir}...")
        try:
            process_venv = subprocess.run(
                ['python3', '-m', 'venv', 'venv'],
                capture_output=True, text=True, check=True
            )
            logging.info(f"Venv creation stdout:\n{process_venv.stdout}")
        except subprocess.CalledProcessError as e:
            logging.error(f"Failed to create virtual environment. Error:\n{e.stderr}")
            return None # Indicate failure
        except FileNotFoundError:
            logging.error("python3 command not found. Please ensure Python 3 is installed and in your PATH.")
            return None


        # Determine paths for venv executables
        pip_executable = os.path.join(venv_dir, 'bin', 'pip')
        python_executable = os.path.join(venv_dir, 'bin', 'python')

        # 2. Install dependencies
        requirements_file = 'requirements.txt'
        if os.path.exists(requirements_file):
            logging.info(f"Installing dependencies from {requirements_file}...")
            try:
                process_deps = subprocess.run(
                    [pip_executable, 'install', '-r', requirements_file],
                    capture_output=True, text=True, check=True
                )
                logging.info(f"Dependencies installation stdout:\n{process_deps.stdout}")
            except subprocess.CalledProcessError as e:
                logging.error(f"Failed to install dependencies. Error:\n{e.stderr}")
                # Optionally, continue if non-critical, but for now, let's treat as failure
                return None
        else:
            logging.warning(f"{requirements_file} not found. Skipping dependency installation.")

        # 3. Run Flask application
        # Try `flask run`
        logging.info(f"Attempting to run with 'flask run' on port {port}...")
        flask_command = [python_executable, '-m', 'flask', 'run', '--host=0.0.0.0', f'--port={port}']

        # For running the app, we use Popen to run it as a background process
        app_process = None
        try:
            # We need to pass the environment of the current process,
            # and potentially modify PATH if `flask` isn't found directly by python -m
            # However, `python -m flask` should generally work if flask is installed in the venv.
            app_process = subprocess.Popen(flask_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            logging.info(f"Flask app started with PID: {app_process.pid}. Waiting for it to be accessible...")
            # Here, we might add a small delay or a check to see if the port is open
            time.sleep(2) # Wait a couple of seconds for the process to potentially fail
            if app_process.poll() is None: # Check if the process is still running
                logging.info(f"Flask app with 'flask run' seems to be running (PID: {app_process.pid}).")
                return app_process
            else:
                logging.warning(f"'flask run' process exited quickly with code {app_process.poll()}. Reading output...")
                stdout, stderr = app_process.communicate()
                if stdout:
                    logging.info(f"Flask run stdout: {stdout.strip()}")
                if stderr:
                    logging.warning(f"Flask run stderr: {stderr.strip()}")
                logging.warning("Proceeding to fallbacks.")
                app_process = None # Ensure app_process is None so fallbacks trigger correctly

        except FileNotFoundError:
            logging.warning("'flask' command (via python -m flask) not found. Trying common app script names.")
            app_process = None # Ensure app_process is None
        except Exception as e: # Catch other potential errors from Popen
            logging.error(f"Failed to start Flask app with 'flask run'. Error: {e}")
            app_process = None # Ensure app_process is None
            # Fall through to try python app.py / main.py

        # Fallback: Try `python app.py`
        # Ensure app_process is None if previous attempts failed to launch or exited quickly
        if app_process is None:
            logging.info("Attempting to run with 'python app.py'...")
            app_py_path = 'app.py'
            if os.path.exists(app_py_path):
                try:
                    app_process = subprocess.Popen(
                        [python_executable, app_py_path],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        env={**os.environ, 'FLASK_RUN_PORT': str(port), 'FLASK_RUN_HOST': '0.0.0.0'} # Pass port via env
                    )
                    logging.info(f"Flask app started with 'python app.py' PID: {app_process.pid}.")
                    return app_process
                except Exception as e:
                    logging.error(f"Failed to start app with 'python app.py'. Error: {e}")
            else:
                logging.warning("'app.py' not found.")

        # Fallback: Try `python main.py`
        if not app_process or app_process.poll() is not None:
            logging.info("Attempting to run with 'python main.py'...")
            main_py_path = 'main.py'
            if os.path.exists(main_py_path):
                try:
                    app_process = subprocess.Popen(
                        [python_executable, main_py_path],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                        env={**os.environ, 'FLASK_RUN_PORT': str(port), 'FLASK_RUN_HOST': '0.0.0.0'}
                    )
                    logging.info(f"Flask app started with 'python main.py' PID: {app_process.pid}.")
                    return app_process
                except Exception as e:
                    logging.error(f"Failed to start app with 'python main.py'. Error: {e}")
            else:
                logging.warning("'main.py' not found.")

        logging.error("Could not start the Flask application using any known method.")
        return None

    except Exception as e:
        logging.error(f"An unexpected error occurred in run_flask_app: {e}")
        return None
    finally:
        # Change back to original directory
        os.chdir(original_cwd)
        logging.info(f"Restored original directory: {os.getcwd()}")


if __name__ == "__main__":
    main()
