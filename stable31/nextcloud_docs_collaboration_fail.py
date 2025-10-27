import contextlib
import re
import string
import sys
import os

from playwright.sync_api import Playwright, sync_playwright, expect

from helpers.helper_functions import log_note, get_random_text, login_nextcloud, close_modal, timeout_handler, user_sleep

DOMAIN = os.environ.get('HOST_URL', 'http://app')

TYPING_DELAY_MS = 100

def collaborate(playwright: Playwright, browser_name: str) -> None:
    log_note(f"Launch two {browser_name} browsers")
    if browser_name == "firefox":
        browser = playwright.firefox.launch(headless=False, args=['-width', '1280', '-height', '720'])
    else:
        browser = playwright.chromium.launch(headless=False, args=['--disable-gpu', '--disable-software-rasterizer', '--ozone-platform=wayland', '--window-size=1280,720'])

    context = browser.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 720})
    admin_user_page = context.new_page()


    if browser_name == "firefox":
        browser_two = playwright.firefox.launch(headless=False, args=['-width', '1280', '-height', '720'])
    else:
        browser_two = playwright.chromium.launch(headless=False, args=['--disable-gpu', '--disable-software-rasterizer', '--ozone-platform=wayland', '--window-size=1280,720'])
    context_two = browser_two.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 720})
    docs_user_page = context_two.new_page()

    try:
        # Login and open the file for both users
        log_note("Logging in with all users")
        login_nextcloud(admin_user_page, "nextcloud", "nextcloud", DOMAIN)
        login_nextcloud(docs_user_page, "docs_dude", "docsrule!12", DOMAIN)
        user_sleep()

        # Wait for the modal to load. As it seems you can't close it while it is showing the opening animation.
        log_note("Close first-time run popup")
        #close_modal(docs_user_page)

        ## TODO: If we are using Chromium with Wayland the test will flake here. Problem being is that Wayland does not render the hidden window somehow ....

        log_note("Opening shares menu with all users")
        admin_user_page.get_by_role("link", name="Files").click()
        docs_user_page.get_by_role("link", name="Files").click()

        admin_user_page.get_by_role("link", name="Shares", exact=True).click()
        docs_user_page.get_by_role("link", name="Shares", exact=True).click()
        user_sleep()

        log_note('Selecting shared document with all users')
        sort_button = admin_user_page.locator('button.files-list__column-sort-button:has-text("Modified")')
        arrow_icon = sort_button.locator('.menu-up-icon')
        if arrow_icon.count() > 0:
            log_note("The arrow is already pointing up. No need to click the button.")
        else:
            sort_button.click()

        tbody = admin_user_page.locator("tbody.files-list__tbody")
        tbody.wait_for()

        rows = tbody.locator('tr[data-cy-files-list-row]')
        first_md_row = rows.filter(
            has=admin_user_page.locator('.files-list__row-name-ext', has_text='.md')
        ).first

        first_md_row.wait_for()

        base = first_md_row.locator('.files-list__row-name-').inner_text().strip()
        ext = first_md_row.locator('.files-list__row-name-ext').inner_text().strip()
        filename = f"{base}{ext}"

        print("Selected filename:", filename)

        admin_user_page.locator(f'tr[data-cy-files-list-row-name="{filename}"]').click()
        docs_user_page.locator(f'tr[data-cy-files-list-row-name="{filename}"]').click()
        user_sleep()

        log_note("Starting to collaborate")
        # Write the first message and assert it's visible for the other user
        log_note("Sending first validation message")
        first_message = "FIRST_VALIDATION_MESSAGE"

        admin_text_box = admin_user_page.locator('div[contenteditable="true"]').first
        user_text_box = docs_user_page.locator('div[contenteditable="true"]').first

        admin_text_box.wait_for(state="visible")
        user_text_box.wait_for(state="visible")

        admin_user_page.keyboard.type(first_message, delay=TYPING_DELAY_MS)
        user_sleep()

        log_note('Checking if message is visible')
        expect(docs_user_page.get_by_text(first_message)).to_be_visible()

        for x in range(1, 7):
            random_message = get_random_text(50)
            # Admin sends on even, docs_dude on odd
            if x % 2 == 0:
                log_note("Admin adding more text")
                admin_user_page.keyboard.type(random_message, delay=TYPING_DELAY_MS) # We could add delay here, but then we need to increase the timeout
                expect(docs_user_page.get_by_text(random_message)).to_be_visible(timeout=15_000)
            else:
                log_note("User adding more text")
                docs_user_page.keyboard.type(random_message, delay=TYPING_DELAY_MS)
                expect(admin_user_page.get_by_text(random_message)).to_be_visible(timeout=15_000)

            user_sleep()

        log_note("Closing browsers")
        # ---------------------
        admin_user_page.close()
        docs_user_page.close()
        context.close()
        context_two.close()
        browser.close()
        browser_two.close()

    except Exception as e:
        if hasattr(e, 'message'): # only Playwright error class has this member
            log_note(f"Exception occurred: {e.message}")
        #log_note(f"Page content was: {docs_user_page.content()}")
        #log_note(f"Page content was: {admin_user_page.content()}")
        raise e



with sync_playwright() as playwright:
    if len(sys.argv) > 1:
        browser_name = sys.argv[1].lower()
        if browser_name not in ["chromium", "firefox"]:
            print("Invalid browser name. Please choose either 'chromium' or 'firefox'.")
            sys.exit(1)
    else:
        browser_name = "firefox"

    collaborate(playwright, browser_name)
