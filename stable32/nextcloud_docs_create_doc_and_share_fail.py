import contextlib
import os
import random
import re
import string
import sys
import signal

from playwright.sync_api import Playwright, sync_playwright

from helpers.helper_functions import log_note, get_random_text, login_nextcloud, close_modal, timeout_handler, user_sleep


DOMAIN = os.environ.get('HOST_URL', 'http://app')


def run(playwright: Playwright, browser_name: str) -> None:
    log_note(f"Launch browser {browser_name}")
    if browser_name == "firefox":
        browser = playwright.firefox.launch(headless=False)
    else:
        browser = playwright.chromium.launch(headless=False, args=['--disable-gpu', '--disable-software-rasterizer', '--ozone-platform=wayland'])
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

        log_note("Create new text file")
        page.get_by_role("link", name="Files").click()
        page.get_by_role("button", name="New", exact=True).click()
        page.click("button[role='menuitem']:has-text('New text file')")

        rand_str = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        file_name = f'Collaborative_doc_{rand_str}.md'
        page.get_by_label('Filename', exact=True).fill(file_name)
        page.locator('.dialog__actions').get_by_role("button", name="Create").click()
        user_sleep()

        # log_note("Share file with other user - Open context menu")
        # modal_header = page.get_by_role("heading", name=re.compile(rf"\b{re.escape(file_name)}\b"))
        # modal = modal_header.locator("..")
        # actions_button = modal.locator("button.action-item__menutoggle[aria-label='Actions']")
        # actions_button.click()
        # user_sleep()

        # log_note('Open sharing menu')
        # page.get_by_role("menuitem", name="Open sidebar").click()
        # page.get_by_role("tab", name="Sharing").click()
        # user_sleep()

        log_note('Sharing with docs_dude user')
        page.get_by_placeholder("Type names or teams").fill("docs")
        page.get_by_text("docs_dude").first.click()
        page.get_by_text("Save Share").first.click()
        user_sleep()


        log_note("Close browser")
        page.close()

        # ---------------------
        context.close()
        browser.close()
    except Exception as e:
        if hasattr(e, 'message'): # only Playwright error class has this member
            log_note(f"Exception occurred: {e.message}")

        # set a timeout. Since the call to page.content() is blocking we need to defer it to the OS
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(5)
        #log_note(f"Page content was: {page.content()}")
        signal.alarm(0) # remove timeout signal

        raise e


with sync_playwright() as playwright:
    if len(sys.argv) > 1:
        browser_name = sys.argv[1].lower()
        if browser_name not in ["chromium", "firefox"]:
            print("Invalid browser name. Please choose either 'chromium' or 'firefox'.")
            sys.exit(1)
    else:
        browser_name = "firefox"

    run(playwright, browser_name)
