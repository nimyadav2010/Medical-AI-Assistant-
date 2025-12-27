# Healthcare Assistant - Deployment & Testing Guide

This guide explains how to share, test, and deploy the Healthcare Assistant application.

## Option 1: Sharing for Local Testing (Zip File)

If you want to share the project with your manager for testing on their local machine:

1.  **Prepare the Zip File:**
    *   Delete the `__pycache__` folders (they are auto-generated).
    *   You can exclude `chroma_db` if you want them to start fresh (they will need to run `setup_rag.py`).
    *   Zip the entire `Healthcare_Assistant` folder.

2.  **Instructions for the Manager:**
    *   Unzip the folder.
    *   Install Python (3.9 or higher).
    *   Open a terminal/command prompt in the folder.
    *   Install dependencies:
        ```bash
        pip install -r requirements.txt
        ```
    *   (Optional) If the database is missing, run:
        ```bash
        python setup_rag.py
        ```
    *   Run the application:
        ```bash
        streamlit run app.py
        ```
    *   The app will open in the browser at `http://localhost:8501`.

## Option 2: Docker Deployment (Recommended)

Docker ensures the app runs exactly the same way on any machine.

1.  **Build the Docker Image:**
    ```bash
    docker build -t healthcare-assistant .
    ```

2.  **Run the Container:**
    ```bash
    docker run -p 8501:8501 healthcare-assistant
    ```

3.  **Access the App:**
    *   Open `http://localhost:8501` in your browser.

## Option 3: Cloud Deployment (Streamlit Community Cloud)

The easiest way to host this for free is using Streamlit Community Cloud.

1.  **Push to GitHub:**
    *   Create a GitHub repository.
    *   Push this code to the repository.

2.  **Deploy:**
    *   Go to [share.streamlit.io](https://share.streamlit.io/).
    *   Connect your GitHub account.
    *   Select your repository and the main file (`app.py`).
    *   Click **Deploy**.

## Important Notes

*   **API Keys:** If you are using OpenAI, make sure to set the `OPENAI_API_KEY` in the `.env` file or as an environment variable in the deployment platform.
*   **Data Persistence:** In the Docker container, the `chroma_db` will be reset if you restart the container unless you use a volume.
    *   To persist data: `docker run -p 8501:8501 -v $(pwd)/chroma_db:/app/chroma_db healthcare-assistant`
