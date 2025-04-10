import os
from dotenv import load_dotenv
from src.conference_submitter import ConferenceSubmitter

def main():
    # Load environment variables from .env
    load_dotenv('config/.env')
    username = os.getenv('CMT3_USERNAME')
    password = os.getenv('CMT3_PASSWORD')

    if not username or not password:
        raise ValueError("CMT3_USERNAME and CMT3_PASSWORD must be set in config/.env")

    # Initialize and run the submitter
    submitter = ConferenceSubmitter(username, password, max_retries=2)
    submitter.run()

if __name__ == "__main__":
    main()