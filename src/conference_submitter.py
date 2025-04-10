import sqlite3
import time
import logging
import os
import json
import csv
import pyautogui
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, TimeoutException, 
    WebDriverException, ElementClickInterceptedException,
    InvalidSessionIdException, NoSuchWindowException 
)

class ConferenceSubmitter:
    def __init__(self, username, password, max_retries=3):
        self.username = username
        self.password = password
        self.max_retries = max_retries
        self.is_first_upload = True  # Track if it's the first upload
        self.script_dir = os.path.dirname(os.path.abspath(__file__))
        self.setup_logging()
        self.load_submission_info()
        self.load_submission_urls()
        self.setup_database()
        self.setup_browser()

    def setup_logging(self):
        log_dir = os.path.join(os.path.dirname(self.script_dir), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'submission.log')
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def load_submission_info(self):
        config_dir = os.path.join(os.path.dirname(self.script_dir), 'config')
        submission_info_path = os.path.join(config_dir, 'submission_info.json')
        try:
            with open(submission_info_path, 'r') as f:
                submission_info = json.load(f)
            self.title = submission_info['title']
            self.abstract = submission_info['abstract']
            self.pdf_path = submission_info['pdf_path']  # Load pdf_path from JSON
            self.logger.debug("Loaded submission info from submission_info.json")
        except FileNotFoundError:
            self.logger.error(f"submission_info.json not found at {submission_info_path}")
            raise
        except json.JSONDecodeError as e:
            self.logger.error(f"Invalid JSON in submission_info.json: {str(e)}")
            raise
        except KeyError as e:
            self.logger.error(f"Missing required field in submission_info.json: {str(e)}")
            raise

    def load_submission_urls(self):
        config_dir = os.path.join(os.path.dirname(self.script_dir), 'config')
        submission_urls_path = os.path.join(config_dir, 'submission_urls.csv')
        self.urls = []
        try:
            with open(submission_urls_path, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    self.urls.append(row['submission_url'])
            self.logger.debug(f"Loaded {len(self.urls)} submission URLs from submission_urls.csv")
        except FileNotFoundError:
            self.logger.error(f"submission_urls.csv not found at {submission_urls_path}")
            raise
        except KeyError:
            self.logger.error("submission_urls.csv must contain a 'submission_url' column")
            raise
        except Exception as e:
            self.logger.error(f"Failed to read submission_urls.csv: {str(e)}")
            raise

    def setup_database(self):
        log_dir = os.path.join(os.path.dirname(self.script_dir), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        db_file = os.path.join(log_dir, 'submission_logs.db')
        try:
            self.conn = sqlite3.connect(db_file)
            self.cursor = self.conn.cursor()
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS failed_links (
                    link TEXT PRIMARY_KEY,
                    error_type TEXT,
                    error_message TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS successful_links (
                    link TEXT PRIMARY_KEY,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.conn.commit()
            self.logger.debug(f"Database setup complete at {db_file}")
        except sqlite3.Error as e:
            self.logger.error(f"Database setup failed: {e}")
            raise

    def setup_browser(self):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--remote-debugging-port=9222")
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            prefs = {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False
            }
            chrome_options.add_experimental_option("prefs", prefs)
            chrome_options.add_argument("--disable-popup-blocking")
            chrome_options.add_argument("--disable-notifications")
            chrome_options.add_argument("--start-maximized")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.set_page_load_timeout(30)
            self.logger.debug("Browser initialized successfully")
        except WebDriverException as e:
            self.logger.error(f"Browser setup failed: {e}")
            raise

    def log_failure(self, url, error_type, error_message):
        try:
            self.cursor.execute(
                'INSERT OR IGNORE INTO failed_links (link, error_type, error_message) VALUES (?, ?, ?)',
                (url, error_type, error_message)
            )
            self.conn.commit()
            self.logger.warning(f"Logged failure - URL: {url}, Type: {error_type}, Message: {error_message}")
        except sqlite3.Error as e:
            self.logger.error(f"Database logging failed: {e}")

    def log_successful_link(self, url):
        try:
            self.cursor.execute(
                'INSERT OR IGNORE INTO successful_links (link) VALUES (?)',
                (url,)
            )
            self.conn.commit()
            self.logger.debug(f"Logged successful link: {url}")
        except sqlite3.Error as e:
            self.logger.error(f"Failed to log successful link {url}: {str(e)}")

    def login_to_cmt3(self):
        login_url = "https://cmt3.research.microsoft.com/User/Login?ReturnUrl=%2FConference%2FRecent"
        try:
            self.logger.debug("Navigating to CMT3 login page")
            self.driver.get(login_url)
            self.logger.debug(f"Loaded URL: {self.driver.current_url}")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            self.logger.debug("Page body loaded")
            username_selectors = [
                (By.XPATH, "//input[@placeholder='Email']")
            ]
            password_selectors = [
                (By.XPATH, "//input[@type='password']")
            ]
            submit_selectors = [
                (By.XPATH, "//button[text()='Log In']")
            ]
            username_field = None
            for by, value in username_selectors:
                try:
                    username_field = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((by, value))
                    )
                    self.logger.debug(f"Found username field with {by}: {value}")
                    break
                except TimeoutException:
                    continue
            if not username_field:
                self.logger.error("Username field not found. Page source saved to page_source.html")
                raise NoSuchElementException("Username field not found with any selector")
            password_field = None
            for by, value in password_selectors:
                try:
                    password_field = self.driver.find_element(by, value)
                    self.logger.debug(f"Found password field with {by}: {value}")
                    break
                except NoSuchElementException:
                    continue
            if not password_field:
                self.logger.error("Password field not found with any selector")
                raise NoSuchElementException("Password field not found with any selector")
            login_button = None
            for by, value in submit_selectors:
                try:
                    login_button = self.driver.find_element(by, value)
                    self.logger.debug(f"Found submit button with {by}: {value}")
                    break
                except NoSuchElementException:
                    continue
            if not login_button:
                self.logger.error("Submit button not found with any selector")
                raise NoSuchElementException("Submit button not found with any selector")
            self.logger.debug("Filling login credentials")
            username_field.clear()
            username_field.send_keys(self.username)
            password_field.clear()
            password_field.send_keys(self.password)
            self.logger.debug("Clicking login button")
            login_button.click()
            WebDriverWait(self.driver, 15).until(
                EC.url_contains("/Conference/Recent")
            )
            self.logger.info("Successfully logged in to CMT3 and redirected to Recent Conferences")
            return True
        except TimeoutException as e:
            self.logger.error(f"Login failed - Timeout: {str(e)}")
            return False
        except NoSuchElementException as e:
            self.logger.error(f"Login failed - Element not found: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"Login failed - Unexpected error: {str(e)}")
            return False

    def submit_form(self, url):
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"Attempt {attempt + 1}/{self.max_retries} for URL: {url}")
                self.driver.get(url)
                self.logger.debug(f"Loaded URL: {self.driver.current_url}")
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                self.logger.debug("Page body loaded")

                # Click "+Create new submission"
                self.logger.debug("Looking for '+Create new submission' button")
                new_submission_btn = None
                new_submission_selectors = [
                    (By.XPATH, "//a[contains(@href, 'Create') and contains(@role, 'button')]"),
                    (By.CSS_SELECTOR, "a.btn.dropdown-toggle")
                ]
                for by, value in new_submission_selectors:
                    try:
                        new_submission_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((by, value))
                        )
                        self.logger.debug(f"Found 'Create new submission' button with {by}: {value}")
                        break
                    except TimeoutException:
                        self.logger.debug(f"Could not find button with {by}: {value}")
                        continue
                if not new_submission_btn:
                    self.logger.error("'Create new submission' button not found with any selector")
                    raise NoSuchElementException("'Create new submission' button not found")

                new_submission_btn.click()
                self.logger.debug("Clicked '+Create new submission'")

                # Wait for dropdown menu to appear
                self.logger.debug("Waiting for dropdown menu to appear")
                dropdown_menu_selectors = [
                    (By.XPATH, "//ul[contains(@class, 'dropdown-menu') and contains(@class, 'show')]")  
                ]
                dropdown_menu = None
                for by, value in dropdown_menu_selectors:
                    try:
                        dropdown_menu = WebDriverWait(self.driver, 5).until(
                            EC.visibility_of_element_located((by, value))
                        )
                        self.logger.debug(f"Found dropdown menu with {by}: {value}")
                        break
                    except TimeoutException:
                        self.logger.debug(f"Dropdown menu not found with {by}: {value}")
                        continue

                if not dropdown_menu:
                    self.logger.warning("Dropdown menu not found, proceeding to form (might not be required)")
                    # with open(os.path.join(self.script_dir, f'dropdown_failure_{url.split("/")[-3]}.html'), 'w', encoding='utf-8') as f:
                    #     f.write(self.driver.page_source)
                    # self.logger.debug(f"Page source saved for {url}")

                # Select "Data Science" from the menu
                if dropdown_menu:
                    # Log all dropdown items for debugging
                    items = dropdown_menu.find_elements(By.XPATH, ".//a")
                    for item in items:
                        item_text = item.text.strip()
                        self.logger.debug(f"Dropdown item found: '{item_text}'")

                    category_selectors = [
                        (By.XPATH, ".//a[contains(text(), 'Data Science')]"),
                        (By.XPATH, ".//a[contains(text(), 'data science')]"),
                        (By.XPATH, ".//a[contains(text(), 'Data')]"),
                        (By.XPATH, ".//a[contains(text(), 'data')]"),
                        (By.XPATH, ".//a[contains(text(), 'Image Processing')]"),
                        (By.XPATH, ".//a[contains(text(), 'image processing')]"),
                        (By.XPATH, ".//a[contains(text(), 'Image')]"),
                        (By.XPATH, ".//a[contains(text(), 'image')]"),
                        (By.XPATH, ".//a[contains(text(), 'Artificial Intelligence')]"),
                        (By.XPATH, ".//a[contains(text(), 'atificial ielligence')]"),
                        (By.XPATH, ".//a[contains(text(), 'AI]"),
                        (By.XPATH, ".//a[contains(text(), 'Machine Learning')]"),
                        (By.XPATH, ".//a[contains(text(), 'Machine learning')]"),
                        (By.XPATH, ".//a[contains(text(), 'machine learning')]"),
                        (By.XPATH, ".//a[contains(text(), 'ML')]"),
                        (By.XPATH, ".//a[contains(text(), 'ml')]"),
                        (By.XPATH, "..//a[contains(text(), 'Smart Computing')]")
                    ]
                    data_science_option = None
                    selected = None
                    for by, value in category_selectors:
                        try:
                            data_science_option = WebDriverWait(dropdown_menu, 5).until(
                                EC.element_to_be_clickable((by, value))
                            )
                            self.logger.debug(f"Found suitable option with {by}: {value}")
                            selected = value
                            break
                        except TimeoutException:
                            self.logger.debug(f"Suitable option not found with {by}: {value}")
                            continue

                    if data_science_option:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", data_science_option)
                        data_science_option.click()
                        self.logger.info(f"Selected {selected} category")
                    else:
                        self.logger.warning("Suitable option not found in menu, proceeding to form")
                        # with open(os.path.join(self.script_dir, f'data_science_failure_{url.split("/")[-3]}.html'), 'w', encoding='utf-8') as f:
                        #     f.write(self.driver.page_source)
                        # self.logger.debug(f"Page source saved for {url}")

                time.sleep(1)
                self.logger.debug("Waiting for submission form to load")
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "form"))
                )
                self.logger.debug("Submission form loaded successfully")

                try:
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    self.logger.warning(f"Alert found: {alert_text}")
                    alert.dismiss()
                    self.logger.debug("Alert dismissed")
                except:
                    self.logger.debug("No alert present")

                def presence_of_any_element(*locators):
                    def _predicate(driver):
                        for locator in locators:
                            try:
                                element = driver.find_element(*locator)
                                if element.is_displayed():
                                    self.logger.debug(f"Found element with locator {locator}")
                                    return element
                                else:
                                    self.logger.debug(f"Element with locator {locator} is not displayed")
                            except:
                                self.logger.debug(f"Element not found with locator {locator}")
                                continue
                        return None
                    return _predicate

                def fill_title(self):
                    self.logger.debug("Filling title field")
                    locators = [
                        (By.XPATH, "//input[contains(@id, 'title') or contains(@name, 'title')]")
                    ]
                    title_field = WebDriverWait(self.driver, 10).until(
                        presence_of_any_element(*locators),
                        message="Title field not found with any locator"
                    )
                    title_field.clear()
                    title_field.send_keys(self.title)
                    self.logger.debug(f"Title field filled with: {self.title}")

                def fill_abstract(self):
                    self.logger.debug("Filling abstract field")
                    locators = [
                        (By.XPATH, "//textarea[contains(@id, 'abstract') or contains(@name, 'abstract')]")
                    ]
                    abstract_field = WebDriverWait(self.driver, 10).until(
                        presence_of_any_element(*locators),
                        message="Abstract field not found with any locator"
                    )
                    abstract_field.clear()
                    abstract_field.send_keys(self.abstract)
                    self.logger.debug("Abstract field filled successfully")

                fill_title(self)
                fill_abstract(self)

                # Handle Checkboxes
                self.logger.debug("Checking for checkboxes on the form")
                checkbox_selectors = [
                    (By.XPATH, "//input[@type='checkbox']"),  # Generic checkbox selector
                    (By.XPATH, "//input[contains(@id, 'agree') or contains(@name, 'agree')]"),  # Agreement checkboxes
                    (By.XPATH, "//input[contains(@id, 'terms') or contains(@name, 'terms')]"),  # Terms of service
                    (By.XPATH, "//input[contains(@id, 'confirm') or contains(@name, 'confirm')]")  # Confirmation checkboxes
                ]
                checkboxes_found = False
                for by, value in checkbox_selectors:
                    try:
                        checkboxes = self.driver.find_elements(by, value)
                        if checkboxes:
                            for checkbox in checkboxes:
                                if checkbox.is_displayed() and not checkbox.is_selected():
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                                    checkbox.click()
                                    self.logger.debug(f"Checked checkbox with {by}: {value}")
                                elif checkbox.is_selected():
                                    self.logger.debug(f"Checkbox with {by}: {value} already checked")
                                else:
                                    self.logger.debug(f"Checkbox with {by}: {value} found but not displayed")
                            checkboxes_found = True
                    except NoSuchElementException:
                        self.logger.debug(f"No checkboxes found with {by}: {value}")
                        continue
                if not checkboxes_found:
                    self.logger.debug("No checkboxes detected on the form")

                # Scroll down to make "Upload from Computer" and "Submit" buttons visible
                self.logger.debug("Scrolling down to make upload and submit buttons visible")
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)  # Brief pause to allow page to settle after scrolling

                # Wait for "Upload from Computer" button to be visible
                WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "//button[contains(text(), 'Upload from Computer')]"))
                )
                self.logger.debug("Upload from Computer button is now visible after scrolling")

                try:
                    self.driver.current_window_handle
                    self.logger.debug("Window is still open after filling form")
                except NoSuchWindowException as e:
                    self.logger.error(f"Window closed unexpectedly after filling form: {str(e)}")
                    raise

                self.logger.debug("Uploading PDF")
                if not os.path.isfile(self.pdf_path):
                    raise FileNotFoundError(f"PDF file not found at: {self.pdf_path}")

                pdf_dir = os.path.dirname(self.pdf_path)
                pdf_name = os.path.basename(self.pdf_path)
                normalized_pdf_dir = pdf_dir.replace('\\', '/')
                self.logger.debug(f"PDF directory: {normalized_pdf_dir}")
                self.logger.debug(f"PDF file name: {pdf_name}")

                try:
                    self.driver.current_window_handle
                    self.logger.debug("Window is still open before locating upload button")
                except NoSuchWindowException as e:
                    self.logger.error(f"Window closed unexpectedly before locating upload button: {str(e)}")
                    raise

                upload_button_selectors = [
                    (By.XPATH, "//button[contains(text(), 'Upload from Computer')]")
                ]
                upload_button = None
                for by, value in upload_button_selectors:
                    try:
                        upload_button = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((by, value))
                        )
                        self.logger.debug(f"Found 'Upload from Computer' button with {by}: {value}")
                        break
                    except TimeoutException:
                        self.logger.debug(f"Could not find 'Upload from Computer' button with {by}: {value}")
                        continue

                if not upload_button:
                    raise NoSuchElementException("Could not find 'Upload from Computer' button with any selector")

                self.logger.info("Using pyautogui to handle file upload")
                try:
                    upload_button.click()
                    self.logger.debug("Clicked 'Upload from Computer' button for pyautogui")
                    time.sleep(5)

                    screen_width, screen_height = pyautogui.size()
                    pyautogui.click(screen_width // 2, screen_height // 2)
                    self.logger.debug("Clicked in the middle of the screen to ensure file dialog focus")

                    if (self.is_first_upload):
                        # First upload: Navigate to the PDF directory
                        pyautogui.hotkey("ctrl", "l")
                        self.logger.debug("Pressed Ctrl + L to focus the address bar")
                        time.sleep(1)

                        pyautogui.write(normalized_pdf_dir, interval=0.05)
                        self.logger.debug(f"Typed directory path: {normalized_pdf_dir}")
                        time.sleep(1)
                        pyautogui.press("enter")
                        self.logger.debug("Pressed Enter to navigate to the directory")
                        time.sleep(2)

                        pyautogui.press("tab", presses=7)
                        self.logger.debug("Pressed Tab to focus the file name field")
                        time.sleep(1)
                    else:
                        # Subsequent uploads: Directory is already set, just select the file
                        self.logger.debug("Directory already set, focusing on file name field")

                    pyautogui.press("enter")
                    pyautogui.write(pdf_name, interval=0.05)
                    self.logger.debug(f"Typed file name: {pdf_name}")
                    time.sleep(1)
                    pyautogui.press("enter")
                    self.logger.debug("Pressed Enter to select the file")
                    time.sleep(2)
                    pyautogui.press("enter")
                    self.logger.debug("Pressed Enter again to confirm file selection")

                    # Set is_first_upload to False after the first successful upload
                    self.is_first_upload = False

                except Exception as e:
                    self.logger.warning(f"pyautogui failed to handle file upload: {str(e)}")
                    self.logger.info("Falling back to Selenium for file upload")
                    upload_button.click()
                    self.logger.debug("Clicked 'Upload from Computer' button for Selenium")
                    time.sleep(5)

                # self.logger.info("Using Selenium to handle file upload")
                # try:
                #     # Click the "Upload from Computer" button to reveal the file input element
                #     upload_button.click()
                #     self.logger.debug("Clicked 'Upload from Computer' button")
                #     time.sleep(2)

                #     # Locate the hidden file input element and upload the file
                #     file_input = WebDriverWait(self.driver, 10).until(
                #         EC.presence_of_element_located((By.XPATH, "//input[@type='file']")),
                #         message="File input element not found"
                #     )
                #     file_input.send_keys(self.pdf_path)
                #     self.logger.debug(f"Uploaded file: {self.pdf_path}")
                #     time.sleep(2)  # Wait for the upload to complete

                #     # Since we're using Selenium, we don't need to track directory navigation
                #     self.is_first_upload = False

                # except Exception as e:
                #     self.logger.error(f"Failed to handle file upload with Selenium: {str(e)}")
                #     raise

                self.logger.debug("PDF uploaded successfully")
                time.sleep(2)

                self.logger.debug("Clicking submit button")
                submit_btn_selectors = [
                    (By.XPATH, "//button[contains(@class, 'btn btn-primary') and (text()='Submit' or text()='Save changes')]")
                ]
                submit_btn = None
                for by, value in submit_btn_selectors:
                    try:
                        submit_btn = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((by, value))
                        )
                        self.logger.debug(f"Found submit button with {by}: {value}")
                        break
                    except TimeoutException:
                        self.logger.debug(f"Could not find submit button with {by}: {value}")
                        continue

                if not submit_btn:
                    raise NoSuchElementException("Submit button not found with any selector")

                original_window = self.driver.current_window_handle
                self.logger.debug(f"Original window handle: {original_window}")

                all_windows_before = self.driver.window_handles
                self.logger.debug(f"Window handles before clicking Submit: {all_windows_before}")

                self.driver.execute_script("arguments[0].click();", submit_btn)
                self.logger.debug("Submit button clicked via JavaScript")

                time.sleep(3)

                all_windows_after = self.driver.window_handles
                self.logger.debug(f"Window handles after clicking Submit: {all_windows_after}")

                if original_window not in all_windows_after:
                    self.logger.warning("Original window closed after clicking Submit")
                    new_windows = [window for window in all_windows_after if window != original_window]
                    if new_windows:
                        self.driver.switch_to.window(new_windows[0])
                        self.logger.debug(f"Switched to new window: {self.driver.current_window_handle}")
                    else:
                        self.logger.error("No new windows available to switch to after original window closed")
                        raise NoSuchWindowException("Original window closed and no new windows available")

                self.logger.debug("Verifying submission success")
                time.sleep(3)

                try:
                    done_btn = WebDriverWait(self.driver, 15).until(
                        EC.element_to_be_clickable((By.XPATH, "//a[text()='Done']"))
                    )
                    done_btn.click()
                    self.logger.debug("Clicked 'Done' button")
                    self.log_successful_link(url)
                    return True
                except TimeoutException:
                    self.logger.warning("Done button not found")
                    self.log_successful_link(url)
                    return True

                self.logger.debug("Waiting for author console")
                time.sleep(3)

            except NoSuchWindowException as e:
                error_type = "NoSuchWindow"
                error_msg = f"Window closed unexpectedly: {str(e)}"
                self.logger.error(f"Window closed unexpectedly: {error_msg}")
                try:
                    self.logger.info("Attempting to recover by restarting browser session")
                    self.driver.quit()
                    self.setup_browser()
                    if self.login_to_cmt3():
                        self.logger.info("Successfully re-logged in after window closure")
                        if attempt < self.max_retries - 1:
                            self.logger.warning(f"Retrying submission for {url} after window closure")
                            continue
                        else:
                            self.logger.error(f"Max retries reached for {url} after window closure")
                            self.log_failure(url, error_type, error_msg)
                            return False
                    else:
                        self.logger.error("Failed to re-login after window closure")
                        self.log_failure(url, error_type, "Failed to re-login after window closure")
                        return False
                except Exception as recovery_error:
                    self.logger.error(f"Recovery failed: {str(recovery_error)}")
                    self.log_failure(url, error_type, f"Recovery failed: {str(recovery_error)}")
                    return False
                
            except TimeoutException as e:
                error_type = "Timeout"
                error_msg = f"Timeout waiting for element: {str(e)}"
                self.logger.error(f"Page source saved to page_source.html. Current URL: {self.driver.current_url}")
            except NoSuchElementException as e:
                error_type = "ElementNotFound"
                error_msg = f"Required element not found: {str(e)}"
                self.logger.error(f"Page source saved to page_source.html. Current URL: {self.driver.current_url}")
            except ElementClickInterceptedException as e:
                error_type = "ClickIntercepted"
                error_msg = f"Click intercepted: {str(e)}"
                self.logger.error(f"Page source saved to page_source.html. Current URL: {self.driver.current_url}")
            except WebDriverException as e:
                error_type = "WebDriverError"
                error_msg = f"Browser error: {str(e)}"
                self.logger.error(f"Page source saved to page_source.html. Current URL: {self.driver.current_url}")
            except InvalidSessionIdException as e:
                error_type = "InvalidSessionId"
                error_msg = f"Session terminated: {str(e)}"
                self.logger.error(f"Session terminated unexpectedly: {error_msg}")
                raise
            except Exception as e:
                error_type = "GeneralError"
                error_msg = f"Unexpected error: {str(e)}"
                self.logger.error(f"Page source saved to page_source.html. Current URL: {self.driver.current_url}")

            # try:
            #     page_source = self.driver.page_source
            #     with open(os.path.join(self.script_dir, 'page_source.html'), 'w', encoding='utf-8') as f:
            #         f.write(page_source)
            # except (NoSuchWindowException, InvalidSessionIdException):
            #     self.logger.error("Cannot save page source: Window or session is invalid")

            if attempt < self.max_retries - 1:
                self.logger.warning(f"Attempt {attempt + 1} failed for {url}: {error_msg}. Retrying...")
                time.sleep(2)
            else:
                self.logger.error(f"All attempts failed for {url}: {error_msg}")
                self.log_failure(url, error_type, error_msg)
                return False

    def run(self):
        successful = []
        failed = []
        session_retries = 3
        for session_attempt in range(session_retries):
            try:
                if not hasattr(self, 'driver') or self.driver is None:
                    self.setup_browser()
                if not self.login_to_cmt3():
                    self.logger.error("Initial login failed, aborting submissions")
                    return
                for url in self.urls:
                    if url in successful or url in failed:
                        continue
                    self.logger.info(f"Starting submission for {url}")
                    try:
                        if self.submit_form(url):
                            successful.append(url)
                        else:
                            failed.append(url)
                    except (NoSuchWindowException, InvalidSessionIdException) as e:
                        self.logger.error(f"Session terminated during submission for {url}: {str(e)}")
                        failed.append(url)
                        break
                    time.sleep(2)
                break
            except (InvalidSessionIdException, NoSuchWindowException) as e:
                self.logger.error(f"Session terminated (attempt {session_attempt + 1}/{session_retries}): {str(e)}")
                if session_attempt < session_retries - 1:
                    self.logger.info("Restarting browser session...")
                    try:
                        self.driver.quit()
                    except:
                        self.logger.debug("Browser already closed")
                    self.setup_browser()
                    time.sleep(5)
                else:
                    self.logger.error("Max session retries reached")
                    failed.extend([url for url in self.urls if url not in successful and url not in failed])
                    break
            except Exception as e:
                self.logger.error(f"Unexpected error during execution: {str(e)}")
                failed.extend([url for url in self.urls if url not in successful and url not in failed])
                break
            finally:
                try:
                    if hasattr(self, 'driver') and self.driver is not None:
                        self.driver.quit()
                except:
                    self.logger.debug("Browser already closed during cleanup")
                try:
                    self.conn.close()
                except:
                    self.logger.debug("Database connection already closed")
                self.logger.info("Browser and database connections closed")
                self.logger.info("\nSubmission Summary:")
                self.logger.info(f"Successful submissions: {len(successful)}")
                for url in successful:
                    self.logger.info(f"✓ {url}")
                self.logger.info(f"Failed submissions: {len(failed)}")
                for url in failed:
                    self.logger.info(f"X {url}")