import contextlib
import os
import sys
from time import time_ns, sleep
import signal
import random
import string

from playwright.sync_api import Playwright, sync_playwright, expect

from helpers.helper_functions import log_note, get_random_text, login_nextcloud, close_modal, timeout_handler, user_sleep

DOMAIN = os.environ.get('HOST_URL', 'http://app')

FILE_PATH = '/tmp/repo/1mb.txt'

def download(playwright: Playwright, browser_name: str, download_url:str) -> None:
    log_note(f"Launch download browser {browser_name}")

    download_path = os.path.join(os.getcwd(), 'downloads')
    os.makedirs(download_path, exist_ok=True)

    if browser_name == "firefox":
        browser = playwright.firefox.launch(headless=False, downloads_path=download_path)
    else:
        browser = playwright.chromium.launch(headless=False, downloads_path=download_path, args=['--disable-gpu', '--disable-software-rasterizer', '--ozone-platform=wayland'])


    context = browser.new_context(accept_downloads=True, ignore_https_errors=True)
    page = context.new_page()

    try:

        log_note('Opening shared link')
        page.goto(download_url)
        user_sleep()

        log_note('Clicking download link')

        page.get_by_role("button", name="Actions", exact=True).click()

        #download_url = page.locator("#header-primary-action a.primary.button").get_attribute("href")

        with page.expect_download() as download_info:
            menu = page.locator(".v-popper__popper--shown [role='menu']")
            menu.get_by_role("menuitem", name="Download").click()

            #page.evaluate(f"window.location.href = '{download_url}'")

        download = download_info.value

        download_file_name = download_path + '/' + download.suggested_filename
        download.save_as(download_file_name)

        if os.path.exists(download_file_name):
            if download_file_name_size := os.path.getsize(download_file_name) >= (1 * 1024 * 1024 - 16): # We substract 16 to avoid one off errors
                log_note(f"File {download_file_name} downloaded")
            else:
                log_note(f"File {download_file_name} downloaded and right size: {download_file_name_size}")
                raise ValueError(f"File not the right size")
        else:
            raise FileNotFoundError(f"File download failed")
        user_sleep()

        log_note('Download finished')

        page.close()
        log_note("Close download browser")

    except Exception as e:
        if hasattr(e, 'message'): # only Playwright error class has this member
            log_note(f"Exception occurred: {e.message}")

        # set a timeout. Since the call to page.content() is blocking we need to defer it to the OS
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(20)
        #log_note(f"Page content was: {page.content()}")
        signal.alarm(0) # remove timeout signal

        raise e

    # ---------------------
    context.close()
    browser.close()

def run(playwright: Playwright, browser_name: str, headless=False) -> None:
    log_note(f"Launch browser {browser_name}")
    if browser_name == "firefox":
        browser = playwright.firefox.launch(headless=False)

    else:
        browser = playwright.chromium.launch(headless=False, downloads_path=download_path, args=['--disable-gpu', '--disable-software-rasterizer', '--ozone-platform=wayland'])

    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    try:
        log_note("Opening login page")
        page.goto(f"{DOMAIN}/login")

        log_note("Logging in")
        login_nextcloud(page, domain=DOMAIN)
        user_sleep()

        # Wait for the modal to load. As it seems you can't close it while it is showing the opening animation.
        log_note("Close first-time run popup")
        close_modal(page)

        log_note("Go to Files")
        page.get_by_role("link", name="Files").click()
        user_sleep()

        log_note("Upload File")
        page.get_by_role("button", name="New").click()
        user_sleep()

        div_selector = 'div.v-popper__wrapper:has(ul[role="menu"])'
        page.wait_for_selector(div_selector, state='visible')

        file_name = ''.join(random.choices(string.ascii_letters, k=5)) + '.txt'

        with open(FILE_PATH, 'rb') as f:
            file_content = f.read()

        file_payload = {
            'name': file_name,
            'mimeType': 'text/plain',
            'buffer': file_content,
        }

        with page.expect_file_chooser() as fc_info:
            page.locator(f'{div_selector} button:has-text("Upload files")').click()

        file_chooser = fc_info.value
        file_chooser.set_files(file_payload)
        user_sleep()

        log_note('Validate file upload')
        updated_file_locator = page.locator(f'tr[data-cy-files-list-row-name="{file_name}"]')
        expect(updated_file_locator).to_have_count(1)
        user_sleep()

        # SHARE
        log_note("Get file share link")
        updated_file_locator.locator('button[data-cy-files-list-row-action="sharing-status"]').click()
        page.locator('button.new-share-link').click()

        toast_selector = 'div.toastify.toast-success:has-text("Link copied")'
        page.wait_for_selector(toast_selector)
        user_sleep()

        # Does not work with Firefox since clipboard access is blocked for security reasons
        # log_note('Validate share link and go to home')
        # link_url = page.evaluate('navigator.clipboard.readText()')
        # user_sleep()

        link_url = page.locator("a.sharing-entry__copy").get_attribute("href")
        log_note(f"Download link is: {link_url}")
        page.goto(f"{DOMAIN}")
        user_sleep()

        download(playwright, browser_name, link_url)

        log_note('Delete file')
        page.get_by_role("link", name="Files").click()
        page.locator(f'tr[data-cy-files-list-row-name="{file_name}"] button[aria-label="Actions"]').click()
        page.locator(f'li[data-cy-files-list-row-action="delete"] button').click()
        user_sleep()

        page.close()
        log_note("Close browser")

    except Exception as e:
        if hasattr(e, 'message'): # only Playwright error class has this member
            log_note(f"Exception occurred: {e.message}")

        # set a timeout. Since the call to page.content() is blocking we need to defer it to the OS
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(20)
        #log_note(f"Page content was: {page.content()}")
        signal.alarm(0) # remove timeout signal

        raise e

    # ---------------------
    context.close()
    browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        browser_name = sys.argv[1].lower()
        if browser_name not in ["chromium", "firefox"]:
            print("Invalid browser name. Please choose either 'chromium' or 'firefox'.")
            sys.exit(1)
    else:
        browser_name = "firefox"

    with sync_playwright() as playwright:
        run(playwright, browser_name)
