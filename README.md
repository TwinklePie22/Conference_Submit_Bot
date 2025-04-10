# Conference Submission Bot

A Python script to automate paper submissions to conferences on the [CMT3 platform](https://cmt3.research.microsoft.com). This bot logs into CMT3, navigates to submission pages, selects a category (e.g., "Data Science"), fills in the title and abstract, uploads a PDF, and submits the form for multiple conference URLs.

## Features

- Automates paper submissions to multiple CMT3 conference submission URLs.
- Configurable via external files for credentials, submission info, and URLs.
- Robust error handling with retries and logging.
- Tracks successful and failed submissions in a SQLite database.
- Optimized PDF upload: navigates to the PDF directory only for the first submission, speeding up subsequent uploads.
- Supports running via Docker, so no need to install Python or dependencies locally.
- Uses Selenium for reliable file uploads, compatible with headless environments.

## 📁 Project Structure

```
conference_submission_bot/
├── config/
│   ├── .env                        # Store CMT3 username and password (sensitive data)
│   ├── submission_info.json        # Store submission title, abstract, and PDF path
│   └── submission_urls.csv         # List of submission URLs
├── logs/
│   ├── submission.log             # Log file for debugging and tracking progress
│   └── submission_logs.db         # SQLite database for tracking successful/failed submissions
├── src/
│   ├── __init__.py                # Makes src a Python package
│   └── conference_submitter.py    # Main script with ConferenceSubmitter class
├── requirements.txt               # List of Python dependencies
├── Dockerfile                     # Docker configuration to build the project image
├── IEEE_Conference.pdf            # Your Conference Paper
├── README.md                      # Project Documentation
└── run.py                         # Entry point to run the script
```

## 🛠 Setup Instructions

You can run this project in two ways:
1. **Using Docker** (recommended if you don’t have Python installed).
2. **Traditional Setup** (requires Python and dependencies installed locally).

### Option 1: Running with Docker (No Python Installation Needed)

Docker allows you to run this project without installing Python, Chrome, or any dependencies on your machine. You only need to install Docker.

#### Prerequisites for Docker

1. **Install Docker**
   - Download and install Docker Desktop from [docker.com](https://www.docker.com/products/docker-desktop/).
   - For Windows and macOS, Docker Desktop includes everything you need.
   - For Linux, install Docker Engine: [Docker Engine Installation](https://docs.docker.com/engine/install/).
   - Verify Docker is installed:
     ```bash
     docker --version
     ```

2. **Clone the Repository**
   ```bash
   git clone https://github.com/TwinklePie22/Conference_Submit_Bot.git
   cd conference_submission_bot
   ```

3. **Configure the Project**

**Set Up the .env File**

```bash
touch config/.env
```
Open `config/.env` in a text editor and add your CMT3 credentials:
```
CMT3_USERNAME=your_email@example.com
CMT3_PASSWORD=your_password
```

**Configure submission_info.json**

```bash
touch config/submission_info.json
```

```json
{
    "title": "Your Paper Title",
    "abstract": "Your paper abstract goes here.",
    "pdf_path": "/app/IEEE_Conference.pdf"
}
```
Place your PDF file (e.g., `IEEE_Conference.pdf`) in the project root directory.

**Configure submission_urls.csv**

```bash
touch config/submission_urls.csv
```

```csv
submission_url
https://cmt3.research.microsoft.com/ICCTDC2025/Submission/Index
https://cmt3.research.microsoft.com/ICWITE2025/Submission/Index
```

4. ▶️**Pull the Existing Docker Image and Run it**

```bash
docker pull your-dockerhub-username/conference-submission-bot:latest
docker run --rm -it your-dockerhub-username/conference-submission-bot:latest
```
 OR 

**Build and Run the Docker Container**

Build the Docker Image
```bash
docker build -t conference-submission-bot .
```

Run the Container
```bash
docker run --rm -it conference-submission-bot
```

Optional: Mount Logs
```bash
docker run --rm -it -v $(pwd)/logs:/app/logs conference-submission-bot
```

### Option 2: Traditional Setup (Requires Python Installation)

1. **Install Python 3.8+** from [python.org](https://www.python.org/).
2. **Install Google Chrome** and matching **ChromeDriver** in your PATH.
3. **Clone the Repository**:
    ```bash
    git clone https://github.com/TwinklePie22/Conference_Submit_Bot.git
    cd conference_submission_bot
    ```
4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Configure Project Files**
    Same as the Docker setup above. For `pdf_path`, use a local path like:
    ```json
    {
        "title": "Your Paper Title",
        "abstract": "Your paper abstract goes here.",
        "pdf_path": "C:\\Users\\YourName\\Documents\\IEEE_Conference.pdf"
    }
    ```
6. ▶️**Run the Script**:
   ```bash
   python run.py
   ```

## 📄 Logs & Output
- **Log File**: `logs/submission.log`
- **Database**: `logs/submission_logs.db`
- **Console Output**: Shows real-time submission success/failure summary

<!-- ### Example Output
```
Submission Summary:
Successful submissions: 2
✓ https://cmt3.research.microsoft.com/ICCTDC2025/Submission/Index
✓ https://cmt3.research.microsoft.com/ICWITE2025/Submission/Index
Failed submissions: 1
X https://cmt3.research.microsoft.com/ICEI2026/Submission/Index
``` -->

## 🔧 Customization

### Changing the Submission Category
 
Modify the `category_selectors` in `src/conference_submitter.py`:
```python
category_selectors = [
    (By.XPATH, ".//a[contains(text(), 'Your Category')]"),
    (By.XPATH, ".//a[contains(text(), 'your category')"]),
    (By.XPATH, ".//a[contains(text(), 'Your')"]),
    (By.XPATH, ".//a[contains(text(), 'your')"]),
]
```

<!-- Change Retry Count  
Modify `max_retries` in `run.py`:
```python
submitter = ConferenceSubmitter(username, password, max_retries=5)
``` -->

## ❗Troubleshooting

### Docker Issues
### Docker Issues
- **Build Fails**: Make sure Docker is running and the PDF exists in the root before building.
- **File Upload Fails**: Set `pdf_path` to `/app/<your-pdf>` in `submission_info.json`.

### Traditional Setup Issues
- **ChromeDriver Not Found**: Ensure it’s installed and in PATH.
- **File Upload Fails**: Make sure the file path is correct.
- **Login Fails**: Check credentials and update selectors if CMT3 changes.

### 💡 Debugging Tips
- Check `logs/submission.log`
- Inspect `src/page_source.html` if an element isn’t found
- Use a single URL in `submission_urls.csv` to isolate issues

## 🤝 Contributing
- Happy to get contributions
- Make category configurable via `submission_info.json`

## 📜 License
MIT License. See `LICENSE`.

## 🙌 Acknowledgments
- Built with Selenium
- Uses PyAutoGUI (can be replaced for Docker use with Selenium)
- Inspired by the need to automate repetitive submission tasks

